"""Configuration management for Quration."""

import os
from pathlib import Path
from typing import Literal

import yaml
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Import observability config (lazy import to avoid circular dependencies)
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from quration.observability.config import ObservabilityConfig
else:
    try:
        from quration.observability.config import ObservabilityConfig
    except ImportError:
        ObservabilityConfig = type(None)  # type: ignore


class AnthropicConfig(BaseSettings):
    """Anthropic API configuration."""

    model_config = SettingsConfigDict(extra="ignore", populate_by_name=True)

    api_key: str = Field(default="", validation_alias="ANTHROPIC_API_KEY")
    fast_model: str = "claude-haiku-4-5-20251001"  # Claude Haiku 4.5 (October 2025)
    smart_model: str = "claude-sonnet-4-5-20250929"  # Claude Sonnet 4.5 (September 2025)
    max_tokens: int = 4096
    temperature: float = 0.0
    enable_prompt_caching: bool = True


class AWSBedrockConfig(BaseSettings):
    """AWS Bedrock configuration."""

    model_config = SettingsConfigDict(extra="ignore", populate_by_name=True)

    region: str = "us-east-1"
    access_key_id: str = Field(default="", validation_alias="AWS_ACCESS_KEY_ID")
    secret_access_key: str = Field(default="", validation_alias="AWS_SECRET_ACCESS_KEY")
    model_id: str = "anthropic.claude-3-5-sonnet-20241022-v2:0"


class GCPVertexConfig(BaseSettings):
    """GCP Vertex AI configuration."""

    model_config = SettingsConfigDict(extra="ignore", populate_by_name=True)

    project_id: str = ""
    location: str = "us-central1"
    credentials_path: str = ""


class ClaudeSubscriptionConfig(BaseSettings):
    """Claude Code subscription provider configuration.

    Drives the headless ``claude -p`` CLI using the locally logged-in
    Claude Code (Pro/Max) subscription OAuth instead of a metered API key.

    Intended for **local, single-operator use only** (you running your own
    app on your own subscription). Using subscription auth to serve other
    users / a deployed product violates Anthropic's terms — use the
    ``anthropic`` provider with an API key for any shared/self-serve demo.
    """

    model_config = SettingsConfigDict(extra="ignore", populate_by_name=True)

    claude_executable: str = Field(
        default="claude", validation_alias="CLAUDE_CLI_PATH"
    )
    # Map the app's full model IDs to CLI aliases (sonnet/opus/haiku).
    fast_model: str = "haiku"
    smart_model: str = "sonnet"
    # Force subscription OAuth by removing ANTHROPIC_API_KEY from the CLI's
    # environment, so a stray key can't silently switch to metered billing.
    force_subscription: bool = True
    timeout_seconds: int = 180


class CodexSubscriptionConfig(BaseSettings):
    """ChatGPT Codex subscription provider configuration.

    Drives the headless ``codex exec`` CLI using the locally logged-in ChatGPT
    subscription instead of a metered ``OPENAI_API_KEY``.

    Same boundary as :class:`ClaudeSubscriptionConfig`: **local, single-operator
    use only**. Serving other users from a personal subscription violates the
    provider's terms — use a metered API key for anything shared.
    """

    model_config = SettingsConfigDict(extra="ignore", populate_by_name=True)

    codex_executable: str = Field(default="codex", validation_alias="CODEX_CLI_PATH")
    # Empty means "whatever the CLI is configured to use". Unlike the Claude CLI
    # there are no stable family aliases to map onto, so guessing a model id here
    # would break the moment the default changes upstream.
    fast_model: str = ""
    smart_model: str = ""
    # Force subscription auth by removing OPENAI_API_KEY from the CLI's
    # environment, so a stray key cannot silently switch to metered billing.
    force_subscription: bool = True
    timeout_seconds: int = 180


class OpenRouterConfig(BaseSettings):
    """OpenRouter API configuration."""

    model_config = SettingsConfigDict(extra="ignore", populate_by_name=True)

    api_key: str = Field(default="", validation_alias="OPENROUTER_API_KEY")
    site_url: str = Field(default="", validation_alias="OPENROUTER_SITE_URL")
    app_name: str = Field(default="quration", validation_alias="OPENROUTER_APP_NAME")
    # Model names for OpenRouter (Claude models via OpenRouter)
    fast_model: str = "anthropic/claude-haiku-4.5"  # Claude Haiku 4.5 (October 2025)
    smart_model: str = "anthropic/claude-sonnet-4.5"  # Claude Sonnet 4.5 (September 2025)
    max_tokens: int = 4096
    temperature: float = 0.0


