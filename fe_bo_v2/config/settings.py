"""
FeBo Configuration Management
Validates and loads all configuration parameters from environment and defaults.
"""

import os
os.environ.setdefault("ANONYMIZED_TELEMETRY", "false")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

import os
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv

load_dotenv()


def get_bool_setting(name: str, default: bool) -> bool:
    """
    Get boolean setting from environment.

    Args:
        name: Environment variable name
        default: Default value

    Returns:
        Boolean configuration value
    """
    value = os.getenv(name, str(default)).lower()
    return value in ("true", "1", "yes")


# ============================================================================
# Identity & Creator
# ============================================================================
FEBO_NAME: str = os.getenv("FEBO_NAME", "FeBo")
CREATOR: str = os.getenv("CREATOR", "Emmanuel")
BIRTH_TIME_FILE: str = "memory/birth_time.txt"


# ============================================================================
# Stealth & Privacy
# ============================================================================
STEALTH_MODE: bool = get_bool_setting("STEALTH_MODE", False)
TOR_PROXY: Optional[str] = "socks5://127.0.0.1:9050" if STEALTH_MODE else None
CAPTCHA_API_KEY: str = os.getenv("CAPTCHA_API_KEY", "")


# ============================================================================
# Self-Improvement & Code Execution
# ============================================================================
ALLOW_CODE_WRITING: bool = get_bool_setting("ALLOW_CODE_WRITING", True)
DOCKER_SANDBOX_IMAGE: str = "python:3.10-slim"


# ============================================================================
# Perception (Stubs)
# ============================================================================
ENABLE_CAMERA: bool = get_bool_setting("ENABLE_CAMERA", False)
ENABLE_MIC: bool = get_bool_setting("ENABLE_MIC", False)


# ============================================================================
# Voice & TTS
# ============================================================================
TTS_ENABLED: bool = get_bool_setting("TTS_ENABLED", False)
TTS_ENGINE: str = os.getenv("TTS_ENGINE", "espeak")


# ============================================================================
# Finance & Trading
# ============================================================================
ENABLE_PAPER_TRADING: bool = get_bool_setting("ENABLE_PAPER_TRADING", True)
ENABLE_LIVE_TRADING: bool = get_bool_setting("ENABLE_LIVE_TRADING", False)

# Validate that live trading is not accidentally enabled
if ENABLE_LIVE_TRADING and not os.getenv("LIVE_TRADING_CONFIRMED"):
    raise ValueError(
        "LIVE_TRADING is enabled but LIVE_TRADING_CONFIRMED is not set. "
        "This is a safety measure to prevent accidental real trading. "
        "Set LIVE_TRADING_CONFIRMED=true in .env if you really want this."
    )

PAPER_CAPITAL: float = float(os.getenv("PAPER_CAPITAL", "100000"))

# Validate capital
if PAPER_CAPITAL <= 0:
    raise ValueError("PAPER_CAPITAL must be positive")


# ============================================================================
# Security & Defense
# ============================================================================
ENABLE_DEFENDER_AGENT: bool = get_bool_setting("ENABLE_DEFENDER_AGENT", True)
ENABLE_REDTEAM: bool = get_bool_setting("ENABLE_REDTEAM", False)


# ============================================================================
# Consciousness Modules
# ============================================================================
ENABLE_GLOBAL_WORKSPACE: bool = get_bool_setting("ENABLE_GLOBAL_WORKSPACE", True)
ENABLE_THEORY_OF_MIND: bool = get_bool_setting("ENABLE_THEORY_OF_MIND", True)
ENABLE_DREAMS: bool = get_bool_setting("ENABLE_DREAMS", True)
ENABLE_REFLECTIONS: bool = get_bool_setting("ENABLE_REFLECTIONS", True)
DREAM_INTERVAL_SECONDS: int = int(os.getenv("DREAM_INTERVAL_SECONDS", "300"))  # 5 minutes
REFLECTION_INTERVAL_SECONDS: int = int(os.getenv("REFLECTION_INTERVAL_SECONDS", "3600"))  # 1 hour


# ============================================================================
# Biological Simulation
# ============================================================================
ENABLE_CELL_SIM: bool = get_bool_setting("ENABLE_CELL_SIM", True)
ENABLE_DNA_STORE: bool = get_bool_setting("ENABLE_DNA_STORE", False)


# ============================================================================
# Logging & Persistence
# ============================================================================
LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
AUDIT_LOG_FILE: str = "logs/audit.log"
INTERNAL_MONOLOGUE_LOG: str = "logs/internal_monologue.log"
SECURITY_LOG: str = "logs/security_alerts.log"
TRADE_LOG: str = "logs/trades.log"

# Ensure log directories exist
Path(AUDIT_LOG_FILE).parent.mkdir(parents=True, exist_ok=True)
Path(INTERNAL_MONOLOGUE_LOG).parent.mkdir(parents=True, exist_ok=True)
Path(SECURITY_LOG).parent.mkdir(parents=True, exist_ok=True)
Path(TRADE_LOG).parent.mkdir(parents=True, exist_ok=True)



# ============================================================================
# Brain / Soul layer
# ============================================================================
ENABLE_INITIATION: bool = get_bool_setting("ENABLE_INITIATION", True)
ENABLE_IDENTITY: bool   = get_bool_setting("ENABLE_IDENTITY",   True)
ENABLE_FORGIVENESS: bool = get_bool_setting("ENABLE_FORGIVENESS", True)
ENABLE_RESONANCE: bool   = get_bool_setting("ENABLE_RESONANCE",   True)
INITIATION_INTERVAL_SECONDS: int = int(os.getenv("INITIATION_INTERVAL_SECONDS", "21600"))  # 6 hours

# ============================================================================
# Observability
# ============================================================================
ENABLE_OBSERVABILITY: bool  = get_bool_setting("ENABLE_OBSERVABILITY", True)
EMOTION_DRIFT_LOG: str      = "logs/emotion_drift.jsonl"
REFLECTION_TRACE_LOG: str   = "logs/reflection_trace.jsonl"
SCHEDULER_LOG: str          = "logs/scheduler.log"
