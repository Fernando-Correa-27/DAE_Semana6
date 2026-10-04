"""
Custom template tags for the movies app.
"""

from django import template

register = template.Library()


@register.filter
def get_item(dictionary, key):
    """Get an item from a dictionary using a key.

    Returns ``None`` for anything that is not dict-like instead of raising.

    A template that uses the filter on a context variable the view did not
    provide gets the empty string, not ``None`` (Django substitutes
    ``string_if_invalid`` and then *keeps applying the filters*), so
    ``{% with form=movie_rating_forms|get_item:movie.id %}`` on a listing that
    does not build the per-movie forms used to take the whole page down with
    ``AttributeError: 'str' object has no attribute 'get'``. A filter that can
    kill a page is worse than one that returns nothing.
    """
    if not hasattr(dictionary, 'get'):
        return None
    return dictionary.get(key)
