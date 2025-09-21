"""OpenAI gateway implementations for preflight extraction workflows.

Purpose:
    Bridge the application layer's preflight ports to the OpenAI provider
    client. The adapters compose prompts, execute model calls with retries and
    timeouts, and convert structured responses into immutable domain models.
External Dependencies:
    Relies on the OpenAI client housed in :mod:`src.providers.openai_client`
    and parsing utilities from :mod:`src.application.preflight`.
Fallback Semantics:
    When validation fails the adapters return fallback domain objects emitted
    by the parsers. These objects retain the raw provider response and
    formatted validation errors so callers can persist diagnostic artefacts.
Timeout Strategy:
    Uses :func:`src.infrastructure.timeouts.operation_timeout` to enforce the
    configured wall-clock timeout for each provider invocation.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
import logging
import time
from typing import Any, Callable, Mapping, Optional, Sequence, Tuple, TypeVar, Protocol

from ...application.preflight.extraction_parser import ExtractionResponseParser
from ...application.preflight.prompts import (
    PromptBundle,
    build_extraction_prompt,
    build_query_plan_prompt,
)
from ...application.preflight.query_parser import QueryPlanResponseParser
from ...application.preflight.schema_validation import (
    StructuredParseResult,
    ValidationIssue,
)
from ...application.preflight.schemas import (
    load_extraction_schema,
    load_query_plan_schema,
)
from ...application.preflight.ports import (
    PointExtractorGateway,
    QueryBuilderGateway,
)
from ...domain.preflight import ExtractedPoint, ExtractionResult, QueryPlan
from ...pipeline_input import PipelineInput
from ...providers import openai_client
from ..timeouts import TimeoutConfig, get_timeout_config, operation_timeout


_LOGGER = logging.getLogger(__name__)


DEFAULT_PROVIDER_TIMEOUT_SECONDS = 60.0
DEFAULT_MAX_OUTPUT_TOKENS = 4096
MINIMUM_CONTENT_CHARACTERS = 50


JsonLike = Any
ProviderCall = Callable[..., Tuple[JsonLike, str]]

DEFAULT_CHUNK_MAX_CHARACTERS = 4000
DEFAULT_CHUNK_OVERLAP_CHARACTERS = 200
DEFAULT_CHUNK_MAX_POINTS_PER_CHUNK = 4


@dataclass(frozen=True)
class ChunkingSettings:
    """Configuration describing how large pipeline inputs should be chunked."""

    enabled: bool
    max_characters: int
    overlap_characters: int
    max_points_per_chunk: Optional[int]


@dataclass(frozen=True)
class _PipelineChunk:
    """Represents a single chunk of the original pipeline content."""

    index: int
    start_offset: int
    end_offset: int
    content: str


def _format_bool(value: bool) -> str:
    """Return a lower-case string representation of ``value``."""

    return "true" if value else "false"


@dataclass(frozen=True)
class OpenAIRequestPayload:
    """Describe the parameters required to issue a single OpenAI request.

    Attributes:
        system_message: Instructional content supplied as the system message.
        user_message: Main user prompt delivered to the model.
        max_output_tokens: Optional cap for tokens emitted by the model.
        temperature: Optional sampling temperature override.
    """

    system_message: str
    user_message: str
    max_output_tokens: Optional[int]
    temperature: Optional[float]


@dataclass(frozen=True)
class OpenAIDefaults:
    """Capture default OpenAI parameters resolved from configuration.

    Attributes:
        max_output_tokens: Optional fallback token cap for responses.
        temperature: Optional fallback temperature used when overrides are
            absent.
    """

    max_output_tokens: Optional[int]
    temperature: Optional[float]


ModelT = TypeVar("ModelT")


class _ResponseParser(Protocol[ModelT]):
    """Protocol describing the parser interface consumed by the gateways."""

    def parse(self, raw_text: str) -> StructuredParseResult[ModelT]:
        """Parse ``raw_text`` into a structured result."""

    def build_retry_message(self, issues: Sequence[ValidationIssue]) -> str:
        """Render ``issues`` into a guidance string for retries."""


def _coerce_optional_int(value: Any) -> Optional[int]:
    """Convert ``value`` to ``int`` when feasible.

    Args:
        value: Candidate value that may represent an integer.

    Returns:
        Normalised integer when conversion succeeds and the value is positive;
        otherwise ``None``.

    Raises:
        None. Invalid inputs return ``None`` instead of raising exceptions.

    Side Effects:
        None.

    Timeout:
        Not applicable; execution is CPU-bound.
    """

    if value is None:
        return None
    try:
        converted = int(value)
    except (TypeError, ValueError):
        return None
    if converted <= 0:
        return None
    return converted


def _coerce_optional_float(value: Any) -> Optional[float]:
    """Convert ``value`` to ``float`` when feasible.

    Args:
        value: Candidate numeric value.

    Returns:
        Float representation when conversion succeeds; otherwise ``None``.

    Raises:
        None.

    Side Effects:
        None.

    Timeout:
        Not applicable; execution is CPU-bound.
    """

    if value is None:
        return None
    try:
        converted = float(value)
    except (TypeError, ValueError):
        return None
    return converted


def _normalise_json_like(value: JsonLike) -> str:
    """Serialise ``value`` to a JSON string when necessary.

    Args:
        value: Provider response payload that may already be a string or a
            JSON-compatible object.

    Returns:
        Raw string representation suitable for downstream parsing.

    Raises:
        RuntimeError: If the provider returns an object that cannot be
            serialised to JSON.

    Side Effects:
        None.

    Timeout:
        Not applicable; execution is CPU-bound.
    """

    if isinstance(value, str):
        return value
    try:
        return json.dumps(value, ensure_ascii=False)
    except TypeError as exc:  # pragma: no cover - defensive branch
        raise RuntimeError("Provider returned a non-serialisable payload") from exc


def _resolve_chunking_settings(config: Mapping[str, Any]) -> ChunkingSettings:
    """Resolve chunking settings from the provided configuration mapping."""

    preflight = config.get("preflight") if isinstance(config, Mapping) else None
    extract_config: Mapping[str, Any] = {}
    if isinstance(preflight, Mapping):
        extract_candidate = preflight.get("extract")
        if isinstance(extract_candidate, Mapping):
            extract_config = extract_candidate
    chunk_candidate = extract_config.get("chunking") if extract_config else None
    chunk_config = chunk_candidate if isinstance(chunk_candidate, Mapping) else {}

    enabled_value = chunk_config.get("enabled")
    enabled = True if enabled_value is None else bool(enabled_value)

    raw_max_chars = chunk_config.get("max_characters")
    max_chars_value = _coerce_optional_int(raw_max_chars)
    if raw_max_chars is not None and (max_chars_value is None or max_chars_value <= 0):
        enabled = False
        max_characters = DEFAULT_CHUNK_MAX_CHARACTERS
    else:
        max_characters = max_chars_value or DEFAULT_CHUNK_MAX_CHARACTERS

    overlap_value = chunk_config.get("overlap_characters")
    overlap_characters = _coerce_optional_int(overlap_value)
    if overlap_characters is None or overlap_characters < 0:
        overlap_characters = DEFAULT_CHUNK_OVERLAP_CHARACTERS
    if overlap_characters >= max_characters:
        overlap_characters = max(0, max_characters // 4)

    per_chunk_value = chunk_config.get("max_points_per_chunk")
    if per_chunk_value == 0:
        max_points_per_chunk: Optional[int] = None
    else:
        per_chunk_limit = _coerce_optional_int(per_chunk_value)
        max_points_per_chunk = (
            per_chunk_limit if per_chunk_limit is not None else DEFAULT_CHUNK_MAX_POINTS_PER_CHUNK
        )

    return ChunkingSettings(
        enabled=enabled and max_characters > 0,
        max_characters=max_characters,
        overlap_characters=overlap_characters,
        max_points_per_chunk=max_points_per_chunk,
    )


def _split_into_chunks(content: str, settings: ChunkingSettings) -> Tuple[_PipelineChunk, ...]:
    """Split ``content`` into bounded chunks using soft paragraph boundaries."""

    total_length = len(content)
    if total_length == 0:
        return (
            _PipelineChunk(index=0, start_offset=0, end_offset=0, content=""),
        )

    chunks: list[_PipelineChunk] = []
    start = 0
    index = 0
    while start < total_length:
        proposed_end = min(start + settings.max_characters, total_length)
        if proposed_end < total_length:
            search_floor = min(proposed_end, start + max(settings.max_characters // 2, 1))
            boundary = content.rfind("\n\n", search_floor, proposed_end)
            if boundary == -1:
                boundary = content.rfind("\n", search_floor, proposed_end)
            if boundary > start:
                proposed_end = boundary
        if proposed_end <= start:
            proposed_end = min(start + settings.max_characters, total_length)

        chunk_text = content[start:proposed_end]
        if not chunk_text:
            break

        chunks.append(
            _PipelineChunk(
                index=index,
                start_offset=start,
                end_offset=proposed_end,
                content=chunk_text,
            )
        )

        if proposed_end >= total_length:
            break

        chunk_length = proposed_end - start
        overlap = settings.overlap_characters
        if overlap <= 0 or overlap >= chunk_length:
            next_start = proposed_end
        else:
            next_start = proposed_end - overlap
        if next_start <= start:
            next_start = proposed_end

        start = next_start
        index += 1

    return tuple(chunks)


def _compose_chunk_pipeline_input(
    pipeline_input: PipelineInput,
    chunk: _PipelineChunk,
    *,
    chunk_count: int,
    overlap: int,
) -> PipelineInput:
    """Create a chunk-specific :class:`PipelineInput` with metadata annotations."""

    parent_metadata = dict(pipeline_input.metadata or {})
    parent_metadata["chunk"] = {
        "index": chunk.index,
        "count": chunk_count,
        "start_offset": chunk.start_offset,
        "end_offset": chunk.end_offset,
        "characters": chunk.end_offset - chunk.start_offset,
        "overlap_characters": overlap,
    }
    chunk_source = pipeline_input.source or "pipeline-input"
    chunk_source = f"{chunk_source}#chunk-{chunk.index + 1}"
    return PipelineInput(content=chunk.content, source=chunk_source, metadata=parent_metadata)


def _compose_chunk_provider_metadata(
    metadata: Optional[Mapping[str, object]],
    chunk: _PipelineChunk,
    *,
    chunk_count: int,
) -> Optional[Mapping[str, object]]:
    """Build provider metadata that advertises the current chunk context."""

    base = dict(metadata) if metadata is not None else {}
    base["preflight_chunk"] = {
        "index": chunk.index,
        "count": chunk_count,
        "start_offset": chunk.start_offset,
        "end_offset": chunk.end_offset,
    }
    return base if base else None


def _select_points(
    candidates: Sequence[Tuple[ExtractedPoint, int, int]],
    *,
    max_points: Optional[int],
) -> Tuple[Tuple[ExtractedPoint, ...], bool, int]:
    """Return deduplicated points ordered by confidence and chunk index."""

    if not candidates:
        return (), False, 0

    unique_keys = {
        (point.title.strip().lower(), point.summary.strip().lower())
        for point, _, _ in candidates
    }
    sorted_candidates = sorted(
        candidates,
        key=lambda item: (
            -item[0].confidence,
            item[1],
            item[2],
            item[0].id,
        ),
    )

    selected: list[ExtractedPoint] = []
    seen: set[Tuple[str, str]] = set()
    for point, _, _ in sorted_candidates:
        key = (point.title.strip().lower(), point.summary.strip().lower())
        if key in seen:
            continue
        seen.add(key)
        selected.append(point)
        if max_points is not None and len(selected) >= max_points:
            break

    truncated = max_points is not None and len(selected) < len(unique_keys)
    return tuple(selected), truncated, len(unique_keys)


def _merge_chunk_results(
    *,
    pipeline_input: PipelineInput,
    total_characters: int,
    chunks: Sequence[_PipelineChunk],
    chunk_results: Sequence[ExtractionResult],
    max_points: Optional[int],
    settings: ChunkingSettings,
) -> ExtractionResult:
    """Merge chunk-level extraction outputs into a single aggregated result."""

    candidates: list[Tuple[ExtractedPoint, int, int]] = []
    aggregated_errors: list[str] = []
    fallback_chunks: list[dict[str, Any]] = []
    chunk_stats: list[dict[str, Any]] = []
    truncated = False

    for chunk, result in zip(chunks, chunk_results):
        chunk_stats.append(
            {
                "index": chunk.index,
                "start_offset": chunk.start_offset,
                "end_offset": chunk.end_offset,
                "characters": chunk.end_offset - chunk.start_offset,
                "points": len(result.points),
                "truncated": result.truncated,
                "validation_error_count": len(result.validation_errors),
            }
        )
        truncated = truncated or result.truncated
        if result.raw_response is not None or result.validation_errors:
            fallback_chunks.append(
                {
                    "index": chunk.index,
                    "raw_response": result.raw_response,
                    "validation_errors": list(result.validation_errors),
                }
            )
        for message in result.validation_errors:
            aggregated_errors.append(f"chunk[{chunk.index + 1}]: {message}")
        for order, point in enumerate(result.points):
            candidates.append((point, chunk.index, order))

    selected_points, truncated_by_limit, unique_candidate_count = _select_points(
        candidates,
        max_points=max_points,
    )
    truncated = truncated or truncated_by_limit

    chunking_stats: dict[str, Any] = {
        "strategy": "chunked_map_reduce",
        "chunk_count": len(chunks),
        "chunk_size_limit": settings.max_characters,
        "chunk_overlap": settings.overlap_characters,
        "max_points_per_chunk": settings.max_points_per_chunk,
        "map_points_before_merge": len(candidates),
        "unique_candidates": unique_candidate_count,
        "selected_points": len(selected_points),
        "truncated_chunks": sum(1 for stats in chunk_stats if stats["truncated"]),
        "fallback_chunks": len(fallback_chunks),
        "chunks": chunk_stats,
    }
    if max_points is not None:
        chunking_stats["global_point_limit"] = max_points

    source_stats: dict[str, Any] = {
        "characters": total_characters,
        "chunking": chunking_stats,
    }

    metadata_view = dict(pipeline_input.metadata or {})
    if metadata_view.get("truncated") and not source_stats.get("input_truncated"):
        source_stats["input_truncated"] = True
        truncation_reason = metadata_view.get("truncation_reason")
        if truncation_reason:
            source_stats["input_truncation_reason"] = str(truncation_reason)

    raw_response: Optional[str] = None
    if fallback_chunks:
        raw_response = json.dumps({"chunk_fallbacks": fallback_chunks}, ensure_ascii=False)

    return ExtractionResult(
        points=selected_points,
        source_stats=source_stats,
        truncated=truncated,
        raw_response=raw_response,
        validation_errors=tuple(aggregated_errors),
    )



def _compose_retry_prompt(base_prompt: str, retry_guidance: str) -> str:
    """Append retry guidance to the original user prompt.

    Args:
        base_prompt: Original user prompt supplied to the provider.
        retry_guidance: Additional instruction describing validation issues.

    Returns:
        Updated prompt instructing the model to correct prior validation
        problems.

    Raises:
        None.

    Side Effects:
        None.

    Timeout:
        Not applicable; execution is CPU-bound.
    """

    return f"{base_prompt}\n\n=== Retry Guidance ===\n{retry_guidance}\n"


def _extract_override(
    metadata: Optional[Mapping[str, Any]],
    key: str,
    coercer: Callable[[Any], Optional[Any]],
) -> Optional[Any]:
    """Resolve an override value from ``metadata`` using ``key``.

    Args:
        metadata: Optional metadata mapping passed to the gateway.
        key: Override key to resolve (for example ``"max_output_tokens"``).
        coercer: Callable that normalises the resolved value.

    Returns:
        Normalised override when present; otherwise ``None``.

    Raises:
        None.

    Side Effects:
        None.

    Timeout:
        Not applicable; execution is CPU-bound.
    """

    if metadata is None or not isinstance(metadata, Mapping):
        return None
    if key in metadata:
        value = coercer(metadata[key])
        if value is not None:
            return value
    provider_overrides = metadata.get("provider_overrides")
    if isinstance(provider_overrides, Mapping) and key in provider_overrides:
        return coercer(provider_overrides[key])
    return None


def _read_openai_defaults(config: Mapping[str, Any]) -> OpenAIDefaults:
    """Extract default OpenAI parameters from ``config``.

    Args:
        config: Application configuration mapping.

    Returns:
        :class:`OpenAIDefaults` containing fallback token and temperature
        values.

    Raises:
        None.

    Side Effects:
        None.

    Timeout:
        Not applicable; execution is CPU-bound.
    """

    api_section = config.get("api", {}) if isinstance(config, Mapping) else {}
    if not isinstance(api_section, Mapping):
        api_section = {}
    openai_config = api_section.get("openai", {})
    if not isinstance(openai_config, Mapping):
        openai_config = {}

    max_tokens = _coerce_optional_int(openai_config.get("max_tokens"))
    if max_tokens is None:
        max_tokens = DEFAULT_MAX_OUTPUT_TOKENS
    temperature = _coerce_optional_float(openai_config.get("temperature"))
    if temperature is None:
        temperature = 0.2
    return OpenAIDefaults(max_output_tokens=max_tokens, temperature=temperature)


class _OpenAIPreflightGatewayBase:
    """Common functionality shared by OpenAI-backed preflight gateways."""

    def __init__(
        self,
        *,
        config: Optional[Mapping[str, Any]],
        call_model: ProviderCall,
        max_retries: int,
        timeout_scope: str,
        default_total_timeout: Optional[float],
        max_output_tokens: Optional[int],
        temperature: Optional[float],
    ) -> None:
        """Initialise shared dependencies for the OpenAI gateways.

        Args:
            config: Optional application configuration mapping used to resolve
                provider settings and timeouts.
            call_model: Callable responsible for executing the OpenAI request.
            max_retries: Maximum number of retries after the first attempt.
            timeout_scope: Dot-delimited scope for looking up timeout config.
            default_total_timeout: Fallback timeout when configuration omits a
                value.
            max_output_tokens: Optional override for the maximum tokens.
            temperature: Optional override for the sampling temperature.

        Raises:
            ValueError: If ``max_retries`` is negative.

        Side Effects:
            Reads timeout settings from ``config``.

        Timeout:
            Not applicable; the constructor performs synchronous setup.
        """

        self._config: Mapping[str, Any] = dict(config or {})
        if max_retries < 0:
            raise ValueError("max_retries must be a non-negative integer")
        self._call_model = call_model
        self._max_retries = max_retries
        defaults = _read_openai_defaults(self._config)
        self._max_output_tokens = (
            max_output_tokens if max_output_tokens is not None else defaults.max_output_tokens
        )
        self._temperature = temperature if temperature is not None else defaults.temperature
        self._timeout_config: TimeoutConfig = get_timeout_config(
            self._config,
            scope=timeout_scope,
            default_total_seconds=default_total_timeout,
        )

    def _prepare_request(
        self,
        *,
        system_message: str,
        user_message: str,
        metadata: Optional[Mapping[str, Any]],
    ) -> OpenAIRequestPayload:
        """Build a request payload including overrides from ``metadata``.

        Args:
            system_message: System-level instruction for the provider.
            user_message: User prompt delivered to the provider.
            metadata: Optional mapping containing override hints.

        Returns:
            Instance of :class:`OpenAIRequestPayload` encapsulating the
            resolved provider parameters.

        Raises:
            None.

        Side Effects:
            None.

        Timeout:
            Not applicable; execution is CPU-bound.
        """

        max_tokens = _extract_override(metadata, "max_output_tokens", _coerce_optional_int)
        if max_tokens is None:
            max_tokens = _extract_override(metadata, "max_tokens", _coerce_optional_int)
        temperature = _extract_override(metadata, "temperature", _coerce_optional_float)
        return OpenAIRequestPayload(
            system_message=system_message,
            user_message=user_message,
            max_output_tokens=max_tokens if max_tokens is not None else self._max_output_tokens,
            temperature=temperature if temperature is not None else self._temperature,
        )

    def _invoke_model(
        self,
        request: OpenAIRequestPayload,
        *,
        operation_name: str,
    ) -> str:
        """Execute the provider call and return the raw response text.

        Args:
            request: Prepared OpenAI request payload.
            operation_name: Human-readable operation label used in timeout
                error messages.

        Returns:
            Raw string returned by the provider after serialisation.

        Raises:
            TimeoutError: When the provider call exceeds the configured
                timeout.

        Side Effects:
            Issues HTTP requests via the provider client.

        Timeout:
            Enforced via :func:`operation_timeout` using the configured
            :class:`TimeoutConfig`.
        """

        kwargs: dict[str, Any] = {}
        if request.max_output_tokens is not None:
            kwargs["max_tokens"] = request.max_output_tokens
        if request.temperature is not None:
            kwargs["temperature"] = request.temperature
        try:
            with operation_timeout(self._timeout_config, operation=operation_name):
                response, _ = self._call_model(
                    prompt_template=request.user_message,
                    context={},
                    config=self._config,
                    is_structured=True,
                    system_message=request.system_message,
                    **kwargs,
                )
        except Exception as exc:
            _LOGGER.error(
                (
                    "event=provider_call_failed provider=openai operation=%s stage=invoke "
                    "failure_class=%s fallback_used=%s"
                ),
                operation_name,
                exc.__class__.__name__,
                _format_bool(False),
                exc_info=False,
            )
            raise
        return _normalise_json_like(response)

    def _execute_with_retries(
        self,
        *,
        system_message: str,
        user_message: str,
        parser: _ResponseParser[ModelT],
        metadata: Optional[Mapping[str, Any]],
        operation_name: str,
    ) -> ModelT:
        """Perform the model call with validation-aware retries.

        Args:
            system_message: System prompt used for the request.
            user_message: Base user prompt for the first attempt.
            parser: Parser responsible for validating provider output.
            metadata: Optional override metadata for provider parameters.
            operation_name: Human-readable operation identifier.

        Returns:
            Parsed domain model or fallback artefact emitted by the parser.

        Raises:
            RuntimeError: If the parser fails to return a fallback artefact
                after exhausting retries.

        Side Effects:
            Issues up to ``max_retries + 1`` provider calls.

        Timeout:
            Each provider call is wrapped in :func:`operation_timeout`.
        """

        prompt = user_message
        fallback: Optional[ModelT] = None
        issues: Sequence[ValidationIssue] = ()
        for attempt in range(self._max_retries + 1):
            request = self._prepare_request(
                system_message=system_message,
                user_message=prompt,
                metadata=metadata,
            )
            call_started = time.perf_counter()
            raw_text = self._invoke_model(request, operation_name=operation_name)
            total_duration_ms = (time.perf_counter() - call_started) * 1000.0
            _LOGGER.info(
                (
                    "event=provider_call_metrics provider=openai operation=%s stage=completed "
                    "attempt=%d time_to_first_token_ms=%.2f total_duration_ms=%.2f emitted_count=1"
                ),
                operation_name,
                attempt,
                total_duration_ms,
                total_duration_ms,
            )
            result = parser.parse(raw_text)
            if result.model is not None:
                fallback = result.model
            if result.is_valid:
                _LOGGER.info(
                    (
                        "event=provider_validation_passed provider=openai operation=%s "
                        "attempt=%d fallback_used=%s"
                    ),
                    operation_name,
                    attempt,
                    _format_bool(False),
                )
                assert result.model is not None
                return result.model
            issues = result.validation_errors
            issue_count = len(issues)
            will_retry = attempt < self._max_retries
            _LOGGER.warning(
                (
                    "event=provider_validation_failed provider=openai operation=%s stage=validation "
                    "attempt=%d failure_class=SchemaValidationError fallback_used=%s "
                    "validation_error_count=%d will_retry=%s"
                ),
                operation_name,
                attempt,
                _format_bool(False),
                issue_count,
                _format_bool(will_retry),
            )
            if attempt >= self._max_retries:
                break
            retry_message = parser.build_retry_message(issues)
            prompt = _compose_retry_prompt(user_message, retry_message)
        if fallback is None:
            _LOGGER.error(
                (
                    "event=provider_fallback_missing provider=openai operation=%s stage=fallback "
                    "failure_class=ParserFallbackMissing fallback_used=%s"
                ),
                operation_name,
                _format_bool(False),
            )
            raise RuntimeError("Parser did not return a fallback model after retries.")
        _LOGGER.warning(
            (
                "event=provider_fallback_returned provider=openai operation=%s stage=fallback "
                "failure_class=SchemaValidationError fallback_used=%s validation_error_count=%d"
            ),
            operation_name,
            _format_bool(True),
            len(issues),
        )
        return fallback


class OpenAIPointExtractorGateway(_OpenAIPreflightGatewayBase, PointExtractorGateway):
    """OpenAI-backed implementation of :class:`PointExtractorGateway`.

    The gateway composes prompts using the application-layer helpers,
    executes OpenAI calls with timeout and retry controls, and converts
    responses into immutable domain models via
    :class:`ExtractionResponseParser`.
    """

    def __init__(
        self,
        *,
        config: Optional[Mapping[str, Any]] = None,
        parser: Optional[ExtractionResponseParser] = None,
        call_model: ProviderCall = openai_client.call_openai_with_retry,
        prompt_builder: Callable[..., PromptBundle] = build_extraction_prompt,
        schema_loader: Callable[[], Mapping[str, Any]] = load_extraction_schema,
        max_retries: int = 1,
        max_output_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        default_total_timeout: Optional[float] = DEFAULT_PROVIDER_TIMEOUT_SECONDS,
    ) -> None:
        """Configure the gateway with prompt builders, parser, and settings.

        Args:
            config: Optional configuration mapping forwarded to the provider
                client and timeout helpers.
            parser: Optional custom parser used to validate extraction
                responses.
            call_model: Callable executing the provider request.
            prompt_builder: Callable that composes prompts for the model.
            schema_loader: Callable returning the JSON schema mapping.
            max_retries: Number of retry attempts on validation failure.
            max_output_tokens: Optional override for the response token cap.
            temperature: Optional override for the sampling temperature.
            default_total_timeout: Fallback timeout when configuration omits
                a value.

        Raises:
            ValueError: Propagated from the base class when ``max_retries`` is
                negative.

        Side Effects:
            None beyond reading configuration data.

        Timeout:
            Not applicable; the constructor performs synchronous setup.
        """

        super().__init__(
            config=config,
            call_model=call_model,
            max_retries=max_retries,
            timeout_scope="preflight.extraction",
            default_total_timeout=default_total_timeout,
            max_output_tokens=max_output_tokens,
            temperature=temperature,
        )
        self._parser = parser or ExtractionResponseParser()
        self._prompt_builder = prompt_builder
        self._schema_loader = schema_loader
        self._chunking_settings = _resolve_chunking_settings(self._config)

    def _should_chunk(self, total_characters: int) -> bool:
        """Determine whether the pipeline input should be processed in chunks."""

        settings = self._chunking_settings
        return settings.enabled and total_characters > settings.max_characters

    def _determine_chunk_limit(self, global_limit: Optional[int]) -> Optional[int]:
        """Return the per-chunk point limit given the global ``global_limit``."""

        per_chunk = self._chunking_settings.max_points_per_chunk
        if per_chunk is None or per_chunk <= 0:
            return global_limit
        if global_limit is None:
            return per_chunk
        return min(per_chunk, global_limit)

    def _extract_single(
        self,
        pipeline_input: PipelineInput,
        schema: Mapping[str, Any],
        *,
        max_points: Optional[int],
        metadata: Optional[Mapping[str, object]],
        operation_name: str,
        total_characters: int,
    ) -> ExtractionResult:
        """Execute a single extraction request without chunking."""

        prompt_bundle = self._prompt_builder(
            pipeline_input,
            schema,
            max_points=max_points,
        )
        metadata_copy = dict(metadata) if metadata is not None else None
        result = self._execute_with_retries(
            system_message=prompt_bundle.system,
            user_message=prompt_bundle.user,
            parser=self._parser,
            metadata=metadata_copy,
            operation_name=operation_name,
        )

        enriched_stats = dict(result.source_stats or {})
        enriched_stats["characters"] = total_characters
        metadata_view = pipeline_input.metadata or {}
        if metadata_view.get("truncated") and "input_truncated" not in enriched_stats:
            enriched_stats["input_truncated"] = True
            truncation_reason = metadata_view.get("truncation_reason")
            if truncation_reason and "input_truncation_reason" not in enriched_stats:
                enriched_stats["input_truncation_reason"] = str(truncation_reason)

        truncated = result.truncated
        if not truncated and max_points is not None and len(result.points) >= max_points:
            truncated = True

        return ExtractionResult(
            points=result.points,
            source_stats=enriched_stats,
            truncated=truncated,
            raw_response=result.raw_response,
            validation_errors=result.validation_errors,
        )

    def _extract_with_chunking(
        self,
        pipeline_input: PipelineInput,
        schema: Mapping[str, Any],
        *,
        max_points: Optional[int],
        metadata: Optional[Mapping[str, object]],
    ) -> ExtractionResult:
        """Run the chunked extraction pipeline for large inputs."""

        settings = self._chunking_settings
        chunks = _split_into_chunks(pipeline_input.content, settings)
        if not chunks:
            return ExtractionResult(
                points=(),
                source_stats={
                    "characters": len(pipeline_input.content),
                    "chunking": {
                        "strategy": "chunked_map_reduce",
                        "chunk_count": 0,
                    },
                },
                truncated=False,
            )

        chunk_count = len(chunks)
        _LOGGER.info(
            (
                "event=preflight_chunking_enabled provider=openai operation=preflight_extraction "
                "chunks=%d chunk_size_limit=%d overlap=%d"
            ),
            chunk_count,
            settings.max_characters,
            settings.overlap_characters,
        )

        chunk_limit = self._determine_chunk_limit(max_points)
        chunk_results: list[ExtractionResult] = []
        for chunk in chunks:
            chunk_input = _compose_chunk_pipeline_input(
                pipeline_input,
                chunk,
                chunk_count=chunk_count,
                overlap=settings.overlap_characters,
            )
            chunk_metadata = _compose_chunk_provider_metadata(
                metadata,
                chunk,
                chunk_count=chunk_count,
            )
            chunk_result = self._extract_single(
                chunk_input,
                schema,
                max_points=chunk_limit,
                metadata=chunk_metadata,
                operation_name=f"preflight_extraction_chunk_{chunk.index + 1}_of_{chunk_count}",
                total_characters=chunk.end_offset - chunk.start_offset,
            )
            chunk_results.append(chunk_result)

        return _merge_chunk_results(
            pipeline_input=pipeline_input,
            total_characters=len(pipeline_input.content),
            chunks=chunks,
            chunk_results=tuple(chunk_results),
            max_points=max_points,
            settings=settings,
        )

    def extract_points(
        self,
        pipeline_input: PipelineInput,
        *,
        max_points: Optional[int] = None,
        metadata: Optional[Mapping[str, object]] = None,
    ) -> ExtractionResult:
        """Extract structured points from ``pipeline_input``.

        Args:
            pipeline_input: Canonical pipeline input for the run.
            max_points: Optional limit for the number of points requested.
            metadata: Optional mapping carrying provider override hints and
                contextual metadata.

        Returns:
            :class:`ExtractionResult` describing the extracted points or a
            fallback artefact when validation fails.

        Raises:
            TimeoutError: Propagated when the provider exceeds the configured
                timeout.
            RuntimeError: Propagated if retries complete without producing a
                fallback artefact, which signals a deeper parser error.

        Side Effects:
            Issues OpenAI API calls and records timeout handlers during those
            invocations.

        Timeout:
            Enforced per request using :func:`operation_timeout`.
        """

        stripped_content = pipeline_input.content.strip()
        total_characters = len(pipeline_input.content)
        if len(stripped_content) < MINIMUM_CONTENT_CHARACTERS:
            source_stats: dict[str, object] = {
                "characters": total_characters,
                "skipped": True,
                "skip_reason": "empty_content"
                if not stripped_content
                else "content_below_min_threshold",
            }
            metadata_view = pipeline_input.metadata or {}
            if metadata_view.get("truncated"):
                source_stats["input_truncated"] = True
                truncation_reason = metadata_view.get("truncation_reason")
                if truncation_reason:
                    source_stats["input_truncation_reason"] = str(truncation_reason)
            return ExtractionResult(
                points=(),
                source_stats=source_stats,
                truncated=False,
            )

        schema = self._schema_loader()
        if self._should_chunk(total_characters):
            return self._extract_with_chunking(
                pipeline_input,
                schema,
                max_points=max_points,
                metadata=metadata,
            )

        return self._extract_single(
            pipeline_input,
            schema,
            max_points=max_points,
            metadata=metadata,
            operation_name="preflight_extraction",
            total_characters=total_characters,
        )


class OpenAIQueryBuilderGateway(_OpenAIPreflightGatewayBase, QueryBuilderGateway):
    """OpenAI-backed implementation of :class:`QueryBuilderGateway`.

    The adapter reuses shared prompt builders and parsers to transform
    extraction results into structured query plans while honouring timeout and
    retry policies.
    """

    def __init__(
        self,
        *,
        config: Optional[Mapping[str, Any]] = None,
        parser: Optional[QueryPlanResponseParser] = None,
        call_model: ProviderCall = openai_client.call_openai_with_retry,
        prompt_builder: Callable[..., PromptBundle] = build_query_plan_prompt,
        schema_loader: Callable[[], Mapping[str, Any]] = load_query_plan_schema,
        max_retries: int = 1,
        max_output_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        default_total_timeout: Optional[float] = DEFAULT_PROVIDER_TIMEOUT_SECONDS,
    ) -> None:
        """Configure the query-building gateway dependencies and defaults.

        Args:
            config: Optional configuration mapping that supplies provider
                defaults and timeout settings.
            parser: Optional parser overriding the default query plan parser.
            call_model: Callable that performs the provider invocation.
            prompt_builder: Callable constructing the prompt bundle.
            schema_loader: Callable returning the JSON schema mapping.
            max_retries: Number of retry attempts when validation fails.
            max_output_tokens: Optional override for provider token caps.
            temperature: Optional override for the sampling temperature.
            default_total_timeout: Fallback timeout when configuration omits
                a value.

        Raises:
            ValueError: Propagated from the base class when ``max_retries`` is
                negative.

        Side Effects:
            None beyond reading configuration data.

        Timeout:
            Not applicable; the constructor performs synchronous setup.
        """

        super().__init__(
            config=config,
            call_model=call_model,
            max_retries=max_retries,
            timeout_scope="preflight.query_planning",
            default_total_timeout=default_total_timeout,
            max_output_tokens=max_output_tokens,
            temperature=temperature,
        )
        self._parser = parser or QueryPlanResponseParser()
        self._prompt_builder = prompt_builder
        self._schema_loader = schema_loader

    def build_queries(
        self,
        extraction: ExtractionResult,
        pipeline_input: Optional[PipelineInput] = None,
        *,
        max_queries: Optional[int] = None,
        metadata: Optional[Mapping[str, object]] = None,
    ) -> QueryPlan:
        """Build a query plan from ``extraction`` and optional ``pipeline_input``.

        Args:
            extraction: Extraction artefact containing the points to analyse.
            pipeline_input: Optional original corpus to provide additional
                context when planning queries.
            max_queries: Optional cap on the number of queries to produce.
            metadata: Optional mapping containing provider override hints.

        Returns:
            :class:`QueryPlan` describing the planned follow-up queries or a
            fallback plan when validation fails.

        Raises:
            TimeoutError: If the provider call exceeds the configured timeout.
            RuntimeError: When retries conclude without a fallback artefact,
                indicating an internal parsing error.

        Side Effects:
            Issues OpenAI API requests and temporarily installs timeout
            handlers.

        Timeout:
            Managed per request via :func:`operation_timeout`.
        """

        schema = self._schema_loader()
        prompt_bundle = self._prompt_builder(
            extraction,
            schema,
            pipeline_input=pipeline_input,
            max_queries=max_queries,
        )
        metadata_copy = dict(metadata) if metadata is not None else None
        return self._execute_with_retries(
            system_message=prompt_bundle.system,
            user_message=prompt_bundle.user,
            parser=self._parser,
            metadata=metadata_copy,
            operation_name="preflight_query_planning",
        )


__all__ = ["OpenAIPointExtractorGateway", "OpenAIQueryBuilderGateway"]
