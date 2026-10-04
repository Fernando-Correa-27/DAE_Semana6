"""
Tests de invalidacion de la cache de busqueda y filtrado.

``movies/services/search_service.py`` memoiza los *ids* devueltos por
``search_movies()`` y ``filter_movies()`` bajo claves que dependen solo de los
parametros de la consulta (``search:<md5>`` / ``filter:<md5>``), con un TTL de
5 minutos. Estos tests comprueban que cualquier escritura de una pelicula
(crear, renombrar, editar el anio, borrar) invalida esas claves - y que la cache
sigue siendo efectiva cuando no hay escrituras (criterio de rendimiento 2.2).

Se ejecutan con el label explicito (el descubrimiento de ``movies/tests/``
depende de la infraestructura):

    .\\venv\\Scripts\\python.exe manage.py test movies.tests.test_search_cache_invalidation -v 2
"""

from unittest import mock

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse

from movies.models import Genre, Movie
from movies.services import search_service
from movies.services.cache_registry import tracked_keys_for
from movies.services.search_service import (
    _FILTER_SCOPE,
    _SEARCH_SCOPE,
    _cache_key,
    _filter_cache_key,
    _search_cache_key,
    filter_movies,
    invalidate_search_caches,
    search_movies,
)
from movies.services.rating_service import create_rating

User = get_user_model()


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

    def clear(self):
        return self._real.clear()


class SearchCacheInvalidationTestCase(TestCase):
    """Base: cache limpia en cada test para que no dependan del orden."""

    def setUp(self):
        cache.clear()
        self.addCleanup(cache.clear)
        self.genre = Genre.objects.create(name='Action')

    # -- helpers ----------------------------------------------------------
    def _create_movie(self, title='Movie', year=2020, genre=None, **extra):
        movie = Movie.objects.create(title=title, release_year=year, **extra)
        if genre is not None:
            movie.genres.add(genre)
        return movie

    @staticmethod
    def _ids(result, key='movies'):
        return list(result[key].values_list('pk', flat=True))

    @staticmethod
    def _search_ids(query):
        return list(search_movies(query)['movies'].values_list('pk', flat=True))

    @staticmethod
    def _filter_ids(**kwargs):
        return list(filter_movies(**kwargs)['movies'].values_list('pk', flat=True))


