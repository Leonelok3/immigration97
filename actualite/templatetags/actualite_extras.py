from django import template

register = template.Library()


@register.filter
def country_label(country_code):
    """
    Convertit code pays -> label lisible
    """
    return {
        "US": "USA",
        "CA": "Canada",
        "DE": "Allemagne",
        "EU": "Europe",
        "IT": "Italie",
        "FR": "France",
    }.get(country_code, country_code)


@register.filter
def country_slug(country_code):
    """
    Convertit code pays -> slug URL
    """
    return {
        "US": "usa",
        "CA": "canada",
        "DE": "allemagne",
        "EU": "europe",
        "IT": "italie",
        "FR": "france",
    }.get(country_code, "")


@register.filter
def truncate_words(value, arg=30):
    """
    Tronque un texte à X mots (fallback utile)
    """
    try:
        words = value.split()
        return " ".join(words[:arg]) + ("…" if len(words) > arg else "")
    except Exception:
        return value
