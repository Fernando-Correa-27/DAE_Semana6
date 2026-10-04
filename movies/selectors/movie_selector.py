"""
Selectors de peliculas: consultas a base de datos para peliculas.
"""

from typing import TYPE_CHECKING

from django.db.models import Avg, QuerySet

if TYPE_CHECKING:
    from movies.models import Movie


def get_movie_recommendations(genre_name: str, limit: int = 10) -> 'QuerySet[Movie]':
    """
    Obtiene peliculas recomendadas para un genero dado.
    Prioriza las peliculas con mejor valoracion.

    Args:
        genre_name: Nombre del genero cinematografico.
        limit: Numero maximo de recomendaciones a devolver.

    Returns:
        QuerySet de peliculas recomendadas con annotation 'rating_avg'.
    """
    from movies.models import Movie

    queryset = (
        Movie.objects
        .prefetch_related('genres', 'rating_set')
        .filter(genres__name=genre_name)
        .annotate(rating_avg=Avg('rating_set__score'))
        .filter(rating_avg__isnull=False)
        .order_by('-rating_avg', '-release_year')
    )
    # Use distinct to handle duplicate rows from M2M join, then slice
    distinct_ids = list(queryset.values_list('id', flat=True).distinct()[:limit])
    return (
        Movie.objects
        .filter(id__in=distinct_ids)
        .prefetch_related('genres', 'rating_set')
        .annotate(rating_avg=Avg('rating_set__score'))
        .filter(rating_avg__isnull=False)
        .order_by('-rating_avg', '-release_year')
    )


def get_movies_by_genre_with_rating(genre_name: str) -> 'QuerySet[Movie]':
    """
    Obtiene todas las peliculas de un genero con su valoracion media,
    incluyendo las que no tienen valoraciones.

    Args:
        genre_name: Nombre del genero cinematico.

    Returns:
        QuerySet de todas las peliculas del genero con annotation 'rating_avg'.
    """
    from movies.models import Movie

    return (
        Movie.objects
        .prefetch_related('genres', 'rating_set')
        .filter(genres__name=genre_name)
        .annotate(rating_avg=Avg('rating_set__score'))
        .order_by('-release_year', 'title')
    )
