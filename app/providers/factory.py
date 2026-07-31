from app.core.config import Settings
from app.providers.email_analysis import EmailAnalyzer, FakeEmailAnalyzer
from app.providers.openrouter_email_analysis import OpenRouterEmailAnalyzer


class UnsupportedEmailAnalyzerError(ValueError):
    """Raised when configuration selects an unknown analyzer provider."""


def build_email_analyzer(settings: Settings) -> EmailAnalyzer:
    provider = settings.ai_provider.strip().lower()
    if provider == "fake":
        return FakeEmailAnalyzer()
    if provider == "openrouter":
        if settings.ai_api_key is None:
            raise UnsupportedEmailAnalyzerError(
                "AI_API_KEY is required for the OpenRouter provider."
            )
        return OpenRouterEmailAnalyzer(
            api_key=settings.ai_api_key.get_secret_value(),
            model=settings.ai_model,
            base_url=settings.ai_base_url,
            timeout_seconds=settings.ai_timeout_seconds,
        )
    raise UnsupportedEmailAnalyzerError(
        f"Unsupported email analyzer provider: {settings.ai_provider}"
    )
