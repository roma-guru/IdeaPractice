import os

from django import template

register = template.Library()


@register.filter
def get_item(dictionary, key):
    """Dict lookup: {{ my_dict|get_item:key }}"""
    return dictionary.get(key)


@register.filter
def basename(value):
    """Return just the filename portion of a path."""
    return os.path.basename(str(value))


@register.filter
def format_duration(value):
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
