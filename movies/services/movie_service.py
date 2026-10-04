"""
Servicios de peliculas: logica para consultas de peliculas.

Delegate operations to movie selectors for read/query operations.
Includes caching for read-heavy operations plus write-time invalidation.
"""

import logging
from collections.abc import Iterable
from typing import TYPE_CHECKING

from django.core.cache import cache
from django.db.models import Avg

from movies.selectors.movie_selector import (
    get_movie_recommendations,
    get_movies_by_genre_with_rating,
)
from movies.services.cache_registry import (
    _MAX_TRACKED_KEYS,        # noqa: F401  re-exported: pre-existing contract
    _registry_lock,           # noqa: F401  re-exported: pre-existing contract
    _scope_keys,              # noqa: F401  re-exported: pre-existing contract
    _take_scope_keys,
    _tracked_keys,            # noqa: F401  re-exported: pre-existing contract
    _track_key,
    make_cache_key,
)

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from movies.models import Movie

# Cache TTLs in seconds
CACHE_TTL_SHORT = 300      # 5 minutes
CACHE_TTL_MEDIUM = 600     # 10 minutes

# ---------------------------------------------------------------------------
# Cache key bookkeeping
# ---------------------------------------------------------------------------
# The read functions below memoise the *list of movie ids* under md5-hashed
# keys ("movies:<md5>"). Two facts drive the invalidation design:
#
# 1. ``cache.delete_pattern()`` does not exist on the configured backend.
#    ``settings.CACHES`` uses ``LocMemCache`` and ``delete_pattern`` is a
#    ``django-redis`` extension, not part of Django core (verified against the
#    installed Django: neither ``BaseCache`` nor ``LocMemCache`` expose it).
# 2. Even on a backend that does implement it, a pattern could never be scoped
#    to one genre: the genre name is hashed away, so "genre:Action:*" cannot be
#    reconstructed from the stored key.
#
# ``genre_recommendations`` is additionally keyed by ``limit``, so no finite set
# of candidate keys can be built up front either. The module therefore keeps a
# registry of the concrete key strings it has generated, grouped by logical
# scope, and invalidation deletes exactly those strings.
#
# That registry now lives in ``movies/services/cache_registry.py`` so that
# ``search_service`` can use the very same mechanism for its own keys; the
# names are re-exported here because they were part of this module's contract.

_HOME_SCOPE = 'home_movies'
_GENRE_SCOPE_PREFIX = 'genre:'


def _cache_key(prefix: str, **kwargs) -> str:
    """Generate a deterministic cache key."""
    return make_cache_key('movies', prefix, **kwargs)


# Deterministic (parameter-less) keys: these can be rebuilt on demand and never
# depend on the registry.
_HOME_CACHE_KEY = _cache_key(_HOME_SCOPE)


def _all_movies_genre_key(genre_name: str) -> str:
    """Cache key of ``get_all_movies_of_genre`` (constructible: no ``limit``)."""
    return _cache_key('all_movies_genre', genre_name=genre_name)


def _genre_recommendations_key(genre_name: str, limit: int) -> str:
    """Cache key of ``get_genre_recommendations`` (NOT reconstructible: hashed
    with an unknown ``limit``, so it can only be found through the registry)."""
    return _cache_key('genre_recommendations', genre_name=genre_name, limit=limit)


def _genre_scope(genre_name: str) -> str:
    """Registry scope for a genre. Case-folded so invalidation still matches
    keys generated from a differently cased genre name; the cache keys
    themselves keep the verbatim name used by the query."""
    return f'{_GENRE_SCOPE_PREFIX}{str(genre_name).casefold()}'


def invalidate_movie_caches(genre_names: Iterable[str] | None = None) -> None:
    """Invalidate cached movie lists. Pass genre_names to also clear per-genre keys.

    Always drops the parameter-less ``home_movies`` key. For every genre in
    ``genre_names`` it drops:

    * the ``all_movies_genre:<genre>`` key, and
    * every ``genre_recommendations:<genre>:<limit>`` key generated so far
      (all limit variants at once, via the module key registry).

    Must be called after the DB write has succeeded, and is best-effort by
    design: it never raises, so it is safe to call from ``Movie.save()`` /
    ``Movie.delete()``, which also run during migrations and test-data loading.

    Args:
        genre_names: Nombres de los generos afectados. ``None`` (or empty)
            only invalidates the global ``home_movies`` key.
    """
    names = [str(name) for name in (genre_names or ()) if name]

    # 1. Keys that can be rebuilt deterministically (no registry needed).
    keys: list[str] = [_HOME_CACHE_KEY]
    keys.extend(_all_movies_genre_key(name) for name in names)

    # 2. Keys that cannot be reconstructed (``genre_recommendations`` depends on
    #    an arbitrary ``limit``): drop every variant tracked for these scopes.
    scopes = [_HOME_SCOPE, *(_genre_scope(name) for name in names)]
    known = set(keys)
    for key in _take_scope_keys(scopes):
        if key not in known:
            known.add(key)
            keys.append(key)

    try:
        cache.delete_many(keys)
    except Exception:
        logger.warning(
            'No se pudo invalidar la cache de peliculas (%d claves).',
            len(keys), exc_info=True,
        )
        return

    logger.debug('Cache de peliculas invalidada: %d claves (%s)', len(keys), ', '.join(scopes))


