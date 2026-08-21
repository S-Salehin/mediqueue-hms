import json
import logging
from datetime import datetime, timezone


class JSONFormatter(logging.Formatter):
    def format(self, record):
        payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        request_id = getattr(record, "request_id", None)
        if request_id:
            payload["request_id"] = str(request_id)
        for field in ("event", "exception_class", "view"):
            value = getattr(record, field, None)
            if value:
                payload[field] = str(value)
        return json.dumps(payload, ensure_ascii=True)
