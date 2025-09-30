# tests/test_reasoning_agent.py

import logging
import os
import pytest
import sys
from unittest.mock import MagicMock, patch

# Adjust path to import from the new src directory
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from src.reasoning_agent import (
    AristotleAgent,
    BoundaryConditionAnalystAgent,
    DescartesAgent,
    EmpiricalValidationAnalystAgent,
    ExpertArbiterAgent,
    ExpertArbiterBaseAgent,
    FirstPrinciplesAnalystAgent,
    KantAgent,
    LeibnizAgent,
    LogicalStructureAnalystAgent,
    PEER_REVIEW_ENHANCEMENT,
    ReasoningAgent,
    RussellAgent,
    SCIENTIFIC_PEER_REVIEW_ENHANCEMENT,
    ScientificExpertArbiterAgent,
    SystemsAnalystAgent,
    OptimizationAnalystAgent,
    PopperAgent,
)

# List of agent classes for coverage
AGENT_TEST_PARAMS = [
    AristotleAgent,
    DescartesAgent,
    KantAgent,
    LeibnizAgent,
    PopperAgent,
    RussellAgent,
]

SCIENTIFIC_AGENT_TEST_PARAMS = [
    SystemsAnalystAgent,
    FirstPrinciplesAnalystAgent,
    BoundaryConditionAnalystAgent,
    OptimizationAnalystAgent,
    EmpiricalValidationAnalystAgent,
    LogicalStructureAnalystAgent,
]

# --- Fixtures ---

@pytest.fixture(params=AGENT_TEST_PARAMS)
def agent_instance(request):
    """Fixture to create an instance of each philosopher agent."""
    agent_class = request.param
    return agent_class()


class StubAgent(ReasoningAgent):
    """Minimal reasoning agent used to isolate critique behaviours."""

    def __init__(self, directives: str = "BASE DIRECTIVES"):
        super().__init__("StubAgent")
        self._directives = directives

    def get_style_directives(self) -> str:
        return self._directives


def test_reasoning_agent_base_method_can_be_invoked_via_super() -> None:
    class ProxyAgent(ReasoningAgent):
        def __init__(self) -> None:
            super().__init__("ProxyAgent")

        def get_style_directives(self) -> str:
            return super().get_style_directives()  # type: ignore[return-value]

    proxy = ProxyAgent()

    assert proxy.get_style_directives() is None

@pytest.fixture
def mock_tree_execution():
    """Fixture to mock the execute_reasoning_tree function."""
    # Define a consistent mock return value for the tree
    mock_tree_result = {
        'id': 'mock-root-id',
        'claim': 'Mock critique claim',
        'evidence': 'Mock evidence',
        'confidence': 0.8,
        'severity': 'Medium',
        'sub_critiques': []
    }
    # Patch the function in the reasoning_agent module where it's imported
    with patch('src.reasoning_agent.execute_reasoning_tree', return_value=mock_tree_result) as mock_tree:
        yield mock_tree

# --- Test Cases ---

def test_agent_initialization(agent_instance):
    """Tests that agents are initialized with the correct style name."""
    agent_class = next(cls for cls in AGENT_TEST_PARAMS if isinstance(agent_instance, cls))
    assert agent_instance.style == agent_class.__name__.replace("Agent", "")

def test_get_style_directives_returns_prompt(agent_instance):
    """Agents should expose non-empty prompt directives."""

    directives1 = agent_instance.get_style_directives()
    assert isinstance(directives1, str)
    assert directives1.strip()

    directives2 = agent_instance.get_style_directives()
    assert directives2 == directives1


def test_scientific_agents_have_prompts():
    """Scientific agents should expose non-empty prompt directives."""

    for agent_class in SCIENTIFIC_AGENT_TEST_PARAMS:
        agent = agent_class()
        directives = agent.get_style_directives()
        assert isinstance(directives, str)
        assert directives.strip()


def test_stub_agent_set_logger_updates_logger(caplog):
    """Agents should adopt the injected logger and emit an initialization message."""

    stub_agent = StubAgent()
    custom_logger = logging.getLogger('stub-agent-test')

    with caplog.at_level('INFO'):
        stub_agent.set_logger(custom_logger)

    assert stub_agent.logger is custom_logger
    assert any('Agent logger initialized for StubAgent' in message for message in caplog.messages)

