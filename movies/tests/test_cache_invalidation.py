"""
Tests de invalidacion de la cache de peliculas.

Las listas de peliculas cacheadas en ``movies/services/movie_service.py``
memoizan *ids* con TTL de 5-10 minutos. Estos tests comprueban que cualquier
escritura (crear/editar/eliminar una pelicula, valorarla) invalida esas claves
y que la cache sigue siendo efectiva cuando no hay escrituras.

Nota de infraestructura: estos tests se descubren automaticamente con
``manage.py test`` porque ``movies/__init__.py`` existe. Para ejecutarlos solos:

    .\\venv\\Scripts\\python.exe manage.py test movies.tests.test_cache_invalidation -v 2
"""

from unittest import mock

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase

from movies.models import Genre, Movie, Rating
from movies.services import movie_service
from movies.services.movie_service import (
    _all_movies_genre_key,
    _cache_key,
    _genre_recommendations_key,
    get_all_movies_of_genre,
    get_genre_recommendations,
    get_home_movies,
    invalidate_movie_caches,
)
from movies.services.rating_service import create_rating

User = get_user_model()

HOME_KEY = _cache_key('home_movies')


class _CountingCache:
    """Wrapper that counts the calls made by the service to ``django.core.cache``."""

    def __init__(self, real):
        self._real = real
        self.get_calls = 0
        self.set_calls = 0
        self.delete_calls = 0
        self.delete_many_calls = 0

    def get(self, *args, **kwargs):
        self.get_calls += 1
        return self._real.get(*args, **kwargs)

    def set(self, *args, **kwargs):
        self.set_calls += 1
        return self._real.set(*args, **kwargs)

    def delete(self, *args, **kwargs):
        self.delete_calls += 1
        return self._real.delete(*args, **kwargs)

    def delete_many(self, *args, **kwargs):
        self.delete_many_calls += 1
        return self._real.delete_many(*args, **kwargs)


class CacheInvalidationTestCase(TestCase):
    """Base: cache limpia en cada test para que sean independientes del orden."""

    def setUp(self):
        cache.clear()
        self.addCleanup(cache.clear)
        self.genre = Genre.objects.create(name='Action')
        self.other_genre = Genre.objects.create(name='Drama')

    def _create_movie(self, title='Movie', year=2020, genre=None):
        movie = Movie.objects.create(title=title, release_year=year)
        if genre is not None:
            movie.genres.add(genre)
        return movie

    @staticmethod
    def _ids(result, key='movies'):
        return list(result[key].values_list('pk', flat=True))


