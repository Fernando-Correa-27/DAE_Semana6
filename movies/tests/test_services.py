"""
Tests para todos los servicios de la aplicacion movies.

Verifica que cada servicio devuelva dicts con 'success' y 'message',
y que la logica de negocio funcione correctamente.

Estos tests son ``django.test.TestCase`` a proposito (antes eran clases pytest con
``@pytest.fixture``): unittest solo recoge clases que heredan de
``TestCase``, asi que la version anterior se descartaba en silencio y
``manage.py test movies.tests.test_services`` reportaba "Ran 0 tests".
Convertirlos aqui permite que se ejecuten con el runner de Django y **sin
depender de pytest**, que no esta declarado en requirements.txt.

Los servicios memoizan *ids* de peliculas en un ``LocMemCache`` con claves que no
dependen de la base de datos, y el runner de Django no limpia esa cache entre
tests. Por eso la clase base la vacia en ``setUp`` y en el cleanup: sin esto los
resultados dependerian del orden de ejecucion.
"""

import shutil
import tempfile

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase

from movies.models import Favorite, Genre, Movie, Rating
from movies.services import (
    add_favorite,
    create_rating,
    delete_rating,
    filter_movies,
    get_all_movies_of_genre,
    get_genre_recommendations,
    get_home_movies,
    get_revenue_estimate,
    get_rating_stats,
    get_user_favorite_count,
    get_user_favorites,
    get_user_profile_data,
    get_user_rating,
    get_user_rating_history,
    get_user_stats,
    is_favorite,
    remove_favorite,
    search_movies,
    update_profile,
    validate_rating,
)

User = get_user_model()

# JPEG valido de 10x10 generado con Pillow.
#
# Antes era un volcado hexadecimal fijo; estaba truncado, asi que Pillow lo
# rechazaba con ``UnidentifiedImageError`` y ``optimize_image`` caia en su rama
# de reserva en *cada* test que creaba una portada. Generarlo aqui garantiza
# bytes decodificables sin depender de un literal binario verificable a ojo.
def _build_test_image() -> bytes:
    import io

    from PIL import Image

    buffer = io.BytesIO()
    Image.new('RGB', (10, 10), color=(120, 120, 200)).save(buffer, format='JPEG')
    return buffer.getvalue()


_TEST_IMAGE_DATA = _build_test_image()


def _test_image(name='test_movie.jpg'):
    """Un upload nuevo en cada llamada.

    Compartir un unico ``SimpleUploadedFile`` a nivel de modulo hacia que todas
    las peliculas acabaran con el mismo ``cover.name`` y se pisaren entre si
    (y el puntero de lectura quedaba al final para el segundo consumidor).
    """
    return SimpleUploadedFile(
        name=name, content=_TEST_IMAGE_DATA, content_type='image/jpeg'
    )


# ==================== BASE ====================

class ServiceTestCase(TestCase):
    """Base: cache limpia y MEDIA_ROOT temporal, para que el orden no importe.

    Las dos cosas hacen falta:

    * ``cache.clear()``: los servicios cachean listas de ids en un
      ``LocMemCache`` con claves independientes de los datos, y Django no limpia
      esa cache entre tests. Sin esto, un test que deja la cache "caliente"
      contaminaria al siguiente.
    * ``MEDIA_ROOT`` temporal: las peliculas del setUp llevan portada, y sin
      esto cada test dejaria un ``movie_covers/test_movie*.jpg`` en el arbol de
      trabajo (el ``MEDIA_ROOT`` real es ``BASE_DIR / 'media'``).
    """

    def setUp(self):
        super().setUp()
        cache.clear()
        self.addCleanup(cache.clear)

        media_root = tempfile.mkdtemp(prefix='services_media_')
        self.addCleanup(shutil.rmtree, media_root, True)
        override = self.settings(MEDIA_ROOT=media_root, MEDIA_URL='/media/')
        override.enable()
        self.addCleanup(override.disable)

        # Equivalente a la antigua fixture 'user'.
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123',
            email='test@example.com',
        )

    def make_movie(self, title='Test Movie', release_year=2024, genre='Action'):
        """Equivalente a la antigua fixture 'movie' (con su 'genre')."""
        genre_obj = Genre.objects.get_or_create(name=genre)[0]
        movie = Movie.objects.create(
            title=title,
            release_year=release_year,
            cover=_test_image(),
        )
        movie.genres.add(genre_obj)
        return movie

    def make_rating(self, movie, user=None, score=5):
        """Equivalente a la antigua fixture 'rating'."""
        return Rating.objects.create(
            movie=movie, user=user or self.user, score=score,
        )


