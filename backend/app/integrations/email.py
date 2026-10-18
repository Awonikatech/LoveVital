"""Email backend abstraction. `console` logs emails (and they are recorded in `notifications`);
`smtp` sends via any SMTP relay (SES, SendGrid, Mailgun, Postfix...)."""
import logging
import smtplib
from email.message import EmailMessage
from typing import Protocol

from app.core.config import settings

log = logging.getLogger("app.email")


class EmailBackend(Protocol):
    def send(self, to: str, subject: str, text: str, html: str | None = None) -> None: ...


class ConsoleEmailBackend:
    outbox: list[dict] = []

    def send(self, to: str, subject: str, text: str, html: str | None = None) -> None:
        self.outbox.append({"to": to, "subject": subject, "text": text})
        del self.outbox[:-200]
        log.info("EMAIL to=%s subject=%r\n%s", to, subject, text)


class SmtpEmailBackend:
    def send(self, to: str, subject: str, text: str, html: str | None = None) -> None:
        msg = EmailMessage()
        msg["From"] = settings.EMAIL_FROM
        msg["To"] = to
        msg["Subject"] = subject
        msg.set_content(text)
        if html:
            msg.add_alternative(html, subtype="html")
        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=15) as s:
            if settings.SMTP_USE_TLS:
                s.starttls()
            if settings.SMTP_USER:
                s.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            s.send_message(msg)


_backend: EmailBackend | None = None


def get_email_backend() -> EmailBackend:
    global _backend
    if _backend is None:
        _backend = SmtpEmailBackend() if settings.EMAIL_BACKEND == "smtp" else ConsoleEmailBackend()
    return _backend
