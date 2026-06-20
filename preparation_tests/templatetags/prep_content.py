import html
import re

from django import template
from django.utils.html import conditional_escape, strip_tags
from django.utils.safestring import mark_safe


register = template.Library()


_MOJIBAKE_MARKERS = ("Ã", "Â", "â€™", "â€œ", "â€", "�")


def _fix_mojibake(value):
    text = "" if value is None else str(value)
    if not any(marker in text for marker in _MOJIBAKE_MARKERS):
        return text

    try:
        fixed = text.encode("latin1").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        fixed = text

    return (
        fixed.replace("Â ", " ")
        .replace("Â", "")
        .replace("â€™", "'")
        .replace("â€œ", '"')
        .replace("â€", '"')
        .replace("â€“", "-")
        .replace("â€”", "-")
        .replace("â€¦", "...")
    )


def _decode(value):
    return html.unescape(_fix_mojibake(value))


@register.filter
def prep_plain(value):
    """Render imported course text as readable plain text."""
    text = _decode(value)
    text = re.sub(r"(?i)<br\s*/?>", "\n", text)
    text = re.sub(r"(?i)</p\s*>", "\n", text)
    text = strip_tags(text)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    escaped = conditional_escape(text).replace("\n", "<br>")
    return mark_safe(escaped)


@register.filter
def prep_clean(value):
    """Return decoded plain text for attributes and JavaScript data."""
    text = _decode(value)
    text = re.sub(r"(?i)<br\s*/?>", "\n", text)
    text = re.sub(r"(?i)</p\s*>", "\n", text)
    text = strip_tags(text)
    return re.sub(r"\s+", " ", text).strip()


@register.filter
def prep_rich(value):
    """Render trusted lesson HTML after fixing common encoding damage."""
    text = _decode(value)
    return mark_safe(text)