class SearchWriteInvalidationTests(SearchCacheInvalidationTestCase):
    """``Movie.save()`` / ``Movie.delete()`` deben invalidar las claves de busqueda."""

    def test_new_movie_appears_in_search_after_save(self):
        """Regresion: una pelicula nueva no puede quedar oculta hasta 5 minutos.

        Sin invalidacion, la clave ya cacheada con la lista vacia se sigue
        sirviendo y ``/search/`` no muestra la pelicula recien creada.
        """
        # 1. La busqueda se cachea vacia (id list = []).
        self.assertEqual(self._search_ids('Zeta'), [])
        key = _search_cache_key('Zeta')
        self.assertIsNotNone(cache.get(key), 'la clave de busqueda deberia estar cacheada')

        # 2. Se crea una pelicula que coincide con el termino. Sin tocar el TTL,
        #    solo la invalidacion puede hacer visible la nueva.
        movie = self._create_movie('Zeta Dawn', 2021)

        self.assertIn(movie.pk, self._search_ids('Zeta'))
        self.assertEqual(list(search_movies('Zeta')['movies'].values_list('title', flat=True)),
                         ['Zeta Dawn'])

    def test_renamed_movie_appears_under_new_title(self):
        """Regresion: al renombrar, la busqueda del titulo nuevo debe responder.

        Y la del titulo viejo debe dejar de responder en el mismo momento: si la
        clave cacheada sobrevive, ``search_movies('alfa')`` sigue devolviendo el
        id de la pelicula renombrada.
        """
        movie = self._create_movie('Alfa', 2001)

        self.assertIn(movie.pk, self._search_ids('alfa'))          # cache caliente
        self.assertIsNotNone(cache.get(_search_cache_key('alfa')))

        movie.title = 'Beta'
        movie.save()

        # Las dos claves caen: la del termino viejo y la del nuevo, que todavia
        # no se habia generado (se genera al buscar, ya con el dato fresco).
        self.assertIsNone(cache.get(_search_cache_key('alfa')))
        self.assertIsNone(cache.get(_search_cache_key('beta')))

        self.assertIn(movie.pk, self._search_ids('beta'))
        self.assertEqual(list(search_movies('beta')['movies'].values_list('title', flat=True)),
                         ['Beta'])
        self.assertNotIn(movie.pk, self._search_ids('alfa'))

    def test_deleted_movie_disappears_from_search(self):
        """Regresion: al borrar se dropea la clave, no se espera al TTL."""
        movie = self._create_movie('Alfa', 2001)
        keep = self._create_movie('Alfa Dos', 2002)

        self.assertEqual(set(self._search_ids('Alfa')), {movie.pk, keep.pk})
        key = _search_cache_key('Alfa')
        self.assertIsNotNone(cache.get(key), 'la clave de busqueda deberia estar cacheada')

        movie.delete()

        # La clave desaparece: no se siguen sirviendo ids de una fila inexistente.
        self.assertIsNone(cache.get(key))
        self.assertEqual(self._search_ids('Alfa'), [keep.pk])

    def test_every_tracked_search_key_is_dropped_on_write(self):
        """Varias busquedas pendientes se limpian todas de una vez.

        Los terminos buscados no son reconstruibles desde la clave (van
        hasheados), asi que la invalidacion usa el registro de claves: se
        borran todas las variantes generadas, no solo la ultima.
        """
        self._create_movie('Alfa', 2001)
        terms = ('Alfa', 'alfa', 'ALF', 'Al')
        for term in terms:
            self._search_ids(term)
        keys = [_search_cache_key(term) for term in terms]
        for key in keys:
            self.assertIsNotNone(cache.get(key))
        # Las cuatro son claves distintas y las cuatro estan en el registro.
        self.assertEqual(len(set(keys)), len(terms))
        self.assertTrue(set(keys) <= tracked_keys_for((_SEARCH_SCOPE, _FILTER_SCOPE)))

        self._create_movie('Alfa Dos', 2002)

        for term, key in zip(terms, keys):
            self.assertIsNone(cache.get(key), f'la clave de "{term}" deberia estar invalidada')
        self.assertEqual(tracked_keys_for((_SEARCH_SCOPE,)) & set(keys), set())
        # Y la cache se vuelve a poblar con los datos frescos.
        self.assertEqual(len(self._search_ids('Alfa')), 2)
        self.assertIsNotNone(cache.get(keys[0]))

    def test_synopsis_only_edit_also_drops_the_search_key(self):
        """Cualquier ``save()`` invalida, no solo los cambios de titulo/ano."""
        movie = self._create_movie('Alfa', 2001)
        self._search_ids('Alfa')
        self.assertIsNotNone(cache.get(_search_cache_key('Alfa')))

        movie.synopsis = 'Una sinopsis nueva.'
        movie.save()

        self.assertIsNone(cache.get(_search_cache_key('Alfa')))
        self.assertIn(movie.pk, self._search_ids('Alfa'))

    def test_bulk_delete_also_invalidates_search_caches(self):
        """``QuerySet.delete()`` no pasa por ``Movie.delete()`` y aun asi limpia."""
        movie = self._create_movie('Alfa', 2001)
        keep = self._create_movie('Alfa Dos', 2002)
        self._search_ids('Alfa')
        self.assertIsNotNone(cache.get(_search_cache_key('Alfa')))

        Movie.objects.filter(pk=movie.pk).delete()

        self.assertIsNone(cache.get(_search_cache_key('Alfa')))
        self.assertEqual(self._search_ids('Alfa'), [keep.pk])

    def test_search_view_shows_a_movie_created_after_the_first_hit(self):
        """El sintoma de usuario: ``/search/`` deja de estar desactualizado."""
        response = self.client.get(reverse('movies:search'), {'q': 'Zeta'})
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'Zeta Dawn')

        self._create_movie('Zeta Dawn', 2021)

        response = self.client.get(reverse('movies:search'), {'q': 'Zeta'})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Zeta Dawn')