class MovieWriteInvalidationTests(CacheInvalidationTestCase):
    """``Movie.save()`` / ``Movie.delete()`` deben invalidar las claves."""

    def test_new_movie_appears_in_home_after_save(self):
        """Regresion: una pelicula nueva no puede quedar oculta hasta 10 minutos."""
        movie_a = self._create_movie('Movie A', 2001, self.genre)

        first = get_home_movies()
        self.assertTrue(first['success'])
        self.assertIn(movie_a.pk, self._ids(first))
        # La clave esta caliente: el siguiente get_home_movies() la usaria.
        self.assertIsNotNone(cache.get(HOME_KEY))

        # Sin tocar el TTL: solo la invalidacion puede hacer visible la nueva.
        movie_b = self._create_movie('Movie B', 2002, self.genre)

        second = get_home_movies()
        self.assertTrue(second['success'])
        self.assertIn(movie_b.pk, self._ids(second))
        self.assertIn(movie_a.pk, self._ids(second))

    def test_edited_movie_is_reflected_after_save(self):
        """Editar el anio de una pelicula reordena la home sin esperar al TTL."""
        movie = self._create_movie('Movie A', 2001, self.genre)
        self.assertIn(movie.pk, self._ids(get_home_movies()))

        movie.release_year = 2031
        movie.save()

        refreshed = self._ids(get_home_movies())
        self.assertIn(movie.pk, refreshed)
        # La ordenacion se recalcula contra la BD, no contra la lista cacheada.
        home = list(get_home_movies()['movies'])
        self.assertEqual(home[0].pk, movie.pk)

    def test_new_movie_appears_in_genre_after_save(self):
        """``get_all_movies_of_genre`` se invalida tambien."""
        movie_a = self._create_movie('Movie A', 2001, self.genre)

        first = get_all_movies_of_genre(self.genre.name)
        self.assertTrue(first['success'])
        self.assertIn(movie_a.pk, self._ids(first))
        self.assertIsNotNone(cache.get(_all_movies_genre_key(self.genre.name)))

        movie_b = self._create_movie('Movie B', 2002, self.genre)

        second = get_all_movies_of_genre(self.genre.name)
        self.assertIn(movie_b.pk, self._ids(second))
        self.assertIn(movie_a.pk, self._ids(second))

    def test_new_movie_appears_in_recommendations_after_save(self):
        """``get_genre_recommendations`` se invalida (clave con ``limit``)."""
        user = User.objects.create_user(username='critic', password='pw12345')
        movie_a = self._create_movie('Movie A', 2001, self.genre)
        Rating.objects.create(movie=movie_a, user=user, score=8)

        first = get_genre_recommendations(self.genre.name, limit=10)
        self.assertTrue(first['success'])
        self.assertIn(movie_a.pk, self._ids(first, 'recommendations'))

        movie_b = self._create_movie('Movie B', 2002, self.genre)
        user_b = User.objects.create_user(username='critic2', password='pw12345')
        Rating.objects.create(movie=movie_b, user=user_b, score=9)

        second = get_genre_recommendations(self.genre.name, limit=10)
        self.assertIn(movie_b.pk, self._ids(second, 'recommendations'))

    def test_genre_recommendations_invalidated_for_every_limit_variant(self):
        """Todas las variantes de ``limit`` se borran a la vez (no son reconstruibles)."""
        movie_a = self._create_movie('Movie A', 2001, self.genre)
        user = User.objects.create_user(username='critic', password='pw12345')
        Rating.objects.create(movie=movie_a, user=user, score=7)

        limits = (1, 5, 10)
        keys = [_genre_recommendations_key(self.genre.name, limit) for limit in limits]
        for limit in limits:
            self.assertTrue(get_genre_recommendations(self.genre.name, limit=limit)['success'])
        for key in keys:
            self.assertIsNotNone(cache.get(key), f'la variante {key} deberia estar cacheada')

        invalidate_movie_caches([self.genre.name])

        for key in keys:
            self.assertIsNone(cache.get(key), f'la variante {key} deberia estar invalidada')

    def test_deleting_movie_removes_it_from_cache(self):
        """Al borrar una pelicula se borran sus claves, no se espera al TTL."""
        movie = self._create_movie('Movie A', 2001, self.genre)
        keep = self._create_movie('Movie B', 2002, self.genre)

        self.assertIn(movie.pk, self._ids(get_home_movies()))
        self.assertIn(movie.pk, self._ids(get_all_movies_of_genre(self.genre.name)))
        self.assertIsNotNone(cache.get(HOME_KEY))
        self.assertIsNotNone(cache.get(_all_movies_genre_key(self.genre.name)))

        movie.delete()

        # Las claves desaparecen (no se sirven ids de una fila inexistente).
        self.assertIsNone(cache.get(HOME_KEY))
        self.assertIsNone(cache.get(_all_movies_genre_key(self.genre.name)))

        home_ids = self._ids(get_home_movies())
        self.assertNotIn(movie.pk, home_ids)
        self.assertIn(keep.pk, home_ids)
        genre_ids = self._ids(get_all_movies_of_genre(self.genre.name))
        self.assertNotIn(movie.pk, genre_ids)
        self.assertIn(keep.pk, genre_ids)

    def test_genre_change_invalidates_genre_caches(self):
        """Anadir el genero despues de guardar tambien invalida (m2m)."""
        movie = self._create_movie('Movie A', 2001)  # sin generos todavia
        self.assertNotIn(movie.pk, self._ids(get_all_movies_of_genre(self.genre.name)))

        movie.genres.add(self.genre)

        self.assertIn(movie.pk, self._ids(get_all_movies_of_genre(self.genre.name)))
        # Solo se invalida el genero afectado: el otro sigue cacheado.
        get_all_movies_of_genre(self.other_genre.name)
        other_key = _all_movies_genre_key(self.other_genre.name)
        self.assertIsNotNone(cache.get(other_key))
        movie.title = 'Movie A (editada)'
        movie.save()
        self.assertIsNotNone(cache.get(other_key))
        self.assertIsNone(cache.get(HOME_KEY))


class RatingWriteInvalidationTests(CacheInvalidationTestCase):
    """``create_rating`` / ``delete_rating`` deben invalidar la cache."""

    def test_new_rating_invalidates_home_cache(self):
        """Una valoracion nueva cambia media y conteo: la cache debe caer."""
        movie = self._create_movie('Movie A', 2001, self.genre)
        user = User.objects.create_user(username='rater', password='pw12345')

        self.assertIn(movie.pk, self._ids(get_home_movies()))
        self.assertIsNotNone(cache.get(HOME_KEY))
        get_all_movies_of_genre(self.genre.name)
        self.assertIsNotNone(cache.get(_all_movies_genre_key(self.genre.name)))

        result = create_rating(user, movie, 9)
        self.assertTrue(result['success'])

        self.assertIsNone(cache.get(HOME_KEY))
        self.assertIsNone(cache.get(_all_movies_genre_key(self.genre.name)))
        # La media se recalcula al vuelo, no desde la cache.
        refreshed = {m.pk: m.average_rating for m in get_home_movies()['movies']}
        self.assertEqual(refreshed[movie.pk], 9.0)

    def test_deleted_rating_invalidates_home_cache(self):
        """``delete_rating`` tambien invalida."""
        movie = self._create_movie('Movie A', 2001, self.genre)
        user = User.objects.create_user(username='rater', password='pw12345')
        create_rating(user, movie, 4)

        self._ids(get_home_movies())
        self.assertIsNotNone(cache.get(HOME_KEY))

        from movies.services.rating_service import delete_rating
        result = delete_rating(user, movie)
        self.assertTrue(result['success'])

        self.assertIsNone(cache.get(HOME_KEY))
        self.assertIsNone(get_home_movies()['movies'].first().average_rating)

    def test_favorites_do_not_affect_cached_lists(self):
        """Los favoritos no dependen de ninguna clave cacheada (sin invalidacion)."""
        from movies.services.favorite_service import add_favorite, get_user_favorites

        movie = self._create_movie('Movie A', 2001, self.genre)
        user = User.objects.create_user(username='fan', password='pw12345')

        self._ids(get_home_movies())
        home_key_before = cache.get(HOME_KEY)

        self.assertTrue(add_favorite(user, movie)['success'])

        # Sin invalidacion: la cache sigue caliente (a proposito, no la depende).
        self.assertEqual(cache.get(HOME_KEY), home_key_before)
        self.assertEqual(len(get_user_favorites(user)['favorites']), 1)


