"""Model selection. Any LangChain chat model works; Gemini and Groq are wired by default."""

from __future__ import annotations

import os

DEFAULT_MODELS = {
    "google_genai": "gemini-3.6-flash",
    "groq": "openai/gpt-oss-120b",
}
API_KEY_VARS = {
    "google_genai": ("GEMINI_API_KEY", "GOOGLE_API_KEY"),
    "groq": ("GROQ_API_KEY",),
}
ALIASES = {"gemini": "google_genai", "google": "google_genai"}


class ConfigError(Exception):
    pass


def _api_key(provider: str) -> str | None:
    for var in API_KEY_VARS[provider]:
        if os.environ.get(var):
            return os.environ[var]
    return None


def resolve_model_spec(spec: str | None = None) -> tuple[str, str]:
    """Return (provider, model) from "provider:model", a bare provider, or the keys present."""
    spec = spec or os.environ.get("PR_OBSERVER_MODEL")
    if not spec:
        for provider, model in DEFAULT_MODELS.items():
            if _api_key(provider):
                return provider, model
        raise ConfigError(
            "No API key found. Set GEMINI_API_KEY (https://aistudio.google.com/apikey) "
            "or GROQ_API_KEY (https://console.groq.com/keys) in your environment or .env file."
        )

    provider, _, model = spec.partition(":")
    provider = ALIASES.get(provider, provider)
    if provider not in DEFAULT_MODELS:
        raise ConfigError(
            f"Unknown provider '{provider}'. Use one of: {', '.join(DEFAULT_MODELS)} "
            '(format: "provider:model").'
        )
    return provider, model or DEFAULT_MODELS[provider]


def build_model(provider: str, model: str):
    from langchain.chat_models import init_chat_model

    key = _api_key(provider)
    if not key:
        raise ConfigError(f"{' or '.join(API_KEY_VARS[provider])} is not set.")
    # Current Gemini models use fixed sampling and warn when a temperature is passed.
    sampling = {} if provider == "google_genai" else {"temperature": 0}
    return init_chat_model(model, model_provider=provider, api_key=key, max_retries=3, **sampling)
