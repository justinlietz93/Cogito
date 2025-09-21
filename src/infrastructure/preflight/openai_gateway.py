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
from ...domain.preflight import ExtractionResult, QueryPlan
from ...pipeline_input import PipelineInput
from ...providers import openai_client
from ..timeouts import TimeoutConfig, get_timeout_config, operation_timeout


DEFAULT_PROVIDER_TIMEOUT_SECONDS = 60.0
DEFAULT_MAX_OUTPUT_TOKENS = 4096


JsonLike = Any
ProviderCall = Callable[..., Tuple[JsonLike, str]]


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
        with operation_timeout(self._timeout_config, operation=operation_name):
            response, _ = self._call_model(
                prompt_template=request.user_message,
                context={},
                config=self._config,
                is_structured=True,
                system_message=request.system_message,
                **kwargs,
            )
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
            raw_text = self._invoke_model(request, operation_name=operation_name)
            result = parser.parse(raw_text)
            if result.model is not None:
                fallback = result.model
            if result.is_valid:
                assert result.model is not None
                return result.model
            issues = result.validation_errors
            if attempt >= self._max_retries:
                break
            retry_message = parser.build_retry_message(issues)
            prompt = _compose_retry_prompt(user_message, retry_message)
        if fallback is None:
            raise RuntimeError("Parser did not return a fallback model after retries.")
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

        schema = self._schema_loader()
        prompt_bundle = self._prompt_builder(
            pipeline_input,
            schema,
            max_points=max_points,
        )
        metadata_copy = dict(metadata) if metadata is not None else None
        return self._execute_with_retries(
            system_message=prompt_bundle.system,
            user_message=prompt_bundle.user,
            parser=self._parser,
            metadata=metadata_copy,
            operation_name="preflight_extraction",
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