class CacheStillWorksTests(CacheInvalidationTestCase):
    """La cache debe seguir effective (criterio de rendimiento 2.2)."""

    def test_cache_still_hits_on_second_call(self):
        """La segunda llamada se sirve desde cache y no vuelve a guardar."""
        self._create_movie('Movie A', 2001, self.genre)
        counter = _CountingCache(cache)

        with mock.patch.object(movie_service, 'cache', counter):
            first = get_home_movies()
            self.assertTrue(first['success'])
            self.assertEqual(counter.get_calls, 1)
            self.assertEqual(counter.set_calls, 1)
            self.assertIsNotNone(cache.get(HOME_KEY))
            cached_value = cache.get(HOME_KEY)

            second = get_home_movies()
            self.assertTrue(second['success'])

        # Segunda llamada: lee la cache y no vuelve a ejecutar cache.set().
        self.assertEqual(counter.get_calls, 2)
        self.assertEqual(counter.set_calls, 1)
        self.assertEqual(self._ids(first), self._ids(second))
        # La entrada sigue en la cache (no se expiro ni se limpio sola).
        self.assertEqual(cache.get(HOME_KEY), cached_value)

    def test_genre_cache_still_hits_on_second_call(self):
        """Idem para las claves por genero."""
        self._create_movie('Movie A', 2001, self.genre)
        counter = _CountingCache(cache)
        key = _all_movies_genre_key(self.genre.name)

        with mock.patch.object(movie_service, 'cache', counter):
            get_all_movies_of_genre(self.genre.name)
            self.assertEqual(counter.set_calls, 1)
            get_all_movies_of_genre(self.genre.name)
            self.assertEqual(counter.get_calls, 2)
            self.assertEqual(counter.set_calls, 1)
            self.assertIsNotNone(cache.get(key))


class InvalidateMovieCachesTests(CacheInvalidationTestCase):
    """Contrato de ``invalidate_movie_caches``."""

    def test_invalidate_movie_caches_is_safe_to_call_repeatedly(self):
        """Idempotente: llamarla varias veces (o sin claves) no rompe nada."""
        movie = self._create_movie('Movie A', 2001, self.genre)
        get_home_movies()
        get_all_movies_of_genre(self.genre.name)
        get_genre_recommendations(self.genre.name, limit=10)

        for _ in range(3):
            invalidate_movie_caches([self.genre.name])
        invalidate_movie_caches()
        invalidate_movie_caches(None)
        invalidate_movie_caches([])

        self.assertIsNone(cache.get(HOME_KEY))
        self.assertIsNone(cache.get(_all_movies_genre_key(self.genre.name)))
        # Y la cache sigue siendo utilizable despues de invalidar en vacio.
        self.assertIn(movie.pk, self._ids(get_home_movies()))
        self.assertIsNotNone(cache.get(HOME_KEY))

    def test_invalidate_without_genre_names_only_clears_home(self):
        """Sin ``genre_names`` solo se borra la clave global."""
        self._create_movie('Movie A', 2001, self.genre)
        get_home_movies()
        get_all_movies_of_genre(self.genre.name)
        genre_key = _all_movies_genre_key(self.genre.name)

        invalidate_movie_caches()

        self.assertIsNone(cache.get(HOME_KEY))
        self.assertIsNotNone(cache.get(genre_key))

    def test_invalidate_unknown_genre_is_a_noop(self):
        """Un genero sin claves cacheadas no provoca errores."""
        self._create_movie('Movie A', 2001, self.genre)
        get_home_movies()
        home_value = cache.get(HOME_KEY)

        invalidate_movie_caches(['Genero Que No Existe'])

        self.assertIsNone(cache.get(HOME_KEY))
        self.assertNotEqual(home_value, None)
