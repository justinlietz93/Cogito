# src/critique_module/__init__.py

"""
Critique Module Package.

Provides functionality to critique text documents using a council of
reasoning agents based on philosophical principles.
"""

from .main import critique_goal_document
from .pipeline_input import PipelineInput, ensure_pipeline_input

__all__ = ['critique_goal_document', 'PipelineInput', 'ensure_pipeline_input']