class FilterWriteInvalidationTests(SearchCacheInvalidationTestCase):
    """``filter_movies()`` tambien se invalida (criterios de genero/ano/nota)."""

    def test_filter_cache_invalidated_on_movie_year_change(self):
        """Regresion: cambiar el anio de una pelicula cambia el filtro por rango."""
        movie = self._create_movie('Alfa', 1990)

        # Filtro cacheado sin la pelicula (1990 < 2000).
        self.assertNotIn(movie.pk, self._filter_ids(year_min=2000))
        key = _filter_cache_key(year_min=2000)
        self.assertIsNotNone(cache.get(key), 'la clave de filtrado deberia estar cacheada')

        movie.release_year = 2021
        movie.save()

        # La clave cae antes de volver a leerla ( releerla la volveria a cachear).
        self.assertIsNone(cache.get(key))
        self.assertIn(movie.pk, self._filter_ids(year_min=2000))

    def test_filter_cache_invalidated_on_new_movie(self):
        """Una pelicula nueva entra en un filtro ya cacheado."""
        self._create_movie('Fuera de rango', 2010)  # 2010 > year_max
        self.assertEqual(self._filter_ids(year_min=1900, year_max=2000), [])

        new_movie = self._create_movie('Alfa Dos', 1995)

        self.assertIn(new_movie.pk, self._filter_ids(year_min=1900, year_max=2000))

    def test_filter_cache_invalidated_on_genre_change(self):
        """Anadir un genero despues de guardar cambia el filtro por genero."""
        movie = self._create_movie('Alfa', 2001)  # sin generos todavia
        self.assertEqual(self._filter_ids(genres=['Action']), [])

        movie.genres.add(self.genre)

        self.assertIn(movie.pk, self._filter_ids(genres=['Action']))

    def test_filter_cache_invalidated_on_rating_change(self):
        """``min_rating`` ordena por media: una valoracion nueva cambia el filtro."""
        movie = self._create_movie('Alfa', 2001, self.genre)
        self.assertEqual(self._filter_ids(min_rating=5), [])

        user = User.objects.create_user(username='rater', password='pw12345')
        self.assertTrue(create_rating(user, movie, 9)['success'])

        self.assertIn(movie.pk, self._filter_ids(min_rating=5))

    def test_filter_cache_still_hits_on_second_call(self):
        """La cache de filtrado sigue siendo efectiva (criterio 2.2)."""
        self._create_movie('Alfa', 2001, self.genre)
        counter = _CountingCache(cache)

        with mock.patch.object(search_service, 'cache', counter):
            first = self._filter_ids(genres=['Action'])
            self.assertEqual(counter.set_calls, 1)
            second = self._filter_ids(genres=['Action'])
            self.assertEqual(counter.get_calls, 2)

        self.assertEqual(counter.set_calls, 1, 'la segunda llamada no debe volver a cachear')
        self.assertEqual(first, second)
        self.assertIsNotNone(cache.get(_filter_cache_key(genres=['Action'])))


class SearchCacheStillWorksTests(SearchCacheInvalidationTestCase):
    """La cache debe seguir effective: la invalidacion no la sustituye."""

    def test_search_cache_still_hits_on_second_call(self):
        """La segunda busqueda se sirve desde cache y no vuelve a guardar."""
        self._create_movie('Alfa', 2001, self.genre)
        counter = _CountingCache(cache)

        with mock.patch.object(search_service, 'cache', counter):
            first = self._search_ids('Alfa')
            self.assertEqual(counter.get_calls, 1)
            self.assertEqual(counter.set_calls, 1)

            second = self._search_ids('Alfa')
            self.assertEqual(counter.get_calls, 2)

        # Segunda llamada: lee la cache y no ejecuta cache.set() otra vez.
        self.assertEqual(counter.set_calls, 1)
        self.assertEqual(first, second)
        # La entrada sigue en la cache (no se expiro ni se limpio sola).
        self.assertEqual(cache.get(_search_cache_key('Alfa')), first)

    def test_cache_survives_repeated_reads_without_writes(self):
        """Varias lecturas seguidas reutilizan la misma entrada."""
        self._create_movie('Alfa', 2001, self.genre)
        counter = _CountingCache(cache)

        with mock.patch.object(search_service, 'cache', counter):
            for _ in range(5):
                self.assertEqual(self._search_ids('Alfa'), [Movie.objects.get(title='Alfa').pk])
            filter_movies(genres=['Action'])

        self.assertEqual(counter.set_calls, 2)  # 1 busqueda + 1 filtrado
        self.assertEqual(counter.get_calls, 6)