# ==================== TESTS: RATING SERVICE ====================

class TestValidateRating(ServiceTestCase):
    """Tests para validate_rating."""

    def test_validate_rating_valid_score(self):
        """Deberia validar correctamente scores entre 1 y 10."""
        movie = self.make_movie()
        for score in [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]:
            with self.subTest(score=score):
                result = validate_rating(self.user, movie, score)
                self.assertIs(result[0], True)  # (True, [])
                self.assertEqual(result[1], [])

    def test_validate_rating_invalid_low_score(self):
        """Deberia rechazar scores menores a 1."""
        movie = self.make_movie()
        result = validate_rating(self.user, movie, 0)
        self.assertIs(result[0], False)
        self.assertGreater(len(result[1]), 0)

    def test_validate_rating_invalid_high_score(self):
        """Deberia rechazar scores mayores a 10."""
        movie = self.make_movie()
        result = validate_rating(self.user, movie, 11)
        self.assertIs(result[0], False)
        self.assertGreater(len(result[1]), 0)

    def test_validate_rating_negative_score(self):
        """Deberia rechazar scores negativos."""
        movie = self.make_movie()
        result = validate_rating(self.user, movie, -1)
        self.assertIs(result[0], False)
        self.assertGreater(len(result[1]), 0)

    def test_validate_rating_float_score(self):
        """Deberia rechazar scores float."""
        movie = self.make_movie()
        result = validate_rating(self.user, movie, 3.5)
        self.assertIs(result[0], False)
        self.assertGreater(len(result[1]), 0)

    def test_validate_rating_none_movie(self):
        """Deberia rechazar movie None."""
        result = validate_rating(self.user, None, 5)
        self.assertIs(result[0], False)
        self.assertGreater(len(result[1]), 0)

    def test_validate_rating_unauthenticated(self):
        """Deberia rechazar a un usuario no autenticado."""
        from django.contrib.auth.models import AnonymousUser

        movie = self.make_movie()
        result = validate_rating(AnonymousUser(), movie, 5)
        self.assertIs(result[0], False)
        self.assertGreater(len(result[1]), 0)

    def test_validate_rating_duplicate(self):
        """Deberia rechazar una segunda valoracion de la misma pelicula."""
        movie = self.make_movie()
        self.make_rating(movie)
        result = validate_rating(self.user, movie, 7)
        self.assertIs(result[0], False)
        self.assertGreater(len(result[1]), 0)