class LLMConfig(BaseSettings):
    """LLM provider configuration."""

    model_config = SettingsConfigDict(extra="ignore", populate_by_name=True)

    provider: Literal[
        "anthropic",
        "openrouter",
        "aws_bedrock",
        "gcp_vertex",
        "claude_subscription",
        "codex_subscription",
    ] = "anthropic"
    anthropic: AnthropicConfig = Field(default_factory=AnthropicConfig)
    openrouter: OpenRouterConfig = Field(default_factory=OpenRouterConfig)
    aws_bedrock: AWSBedrockConfig = Field(default_factory=AWSBedrockConfig)
    gcp_vertex: GCPVertexConfig = Field(default_factory=GCPVertexConfig)
    claude_subscription: ClaudeSubscriptionConfig = Field(
        default_factory=ClaudeSubscriptionConfig
    )
    codex_subscription: CodexSubscriptionConfig = Field(
        default_factory=CodexSubscriptionConfig
    )


class GEOConfig(BaseSettings):
    """NCBI GEO/E-utilities configuration."""

    model_config = SettingsConfigDict(extra="ignore", populate_by_name=True)

    base_url: str = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
    tool: str = "quration"  # Tool name for NCBI identification (required)
    email: str = "quration@example.com"  # Email for NCBI (REQUIRED to avoid 403 errors)
    api_key: str = ""
    rate_limit: int = 3  # Requests per second (3 without API key, 10 with API key)

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str) -> str:
        """Validate email for NCBI API access.

        Email is REQUIRED by NCBI. Without it, you'll get 403 Forbidden errors.
        """
        if not v:
            raise ValueError("Email is required for NCBI GEO access")
        if v == "quration@example.com":
            import warnings
            warnings.warn(
                "Please set your email in config/config.yaml for NCBI GEO access. "
                "While 'quration@example.com' works for testing, NCBI requests you "
                "provide a real email address."
            )
        return v

    def get_effective_rate_limit(self) -> int:
        """Get effective rate limit based on API key presence."""
        return 10 if self.api_key else 3


class OntologyConfig(BaseSettings):
    """Ontology service configuration."""

    model_config = SettingsConfigDict(extra="ignore", populate_by_name=True)

    ols_base_url: str = "https://www.ebi.ac.uk/ols4/api"
    ontologies: list[str] = Field(
        default_factory=lambda: ["efo", "uberon", "cl", "doid", "mondo"]
    )
    bioportal_api_key: str = ""
    bioportal_base_url: str = "https://data.bioportal.org"


class ProteomicsConfig(BaseSettings):
    """Proteomics database configuration."""

    model_config = SettingsConfigDict(extra="ignore", populate_by_name=True)

    # PRIDE Archive API (primary source)
    pride_base_url: str = "https://www.ebi.ac.uk/pride/ws/archive/v2"
    pride_api_key: str = ""  # Optional API key for increased rate limits

    # ProteomeXchange Central
    px_base_url: str = "http://proteomecentral.proteomexchange.org/cgi/GetDataset"

    # MassIVE (UCSD)
    massive_base_url: str = "https://massive.ucsd.edu/ProteoSAFe/proxi/v0.1"

    # jPOST (Japan ProteOme STandard Repository)
    jpost_base_url: str = "https://repository.jpostdb.org/proxi"

    # PeptideAtlas
    peptide_atlas_base_url: str = "http://www.peptideatlas.org"

    # Rate limiting
    rate_limit: int = 10  # Requests per second

    # Tool identification
    tool: str = "quration"
    email: str = "quration@example.com"

    # Search and filtering options
    default_organisms: list[str] = Field(
        default_factory=lambda: ["Homo sapiens", "Mus musculus", "Rattus norvegicus"]
    )
    default_instruments: list[str] = Field(
        default_factory=lambda: [
            "Orbitrap",
            "Q Exactive",
            "TripleTOF",
            "timsTOF",
            "Fusion",
        ]
    )

    # Data download settings
    enable_data_download: bool = False  # Whether to download actual data files
    download_dir: Path = Path("./data/proteomics")
    max_file_size_mb: int = 1000  # Maximum file size to download


class DataSourcesConfig(BaseSettings):
    """External data sources configuration."""

    model_config = SettingsConfigDict(extra="ignore", populate_by_name=True)

    geo: GEOConfig = Field(default_factory=GEOConfig)
    ontologies: OntologyConfig = Field(default_factory=OntologyConfig)
    proteomics: ProteomicsConfig = Field(default_factory=ProteomicsConfig)


class ProcessingConfig(BaseSettings):
    """Processing configuration."""

    model_config = SettingsConfigDict(extra="ignore", populate_by_name=True)

    batch_size: int = 10
    parallel: bool = True
    max_workers: int = 4
    cache_enabled: bool = True
    cache_dir: Path = Path("./data/cache")
    cache_ttl_hours: int = 24


