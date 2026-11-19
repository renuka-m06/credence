"""Configuration settings for Credence."""

import os
from dataclasses import dataclass, field
from pathlib import Path

# Optional dotenv loading if python-dotenv is installed
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

BASE_DIR = Path(__file__).resolve().parent


@dataclass(frozen=True)
class AccessTierCaps:
    """Confidence caps per access tier as dictated by AGENTS.md."""
    FULL_TEXT: float = 0.9
    ABSTRACT_ONLY: float = 0.6
    METADATA_ONLY: float = 0.2
    INACCESSIBLE: float = 0.0
    NOT_FOUND: float = 0.0


@dataclass
class Settings:
    """Credence global configuration settings."""
    # Base directories
    base_dir: Path = BASE_DIR
    cache_dir: Path = field(
        default_factory=lambda: Path(os.getenv("CREDENCE_CACHE_DIR", str(BASE_DIR / ".cache" / "credence")))
    )
    db_path: Path = field(
        default_factory=lambda: Path(os.getenv("CREDENCE_DB_PATH", str(BASE_DIR / "credence.db")))
    )
    demo_data_dir: Path = field(
        default_factory=lambda: BASE_DIR / "data" / "demo"
    )

    # API Keys
    gemini_api_key: str = field(
        default_factory=lambda: os.getenv("GEMINI_API_KEY", "")
    )
    openalex_api_key: str = field(
        default_factory=lambda: os.getenv("OPENALEX_API_KEY", "")
    )
    semantic_scholar_api_key: str = field(
        default_factory=lambda: os.getenv("SEMANTIC_SCHOLAR_API_KEY", "")
    )
    crossref_mailto: str = field(
        default_factory=lambda: os.getenv("CROSSREF_MAILTO", "researcher@example.com")
    )
    unpaywall_email: str = field(
        default_factory=lambda: os.getenv("UNPAYWALL_EMAIL", "researcher@example.com")
    )
    ollama_host: str = field(
        default_factory=lambda: os.getenv("OLLAMA_HOST", "http://localhost:11434")
    )

    # Access tier confidence caps
    tier_caps: AccessTierCaps = field(default_factory=AccessTierCaps)

    # Verification penalties (used in confidence computation)
    unverified_slot_penalty: float = 0.15
    pass_disagreement_penalty: float = 0.20


# Singleton default settings instance
settings = Settings()
