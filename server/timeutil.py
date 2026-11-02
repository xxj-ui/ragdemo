"""时间格式化：库内 UTC，接口层统一转 +08:00（03 §4.5）。"""
from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

LOCAL_TZ = ZoneInfo("Asia/Shanghai")


def to_local_iso(value: datetime | None) -> str:
    if value is None:
        return ""
    if value.tzinfo is None:          # 理论上不会出现（列是 timestamptz）
        value = value.replace(tzinfo=ZoneInfo("UTC"))
    return value.astimezone(LOCAL_TZ).isoformat(timespec="seconds")