class TestCreateRating(ServiceTestCase):
    """Tests para create_rating."""

    def test_create_rating_success(self):
        """Deberia crear una valoracion correctamente."""
        movie = self.make_movie()
        result = create_rating(self.user, movie, 4)
        self.assertIs(result['success'], True)
        self.assertIn('message', result)
        self.assertTrue(Rating.objects.filter(movie=movie, user=self.user).exists())
        self.assertEqual(Rating.objects.get(movie=movie, user=self.user).score, 4)

    def test_create_rating_duplicate(self):
        """Deberia rechazar valoraciones duplicadas."""
        movie = self.make_movie()
        create_rating(self.user, movie, 4)
        result = create_rating(self.user, movie, 5)
        self.assertIs(result['success'], False)
        self.assertIn('message', result)
        self.assertEqual(Rating.objects.filter(movie=movie, user=self.user).count(), 1)

    def test_create_rating_invalid_score(self):
        """Deberia rechazar scores invalidos (fuera de 1-10)."""
        movie = self.make_movie()
        result = create_rating(self.user, movie, 11)
        self.assertIs(result['success'], False)
        self.assertIn('message', result)
        self.assertIsNone(result.get('rating'))
        self.assertEqual(Rating.objects.count(), 0)

    def test_create_rating_none_user(self):
        """Deberia rechazar valoraciones de usuario None."""
        movie = self.make_movie()
        result = create_rating(None, movie, 4)
        self.assertIs(result['success'], False)
        self.assertIn('message', result)

    def test_create_rating_none_movie(self):
        """Deberia rechazar valoraciones de pelicula None."""
        result = create_rating(self.user, None, 4)
        self.assertIs(result['success'], False)
        self.assertIn('message', result)


class TestDeleteRating(ServiceTestCase):
    """Tests para delete_rating."""

    def test_delete_rating_success(self):
        """Deberia eliminar una valoracion correctamente."""
        movie = self.make_movie()
        rating = self.make_rating(movie)
        result = delete_rating(rating.user, rating.movie)
        self.assertIs(result['success'], True)
        self.assertIn('message', result)
        self.assertFalse(
            Rating.objects.filter(movie=rating.movie, user=rating.user).exists()
        )

    def test_delete_rating_nonexistent(self):
        """Deberia devolver success=False para valoracion inexistente."""
        movie = self.make_movie()
        result = delete_rating(self.user, movie)
        self.assertIs(result['success'], False)
        self.assertIn('message', result)


class TestGetUserRating(ServiceTestCase):
    """Tests para get_user_rating."""

    def test_get_user_rating_exists(self):
        """Deberia devolver la valoracion del usuario para una pelicula."""
        movie = self.make_movie()
        rating = self.make_rating(movie, score=5)
        result = get_user_rating(rating.user, rating.movie)
        self.assertIs(result['success'], True)
        self.assertEqual(result['rating'].score, 5)

    def test_get_user_rating_not_exists(self):
        """Deberia devolver None para valoracion inexistente."""
        movie = self.make_movie()
        result = get_user_rating(self.user, movie)
        self.assertIs(result['success'], True)
        self.assertIsNone(result['rating'])


# ==================== TESTS: FAVORITE SERVICE ====================

class TestIsFavorite(ServiceTestCase):
    """Tests para is_favorite."""

    def test_is_favorite_true(self):
        """Deberia devolver is_favorite=True si es favorita."""
        movie = self.make_movie()
        add_favorite(self.user, movie)
        result = is_favorite(self.user, movie)
        self.assertIs(result['success'], True)
        self.assertIs(result['is_favorite'], True)

    def test_is_favorite_false(self):
        """Deberia devolver is_favorite=False si no es favorita."""
        movie = self.make_movie()
        result = is_favorite(self.user, movie)
        self.assertIs(result['success'], True)
        self.assertIs(result['is_favorite'], False)


class TestAddFavorite(ServiceTestCase):
    """Tests para add_favorite."""

    def test_add_favorite_success(self):
        """Deberia agregar una pelicula a favoritas."""
        movie = self.make_movie()
        result = add_favorite(self.user, movie)
        self.assertIs(result['success'], True)
        self.assertIn('message', result)
        self.assertTrue(Favorite.objects.filter(user=self.user, movie=movie).exists())

    def test_add_favorite_duplicate(self):
        """Deberia manejar duplicados sin error."""
        movie = self.make_movie()
        add_favorite(self.user, movie)
        result = add_favorite(self.user, movie)
        # success=False (duplicado) y sin fila extra.
        self.assertIs(result['success'], False)
        self.assertIn('message', result)
        self.assertEqual(Favorite.objects.filter(user=self.user, movie=movie).count(), 1)