class OutputConfig(BaseSettings):
    """Output configuration."""

    model_config = SettingsConfigDict(extra="ignore", populate_by_name=True)

    output_dir: Path = Path("./data/output")
    formats: list[Literal["json", "jsonld", "parquet"]] = Field(
        default_factory=lambda: ["json", "jsonld", "parquet"]
    )
    pretty_print: bool = True
    include_provenance: bool = True


class ValidationConfig(BaseSettings):
    """Validation configuration."""

    model_config = SettingsConfigDict(extra="ignore", populate_by_name=True)

    level: Literal["strict", "normal", "permissive"] = "normal"
    required_fields: list[str] = Field(
        default_factory=lambda: ["organism", "tissue", "sample_type"]
    )
    validate_ontologies: bool = True
    checks: list[str] = Field(
        default_factory=lambda: ["completeness", "consistency", "ontology_compliance"]
    )


class LoggingConfig(BaseSettings):
    """Logging configuration."""

    model_config = SettingsConfigDict(extra="ignore", populate_by_name=True)

    level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    format: Literal["rich", "json"] = "rich"
    log_file: Path = Path("./logs/quration.log")


class CostTrackingConfig(BaseSettings):
    """Cost tracking configuration."""

    model_config = SettingsConfigDict(extra="ignore", populate_by_name=True)

    enabled: bool = True
    budget_alert_threshold: float = 100.0
    log_token_usage: bool = True


class RedisConfig(BaseSettings):
    """Redis cache configuration."""

    model_config = SettingsConfigDict(extra="ignore", populate_by_name=True)

    url: str = Field(default="redis://localhost:6379/0", validation_alias="REDIS_URL")
    host: str = Field(default="localhost", validation_alias="REDIS_HOST")
    port: int = Field(default=6379, validation_alias="REDIS_PORT")
    password: str = Field(default="", validation_alias="REDIS_PASSWORD")
    db: int = Field(default=0, validation_alias="REDIS_DB")
    enabled: bool = Field(default=True, validation_alias="REDIS_ENABLED")
    max_connections: int = Field(default=10, validation_alias="REDIS_MAX_CONNECTIONS")
    socket_timeout: int = Field(default=5, validation_alias="REDIS_SOCKET_TIMEOUT")
    socket_connect_timeout: int = Field(default=5, validation_alias="REDIS_SOCKET_CONNECT_TIMEOUT")
    key_prefix: str = Field(default="quration:", validation_alias="REDIS_KEY_PREFIX")
    # Per-domain cache TTLs (seconds), consumed by the cache services.
    ttl_conversation: int = Field(default=86400, validation_alias="REDIS_TTL_CONVERSATION")
    ttl_preference: int = Field(default=604800, validation_alias="REDIS_TTL_PREFERENCE")
    ttl_search: int = Field(default=3600, validation_alias="REDIS_TTL_SEARCH")
    ttl_session: int = Field(default=2592000, validation_alias="REDIS_TTL_SESSION")

    def get_connection_kwargs(self) -> dict:
        """Get connection kwargs for redis.ConnectionPool.

        Returns:
            dict: Connection parameters for Redis client
        """
        if self.url:
            # Use URL if provided
            return {"url": self.url}
        else:
            # Use component-based connection
            kwargs = {
                "host": self.host,
                "port": self.port,
                "db": self.db,
                "socket_timeout": self.socket_timeout,
                "socket_connect_timeout": self.socket_connect_timeout,
                "max_connections": self.max_connections,
            }
            if self.password:
                kwargs["password"] = self.password
            return kwargs


class InterpretationConfig(BaseSettings):
    """Interpretation layer configuration."""

    model_config = SettingsConfigDict(extra="ignore", populate_by_name=True)

    enabled: bool = True
    default_model: str = "claude-sonnet-4-5-20250929"  # Default model for interpretations
    fast_model: str = "claude-haiku-4-5-20251001"  # Fast model for simple lookups
    temperature: float = 0.2  # Low temperature for factual responses
    max_tool_calls: int = 10  # Maximum tool calls per interpretation
    confidence_threshold: float = 0.7  # Minimum confidence to include claim
    enable_tool_augmentation: bool = True  # Whether to use external tools
    enable_literature_search: bool = True  # Whether to search PubMed
    cache_ttl_seconds: int = 3600  # Cache TTL for interpretation results
    max_genes_per_lookup: int = 50  # Maximum genes to look up in one request
    parallel_tool_calls: bool = True  # Execute independent tool calls in parallel

    # Cost tracking
    cost_per_input_token: float = 0.000003  # Default Sonnet pricing
    cost_per_output_token: float = 0.000015  # Default Sonnet pricing
    budget_warning_usd: float = 1.0  # Warn if single interpretation exceeds this

    # Tool-specific settings
    uniprot_batch_size: int = 100  # UniProt batch lookup size
    kegg_rate_limit: int = 10  # KEGG requests per second
    reactome_rate_limit: int = 10  # Reactome requests per second
    string_score_threshold: float = 0.4  # STRING interaction score threshold
    pubmed_max_results: int = 5  # Maximum PubMed results per query


