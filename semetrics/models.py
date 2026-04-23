from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional
import uuid


@dataclass
class Event:
    event_name: str
    client_ts: datetime
    user_id: Optional[str] = None
    anonymous_id: Optional[str] = None
    session_id: Optional[str] = None
    platform: str = "python"
    sdk_version: str = "0.1.0"
    properties: Optional[dict[str, Any]] = None
    db_id: Optional[int] = None  # SQLite rowid, None для in-memory событий

    def to_dict(self) -> dict:
        return {
            "event_name": self.event_name,
            "user_id": self.user_id,
            "anonymous_id": self.anonymous_id,
            "session_id": self.session_id,
            "platform": self.platform,
            "sdk_version": self.sdk_version,
            "client_ts": self.client_ts.isoformat(),
            "properties": self.properties or {},
        }