class TestRemoveFavorite(ServiceTestCase):
    """Tests para remove_favorite."""

    def test_remove_favorite_success(self):
        """Deberia remover una pelicula de favoritas."""
        movie = self.make_movie()
        add_favorite(self.user, movie)
        result = remove_favorite(self.user, movie)
        self.assertIs(result['success'], True)
        self.assertIn('message', result)
        self.assertFalse(Favorite.objects.filter(user=self.user, movie=movie).exists())

    def test_remove_favorite_not_exists(self):
        """Deberia devolver success=False si no existe."""
        movie = self.make_movie()
        result = remove_favorite(self.user, movie)
        self.assertIs(result['success'], False)
        self.assertIn('message', result)


class TestGetUserFavorites(ServiceTestCase):
    """Tests para get_user_favorites y get_user_favorite_count."""

    def test_get_user_favorites(self):
        """Deberia devolver las favoritas del usuario."""
        movie = self.make_movie()
        add_favorite(self.user, movie)
        result = get_user_favorites(self.user)
        self.assertIs(result['success'], True)
        self.assertIn('favorites', result)
        self.assertGreaterEqual(len(result['favorites']), 1)
        # Each favorite is a Favorite instance, compare movie
        favorite_movies = [f.movie for f in result['favorites']]
        self.assertIn(movie, favorite_movies)

    def test_get_user_favorites_empty(self):
        """Deberia devolver lista vacia si no hay favoritas."""
        result = get_user_favorites(self.user)
        self.assertIs(result['success'], True)
        self.assertIn('favorites', result)
        self.assertEqual(result['favorites'], [])

    def test_get_user_favorite_count(self):
        """Deberia devolver el conteo de favoritas."""
        movie = self.make_movie()
        add_favorite(self.user, movie)
        result = get_user_favorite_count(self.user)
        self.assertIs(result['success'], True)
        self.assertEqual(result['count'], 1)


# ==================== TESTS: MOVIE SERVICE ====================

class TestGetHomeMovies(ServiceTestCase):
    """Tests para get_home_movies."""

    def test_get_home_movies_success(self):
        """Deberia devolver peliculas para home."""
        self.make_movie()
        result = get_home_movies()
        self.assertIs(result['success'], True)
        self.assertIn('movies', result)
        self.assertGreaterEqual(len(result['movies']), 1)

    def test_get_home_movies_empty(self):
        """Deberia devolver lista vacia si no hay peliculas."""
        Movie.objects.all().delete()
        result = get_home_movies()
        self.assertIs(result['success'], True)
        self.assertIn('movies', result)
        self.assertEqual(len(result['movies']), 0)


class TestGetGenreRecommendations(ServiceTestCase):
    """Tests para get_genre_recommendations."""

    def test_get_genre_recommendations_success(self):
        """Deberia devolver recomendaciones por genero.

        ``get_movie_recommendations()`` descarta las peliculas sin valoraciones
        (``filter(rating_avg__isnull=False)``), asi que la pelicula del setUp
        necesita una valoracion para que la ruta principal se ejercite de verdad.
        """
        movie = self.make_movie()
        self.make_rating(movie, score=8)
        result = get_genre_recommendations('Action', limit=10)
        self.assertIs(result['success'], True)
        self.assertIn('recommendations', result)
        self.assertEqual(len(result['recommendations']), 1)
        self.assertEqual(result['recommendations'][0].pk, movie.pk)

    def test_get_genre_recommendations_excludes_unrated(self):
        """Pelicula sin valorar no aparece: es el filtro ``isnull=False``."""
        unrated = self.make_movie(title='Unrated', release_year=2023)
        self.make_movie(title='Rated', release_year=2024)
        self.make_rating(Movie.objects.get(title='Rated'), score=6)

        result = get_genre_recommendations('Action', limit=10)

        ids = [m.pk for m in result['recommendations']]
        self.assertNotIn(unrated.pk, ids)
        self.assertEqual(len(ids), 1)

    def test_get_genre_recommendations_limit(self):
        """Deberia respetar el limite."""
        for index in range(3):
            movie = self.make_movie(title=f'Movie {index}', release_year=2020 + index)
            other = User.objects.create_user(username=f'critic{index}', password='pw')
            Rating.objects.create(movie=movie, user=other, score=5 + index)

        result = get_genre_recommendations('Action', limit=2)

        self.assertIs(result['success'], True)
        self.assertIn('recommendations', result)
        self.assertEqual(len(result['recommendations']), 2)

    def test_get_genre_recommendations_invalid_genre(self):
        """Deberia manejar generos invalidos."""
        result = get_genre_recommendations('NonExistentGenre')
        self.assertIn('success', result)
        self.assertIn('recommendations', result)
        self.assertEqual(len(result['recommendations']), 0)


