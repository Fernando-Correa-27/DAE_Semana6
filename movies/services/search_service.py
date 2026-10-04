"""
Servicios de busqueda y filtrado: logica para buscar y filtrar peliculas.

Includes caching for search and filter operations plus write-time invalidation.

The cached entries are *id lists* stored under keys that depend only on the
query parameters, so they go stale as soon as a movie is created, renamed or
deleted. Both key families are therefore registered in the shared key registry
(``movies/services/cache_registry.py``) and dropped by
``invalidate_search_caches()`` on every movie write - without which a new movie
would stay invisible in ``/search/`` (and in any filtered list) for the whole
TTL, 5 minutes.
"""

import logging
from typing import Optional

from django.core.cache import cache
from django.db.models import Avg
from movies.models import Movie

from movies.services.cache_registry import (
    _take_scope_keys,
    _track_key,
    make_cache_key,
)

logger = logging.getLogger(__name__)

CACHE_TTL_SHORT = 300  # 5 minutes

# ---------------------------------------------------------------------------
# Cache key bookkeeping
# ---------------------------------------------------------------------------
# Both read functions memoise the matching movie ids under md5-hashed keys
# ("search:<md5>"). Their parameters are hashed away, so the affected keys
# cannot be rebuilt (or pattern-deleted) at invalidation time: a search accepts
# an arbitrary text and a filter any combination of genres/years/rating. Both
# families are therefore registered under a logical scope and every key tracked
# for those scopes is dropped on a write, reusing the mechanism already used by
# ``movie_service``.

_SEARCH_SCOPE = 'search'
_FILTER_SCOPE = 'filter'
# Prefijo de las claves en el backend; el registro usa los scopes de arriba.
_CACHE_NAMESPACE = 'search'


def _cache_key(prefix: str, **kwargs) -> str:
    """Generate a deterministic cache key."""
    return make_cache_key(_CACHE_NAMESPACE, prefix, **kwargs)


def _search_cache_key(query: str) -> str:
    """Cache key of ``search_movies`` (registered under ``_SEARCH_SCOPE``)."""
    return _cache_key('search', q=query)


def _filter_cache_data(
    genres: list[str] = None,
    year_min: Optional[int] = None,
    year_max: Optional[int] = None,
    min_rating: Optional[float] = None,
) -> dict:
    """Normalise the filter parameters into the key payload."""
    return {
        'genres': ','.join(sorted(genres)) if genres else '',
        'year_min': str(year_min) if year_min is not None else '',
        'year_max': str(year_max) if year_max is not None else '',
        'min_rating': str(min_rating) if min_rating is not None else '',
    }


def _filter_cache_key(
    genres: list[str] = None,
    year_min: Optional[int] = None,
    year_max: Optional[int] = None,
    min_rating: Optional[float] = None,
) -> str:
    """Cache key of ``filter_movies`` (registered under ``_FILTER_SCOPE``)."""
    return _cache_key('filter', **_filter_cache_data(genres, year_min, year_max, min_rating))


def invalidate_search_caches() -> None:
    """Invalidate every cached search and filter result.

    Drops all the ``search:<md5>`` and ``filter:<md5>`` keys generated so far
    (found through the shared key registry, since the queries that produced
    them - and the search terms inside them - are not known to the caller).

    Must be called after the DB write has succeeded, and is best-effort by
    design: it never raises, so it is safe to call from ``Movie.save()``,
    ``Movie.delete()`` and the ``post_delete`` signal, which also run during
    migrations and test-data loading.
    """
    scopes = (_SEARCH_SCOPE, _FILTER_SCOPE)
    try:
        keys = _take_scope_keys(scopes)
    except Exception:
        # A registry problem must never break the write that triggered it.
        logger.debug('No se pudo leer el registro de claves de busqueda.', exc_info=True)
        return

    if not keys:
        logger.debug('No hay claves de busqueda/filtrado cacheadas que invalidar.')
        return

    try:
        cache.delete_many(keys)
    except Exception:
        logger.warning(
            'No se pudo invalidar la cache de busqueda/filtrado (%d claves).',
            len(keys), exc_info=True,
        )
        return

    logger.debug('Cache de busqueda/filtrado invalidada: %d claves', len(keys))


