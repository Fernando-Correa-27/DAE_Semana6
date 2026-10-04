"""
Decoradores personalizados para la aplicacion movies.
"""

from django.conf import settings
from django.http import HttpResponseForbidden


def user_not_authenticated(redirect_url=None):
    """
    Decorador que redirige a usuarios ya autenticados.

    Si un usuario ya inicio sesion, se le redirige a la pagina
    de inicio en lugar de permitirle acceder a las vistas de
    login/registro (evita registros duplicados).
    """
    def decorator(view_func):
        def _wrapped_view(request, *args, **kwargs):
            if request.user.is_authenticated:
                target = redirect_url or settings.LOGIN_REDIRECT_URL
                from django.shortcuts import redirect
                return redirect(target)
            return view_func(request, *args, **kwargs)
        return _wrapped_view
    return decorator
