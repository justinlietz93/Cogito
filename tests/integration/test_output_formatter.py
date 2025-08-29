# tests/test_output_formatter.py

import pytest
import os
import sys

# Adjust path to import from the new src directory
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from src.output_formatter import format_critique_output

def test_format_with_findings():
    """Tests formatting when findings are present."""
    critique_data = {
        'final_assessment': 'Assessment with findings.',
        'points': [
            {'area': 'Area 1', 'critique': 'Critique A', 'severity': 'High', 'confidence': 0.9},
            {'area': 'Area 2', 'critique': 'Critique B', 'severity': 'Low', 'confidence': 0.5}
        ],
        'no_findings': False
    }
    output = format_critique_output(critique_data)

    assert "=== CRITIQUE ASSESSMENT REPORT ===" in output
    assert "OVERALL ASSESSMENT:" in output
    assert "- Assessment with findings." in output
    assert "IDENTIFIED POINTS:" in output
    assert "1. AREA: Area 1" in output
    assert "SEVERITY: High (Confidence: 0.90)" in output # Check confidence included
    assert "CRITIQUE: Critique A" in output
    assert "2. AREA: Area 2" in output
    assert "SEVERITY: Low (Confidence: 0.50)" in output # Check confidence included
    assert "CRITIQUE: Critique B" in output
    assert "=== END OF REPORT ===" in output
    assert "NO SIGNIFICANT POINTS" not in output

def test_format_no_findings_flag():
    """Tests formatting when the no_findings flag is True."""
    critique_data = {
        'final_assessment': 'Should be ignored.',
        'points': [{'area': 'Ignore', 'critique': 'Ignore', 'severity': 'Ignore'}],
        'no_findings': True
    }
    output = format_critique_output(critique_data)

    assert "=== CRITIQUE ASSESSMENT REPORT ===" in output
    assert "ANALYSIS COMPLETE. NO SIGNIFICANT POINTS FOR IMPROVEMENT IDENTIFIED." in output
    assert "OVERALL ASSESSMENT:" not in output
    assert "IDENTIFIED POINTS:" not in output
    assert "=== END OF REPORT ===" in output

def test_format_findings_but_empty_points():
    """Tests formatting edge case: no_findings is False but points list is empty."""
    critique_data = {
        'final_assessment': 'Assessment without specific points.',
        'points': [],
        'no_findings': False
    }
    output = format_critique_output(critique_data)

    assert "=== CRITIQUE ASSESSMENT REPORT ===" in output
    assert "OVERALL ASSESSMENT:" in output
    assert "- Assessment without specific points." in output
    assert "IDENTIFIED POINTS:" not in output # Check the specific message for this case
    assert "- No specific points were detailed despite findings being indicated." in output
    assert "=== END OF REPORT ===" in output
    assert "NO SIGNIFICANT POINTS" not in output

def test_format_missing_keys_in_points():
    """Tests formatting robustness if point dictionaries miss keys."""
    critique_data = {
        'final_assessment': 'Assessment with partial points.',
        'points': [
            {'critique': 'Only critique provided', 'severity': 'Medium'}, # Missing area
            {'area': 'Area Only', 'severity': 'Low', 'confidence': 0.6} # Missing critique
        ],
        'no_findings': False
    }
    output = format_critique_output(critique_data)

    assert "=== CRITIQUE ASSESSMENT REPORT ===" in output
    assert "OVERALL ASSESSMENT:" in output
    assert "- Assessment with partial points." in output
    assert "IDENTIFIED POINTS:" in output
    assert "1. AREA: N/A" in output # Check default value
    assert "SEVERITY: Medium" in output # Confidence not present, shouldn't show
    assert "(Confidence:" not in output.splitlines()[6] # Check confidence specifically absent
    assert "CRITIQUE: Only critique provided" in output
    assert "2. AREA: Area Only" in output
    assert "SEVERITY: Low (Confidence: 0.60)" in output # Confidence present, should show
    assert "CRITIQUE: N/A" in output # Check default value
    assert "=== END OF REPORT ===" in output

def test_format_missing_assessment_key():
    """Tests formatting robustness if final_assessment key is missing."""
    critique_data = {
        # 'final_assessment': 'Missing',
        'points': [{'area': 'A', 'critique': 'C', 'severity': 'S'}],
        'no_findings': False
    }
    output = format_critique_output(critique_data)
    assert "=== CRITIQUE ASSESSMENT REPORT ===" in output
    assert "OVERALL ASSESSMENT:" in output
    assert "- Assessment data unavailable." in output # Check default value
    assert "IDENTIFIED POINTS:" in output
    assert "=== END OF REPORT ===" in output