class TestGetAllMoviesOfGenre(ServiceTestCase):
    """Tests para get_all_movies_of_genre."""

    def test_get_all_movies_of_genre_success(self):
        """Deberia devolver todas las peliculas del genero (con o sin nota)."""
        self.make_movie()
        result = get_all_movies_of_genre('Action')
        self.assertIs(result['success'], True)
        self.assertIn('movies', result)
        self.assertGreaterEqual(len(result['movies']), 1)

    def test_get_all_movies_of_genre_invalid(self):
        """Deberia manejar generos invalidos."""
        result = get_all_movies_of_genre('NonExistentGenre')
        self.assertIn('success', result)
        self.assertIn('movies', result)
        self.assertEqual(len(result['movies']), 0)


# ==================== TESTS: SEARCH SERVICE ====================

class TestSearchMovies(ServiceTestCase):
    """Tests para search_movies."""

    def test_search_movies_by_title(self):
        """Deberia buscar peliculas por titulo."""
        self.make_movie(title='Test Movie')
        result = search_movies('Test Movie')
        self.assertIs(result['success'], True)
        self.assertIn('movies', result)
        self.assertGreaterEqual(len(result['movies']), 1)

    def test_search_movies_no_results(self):
        """Deberia devolver lista vacia si no hay resultados."""
        self.make_movie(title='Test Movie')
        result = search_movies('NoExisteEstaPel')
        self.assertIs(result['success'], True)
        self.assertIn('movies', result)
        self.assertEqual(len(result['movies']), 0)

    def test_search_movies_empty_query(self):
        """Deberia manejar query vacia."""
        result = search_movies('')
        self.assertIs(result['success'], True)
        self.assertIn('movies', result)
        self.assertEqual(len(result['movies']), 0)

    def test_search_movies_case_insensitive(self):
        """La busqueda es insensible a mayusculas."""
        self.make_movie(title='Test Movie')
        result = search_movies('test movie')
        self.assertIs(result['success'], True)
        self.assertEqual(len(result['movies']), 1)

    def test_search_movies_new_movie_is_visible(self):
        """Una pelicula creada tras cachear la MISMA busqueda debe aparecer.

        Usa el mismo termino de busqueda en ambas llamadas a proposito: solo
        asi se ejercita la clave de cache (una consulta nueva genera una clave
        nueva y pasaria aunque la invalidacion estuviese rota).
        """
        self.make_movie(title='Action One', genre='Action')
        first = search_movies('Action')
        self.assertEqual(len(first['movies']), 1, 'la cache debe guardar 1')

        self.make_movie(title='Action Two', genre='Action')
        second = search_movies('Action')

        self.assertEqual(
            len(second['movies']), 2,
            'una pelicula nueva no aparece en /search/ porque la clave de '
            'cache no se invalido tras el alta.',
        )
        self.assertEqual(
            {m.title for m in second['movies']}, {'Action One', 'Action Two'},
        )