def get_home_movies() -> dict:
    """
    Obtiene las peliculas principales para la pagina de inicio.

    Uses caching: returns cached queryset data if available,
    otherwise fetches from DB and caches the result.

    The cached entry is dropped by ``invalidate_movie_caches()`` on every
    movie write, so a new/edited movie is visible on the next request.

    Returns:
        Dict con 'success' (bool), 'message' (str), y 'movies' (QuerySet).
    """
    try:
        cache_key = _HOME_CACHE_KEY
        _track_key(_HOME_SCOPE, cache_key)
        cached = cache.get(cache_key)

        if cached is not None:
            logger.debug('Cache hit for home_movies')
            from movies.models import Movie
            movies = (
                Movie.objects.filter(id__in=cached)
                .prefetch_related('genres')
                .annotate(movie_avg_rating=Avg('rating_set__score'))
                .order_by('-release_year', 'title')
            )
            logger.info('Home movies obtenidas desde cache: %d peliculas', len(cached))
            return {'success': True, 'message': 'OK', 'movies': movies}

        from movies.models import Movie

        movies = (
            Movie.objects
            .prefetch_related('genres')
            .annotate(movie_avg_rating=Avg('rating_set__score'))
            .order_by('-release_year', 'title')
        )

        # Cache the movie IDs (queryset evaluation)
        movie_ids = list(movies.values_list('id', flat=True))
        cache.set(cache_key, movie_ids, CACHE_TTL_MEDIUM)
        logger.info('Obtenidas %d peliculas para home (cached)', len(movie_ids))

        return {'success': True, 'message': 'OK', 'movies': movies}
    except Exception as exc:
        logger.error('Error al obtener peliculas para home: %s', exc)
        return {'success': False, 'message': f'Error interno: {exc}', 'movies': []}


def get_genre_recommendations(genre_name: str, limit: int = 10) -> dict:
    """
    Obtiene recomendaciones de peliculas para un genero dado.

    Uses cache with TTL of 5 minutes.

    The key also depends on ``limit``, so it is tracked in the module key
    registry and dropped for every limit variant by
    ``invalidate_movie_caches([genre_name])``.

    Args:
        genre_name: Nombre del genero cinematico.
        limit: Numero maximo de recomendaciones a devolver.

    Returns:
        Dict con 'success' (bool), 'message' (str), y 'recommendations' (QuerySet).
    """
    try:
        cache_key = _genre_recommendations_key(genre_name, limit)
        _track_key(_genre_scope(genre_name), cache_key)
        cached = cache.get(cache_key)

        if cached is not None:
            logger.debug('Cache hit for genre_recommendations: %s', genre_name)
            from movies.models import Movie
            recommendations = (
                Movie.objects
                .filter(id__in=cached)
                .prefetch_related('genres')
                .annotate(movie_avg_rating=Avg('rating_set__score'))
                .order_by('-movie_avg_rating', '-release_year', 'title')[:limit]
            )
            logger.info('Recomendaciones obtenidas desde cache para "%s": %d peliculas', genre_name, len(cached))
            return {'success': True, 'message': 'OK', 'recommendations': recommendations}

        results = get_movie_recommendations(genre_name, limit=limit)
        movie_ids = list(results.values_list('id', flat=True))

        cache.set(cache_key, movie_ids, CACHE_TTL_SHORT)
        logger.info(
            'Recomendaciones para genero "%s": %d peliculas (cached)',
            genre_name, len(movie_ids),
        )

        from movies.models import Movie
        recommendations = (
            Movie.objects.filter(id__in=movie_ids)
            .prefetch_related('genres')
            .annotate(movie_avg_rating=Avg('rating_set__score'))
            .order_by('-movie_avg_rating', '-release_year', 'title')[:limit]
        )
        return {'success': True, 'message': 'OK', 'recommendations': recommendations}
    except Exception as exc:
        logger.error('Error al obtener recomendaciones para genero "%s": %s', genre_name, exc)
        return {'success': False, 'message': f'Error interno: {exc}', 'recommendations': []}


def get_all_movies_of_genre(genre_name: str) -> dict:
    """
    Obtiene todas las peliculas de un genero con su valoracion media.

    Uses cache with TTL of 5 minutes.

    The cached id list is dropped by ``invalidate_movie_caches([genre_name])``.

    Args:
        genre_name: Nombre del genero cinematico.

    Returns:
        Dict con 'success' (bool), 'message' (str), y 'movies' (QuerySet).
    """
    try:
        cache_key = _all_movies_genre_key(genre_name)
        _track_key(_genre_scope(genre_name), cache_key)
        cached = cache.get(cache_key)

        if cached is not None:
            logger.debug('Cache hit for all_movies_genre: %s', genre_name)
            from movies.models import Movie
            movies = (
                Movie.objects
                .filter(id__in=cached)
                .prefetch_related('genres')
                .annotate(movie_avg_rating=Avg('rating_set__score'))
                .order_by('-movie_avg_rating', '-release_year', 'title')
            )
            logger.info('Peliculas de genero "%s" obtenidas desde cache: %d', genre_name, len(cached))
            return {'success': True, 'message': 'OK', 'movies': movies}

        results = get_movies_by_genre_with_rating(genre_name)
        movie_ids = list(results.values_list('id', flat=True))

        cache.set(cache_key, movie_ids, CACHE_TTL_SHORT)
        logger.info(
            'Peliculas de genero "%s": %d peliculas (cached)',
            genre_name, len(movie_ids),
        )

        from movies.models import Movie
        movies = (
            Movie.objects.filter(id__in=movie_ids)
            .prefetch_related('genres')
            .annotate(movie_avg_rating=Avg('rating_set__score'))
            .order_by('-movie_avg_rating', '-release_year', 'title')
        )
        return {'success': True, 'message': 'OK', 'movies': movies}
    except Exception as exc:
        logger.error('Error al obtener peliculas de genero "%s": %s', genre_name, exc)
        return {'success': False, 'message': f'Error interno: {exc}', 'movies': []}
