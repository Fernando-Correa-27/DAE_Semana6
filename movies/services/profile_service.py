"""
Servicios de perfil: logica de negocio para perfiles de usuario.
"""

import logging
from typing import TYPE_CHECKING

from django.contrib.auth import get_user_model
from django.db import transaction

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from django.contrib.auth.models import User


def update_profile(user: 'User', data: dict) -> dict:
    """
    Actualiza los datos de perfil de un usuario.

    Args:
        user: Usuario a actualizar.
        data: Diccionario con los campos a actualizar (username, email, etc.).

    Returns:
        Dict con 'success' (bool), 'message' (str), y 'user' (User|None).
    """
    try:
        if not user.is_authenticated:
            logger.warning('Intento de actualizar perfil sin autenticar: user=%s', user.username)
            return {'success': False, 'message': 'El usuario debe estar autenticado.'}

        username = data.get('username', user.username)
        email = data.get('email', user.email)

        User = get_user_model()
        existing = User.objects.filter(username=username).exclude(pk=user.pk).first()
        if existing:
            logger.warning('Username duplicado al actualizar perfil: %s', username)
            return {'success': False, 'message': f'El nombre de usuario "{username}" ya esta en uso.'}

        if email and User.objects.filter(email=email).exclude(pk=user.pk).exists():
            logger.warning('Email duplicado al actualizar perfil: %s', email)
            return {'success': False, 'message': f'El correo "{email}" ya esta en uso.'}

        with transaction.atomic():
            user.username = username
            user.email = email
            user.save(update_fields=['username', 'email', 'first_name', 'last_name'])

        logger.info('Perfil actualizado: user=%s email=%s', user.username, email)
        return {'success': True, 'message': 'Perfil actualizado correctamente.', 'user': user}
    except Exception as exc:
        logger.error('Error al actualizar perfil: %s', exc)
        return {'success': False, 'message': f'Error interno: {exc}'}


def get_user_profile_data(user: 'User') -> dict:
    """
    Obtiene los datos de perfil de un usuario.

    Args:
        user: Usuario a consultar.

    Returns:
        Dict con 'success' (bool) y 'profile_data' (dict).
    """
    try:
        if not user.is_authenticated:
            logger.info('Intento de obtener perfil sin autenticar: user=%s', user.username)
            return {'success': True, 'profile_data': {}}

        profile_data = {
            'username': user.username,
            'email': user.email,
            'first_name': user.first_name,
            'last_name': user.last_name,
        }
        logger.debug('Datos de perfil obtenidos para user=%s', user.username)
        return {'success': True, 'profile_data': profile_data}
    except Exception as exc:
        logger.error('Error al obtener datos de perfil: %s', exc)
        return {'success': False, 'profile_data': {}}


def get_user_rating_history(user: 'User') -> dict:
    """
    Obtiene el historial de valoraciones de un usuario con detalles de la pelicula.

    Args:
        user: Usuario solicitante.

    Returns:
        Dict con 'success' (bool) y 'history' (list).
    """
    try:
        if not user.is_authenticated:
            logger.info('Intento de obtener historial sin autenticar: user=%s', user.username)
            return {'success': True, 'history': []}

        from movies.models import Rating

        ratings = Rating.objects.filter(user=user).select_related('movie').order_by('-created_at')
        history = [
            {
                'movie_id': r.movie.pk,
                'movie_title': r.movie.title,
                'movie_year': r.movie.release_year,
                'score': r.score,
                'created_at': r.created_at,
            }
            for r in ratings
        ]

        logger.info('Historial de valoraciones: user=%s %d valoraciones', user.username, len(history))
        return {'success': True, 'history': history}
    except Exception as exc:
        logger.error('Error al obtener historial de valoraciones: %s', exc)
        return {'success': False, 'history': []}