def test_critique_method_calls_tree(agent_instance, mock_tree_execution):
    """Tests that the critique method calls execute_reasoning_tree."""
    dummy_content = "Some text to critique."
    result = agent_instance.critique(dummy_content, config={})

    # Check that the tree function was called
    mock_tree_execution.assert_called_once()
    call_args, call_kwargs = mock_tree_execution.call_args
    assert call_kwargs['initial_content'] == dummy_content
    assert call_kwargs['style_directives'] == agent_instance.get_style_directives()
    assert call_kwargs['agent_style'] == agent_instance.style

    # Check the structure of the returned dictionary
    assert result['agent_style'] == agent_instance.style
    assert 'critique_tree' in result
    assert result['critique_tree']['id'] == 'mock-root-id' # Check mock data is returned

def test_critique_method_handles_tree_termination(agent_instance):
    """Tests that critique handles None return from execute_reasoning_tree."""
    # Patch the function in the reasoning_agent module where it's imported
    with patch('src.reasoning_agent.execute_reasoning_tree', return_value=None) as mock_tree:
        result = agent_instance.critique("Some content", config={})
        mock_tree.assert_called_once()
        assert result['agent_style'] == agent_instance.style
        assert result['critique_tree']['id'] == 'root-terminated'
        assert result['critique_tree']['confidence'] == 0.0

def test_self_critique_aligns_with_peer_consensus(agent_instance):
    """Self-critique should nudge confidence toward peer consensus and consider evidence."""

    own_critique = {
        'agent_style': agent_instance.style,
        'critique_tree': {
            'id': 'root-claim',
            'claim': 'Root finding',
            'confidence': 0.9,
            'severity': 'High',
            'evidence': 'Sparse notes',
            'concession': '',
            'sub_critiques': [
                {
                    'id': 'child-claim',
                    'claim': 'Follow-up finding',
                    'confidence': 0.4,
                    'severity': 'Medium',
                    'evidence': 'Extensive supporting evidence that reinforces the critique.' * 3,
                    'concession': 'none',
                    'sub_critiques': [],
                }
            ],
        },
    }

    other_critiques = [
        {
            'agent_style': 'PeerA',
            'critique_tree': {
                'id': 'peer-a',
                'confidence': 0.6,
                'severity': 'Medium',
                'evidence': 'Peer A supplied detailed evidence supporting a moderate concern.',
                'sub_critiques': [],
            },
        },
        {
            'agent_style': 'PeerB',
            'critique_tree': {
                'id': 'peer-b',
                'confidence': 0.55,
                'severity': 'Low',
                'evidence': 'Peer B raised lightweight reservations with minimal urgency.',
                'sub_critiques': [],
            },
        },
    ]

    result = agent_instance.self_critique(own_critique, other_critiques, config={})

    adjustments = {adj['target_claim_id']: adj for adj in result['adjustments']}
    assert 'root-claim' in adjustments
    assert 'child-claim' in adjustments

    root_adjustment = adjustments['root-claim']
    assert root_adjustment['confidence_delta'] == pytest.approx(-0.335, abs=1e-3)
    reasoning_text = root_adjustment['reasoning'].lower()
    assert 'peer confidence average' in reasoning_text
    assert 'lower severity' in reasoning_text
    assert 'limited supporting evidence' in reasoning_text

    child_adjustment = adjustments['child-claim']
    assert child_adjustment['confidence_delta'] == pytest.approx(0.084, abs=1e-3)
    assert 'peer confidence average' in child_adjustment['reasoning'].lower()


def test_self_critique_penalizes_concessions(agent_instance):
    """Concessions should reduce confidence even when peers agree."""

    concession_text = (
        "We might be overlooking alternative explanations and dataset biases that could undermine this point."
    )
    own_critique = {
        'agent_style': agent_instance.style,
        'critique_tree': {
            'id': 'concession-claim',
            'confidence': 0.7,
            'severity': 'Medium',
            'evidence': 'Extensive dataset review and cross validation results support the critique.',
            'concession': concession_text,
            'sub_critiques': [],
        },
    }

    other_critiques = [
        {
            'agent_style': 'Peer',
            'critique_tree': {
                'id': 'peer-root',
                'confidence': 0.7,
                'severity': 'Medium',
                'evidence': 'Peer critique reaches the same conclusion with matching confidence.',
                'sub_critiques': [],
            },
        }
    ]

    result = agent_instance.self_critique(own_critique, other_critiques, config={})

    adjustments = {adj['target_claim_id']: adj for adj in result['adjustments']}
    assert 'concession-claim' in adjustments

    concession_adjustment = adjustments['concession-claim']
    assert concession_adjustment['confidence_delta'] == pytest.approx(-0.09, abs=1e-3)
    assert 'conceded limitations' in concession_adjustment['reasoning'].lower()


