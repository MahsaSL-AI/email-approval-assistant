from typing import Protocol

from app.domain.email import EmailAnalysisResult, InboundEmail


class EmailAnalyzer(Protocol):
    def analyze(self, email: InboundEmail) -> EmailAnalysisResult: ...


class FakeEmailAnalyzer:
    """Deterministic offline analyzer for tests and the first walking skeleton."""

    def analyze(self, email: InboundEmail) -> EmailAnalysisResult:
        language = "fa" if _contains_persian(email.body_text) else "en"
        subject = email.subject or "No subject"
        return EmailAnalysisResult(
            summary=f"Synthetic summary for: {subject}",
            category="other",
            priority="normal",
            language=language,
            sentiment="neutral",
            confidence=1.0,
            suggested_reply=(
                "از پیام شما متشکریم. درخواست شما بررسی و پیگیری خواهد شد."
                if language == "fa"
                else "Thank you for your message. We will review and follow up."
            ),
        )


def _contains_persian(value: str) -> bool:
    return any("\u0600" <= character <= "\u06ff" for character in value)
