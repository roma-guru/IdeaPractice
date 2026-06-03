from __future__ import annotations

import os
from datetime import timedelta
from typing import Any

from django import template

register = template.Library()


@register.filter
def get_item(dictionary: dict[str, Any], key: str) -> Any:
    """Dict lookup: {{ my_dict|get_item:key }}"""
    return dictionary.get(key)


@register.filter
def basename(value: Any) -> str:
    """Return just the filename portion of a path."""
    return os.path.basename(str(value))


@register.filter
def format_duration(value: timedelta | None) -> str:
    if value is None:
        return "—"
    total_seconds = int(value.total_seconds())
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    seconds = total_seconds % 60
    if hours:
        return f"{hours}h {minutes:02d}m"
    if minutes:
        return f"{minutes}m {seconds:02d}s"
    return f"{seconds}s"
