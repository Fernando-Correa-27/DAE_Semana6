"""
Servicios de valoraciones: logica de negocio para Ratings.
"""

import logging
from typing import TYPE_CHECKING

from django.db import transaction
from movies.models import Rating
from movies.services.movie_service import invalidate_movie_caches

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from django.contrib.auth.models import User
    from movies.models import Movie


def _invalidate_caches_for_movie(movie: 'Movie | None') -> None:
    """Drop cached movie lists after a rating write.

    A new or removed rating changes the average and the rating count of the
    movie, which is what the cached id lists are ordered by. It also changes
    which movies match a ``min_rating`` filter, so the cached search/filter
    results are dropped. Best-effort: it never raises, so a cache problem
    cannot break a rating.
    """
    if movie is None or not getattr(movie, 'pk', None):
        return
    try:
        genre_names = [str(name) for name in movie.genres.values_list('name', flat=True)]
        invalidate_movie_caches(genre_names)
    except Exception:
        logger.debug('No se pudo invalidar la cache tras una valoracion.', exc_info=True)
    try:
        from movies.services.search_service import invalidate_search_caches

        invalidate_search_caches()
    except Exception:
        logger.debug('No se pudo invalidar la cache de busqueda tras una valoracion.', exc_info=True)


def validate_rating(user: 'User', movie: 'Movie', score: int) -> Tuple[bool, list[str]]:
    """
    Valida los datos de una valoracion sin guardarla.

    Args:
        user: Usuario que realiza la valoracion.
        movie: Pelicula a valorar.
        score: Puntuacion entre 1 y 10.

    Returns:
        Tupla (es_valida, lista_de_errores).
    """
    errors: list[str] = []

    if not user.is_authenticated:
        errors.append('El usuario debe estar autenticado para valorar una pelicula.')
        return (False, errors)

    if movie is None:
        errors.append('Debe seleccionar una pelicula valida.')
        return (False, errors)

    if not isinstance(score, int) or score < 1 or score > 10:
        errors.append('La puntuacion debe ser un numero entero entre 1 y 10.')
        return (False, errors)

    if Rating.objects.filter(user=user, movie=movie).exists():
        errors.append('El usuario ya ha valorado esta pelicula.')
        return (False, errors)

    return (True, errors)


def create_rating(
    user: 'User',
    movie: 'Movie',
    score: int,
) -> dict:
    """
    Crea una valoracion para una pelicula.

    Valida los datos, verifica duplicados y guarda la valoracion
    dentro de una transaccion atomica.

    Args:
        user: Usuario que valora la pelicula.
        movie: Pelicula valorada.
        score: Puntuacion entre 1 y 10.

    Returns:
        Dict con 'success' (bool), 'message' (str), y 'rating' (Rating|None).
    """
    try:
        is_valid, errors = validate_rating(user, movie, score)
        if not is_valid:
            logger.warning('Valoracion fallida: %s', '; '.join(errors))
            return {'success': False, 'message': '; '.join(errors), 'rating': None}

        with transaction.atomic():
            rating = Rating.objects.create(
                user=user,
                movie=movie,
                score=score,
            )

        _invalidate_caches_for_movie(movie)

        logger.info(
            'Valoracion creada: user=%s movie=%s score=%s',
            user.username, movie.title, score,
        )
        return {'success': True, 'message': 'Valoracion guardada correctamente.', 'rating': rating}
    except Exception as exc:
        logger.error('Error al crear valoracion: %s', exc)
        return {'success': False, 'message': f'Error interno: {exc}', 'rating': None}


def get_user_rating(user: 'User', movie: 'Movie') -> dict:
    """
    Obtiene la valoracion de un usuario para una pelicula.

    Args:
        user: Usuario solicitante.
        movie: Pelicula consultada.

    Returns:
        Dict con 'success' (bool) y 'rating' (Rating|None).
    """
    try:
        if not user.is_authenticated:
            logger.info('Intento de obtener valoracion sin autenticar: user=%s', user.username)
            return {'success': True, 'rating': None}

        rating = Rating.objects.filter(user=user, movie=movie).first()
        logger.debug('Obtenida valoracion: user=%s movie=%s found=%s', user.username, movie.title, bool(rating))
        return {'success': True, 'rating': rating}
    except Exception as exc:
        logger.error('Error al obtener valoracion: %s', exc)
        return {'success': False, 'rating': None}


def delete_rating(user: 'User', movie: 'Movie') -> dict:
    """
    Elimina la valoracion de un usuario para una pelicula.

    Args:
        user: Usuario que elimina su valoracion.
        movie: Pelicula de la que se elimina la valoracion.

    Returns:
        Dict con 'success' (bool), 'message' (str).
    """
    try:
        if not user.is_authenticated:
            logger.warning('Intento de eliminar valoracion sin autenticar: user=%s', user.username)
            return {'success': False, 'message': 'Usuario no autenticado.'}

        rating = Rating.objects.filter(user=user, movie=movie).first()
        if rating:
            rating.delete()
            _invalidate_caches_for_movie(movie)
            logger.info('Valoracion eliminada: user=%s movie=%s', user.username, movie.title)
            return {'success': True, 'message': 'Valoracion eliminada.'}

        logger.info('No se encontro valoracion para eliminar: user=%s movie=%s', user.username, movie.title)
        return {'success': False, 'message': 'No se encontro la valoracion.'}
    except Exception as exc:
        logger.error('Error al eliminar valoracion: %s', exc)
        return {'success': False, 'message': f'Error interno: {exc}'}
