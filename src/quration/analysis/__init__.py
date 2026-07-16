"""
Quration Analysis Module

This module provides tools for analyzing curated NGS datasets using nf-core pipelines.

Features:
- LLM-powered analysis plan generation
- Automated data fetching from GEO/SRA
- Nextflow pipeline execution
- Results parsing and summarization

Main components:
- AnalysisPlanGenerator: Generate analysis plans from curated metadata
- DataFetcher: Download raw data from GEO/SRA
- NextflowExecutor: Execute nf-core pipelines
- ConfigGenerator: Generate pipeline configurations
- ResultsParser: Parse and summarize pipeline outputs
"""

from .config_generator import ConfigGenerator
from .data_fetcher import DataFetcher, GEOToSRAConverter
from .models import (
    AnalysisPlan,
    ComparisonGroup,
    ComputeEnvironment,
    ExecutionResult,
    ExecutionStatus,
    FetchNGSParameters,
    PipelineConfig,
    PipelineType,
    ReferenceGenome,
    RNASeqParameters,
    SampleSheet,
)
from .nextflow_executor import NextflowExecutor, check_nextflow_available
from .pipeline_registry import GenomeRegistry, PipelineRegistry
from .plan_generator import AnalysisPlanGenerator
from .results_parser import MultiQCParser, ResultsParser

__version__ = "0.1.0"

__all__ = [
    # Plan generation
    "AnalysisPlanGenerator",
    "AnalysisPlan",
    # Data fetching
    "DataFetcher",
    "GEOToSRAConverter",
    # Pipeline execution
    "NextflowExecutor",
    "ConfigGenerator",
    "check_nextflow_available",
    # Results
    "ResultsParser",
    "MultiQCParser",
    "ExecutionResult",
    # Models
    "PipelineConfig",
    "PipelineType",
    "ComputeEnvironment",
    "ExecutionStatus",
    "RNASeqParameters",
    "FetchNGSParameters",
    "ComparisonGroup",
    "ReferenceGenome",
    "SampleSheet",
    # Registry
    "PipelineRegistry",
    "GenomeRegistry",
]