class TestFilterMovies(ServiceTestCase):
    """Tests para filter_movies."""

    def test_filter_movies_by_genre(self):
        """Deberia filtrar por genero."""
        self.make_movie(genre='Action')
        result = filter_movies(genres=['Action'])
        self.assertIs(result['success'], True)
        self.assertIn('movies', result)
        self.assertGreaterEqual(len(result['movies']), 1)

    def test_filter_movies_by_year_range(self):
        """Deberia filtrar por rango de anos."""
        self.make_movie(release_year=2024)
        result = filter_movies(year_min=2020, year_max=2030)
        self.assertIs(result['success'], True)
        self.assertIn('movies', result)
        self.assertGreaterEqual(len(result['movies']), 1)

    def test_filter_movies_by_min_rating(self):
        """Deberia filtrar por rating minimo."""
        movie = self.make_movie()
        self.make_rating(movie, score=7)
        result = filter_movies(min_rating=4.0)
        self.assertIs(result['success'], True)
        self.assertIn('movies', result)
        self.assertGreaterEqual(len(result['movies']), 1)

    def test_filter_movies_min_rating_excludes_unrated(self):
        """Un filtro por nota minima excluye lo que no tiene nota."""
        unrated = self.make_movie(title='Unrated')
        result = filter_movies(min_rating=1.0)
        self.assertNotIn(unrated.pk, [m.pk for m in result['movies']])


# ==================== TESTS: PROFILE SERVICE ====================

class TestUpdateProfile(ServiceTestCase):
    """Tests para update_profile."""

    def test_update_profile_success(self):
        """Deberia actualizar el perfil correctamente."""
        result = update_profile(self.user, {'email': 'newemail@example.com'})
        self.assertIs(result['success'], True)
        self.assertIn('message', result)
        self.user.refresh_from_db()
        self.assertEqual(self.user.email, 'newemail@example.com')

    def test_update_profile_duplicate_email(self):
        """Deberia rechazar email ya en uso."""
        User.objects.create_user(
            username='other',
            password='test',
            email='other@example.com',
        )
        result = update_profile(self.user, {'email': 'other@example.com'})
        self.assertIs(result['success'], False)
        self.assertIn('message', result)
        self.user.refresh_from_db()
        self.assertEqual(self.user.email, 'test@example.com')

    def test_update_profile_duplicate_username(self):
        """Deberia rechazar username ya en uso."""
        User.objects.create_user(username='other', password='test')
        result = update_profile(self.user, {'username': 'other'})
        self.assertIs(result['success'], False)
        self.user.refresh_from_db()
        self.assertEqual(self.user.username, 'testuser')

    def test_update_profile_none_user(self):
        """Deberia rechazar usuario None."""
        result = update_profile(None, {'email': 'test@example.com'})
        self.assertIs(result['success'], False)
        self.assertIn('message', result)


class TestGetUserProfileData(ServiceTestCase):
    """Tests para get_user_profile_data."""

    def test_get_user_profile_data(self):
        """Deberia devolver datos del perfil."""
        result = get_user_profile_data(self.user)
        self.assertIn('profile_data', result)
        profile = result['profile_data']
        self.assertIn('username', profile)
        self.assertIn('email', profile)
        self.assertEqual(profile['username'], self.user.username)
        self.assertEqual(profile['email'], self.user.email)

    def test_get_user_profile_data_none_user(self):
        """Deberia devolver dict vacio para None."""
        result = get_user_profile_data(None)
        self.assertIsInstance(result, dict)
        self.assertIn('profile_data', result)
        self.assertEqual(result['profile_data'], {})


