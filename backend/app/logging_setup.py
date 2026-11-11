"""
Logging (shared helper, same file in backend and mcp-server).

- Always logs to the console (stdout). On Azure Functions / App Service this is collected by
  Application Insights (traces table) and the Log stream.
- If LOG_FILE is set (local runs), also writes a rotating file, e.g. logs/backend.log.
- LOG_FORMAT=json writes one JSON object per line (easy to query); "text" is human readable.
"""
from __future__ import annotations

import json
import logging
import os
import sys
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler

_STANDARD = set(vars(logging.LogRecord("", 0, "", 0, "", (), None)).keys()) | {"message", "asctime", "color_message"}


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        data = {
            "time": datetime.fromtimestamp(record.created, timezone.utc).isoformat(timespec="milliseconds"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        data.update({k: v for k, v in record.__dict__.items() if k not in _STANDARD and not k.startswith("_")})
        if record.exc_info:
            data["exception"] = self.formatException(record.exc_info)
        return json.dumps(data, ensure_ascii=False, default=str)


class TextFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        base = super().format(record)
        extra = {k: v for k, v in record.__dict__.items() if k not in _STANDARD and not k.startswith("_")}
        return base + ("  " + json.dumps(extra, ensure_ascii=False, default=str) if extra else "")


def setup_logging(level: str = "INFO", fmt: str = "text", log_file: str = "", max_mb: int = 10, backups: int = 10) -> None:
    root = logging.getLogger()
    if getattr(root, "_va_configured", False):
        return
    formatter = JsonFormatter() if fmt.lower() == "json" else TextFormatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    handlers: list[logging.Handler] = [logging.StreamHandler(sys.stdout)]
    if log_file:
        os.makedirs(os.path.dirname(os.path.abspath(log_file)), exist_ok=True)
        handlers.append(RotatingFileHandler(log_file, maxBytes=max_mb * 1024 * 1024, backupCount=backups, encoding="utf-8"))
    for h in handlers:
        h.setFormatter(formatter)
        root.addHandler(h)
    root.setLevel(level.upper())
    for noisy in ("httpx", "httpcore", "httpx2", "openai._base_client", "mcp.client"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
    root._va_configured = True  # type: ignore[attr-defined]
