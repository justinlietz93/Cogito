"""Focused tests for reasoning self-critique helper utilities."""

import pytest

from src.reasoning_agent_self_critique import (
    build_self_critique_adjustments,
    _normalise_confidence,
    _severity_score,
    _canonical_severity,
    _mean,
    _collect_nodes,
    _filter_peer_nodes,
    _summarise_peers,
    _normalise_text,
)


def test_normalise_confidence_bounds_and_invalid():
    assert _normalise_confidence(-1.2) == 0.0
    assert _normalise_confidence(2.4) == 1.0
    assert _normalise_confidence("not a number") is None


def test_collect_nodes_handles_non_dict_and_invalid_children():
    assert _collect_nodes(None) == []

    tree = {
        'id': 'root',
        'sub_critiques': [
            {'id': 'child'},
            'invalid-child',
            {'id': 'branch', 'sub_critiques': [{'id': 'leaf'}]},
        ],
    }

    collected = _collect_nodes(tree)
    collected_ids = {node.get('id') for node, _depth in collected if isinstance(node, dict)}
    assert {'root', 'child', 'branch', 'leaf'} <= collected_ids


def test_collect_nodes_skips_chameleon_nodes():
    class ChameleonNode:
        def __init__(self, data: dict[str, object]) -> None:
            self._data = data
            self._appears_dict = True

        @property
        def __class__(self):  # type: ignore[override]
            if self._appears_dict:
                self._appears_dict = False
                return dict
            return object

        def get(self, key: str, default: object | None = None) -> object | None:
            return self._data.get(key, default)

    tree = {
        'id': 'root',
        'sub_critiques': [ChameleonNode({'id': 'tricky'})],
    }

    collected = _collect_nodes(tree)
    ids = {node.get('id') for node, _depth in collected}
    assert 'tricky' not in ids


def test_filter_peer_nodes_fallback_to_original():
    peers = [{'assigned_point_id': 'other', 'confidence': 0.5}]
    assert _filter_peer_nodes(peers, 'target') is peers


def test_summarise_peers_handles_missing_values():
    peers = [
        {'confidence': '0.6', 'severity': None},
        {'confidence': 0.4, 'severity': 'high'},
        {'confidence': 'bad-value', 'severity': 'High'},
    ]

    summary = _summarise_peers(peers, assigned_point=None)
    assert summary['confidence_avg'] == pytest.approx(0.5, abs=1e-6)
    assert summary['severity_avg'] == pytest.approx(0.8, abs=1e-6)
    assert summary['severity_label'] == 'High'


def test_severity_normalisation_and_canonicalisation():
    assert _severity_score(None) == 0.5
    assert _canonical_severity(None) is None
    assert _canonical_severity('') is None
    assert _canonical_severity('custom level') == 'Custom Level'


def test_mean_returns_none_for_invalid_values():
    assert _mean([None, None]) is None


def test_normalise_text_for_none():
    assert _normalise_text(None) == ''


def test_build_self_critique_skips_invalid_nodes():
    own_critique = {
        'agent_style': 'Stub',
        'critique_tree': {
            'id': 'root',
            'confidence': 'invalid',
            'severity': 'medium',
            'evidence': 'Minimal evidence',
            'concession': '',
            'sub_critiques': [
                {
                    'confidence': 0.5,
                    'severity': 'low',
                    'evidence': 'Missing identifier should skip this node.',
                    'concession': '',
                    'sub_critiques': [],
                },
                {
                    'id': 'valid-claim',
                    'confidence': 0.45,
                    'severity': None,
                    'evidence': 'Detailed supporting documentation.' * 2,
                    'concession': 'We might have overlooked some nuances.',
                    'sub_critiques': [],
                },
            ],
        },
    }

    adjustments = build_self_critique_adjustments(own_critique, other_critiques=[], config={'self_critique': {'minimum_delta': 0.0}})
    adjustment_map = {adj['target_claim_id']: adj for adj in adjustments}

    assert 'valid-claim' in adjustment_map
    reasoning = adjustment_map['valid-claim']['reasoning']
    assert 'Agent conceded limitations' in reasoning
    assert adjustment_map['valid-claim']['confidence_delta'] < 0

