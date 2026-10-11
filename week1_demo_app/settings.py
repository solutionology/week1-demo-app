"""Load shared defaults, overridden by deployment environment or local .env."""

import os
from dataclasses import dataclass, field
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:
    import tomli as tomllib
from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parent


@dataclass(frozen=True)
class Settings:
    provider: str
    base_url: str
    model: str
    api_key: str = field(repr=False)
    system_prompt: str = ""
    user_prompt: str = ""
    timeout: float = 120
    web_search_enabled: bool = False
    search_api_key: str = field(default="", repr=False)
    search_max_results: int = 5
    search_timeout: float = 30


def load_settings():
    with (ROOT / "config.toml").open("rb") as handle:
        config = tomllib.load(handle)
    env = {**dotenv_values(ROOT / ".env"), **os.environ}
    flag = str(env.get("LOCAL", config["local"])).strip().lower()
    if flag not in {"true", "false", "1", "0"}:
        raise ValueError("LOCAL must be true or false.")
    provider = "ollama" if flag in {"true", "1"} else "openrouter"
    section = config[provider]
    prefix = provider.upper()
    timeout = float(env.get("REQUEST_TIMEOUT", config["request_timeout"]))
    if not 1 <= timeout <= 600:
        raise ValueError("REQUEST_TIMEOUT must be between 1 and 600 seconds.")
    search = config.get("web_search", {})
    search_flag = (
        str(env.get("WEB_SEARCH_ENABLED", search.get("enabled", True))).strip().lower()
    )
    if search_flag not in {"true", "false", "1", "0"}:
        raise ValueError("WEB_SEARCH_ENABLED must be true or false.")
    search_max_results = int(
        env.get("SEARCH_MAX_RESULTS", search.get("max_results", 5))
    )
    search_timeout = float(env.get("SEARCH_TIMEOUT", search.get("timeout", 30)))
    if not 1 <= search_max_results <= 10 or not 1 <= search_timeout <= 120:
        raise ValueError(
            "Search results must be 1–10 and search timeout must be 1–120 seconds."
        )
    return Settings(
        provider=provider,
        base_url=env.get(f"{prefix}_BASE_URL", section["base_url"]).strip().rstrip("/"),
        model=(
            env.get("MODEL_NAME") or env.get(f"{prefix}_MODEL") or section["model_name"]
        ).strip(),
        api_key=(env.get(section["api_key_env"]) or "").strip(),
        system_prompt=env.get("SYSTEM_PROMPT", config["prompts"]["system_prompt"]),
        user_prompt=env.get("USER_PROMPT", config["prompts"]["user_prompt"]),
        timeout=timeout,
        web_search_enabled=search_flag in {"true", "1"},
        search_api_key=(env.get("TAVILY_API_KEY") or "").strip(),
        search_max_results=search_max_results,
        search_timeout=search_timeout,
    )