def test_self_critique_handles_conflicting_peer_evidence(agent_instance):
    """Conflicting peer feedback should result in moderated adjustments."""

    own_critique = {
        'agent_style': agent_instance.style,
        'critique_tree': {
            'id': 'root-claim',
            'claim': 'Conflicting finding',
            'confidence': 0.6,
            'severity': 'Medium',
            'evidence': 'Extensive analysis with multiple supporting experiments.' * 3,
            'concession': '',
            'sub_critiques': [],
        },
    }

    other_critiques = [
        {
            'agent_style': 'Peer-High',
            'critique_tree': {
                'id': 'peer-high',
                'confidence': 0.9,
                'severity': 'High',
                'evidence': 'Peer high confidence backed by strong data.',
                'sub_critiques': [],
            },
        },
        {
            'agent_style': 'Peer-Low',
            'critique_tree': {
                'id': 'peer-low',
                'confidence': 0.2,
                'severity': 'Low',
                'evidence': 'Peer low confidence citing methodological issues.',
                'sub_critiques': [],
            },
        },
    ]

    result = agent_instance.self_critique(own_critique, other_critiques, config={})

    assert result['adjustments'] == []


def test_stub_agent_applies_peer_review_and_assigned_points():
    """Peer-review mode should append enhancements and surface assigned points."""

    stub_agent = StubAgent()
    expected_tree = {
        'id': 'node-1',
        'claim': 'Delegated claim',
        'evidence': 'Synthesised evidence',
        'confidence': 0.91,
        'severity': 'High',
        'sub_critiques': [],
    }

    with patch('src.reasoning_agent.execute_reasoning_tree', return_value=expected_tree) as mock_tree:
        assigned_points = [{'id': 'focus-1', 'point': 'Analyse fairness constraints'}]
        result = stub_agent.critique(
            content='Content under review' * 10,
            config={'goal': 'Unit test goal'},
            peer_review=True,
            assigned_points=assigned_points,
        )

    mock_tree.assert_called_once()
    call_kwargs = mock_tree.call_args.kwargs
    assert call_kwargs['assigned_points'] is assigned_points
    style_directives = call_kwargs['style_directives']
    assert stub_agent.get_style_directives() in style_directives
    assert PEER_REVIEW_ENHANCEMENT.strip().splitlines()[0] in style_directives
    assert '--- ASSIGNED POINTS ENHANCEMENT ---' in style_directives
    assert 'Analyse fairness constraints' in style_directives
    assert result['critique_tree'] == expected_tree


def test_stub_agent_handles_prompt_load_error():
    """Prompt loading failures should surface an explanatory error payload."""

    stub_agent = StubAgent(directives='ERROR: missing directives')

    with patch('src.reasoning_agent.execute_reasoning_tree') as mock_tree:
        result = stub_agent.critique('Long enough content to avoid pruning' * 3, config={})

    mock_tree.assert_not_called()
    assert result['agent_style'] == 'StubAgent'
    assert 'Failed to load style directives' in result['error']


def test_self_critique_returns_empty_when_tree_missing(agent_instance):
    """Missing critique trees should produce no adjustments."""

    result = agent_instance.self_critique({'agent_style': agent_instance.style}, other_critiques=[], config={})

    assert result['adjustments'] == []


