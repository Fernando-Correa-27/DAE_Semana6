"""
Tests para la funcionalidad de busqueda y filtrado.
"""

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from movies.forms import SearchForm
from movies.models import Genre, Movie
from movies.services import search_movies, filter_movies


class SearchViewTest(TestCase):
    """Tests para la vista de busqueda."""

    def setUp(self):
        self.action_genre = Genre.objects.create(name='Action')
        self.comedy_genre = Genre.objects.create(name='Comedy')
        self.movie1 = Movie.objects.create(title='The Matrix', release_year=1999)
        self.movie1.genres.add(self.action_genre)
        self.movie2 = Movie.objects.create(title='The Hangover', release_year=2009)
        self.movie2.genres.add(self.comedy_genre)
        self.movie3 = Movie.objects.create(title='Dark Knight', release_year=2008)
        self.movie3.genres.add(self.action_genre)

    def test_search_view_basic(self):
        """Debe mostrar la pagina de busqueda."""
        response = self.client.get(reverse('movies:search'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Buscar Peliculas')

    def test_search_by_title(self):
        """Debe buscar por titulo."""
        response = self.client.get(reverse('movies:search'), {'q': 'Matrix'})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'The Matrix')
        self.assertNotContains(response, 'The Hangover')

    def test_search_case_insensitive(self):
        """La busqueda debe ser insensible a mayusculas."""
        response = self.client.get(reverse('movies:search'), {'q': 'matrix'})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'The Matrix')

    def test_search_no_results(self):
        """Debe mostrar mensaje cuando no hay resultados."""
        response = self.client.get(reverse('movies:search'), {'q': 'NonExistent'})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'No se encontraron peliculas')

    def test_search_too_short(self):
        """No debe buscar con query menor a 2 caracteres."""
        response = self.client.get(reverse('movies:search'), {'q': 'A'})
        self.assertEqual(response.status_code, 200)


class SearchFilterTest(TestCase):
    """Tests para el filtrado de peliculas."""

    def setUp(self):
        self.action_genre = Genre.objects.create(name='Action')
        self.comedy_genre = Genre.objects.create(name='Comedy')
        self.user1 = User.objects.create_user(username='user1', password='pass')
        self.user2 = User.objects.create_user(username='user2', password='pass')
        self.movie1 = Movie.objects.create(title='Action Movie', release_year=2020)
        self.movie1.genres.add(self.action_genre)
        self.movie2 = Movie.objects.create(title='Comedy Movie', release_year=2015)
        self.movie2.genres.add(self.comedy_genre)
        self.movie3 = Movie.objects.create(title='Old Action', release_year=1990)
        self.movie3.genres.add(self.action_genre)

    def test_filter_by_genre(self):
        """Debe filtrar por genero.

        ``filter_movies`` devuelve un dict; el queryset va en la clave 'movies'.
        """
        results = filter_movies(genres=['Action'])
        self.assertTrue(results['success'])
        movies = results['movies']
        self.assertEqual(movies.count(), 2)
        self.assertIn(self.movie1, movies)
        self.assertIn(self.movie3, movies)

    def test_filter_by_year_range(self):
        """Debe filtrar por rango de anos."""
        results = filter_movies(year_min=2000, year_max=2025)
        self.assertTrue(results['success'])
        movies = results['movies']
        self.assertEqual(movies.count(), 2)
        self.assertIn(self.movie1, movies)
        self.assertIn(self.movie2, movies)

    def test_filter_multiple_genres(self):
        """Debe filtrar por multiples generos."""
        results = filter_movies(genres=['Action', 'Comedy'])
        self.assertTrue(results['success'])
        self.assertEqual(results['movies'].count(), 3)

    def test_search_movies_basic(self):
        """Debe buscar peliculas por titulo.

        ``'Action'`` aparece en dos titulos del setUp ('Action Movie' y
        'Old Action'), asi que ``icontains`` devuelve los dos. La expectativa
        anterior de 1 resultado no era compatible con estos datos.
        """
        results = search_movies('Action')
        self.assertTrue(results['success'])
        titles = {m.title for m in results['movies']}
        self.assertEqual(titles, {'Action Movie', 'Old Action'})

    def test_search_movies_empty(self):
        """Debe retornar queryset vacio para query vacia."""
        results = search_movies('')
        self.assertTrue(results['success'])
        self.assertEqual(results['movies'].count(), 0)

    def test_search_movies_case_insensitive(self):
        """La busqueda debe ser insensible a mayusculas."""
        results = search_movies('action')
        self.assertTrue(results['success'])
        titles = {m.title for m in results['movies']}
        self.assertEqual(titles, {'Action Movie', 'Old Action'})


class SearchFormTest(TestCase):
    """Tests para el formulario de busqueda."""

    def test_search_form_valid(self):
        """Debe ser valido con query valida."""
        form = SearchForm(data={'q': 'Matrix'})
        self.assertTrue(form.is_valid())

    def test_search_form_too_short(self):
        """Debe ser invalido con query menor a 2 caracteres."""
        form = SearchForm(data={'q': 'A'})
        self.assertFalse(form.is_valid())

    def test_search_form_empty(self):
        """Debe ser invalido con query vacia."""
        form = SearchForm(data={'q': ''})
        self.assertFalse(form.is_valid())
