"""Logging with a redaction filter so secrets never reach log output."""
import logging
import re

from app.core.config import settings

_PATTERNS = [
    (re.compile(r"(?i)(password|passwd|secret|token|authorization|signature|api[_-]?key)(['\"]?\s*[:=]\s*['\"]?)([^\s'\",}&]+)"), r"\1\2***"),
    (re.compile(r"(?i)([?&](?:key|token)=)[^&\s\"]+"), r"\1***"),  # capability tokens in URLs
    (re.compile(r"(?i)bearer\s+[a-z0-9\-_\.]+"), "Bearer ***"),
    (re.compile(r"\b(?:\d[ -]?){13,19}\b"), "[redacted-number]"),
]


def redact(value: str) -> str:
    for pat, repl in _PATTERNS:
        value = pat.sub(repl, value)
    return value


class RedactFilter(logging.Filter):
    """Redacts the message template and any string arguments in place (keeps record.args intact,
    which formatters such as uvicorn's AccessFormatter rely on)."""

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = redact(record.msg)
        if isinstance(record.args, tuple):
            record.args = tuple(redact(a) if isinstance(a, str) else a for a in record.args)
        elif isinstance(record.args, dict):
            record.args = {k: redact(v) if isinstance(v, str) else v for k, v in record.args.items()}
        return True


def configure_logging() -> None:
    root = logging.getLogger()
    if getattr(root, "_swk_configured", False):
        return
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s [%(name)s] %(message)s"))
    handler.addFilter(RedactFilter())
    root.handlers = [handler]
    root.setLevel(logging.DEBUG if settings.DEBUG else logging.INFO)
    for name in ("uvicorn.access", "uvicorn.error"):
        logging.getLogger(name).addFilter(RedactFilter())
    root._swk_configured = True  # type: ignore[attr-defined]
