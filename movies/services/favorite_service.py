"""
Servicios de favoritos: logica de negocio para gestionar favoritos.
"""

import logging
from typing import TYPE_CHECKING

from django.db import transaction
from movies.models import Favorite

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from django.contrib.auth.models import User
    from movies.models import Movie


def add_favorite(user: 'User', movie: 'Movie') -> dict:
    """
    Añade una pelicula a los favoritos de un usuario.

    Args:
        user: Usuario propietario del favorito.
        movie: Pelicula a anadir a favoritos.

    Returns:
        Dict con 'success' (bool), 'message' (str), y 'favorite' (Favorite|None).
    """
    try:
        if not user.is_authenticated:
            logger.warning('Intento de anadir favorito sin autenticar: user=%s', user.username)
            return {'success': False, 'message': 'El usuario debe estar autenticado.'}

        if Favorite.objects.filter(user=user, movie=movie).exists():
            logger.info('Pelicula ya en favoritos: user=%s movie=%s', user.username, movie.title)
            return {'success': False, 'message': 'Esta pelicula ya esta en favoritos.'}

        with transaction.atomic():
            favorite = Favorite.objects.create(user=user, movie=movie)

        logger.info('Favorito anadido: user=%s movie=%s', user.username, movie.title)
        return {'success': True, 'message': 'Pelicula anadida a favoritos.', 'favorite': favorite}
    except Exception as exc:
        logger.error('Error al anadir favorito: %s', exc)
        return {'success': False, 'message': f'Error interno: {exc}'}


def remove_favorite(user: 'User', movie: 'Movie') -> dict:
    """
    Elimina una pelicula de los favoritos de un usuario.

    Args:
        user: Usuario propietario del favorito.
        movie: Pelicula a eliminar de favoritos.

    Returns:
        Dict con 'success' (bool) y 'message' (str).
    """
    try:
        if not user.is_authenticated:
            logger.warning('Intento de eliminar favorito sin autenticar: user=%s', user.username)
            return {'success': False, 'message': 'Usuario no autenticado.'}

        favorite = Favorite.objects.filter(user=user, movie=movie).first()
        if favorite:
            favorite.delete()
            logger.info('Favorito eliminado: user=%s movie=%s', user.username, movie.title)
            return {'success': True, 'message': 'Pelicula eliminada de favoritos.'}

        logger.info('No se encontro favorito: user=%s movie=%s', user.username, movie.title)
        return {'success': False, 'message': 'No se encontro el favorito.'}
    except Exception as exc:
        logger.error('Error al eliminar favorito: %s', exc)
        return {'success': False, 'message': f'Error interno: {exc}'}


def is_favorite(user: 'User', movie: 'Movie') -> dict:
    """
    Verifica si una pelicula esta en favoritos de un usuario.

    Args:
        user: Usuario a consultar.
        movie: Pelicula a verificar.

    Returns:
        Dict con 'success' (bool) y 'is_favorite' (bool).
    """
    try:
        if not user.is_authenticated:
            return {'success': True, 'is_favorite': False}

        result = Favorite.objects.filter(user=user, movie=movie).exists()
        logger.debug('Verificacion de favorito: user=%s movie=%s is_favorite=%s', user.username, movie.title, result)
        return {'success': True, 'is_favorite': result}
    except Exception as exc:
        logger.error('Error al verificar favorito: %s', exc)
        return {'success': False, 'is_favorite': False}


def get_user_favorites(user: 'User') -> dict:
    """
    Obtiene todos los favoritos de un usuario.

    Args:
        user: Usuario solicitante.

    Returns:
        Dict con 'success' (bool) y 'favorites' (QuerySet|list).
    """
    try:
        if not user.is_authenticated:
            logger.info('Intento de obtener favoritos sin autenticar: user=%s', user.username)
            return {'success': True, 'favorites': []}

        favorites = Favorite.objects.filter(user=user)
        logger.info('Obtenidos %d favoritos para user=%s', favorites.count(), user.username)
        return {'success': True, 'favorites': list(favorites)}
    except Exception as exc:
        logger.error('Error al obtener favoritos: %s', exc)
        return {'success': False, 'favorites': []}


def get_user_favorite_count(user: 'User') -> dict:
    """
    Obtiene el numero de favoritos de un usuario.

    Args:
        user: Usuario solicitante.

    Returns:
        Dict con 'success' (bool) y 'count' (int).
    """
    try:
        if not user.is_authenticated:
            return {'success': True, 'count': 0}

        count = Favorite.objects.filter(user=user).count()
        logger.debug('Conteo de favoritos: user=%s count=%d', user.username, count)
        return {'success': True, 'count': count}
    except Exception as exc:
        logger.error('Error al contar favoritos: %s', exc)
        return {'success': False, 'count': 0}
