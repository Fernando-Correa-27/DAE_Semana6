"""
Registro compartido de claves de cache para los servicios de ``movies``.

Varios servicios memoizan *ids* de peliculas bajo claves que no dependen del
contenido de la base de datos (``movie_service``: home y listas por genero;
``search_service``: resultados de busqueda y de filtrado). Para que una
escritura pueda invalidarlas hace falta recordar las claves concretas que se
han generado, y eso es exactamente lo que hace este modulo:

* ``cache.delete_pattern()`` no existe en el backend configurado.
  ``settings.CACHES`` usa ``LocMemCache`` y ``delete_pattern`` es una extension
  de ``django-redis``, no de Django (comprobado contra el Django instalado:
  ni ``BaseCache`` ni ``LocMemCache`` la exponen).
* Aunque existiera, un patron nunca podria acotarse a un subconjunto logico:
  los parametros van hasheados en la clave, asi que "genre:Action:*" o
  "search:*" no se pueden reconstruir desde la clave almacenada. Y hay
  parametros que ni siquiera conoce el invalidador (la ``limit`` de
  ``get_genre_recommendations``, el texto de una busqueda arbitraria).

Por eso el registro es *explicitito*: cada servicio registra las claves que
genera, agrupadas por un "scope" logico (``search``, ``filter``, ``home_movies``,
``genre:<nombre>``, ...) y la invalidacion borra exactamente las claves de los
scopes afectados. El estado es compartido por todos los servicios, con un tope
de claves vivas para que no crezca sin limite (una clave expulsada del registro
sigue acotada por su TTL).

Este modulo no toca ``django.core.cache``: cada servicio borra sus propias
claves usando su propio ``cache``, igual que hacia antes de extraer el registro.

Los nombres con prefijo ``_`` son la API interna compartida por los servicios
(``movie_service`` los reexporta) y no se usan fuera de ``movies/services``.
"""

import hashlib
import logging
import threading
from collections.abc import Iterable

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Estado del registro
# ---------------------------------------------------------------------------

# Upper bound for the registry so it cannot grow without limit. A key evicted
# from the registry is still bounded by its TTL, so this only needs to be
# comfortably larger than the number of live (scope, parameters) pairs.
_MAX_TRACKED_KEYS = 2048

_registry_lock = threading.RLock()
_tracked_keys: dict[str, str] = {}      # cache key -> scope (insertion ordered)
_scope_keys: dict[str, set[str]] = {}   # scope -> {cache key}


# ---------------------------------------------------------------------------
# Claves deterministas
# ---------------------------------------------------------------------------

def make_cache_key(namespace: str, prefix: str, **kwargs) -> str:
    """Build a deterministic ``<namespace>:<md5>`` cache key.

    The key depends only on the parameters, never on the data in the database,
    so it is stable across processes but *not* self-invalidating: registering
    it (see ``_track_key``) is what makes a write able to drop it.

    Args:
        namespace: Prefijo del backend, p. ej. ``'movies'`` o ``'search'``.
        prefix: Sub-clave logica, p. ej. ``'home_movies'`` o ``'search'``.
        **kwargs: Parametros de la consulta; se ordenan para que el orden de
            las llamadas no cambie la clave.
    """
    key_data = f"{prefix}:{'.'.join(f'{k}={v}' for k, v in sorted(kwargs.items()))}"
    return f"{namespace}:{hashlib.md5(key_data.encode()).hexdigest()}"


# ---------------------------------------------------------------------------
# Registro / consulta de claves
# ---------------------------------------------------------------------------

def _track_key(scope: str, key: str) -> None:
    """Remember a generated key so a later write can delete it."""
    if key in _tracked_keys:
        return  # fast path: already tracked, dict read is atomic under the GIL
    with _registry_lock:
        if key in _tracked_keys:
            return
        _tracked_keys[key] = scope
        _scope_keys.setdefault(scope, set()).add(key)
        while len(_tracked_keys) > _MAX_TRACKED_KEYS:
            oldest = next(iter(_tracked_keys))
            oldest_scope = _tracked_keys.pop(oldest)
            scope_keys = _scope_keys.get(oldest_scope)
            if scope_keys is not None:
                scope_keys.discard(oldest)
                if not scope_keys:
                    del _scope_keys[oldest_scope]


def _take_scope_keys(scopes: Iterable[str]) -> list[str]:
    """Detach and return every tracked key belonging to ``scopes``.

    "Detach" (pop) y no "read": una clave invalidada ya no necesita seguir en el
    registro, asi que a partir de aqui solo se rastrean las generadas despues.
    """
    keys: list[str] = []
    with _registry_lock:
        for scope in scopes:
            for key in _scope_keys.pop(scope, set()):
                _tracked_keys.pop(key, None)
                keys.append(key)
    return keys


def tracked_keys_for(scopes: Iterable[str] | None = None) -> set[str]:
    """Read-only snapshot of the tracked keys (for tests/diagnostics)."""
    with _registry_lock:
        if scopes is None:
            return set(_tracked_keys)
        wanted = set()
        for scope in scopes:
            wanted |= _scope_keys.get(scope, set())
        return wanted