def test_self_critique_scopes_peer_consensus_to_assigned_points(agent_instance):
    """Only peers addressing the same assigned point should influence adjustments."""

    own_critique = {
        'agent_style': agent_instance.style,
        'critique_tree': {
            'id': 'scoped-claim',
            'confidence': 0.3,
            'severity': 'low',
            'evidence': 'Detailed analysis backing the concern.' * 8,
            'concession': '',
            'sub_critiques': [],
            'assigned_point_id': 'focus-1',
        },
    }

    other_critiques = [
        {
            'agent_style': 'AlignedPeerA',
            'critique_tree': {
                'id': 'aligned-a',
                'confidence': 0.9,
                'severity': 'high',
                'evidence': 'Shared focus with substantial empirical backing.',
                'sub_critiques': [],
                'assigned_point_id': 'focus-1',
            },
        },
        {
            'agent_style': 'AlignedPeerB',
            'critique_tree': {
                'id': 'aligned-b',
                'confidence': 0.88,
                'severity': 'high',
                'evidence': 'Additional targeted experiments confirm the issue.',
                'sub_critiques': [],
                'assigned_point_id': 'focus-1',
            },
        },
        {
            'agent_style': 'NeutralPeer',
            'critique_tree': {
                'id': 'neutral',
                'confidence': 0.5,
                'severity': 'medium',
                'evidence': 'General observations relevant to multiple findings.',
                'sub_critiques': [],
                'assigned_point_id': None,
            },
        },
        {
            'agent_style': 'UnrelatedPeerA',
            'critique_tree': {
                'id': 'other-a',
                'confidence': 0.95,
                'severity': 'critical',
                'evidence': 'Focus on a separate assigned point.',
                'sub_critiques': [],
                'assigned_point_id': 'different-point',
            },
        },
        {
            'agent_style': 'UnrelatedPeerB',
            'critique_tree': {
                'id': 'other-b',
                'confidence': 0.97,
                'severity': 'critical',
                'evidence': 'Another unrelated focus area.',
                'sub_critiques': [],
                'assigned_point_id': 'different-point',
            },
        },
    ]

    result = agent_instance.self_critique(own_critique, other_critiques, config={'self_critique': {'minimum_delta': 0.01}})

    adjustments = {adj['target_claim_id']: adj for adj in result['adjustments']}
    scoped_adjustment = adjustments['scoped-claim']
    assert scoped_adjustment['confidence_delta'] == pytest.approx(0.35, abs=1e-3)
    reasoning = scoped_adjustment['reasoning']
    assert 'Adjusted up toward peer confidence average' in reasoning
    assert 'Peers reported higher severity (High).' in reasoning
    assert 'Critical' not in reasoning


def test_arbitrate_scientific_peer_review(monkeypatch):
    """Scientific arbiters should request peer-review enhancements and structured output."""

    arbiter = ScientificExpertArbiterAgent()
    monkeypatch.setattr(arbiter, 'get_style_directives', MagicMock(return_value='BASE ARBITER DIRECTIVES'))

    recorded = {}

    def _fake_call(prompt_template, context, config, is_structured):
        recorded['prompt_template'] = prompt_template
        recorded['context'] = context
        recorded['is_structured'] = is_structured
        return (
            {
                'adjustments': [{'target_claim_id': 'root', 'confidence_delta': -0.1}],
                'arbiter_overall_score': 0.72,
                'arbiter_score_justification': 'Calibration rationale.',
            },
            'arbiter-model',
        )

    with patch('src.reasoning_agent.call_with_retry', side_effect=_fake_call) as mock_call:
        result = arbiter.arbitrate(
            original_content='Original content under review',
            initial_critiques=[{'agent_style': 'Test', 'critique_tree': {'id': 'root'}}],
            config={'goal': 'Arbitration'},
            peer_review=True,
        )

    mock_call.assert_called_once()
    assert recorded['is_structured'] is True
    assert 'scientific_critiques_json' in recorded['context']
    assert 'philosophical_critiques_json' not in recorded['context']
    assert SCIENTIFIC_PEER_REVIEW_ENHANCEMENT.strip().splitlines()[0] in recorded['prompt_template']
    assert 'BASE ARBITER DIRECTIVES' in recorded['prompt_template']
    assert result['agent_style'] == 'ScientificExpertArbiter'
    assert result['adjustments'] == [{'target_claim_id': 'root', 'confidence_delta': -0.1}]
    assert result['arbiter_overall_score'] == 0.72
    assert result['arbiter_score_justification'] == 'Calibration rationale.'


