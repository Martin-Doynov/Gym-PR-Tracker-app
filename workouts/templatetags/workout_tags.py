from django import template

register = template.Library()

@register.filter
def pad2(value):
    """Zero-pad a number to 2 digits."""
    try:
        return f"{int(value):02d}"
    except (ValueError, TypeError):
        return value