class TestGetUserRatingHistory(ServiceTestCase):
    """Tests para get_user_rating_history."""

    def test_get_user_rating_history(self):
        """Deberia devolver el historial de valoraciones."""
        movie = self.make_movie()
        self.make_rating(movie, score=6)
        result = get_user_rating_history(self.user)
        self.assertIs(result.get('success'), True)
        self.assertIn('history', result)
        self.assertGreaterEqual(len(result['history']), 1)
        self.assertEqual(result['history'][0]['movie_title'], movie.title)
        self.assertEqual(result['history'][0]['score'], 6)

    def test_get_user_rating_history_empty(self):
        """Deberia devolver lista vacia si no hay valoraciones."""
        result = get_user_rating_history(self.user)
        self.assertIs(result.get('success'), True)
        self.assertIn('history', result)
        self.assertEqual(result['history'], [])


# ==================== TESTS: REPORT SERVICE ====================

class TestGetRatingStats(ServiceTestCase):
    """Tests para get_rating_stats."""

    def test_get_rating_stats_with_ratings(self):
        """Deberia devolver estadisticas con valoraciones."""
        movie = self.make_movie()
        self.make_rating(movie, score=5)
        result = get_rating_stats()
        self.assertIn('total_ratings', result)
        self.assertIn('average_rating', result)
        self.assertGreaterEqual(result['total_ratings'], 1)

    def test_get_rating_stats_empty(self):
        """Deberia devolver estadisticas vacias."""
        Rating.objects.all().delete()
        result = get_rating_stats()
        self.assertEqual(result['total_ratings'], 0)
        self.assertIsNone(result['average_rating'])

    def test_get_rating_stats_structure(self):
        """Deberia devolver todas las claves esperadas."""
        result = get_rating_stats()
        expected_keys = [
            'total_ratings', 'average_rating', 'max_rating', 'min_rating',
            'ratings_per_movie',
        ]
        for key in expected_keys:
            self.assertIn(key, result, f'Falta clave: {key}')


class TestGetUserStats(ServiceTestCase):
    """Tests para get_user_stats."""

    def test_get_user_stats_authenticated(self):
        """Deberia devolver estadisticas de usuario autenticado."""
        movie = self.make_movie()
        self.make_rating(movie, score=5)
        result = get_user_stats(self.user)
        self.assertIn('rating_count', result)
        self.assertIn('favorite_count', result)
        self.assertGreaterEqual(result['rating_count'], 1)

    def test_get_user_stats_unauthenticated(self):
        """Deberia devolver dict con campos cero para None."""
        result = get_user_stats(None)
        self.assertIsInstance(result, dict)
        self.assertEqual(result['rating_count'], 0)

    def test_get_user_stats_structure(self):
        """Deberia devolver todas las claves esperadas."""
        result = get_user_stats(self.user)
        expected_keys = [
            'rating_count', 'average_rating', 'favorite_count',
            'most_rated_genre', 'highest_rating', 'lowest_rating',
        ]
        for key in expected_keys:
            self.assertIn(key, result, f'Falta clave: {key}')


class TestGetRevenueEstimate(ServiceTestCase):
    """Tests para get_revenue_estimate."""

    def test_get_revenue_estimate_with_movies(self):
        """Deberia devolver estimacion con peliculas y valoraciones."""
        movie = self.make_movie()
        self.make_rating(movie, score=5)
        result = get_revenue_estimate()
        self.assertIn('total_movies', result)
        self.assertIn('avg_revenue_estimate', result)
        self.assertIn('top_rated_movies', result)
        self.assertGreaterEqual(result['total_movies'], 1)

    def test_get_revenue_estimate_empty(self):
        """Deberia devolver estimacion vacia."""
        Movie.objects.all().delete()
        Rating.objects.all().delete()
        result = get_revenue_estimate()
        self.assertEqual(result['total_movies'], 0)
        self.assertEqual(result['avg_revenue_estimate'], 0.0)
        self.assertEqual(result['top_rated_movies'], [])

    def test_get_revenue_estimate_structure(self):
        """Deberia devolver todas las claves esperadas."""
        result = get_revenue_estimate()
        expected_keys = ['total_movies', 'avg_revenue_estimate', 'top_rated_movies']
        for key in expected_keys:
            self.assertIn(key, result, f'Falta clave: {key}')