def test_arbitrate_handles_json_serialisation_errors(monkeypatch):
    """Non-serialisable critiques should surface a clear error payload."""

    arbiter = ExpertArbiterAgent()
    monkeypatch.setattr(arbiter, 'get_style_directives', MagicMock(return_value='BASE ARBITER DIRECTIVES'))

    result = arbiter.arbitrate(
        original_content='Original content',
        initial_critiques=[{'agent_style': 'A', 'critique_tree': {'id': 'root'}, 'bad': {'unserialisable'}}],
        config={},
        peer_review=False,
    )

    assert result['adjustments'] == []
    assert result['arbiter_overall_score'] is None
    assert 'Failed to serialize critiques to JSON' in result['error']


def test_arbitrate_handles_invalid_structured_response(monkeypatch):
    """Unexpected arbitration payloads should report a validation error."""

    arbiter = ExpertArbiterAgent()
    monkeypatch.setattr(arbiter, 'get_style_directives', MagicMock(return_value='BASE ARBITER DIRECTIVES'))

    with patch('src.reasoning_agent.call_with_retry', return_value=({'unexpected': True}, 'arbiter-model')):
        result = arbiter.arbitrate(
            original_content='Original content',
            initial_critiques=[{'agent_style': 'A', 'critique_tree': {'id': 'root'}}],
            config={},
        )

    assert result['error'] == 'Invalid arbitration result structure'
    assert result['adjustments'] == []
    assert result['arbiter_overall_score'] is None


def test_arbitrate_handles_call_failures(monkeypatch):
    """Provider failures should be caught and returned as structured errors."""

    arbiter = ExpertArbiterAgent()
    monkeypatch.setattr(arbiter, 'get_style_directives', MagicMock(return_value='BASE ARBITER DIRECTIVES'))

    with patch('src.reasoning_agent.call_with_retry', side_effect=RuntimeError('upstream failure')):
        result = arbiter.arbitrate(
            original_content='Original content',
            initial_critiques=[{'agent_style': 'A', 'critique_tree': {'id': 'root'}}],
            config={},
        )

    assert 'Arbitration failed: upstream failure' in result['error']
    assert result['adjustments'] == []
    assert result['arbiter_overall_score'] is None


def test_expert_arbiter_get_style_directives_returns_prompt():
    """Arbiter base class should return the provided prompt text."""

    arbiter = ExpertArbiterBaseAgent('TestArbiter', 'ARB PROMPT')

    first_read = arbiter.get_style_directives()
    assert first_read == 'ARB PROMPT'
    assert arbiter.get_style_directives() == 'ARB PROMPT'


def test_expert_arbiter_base_methods_raise():
    """Base arbiter agents should not implement critique flows."""

    arbiter = ExpertArbiterBaseAgent('TestArbiter', 'PROMPT TEXT')

    with pytest.raises(NotImplementedError):
        arbiter.critique('content', config={})

    with pytest.raises(NotImplementedError):
        arbiter.self_critique({}, [], config={})


def test_arbitrate_handles_prompt_loading_error(monkeypatch):
    """Prompt-loading failures should short-circuit arbitration."""

    arbiter = ExpertArbiterAgent()
    monkeypatch.setattr(arbiter, 'get_style_directives', MagicMock(return_value='ERROR: prompt missing'))

    result = arbiter.arbitrate('Original content', [], config={})

    assert result['error'] == 'ERROR: prompt missing'
    assert result['adjustments'] == []
    assert result['arbiter_overall_score'] is None


def test_arbitrate_non_scientific_peer_review(monkeypatch):
    """Philosophical arbiters should apply the peer-review enhancement."""

    arbiter = ExpertArbiterAgent()
    monkeypatch.setattr(arbiter, 'get_style_directives', MagicMock(return_value='BASE ARBITER DIRECTIVES'))

    captured = {}

    def _fake_call(prompt_template, context, config, is_structured):
        captured['prompt_template'] = prompt_template
        return (
            {
                'adjustments': [],
                'arbiter_overall_score': 0.6,
                'arbiter_score_justification': 'Balanced.',
            },
            'arbiter-model',
        )

    with patch('src.reasoning_agent.call_with_retry', side_effect=_fake_call):
        arbiter.arbitrate(
            original_content='Original content',
            initial_critiques=[{'agent_style': 'A', 'critique_tree': {'id': 'root'}}],
            config={},
            peer_review=True,
        )

    assert PEER_REVIEW_ENHANCEMENT.strip().splitlines()[0] in captured['prompt_template']
