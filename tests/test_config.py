"""Tests for configuration management."""

import pytest
from pydantic import ValidationError

from quration.config import QurationConfig, GEOConfig


def test_geo_config_requires_email():
    """Test that GEO config requires an email."""
    with pytest.raises(ValidationError):
        GEOConfig(email="")


def test_config_defaults():
    """Test that config has sensible defaults."""
    # Should work with minimal config
    config = QurationConfig(
        data_sources={
            "geo": {
                "email": "test@example.com"
            }
        }
    )

    assert config.llm.provider == "anthropic"
    assert config.output.output_dir.name == "output"
    assert "json" in config.output.formats


def test_config_nested_settings():
    """Test nested configuration."""
    config = QurationConfig(
        llm={
            "anthropic": {
                "fast_model": "claude-3-5-haiku-20241022",
                "enable_prompt_caching": True,
            }
        },
        data_sources={
            "geo": {
                "email": "test@example.com"
            }
        }
    )

    assert config.llm.anthropic.fast_model == "claude-3-5-haiku-20241022"
    assert config.llm.anthropic.enable_prompt_caching is True
