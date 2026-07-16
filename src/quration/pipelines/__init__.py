"""
Nextflow pipeline integration module.

This module provides:
- Pipeline catalog and registry
- Pipeline execution engine
- Output processing and metadata mapping
"""

from .registry import PipelineRegistry, get_pipeline_registry
from .executor import NextflowExecutor
from .output_processor import OutputProcessor

__all__ = [
    "PipelineRegistry",
    "get_pipeline_registry",
    "NextflowExecutor",
    "OutputProcessor",
]
