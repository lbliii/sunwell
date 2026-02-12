"""Settings-related form schemas."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ProviderForm:
    """Provider configuration form.

    Fields:
        provider: LLM provider (ollama/anthropic/openai)
        ollama_base: Ollama base URL (optional)
        ollama_model: Ollama model name (optional)
    """

    provider: str
    ollama_base: str = ""
    ollama_model: str = ""


@dataclass(frozen=True, slots=True)
class PreferencesForm:
    """Studio preferences form.

    Fields:
        theme: UI theme (dark/light/auto, defaults to dark)
        auto_save: Enable auto-save (defaults to False)
        show_token_counts: Show token counts in UI (defaults to False)
    """

    theme: str = "dark"
    auto_save: bool = False
    show_token_counts: bool = False


@dataclass(frozen=True, slots=True)
class APIKeysForm:
    """API keys configuration form.

    Fields:
        anthropic_api_key: Anthropic API key (optional)
        openai_api_key: OpenAI API key (optional)
    """

    anthropic_api_key: str = ""
    openai_api_key: str = ""
