"""
Servicios de reportes: estadisticas generales, por usuario y estimaciones.

Todos los servicios devuelven dicts con 'success' (bool),
'message' (str) y datos opcionales.
"""

import logging
from typing import Any

from django.contrib.auth import get_user_model
from django.db.models import Avg, Count, Max, Min, Sum
from movies.models import Favorite, Movie, Rating

logger = logging.getLogger(__name__)


def get_rating_stats() -> dict[str, Any]:
    """
    Obtiene estadisticas generales de las valoraciones.

    Returns:
        Diccionario con: total_ratings, average_rating, max_rating,
        min_rating, ratings_per_movie (dict con movie_id -> count).
    """
    try:
        ratings = Rating.objects.aggregate(
            total=Count('id'),
            avg=Avg('score'),
            max_score=Max('score'),
            min_score=Min('score'),
        )

        ratings_per_movie = (
            Rating.objects.values('movie__title')
            .annotate(count=Count('id'))
            .order_by('-count')
        )

        result = {
            'total_ratings': ratings['total'] or 0,
            'average_rating': round(float(ratings['avg']), 2) if ratings['avg'] else None,
            'max_rating': ratings['max_score'] or 0,
            'min_rating': ratings['min_score'] or 0,
            'ratings_per_movie': list(ratings_per_movie),
        }

        logger.info('Estadisticas de valoraciones obtenidas: total=%d', result['total_ratings'])
        return result
    except Exception as exc:
        logger.error('Error al obtener estadisticas de valoraciones: %s', exc)
        return {
            'total_ratings': 0,
            'average_rating': None,
            'max_rating': 0,
            'min_rating': 0,
            'ratings_per_movie': [],
        }


def get_user_stats(user) -> dict[str, Any]:
    """
    Obtiene estadisticas de un usuario especifico.

    Args:
        user: Instancia de User autenticado.

    Returns:
        Diccionario con: rating_count, average_rating, favorite_count,
        most_rated_genre, highest_rating, lowest_rating.
    """
    try:
        User = get_user_model()
        if not user or not user.is_authenticated:
            return {
                'rating_count': 0,
                'average_rating': None,
                'favorite_count': 0,
                'most_rated_genre': None,
                'highest_rating': 0,
                'lowest_rating': 0,
            }

        user_ratings = Rating.objects.filter(user=user)
        rating_stats = user_ratings.aggregate(
            total=Count('id'),
            avg=Avg('score'),
            max_score=Max('score'),
            min_score=Min('score'),
        )

        favorite_count = Favorite.objects.filter(user=user).count()

        # Find most rated genre
        most_rated_genre = None
        if user_ratings.exists():
            most_rated = (
                user_ratings.select_related('movie')
                .values('movie__genres__name')
                .annotate(count=Count('id'))
                .order_by('-count')
                .first()
            )
            if most_rated:
                most_rated_genre = most_rated['movie__genres__name']

        result = {
            'rating_count': rating_stats['total'] or 0,
            'average_rating': round(float(rating_stats['avg']), 2) if rating_stats['avg'] else None,
            'favorite_count': favorite_count,
            'most_rated_genre': most_rated_genre,
            'highest_rating': rating_stats['max_score'] or 0,
            'lowest_rating': rating_stats['min_score'] or 0,
        }

        logger.info('Estadisticas de usuario %s obtenidas: rating_count=%d', user.username, result['rating_count'])
        return result
    except Exception as exc:
        logger.error('Error al obtener estadisticas de usuario: %s', exc)
        return {
            'rating_count': 0,
            'average_rating': None,
            'favorite_count': 0,
            'most_rated_genre': None,
            'highest_rating': 0,
            'lowest_rating': 0,
        }


def get_revenue_estimate() -> dict[str, Any]:
    """
    Calcula una estimacion basada en las valoraciones y peliculas.

    Returns:
        Diccionario con: total_movies, avg_revenue_estimate, top_rated_movies
        (list of {title, avg_rating} sorted by avg rating descending).
    """
    try:
        movies_with_ratings = Movie.objects.annotate(
            rating_count=Count('rating_set'),
            avg_rating=Avg('rating_set__score'),
        ).filter(rating_count__gt=0)

        total_movies = Movie.objects.count()
        avg_revenue_estimate = 0.0
        if movies_with_ratings.exists():
            avg_rating_overall = movies_with_ratings.aggregate(
                avg=Avg('avg_rating')
            )['avg']
            if avg_rating_overall:
                avg_revenue_estimate = round(float(avg_rating_overall) * 1000000, 2)

        top_rated = [
            {
                'title': m.title,
                'avg_rating': round(float(m.avg_rating), 2),
                'rating_count': m.rating_count,
            }
            for m in movies_with_ratings.order_by('-avg_rating')[:10]
        ]

        result = {
            'total_movies': total_movies,
            'avg_revenue_estimate': avg_revenue_estimate,
            'top_rated_movies': top_rated,
        }

        logger.info('Estimacion de revenue calculada: total_movies=%d, avg_revenue=%.2f', total_movies, avg_revenue_estimate)
        return result
    except Exception as exc:
        logger.error('Error al calcular estimacion de revenue: %s', exc)
        return {
            'total_movies': 0,
            'avg_revenue_estimate': 0.0,
            'top_rated_movies': [],
        }