class NextflowConfig(BaseSettings):
    """Nextflow pipeline configuration."""

    model_config = SettingsConfigDict(extra="ignore", populate_by_name=True)

    nextflow_executable: str = "nextflow"  # Path to Nextflow executable
    nf_core_executable: str = "nf-core"  # Path to nf-core tools (optional)
    work_dir: Path = Path("./work")  # Default work directory for pipelines
    output_dir: Path = Path("./results")  # Default output directory
    cache_dir: Path | None = None  # Nextflow cache directory (uses default if None)

    # Execution profiles
    enable_conda: bool = False  # Enable Conda support
    enable_docker: bool = True  # Enable Docker support (default)
    enable_singularity: bool = False  # Enable Singularity support
    default_profile: str = "docker"  # Default execution profile

    # Execution tracking
    max_retries: int = 3  # Maximum execution retries on failure
    trace_enabled: bool = True  # Enable execution trace
    report_enabled: bool = True  # Enable execution reports
    timeline_enabled: bool = True  # Enable execution timeline
    dag_enabled: bool = True  # Enable DAG visualization

    # Resource defaults (can be overridden per-pipeline)
    default_max_cpus: int | None = None  # Default max CPUs
    default_max_memory_gb: int | None = None  # Default max memory in GB
    default_max_time_hours: int | None = None  # Default max time in hours

    @field_validator("work_dir", "output_dir")
    @classmethod
    def create_directory(cls, v: Path) -> Path:
        """Ensure directory exists."""
        v.mkdir(parents=True, exist_ok=True)
        return v


class QurationConfig(BaseSettings):
    """Main Quration configuration."""

    model_config = SettingsConfigDict(
        env_prefix="QURATION_",
        env_nested_delimiter="__",
        case_sensitive=False,
        extra="ignore",
        populate_by_name=True,
    )

    llm: LLMConfig = Field(default_factory=LLMConfig)
    data_sources: DataSourcesConfig = Field(default_factory=DataSourcesConfig)
    processing: ProcessingConfig = Field(default_factory=ProcessingConfig)
    output: OutputConfig = Field(default_factory=OutputConfig)
    validation: ValidationConfig = Field(default_factory=ValidationConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    cost_tracking: CostTrackingConfig = Field(default_factory=CostTrackingConfig)
    redis: RedisConfig = Field(default_factory=RedisConfig)
    observability: "ObservabilityConfig | None" = Field(  # type: ignore
        default=None,
        description="Observability configuration (LangFuse, metrics, structured logging)",
    )
    nextflow: NextflowConfig = Field(default_factory=NextflowConfig)
    interpretation: InterpretationConfig = Field(default_factory=InterpretationConfig)

    @classmethod
    def from_yaml(cls, config_path: str | Path) -> "QurationConfig":
        """Load configuration from YAML file.

        Args:
            config_path: Path to YAML configuration file

        Returns:
            QurationConfig instance
        """
        config_path = Path(config_path)
        if not config_path.exists():
            raise FileNotFoundError(f"Configuration file not found: {config_path}")

        with open(config_path) as f:
            config_dict = yaml.safe_load(f)

        return cls(**config_dict)

    @classmethod
    def load(cls, config_path: str | Path | None = None) -> "QurationConfig":
        """Load configuration from file or environment.

        Precedence (highest to lowest):
        1. Environment variables
        2. Config file (if provided)
        3. Default values

        Args:
            config_path: Optional path to YAML config file

        Returns:
            QurationConfig instance
        """
        if config_path:
            return cls.from_yaml(config_path)

        # Try to find config.yaml in common locations
        search_paths = [
            Path("config/config.yaml"),
            Path("config.yaml"),
            Path.home() / ".quration" / "config.yaml",
        ]

        for path in search_paths:
            if path.exists():
                return cls.from_yaml(path)

        # Fall back to environment variables and defaults
        return cls()


# Singleton instance
_config: QurationConfig | None = None


def get_config(config_path: str | Path | None = None, reload: bool = False) -> QurationConfig:
    """Get or create global configuration instance.

    Args:
        config_path: Optional path to configuration file
        reload: Force reload configuration

    Returns:
        QurationConfig instance
    """
    global _config

    if _config is None or reload:
        _config = QurationConfig.load(config_path)

        # Explicit env override for the LLM provider. A YAML config otherwise
        # wins over env vars (it's passed as init kwargs), so this lets you run
        # locally on your Claude Code subscription without editing — or risking
        # committing — config/config.yaml:
        #     QURATION_PROVIDER=claude_subscription <run backend / CLI>
        provider_override = os.environ.get("QURATION_PROVIDER")
        if provider_override:
            _config.llm.provider = provider_override

    return _config
