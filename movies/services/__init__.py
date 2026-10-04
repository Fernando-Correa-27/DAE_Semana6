"""
Servicios de la aplicacion movies.

Este paquete contiene toda la logica de negocio de la aplicacion.
Las vistas deben interactuar con estos servicios en lugar de llamar
directamente a los modelos o selectores.
"""

# Rating services
from movies.services.rating_service import (
    create_rating,
    delete_rating,
    get_user_rating,
    validate_rating,
)

# Favorite services
from movies.services.favorite_service import (
    add_favorite,
    get_user_favorite_count,
    get_user_favorites,
    is_favorite,
    remove_favorite,
)

# Search services
from movies.services.search_service import filter_movies, search_movies

# Profile services
from movies.services.profile_service import (
    get_user_profile_data,
    get_user_rating_history,
    update_profile,
)

# Movie services
from movies.services.movie_service import (
    get_all_movies_of_genre,
    get_genre_recommendations,
    get_home_movies,
)

# Report services
from movies.services.report_service import (
    get_rating_stats,
    get_user_stats,
    get_revenue_estimate,
)

__all__ = [
    # Rating
    'create_rating',
    'delete_rating',
    'get_user_rating',
    'validate_rating',
    # Favorite
    'add_favorite',
    'get_user_favorite_count',
    'get_user_favorites',
    'is_favorite',
    'remove_favorite',
    # Search
    'filter_movies',
    'search_movies',
    # Profile
    'get_user_profile_data',
    'get_user_rating_history',
    'update_profile',
    # Movie
    'get_all_movies_of_genre',
    'get_genre_recommendations',
    'get_home_movies',
    # Reports
    'get_rating_stats',
    'get_user_stats',
    'get_revenue_estimate',
]