class InvalidateSearchCachesTests(SearchCacheInvalidationTestCase):
    """Contrato de ``invalidate_search_caches()``."""

    def test_invalidation_is_safe_when_cache_is_empty(self):
        """Sin claves cacheadas, y repetidas veces, no falla ni rompe nada."""
        self._create_movie('Alfa', 2001, self.genre)

        # Cache vacia de entrada (nada se ha leido todavia).
        invalidate_search_caches()
        invalidate_search_caches()

        # Tampoco con la cache ya poblada y luego vaciada a mano.
        self._search_ids('Alfa')
        self._filter_ids(year_min=2000)
        cache.clear()
        invalidate_search_caches()

        # Y la cache sigue siendo utilizable despues de invalidar en vacio.
        self.assertEqual(self._search_ids('Alfa'), [Movie.objects.get(title='Alfa').pk])
        self.assertIsNotNone(cache.get(_search_cache_key('Alfa')))

    def test_invalidation_never_raises_when_the_cache_backend_fails(self):
        """Un backend caido se registra, pero no rompe la escritura que lo pidio."""

        # Hay que sembrar una clave real antes de romper la cache. La rama que se
        # quiere ejercitar es la de ``cache.delete_many``, y esa solo se alcanza si
        # el registro de claves tiene algo que tirar: con el registro vacio
        # ``invalidate_search_caches()`` sale por su ``return`` temprano y no
        # registra ningun WARNING. El registro es un global a nivel de modulo que
        # ``cache.clear()`` no toca, asi que sin esta siembra el test solo pasaba
        # cuando otro test habia cacheado una busqueda antes (fallaba con
        # ``--shuffle=1`` y ``--shuffle=42``).
        self._create_movie('Alfa', 2001, self.genre)
        self._search_ids('Alfa')

        class _BrokenCache:
            def get(self, *args, **kwargs):
                raise RuntimeError('cache backend caido')

            def set(self, *args, **kwargs):
                raise RuntimeError('cache backend caido')

            def delete_many(self, *args, **kwargs):
                raise RuntimeError('cache backend caido')

        with mock.patch.object(search_service, 'cache', _BrokenCache()):
            with self.assertLogs('movies.services.search_service', level='WARNING') as logs:
                self.assertIsNone(invalidate_search_caches())  # no lanza
            self.assertTrue(any('busqueda' in line for line in logs.output))

        # La escritura que dispara la invalidacion tampoco falla.
        self._create_movie('Alfa', 2001)

    def test_invalidation_drops_search_and_filter_keys_together(self):
        """Un solo paso limpia las dos familias de claves."""
        self._create_movie('Alfa', 2001, self.genre)
        self._search_ids('Alfa')
        self._filter_ids(year_min=2000)
        self._filter_ids(genres=['Action'])
        keys = [
            _search_cache_key('Alfa'),
            _filter_cache_key(year_min=2000),
            _filter_cache_key(genres=['Action']),
        ]
        for key in keys:
            self.assertIsNotNone(cache.get(key))

        invalidate_search_caches()

        for key in keys:
            self.assertIsNone(cache.get(key))

    def test_movie_service_keys_are_not_touched_by_search_invalidation(self):
        """La invalidacion de busqueda es independiente de la de listas de home/genero."""
        from movies.services import movie_service
        from movies.services.movie_service import _all_movies_genre_key, _cache_key as movie_key

        self._create_movie('Alfa', 2001, self.genre)
        self._search_ids('Alfa')
        movie_service.get_home_movies()
        movie_service.get_all_movies_of_genre(self.genre.name)
        home_key = movie_key('home_movies')
        genre_key = _all_movies_genre_key(self.genre.name)

        invalidate_search_caches()

        self.assertIsNone(cache.get(_search_cache_key('Alfa')))
        self.assertIsNotNone(cache.get(home_key))
        self.assertIsNotNone(cache.get(genre_key))

    def test_search_key_builders_stay_deterministic(self):
        """Las claves se pueden reconstruir en cualquier momento (mismo md5)."""
        self.assertEqual(_search_cache_key('Alfa'), _cache_key('search', q='Alfa'))
        self.assertEqual(
            _filter_cache_key(['Action', 'Drama'], 2000, 2020, 5.0),
            _cache_key(
                'filter',
                genres='Action,Drama',
                year_min='2000',
                year_max='2020',
                min_rating='5.0',
            ),
        )
        # El orden de los generos no cambia la clave (se normaliza al ordenar).
        self.assertEqual(
            _filter_cache_key(['Drama', 'Action']),
            _filter_cache_key(['Action', 'Drama']),
        )