def search_movies(query: str) -> dict:
    """
    Busca peliculas por titulo (insensible a mayusculas).

    Uses caching: the matching id list is dropped by
    ``invalidate_search_caches()`` on every movie write, so a new or renamed
    movie is visible on the next search.

    Args:
        query: Texto de busqueda para empar con el titulo.

    Returns:
        Dict con 'success' (bool), 'message' (str), y 'movies' (QuerySet).
    """
    try:
        if not query:
            logger.info('Busqueda vacia recibida')
            return {'success': True, 'message': 'OK', 'movies': Movie.objects.none()}

        cache_key = _search_cache_key(query)
        _track_key(_SEARCH_SCOPE, cache_key)
        cached = cache.get(cache_key)

        if cached is not None:
            logger.debug('Cache hit for search: %s', query)
            movies = Movie.objects.filter(id__in=cached).order_by('title')
            logger.info('Busqueda "%s" obtenida desde cache: %d resultados', query, len(cached))
            return {'success': True, 'message': 'OK', 'movies': movies}

        results = Movie.objects.filter(title__icontains=query).order_by('title')
        movie_ids = list(results.values_list('id', flat=True))

        cache.set(cache_key, movie_ids, CACHE_TTL_SHORT)
        logger.info('Busqueda "%s": %d resultados (cached)', query, len(movie_ids))

        return {'success': True, 'message': 'OK', 'movies': results}
    except Exception as exc:
        logger.error('Error al buscar peliculas "%s": %s', query, exc)
        return {'success': False, 'message': f'Error interno: {exc}', 'movies': []}


def filter_movies(
    genres: list[str] = None,
    year_min: Optional[int] = None,
    year_max: Optional[int] = None,
    min_rating: Optional[float] = None,
) -> dict:
    """
    Filtra peliculas por criterios dados.

    Uses caching: the matching id list is dropped by
    ``invalidate_search_caches()`` on every movie write (and on a rating
    write, since ``min_rating`` filters by the average score).

    Args:
        genres: Lista de nombres de generos para filtrar.
        year_min: Ano minimo de lanzamiento (inclusive).
        year_max: Ano maximo de lanzamiento (inclusive).
        min_rating: Puntuacion media minima.

    Returns:
        Dict con 'success' (bool), 'message' (str), y 'movies' (QuerySet).
    """
    try:
        # Build a cache key from the filter parameters
        cache_key = _filter_cache_key(genres, year_min, year_max, min_rating)
        _track_key(_FILTER_SCOPE, cache_key)
        cached = cache.get(cache_key)

        if cached is not None:
            logger.debug('Cache hit for filter')
            movies = Movie.objects.filter(id__in=cached)
            logger.info('Filtrado obtenido desde cache: %d resultados', len(cached))
            return {'success': True, 'message': 'OK', 'movies': movies}

        queryset = Movie.objects.prefetch_related('genres').annotate(
            rating_avg=Avg('rating_set__score')
        )

        if genres:
            queryset = queryset.filter(genres__name__in=genres)

        if year_min is not None:
            queryset = queryset.filter(release_year__gte=year_min)

        if year_max is not None:
            queryset = queryset.filter(release_year__lte=year_max)

        if min_rating is not None:
            queryset = queryset.filter(rating_avg__gte=min_rating)

        results = queryset.distinct().order_by('-rating_avg', '-release_year', 'title')
        movie_ids = list(results.values_list('id', flat=True))

        cache.set(cache_key, movie_ids, CACHE_TTL_SHORT)
        logger.info(
            'Filtrado: genres=%s year_min=%s year_max=%s min_rating=%s => %d resultados (cached)',
            genres, year_min, year_max, min_rating, len(movie_ids),
        )

        return {'success': True, 'message': 'OK', 'movies': Movie.objects.filter(id__in=movie_ids)}
    except Exception as exc:
        logger.error('Error al filtrar peliculas: %s', exc)
        return {'success': False, 'message': f'Error interno: {exc}', 'movies': []}
