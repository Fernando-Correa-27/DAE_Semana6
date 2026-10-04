"""
Decoradores personalizados para la aplicacion movies.
"""

from functools import wraps

from django.conf import settings
from django.shortcuts import redirect


def user_not_authenticated(redirect_url=None):
    """
    Decorador que redirige a usuarios ya autenticados.

    Si un usuario ya inicio sesion, se le redirige a la pagina
    de inicio en lugar de permitirle acceder a las vistas de
    login/registro (evita registros duplicados).

    Funciona tanto con vistas function-based como class-based.
    Para CBV, se usa como @method_decorator en el dispatch.
    """
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            if request.user.is_authenticated:
                target = redirect_url or settings.LOGIN_REDIRECT_URL
                return redirect(target)
            return view_func(request, *args, **kwargs)
        return _wrapped_view
    return decorator
