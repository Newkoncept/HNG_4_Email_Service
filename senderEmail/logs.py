import logging
import os
import sys
from pathlib import Path



BASE_DIR = Path(__file__).resolve().parent.parent 
if str(BASE_DIR) not in sys.path:
    sys.path.append(str(BASE_DIR))

# ---------- Logging setup ----------
class _PayloadFilter(logging.Filter):
    """
    Injects request_id, notification_id, attempt into every record if present.
    Call set_context(...) before logging inside your callback.
    """
    def __init__(self):
        super().__init__()
        self._ctx = {"request_id": "-", "notification_id": "-", "attempt": "-"}

    def set_context(self, request_id=None, notification_id=None, attempt=None):
        if request_id is not None:
            self._ctx["request_id"] = request_id
        if notification_id is not None:
            self._ctx["notification_id"] = notification_id
        if attempt is not None:
            self._ctx["attempt"] = attempt

    def filter(self, record):
        record.request_id = self._ctx.get("request_id", "-")
        record.notification_id = self._ctx.get("notification_id", "-")
        record.attempt = self._ctx.get("attempt", "-")
        return True