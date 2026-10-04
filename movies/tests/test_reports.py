"""
Tests para la funcionalidad de reportes y estadisticas.

Contrato actual de los servicios (``movies/services/report_service.py``):

* ``get_rating_stats()`` -> sin argumentos. Devuelve ``total_ratings``,
  ``average_rating``, ``max_rating``, ``min_rating`` y ``ratings_per_movie``.
  No acepta ``movie=`` ni expone ``total_users`` / ``total_movies``.
* ``get_user_stats(user)`` -> devuelve ``rating_count``, ``average_rating``,
  ``favorite_count``, ``most_rated_genre``, ``highest_rating`` y
  ``lowest_rating``. No expone ``total_ratings`` ni ``rated_movies``.
* ``get_revenue_estimate()`` -> sin argumentos. Devuelve ``total_movies``,
  ``avg_revenue_estimate`` y ``top_rated_movies``.

Ademas, ``movies:stats`` esta protegida con ``@staff_member_required``, asi que
para ver el 200 hace falta un usuario ``is_staff``, no solo autenticado.
"""

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from movies.models import Favorite, Genre, Movie, Rating
from movies.services import get_rating_stats, get_revenue_estimate, get_user_stats


class RatingStatsTest(TestCase):
    """Tests para las estadisticas de calificaciones."""

    def setUp(self):
        self.user1 = User.objects.create_user(username='user1', password='pass')
        self.user2 = User.objects.create_user(username='user2', password='pass')
        self.movie1 = Movie.objects.create(title='Movie 1', release_year=2020)
        self.movie2 = Movie.objects.create(title='Movie 2', release_year=2019)
        self.gen = Genre.objects.create(name='Action')
        self.movie1.genres.add(self.gen)
        Rating.objects.create(user=self.user1, movie=self.movie1, score=5)
        Rating.objects.create(user=self.user2, movie=self.movie1, score=3)
        Rating.objects.create(user=self.user1, movie=self.movie2, score=4)

    def test_get_rating_stats_all(self):
        """Debe retornar estadisticas globales."""
        stats = get_rating_stats()
        self.assertEqual(stats['total_ratings'], 3)
        self.assertEqual(stats['average_rating'], 4.0)
        self.assertEqual(stats['max_rating'], 5)
        self.assertEqual(stats['min_rating'], 3)

    def test_get_rating_stats_per_movie_counts(self):
        """Debe desglosar el numero de valoraciones por pelicula."""
        stats = get_rating_stats()
        by_movie = {row['movie__title']: row['count'] for row in stats['ratings_per_movie']}
        self.assertEqual(by_movie['Movie 1'], 2)
        self.assertEqual(by_movie['Movie 2'], 1)

    def test_get_rating_stats_single_rating(self):
        """Debe manejar una sola calificacion."""
        Rating.objects.all().delete()
        Rating.objects.create(user=self.user1, movie=self.movie2, score=4)
        stats = get_rating_stats()
        self.assertEqual(stats['total_ratings'], 1)
        self.assertEqual(stats['average_rating'], 4.0)
        self.assertEqual(stats['max_rating'], 4)
        self.assertEqual(stats['min_rating'], 4)

    def test_get_rating_stats_empty(self):
        """Debe manejar una base de datos sin calificaciones.

        Sin valoraciones no hay media que promediar, asi que ``average_rating``
        es ``None`` (no 0) y los extremos caen a 0.
        """
        Rating.objects.all().delete()
        Movie.objects.create(title='No Ratings', release_year=2018)
        stats = get_rating_stats()
        self.assertEqual(stats['total_ratings'], 0)
        self.assertIsNone(stats['average_rating'])
        self.assertEqual(stats['max_rating'], 0)
        self.assertEqual(stats['min_rating'], 0)
        self.assertEqual(stats['ratings_per_movie'], [])


class UserStatsTest(TestCase):
    """Tests para las estadisticas por usuario."""

    def setUp(self):
        self.user1 = User.objects.create_user(username='user1', password='pass')
        self.user2 = User.objects.create_user(username='user2', password='pass')
        self.movie1 = Movie.objects.create(title='Movie 1', release_year=2020)
        self.movie2 = Movie.objects.create(title='Movie 2', release_year=2019)
        self.movie3 = Movie.objects.create(title='Movie 3', release_year=2018)
        Rating.objects.create(user=self.user1, movie=self.movie1, score=5)
        Rating.objects.create(user=self.user1, movie=self.movie2, score=3)
        Rating.objects.create(user=self.user2, movie=self.movie1, score=4)
        Favorite.objects.create(user=self.user1, movie=self.movie3)

    def test_get_user_stats_existing_user(self):
        """Debe retornar estadisticas de usuario existente."""
        stats = get_user_stats(self.user1)
        self.assertEqual(stats['rating_count'], 2)
        self.assertEqual(stats['average_rating'], 4.0)
        self.assertEqual(stats['highest_rating'], 5)
        self.assertEqual(stats['lowest_rating'], 3)
        self.assertEqual(stats['favorite_count'], 1)

    def test_get_user_stats_no_ratings(self):
        """Debe manejar usuario sin calificaciones."""
        stats = get_user_stats(self.user2)
        self.assertEqual(stats['rating_count'], 1)
        self.assertEqual(stats['average_rating'], 4.0)

    def test_get_user_stats_user_without_any_activity(self):
        """Un usuario sin valoraciones ni favoritos devuelve todo a cero."""
        User.objects.create_user(username='user3', password='pass')
        stats = get_user_stats(User.objects.get(username='user3'))
        self.assertEqual(stats['rating_count'], 0)
        self.assertIsNone(stats['average_rating'])
        self.assertEqual(stats['favorite_count'], 0)
        self.assertEqual(stats['highest_rating'], 0)
        self.assertEqual(stats['lowest_rating'], 0)
        self.assertIsNone(stats['most_rated_genre'])

    def test_get_user_stats_unknown_user(self):
        """Debe retornar ceros para usuario inexistente (``None``)."""
        stats = get_user_stats(None)
        self.assertIsInstance(stats, dict)
        self.assertEqual(stats['rating_count'], 0)
        self.assertIsNone(stats['average_rating'])
        self.assertEqual(stats['favorite_count'], 0)

    def test_get_user_stats_most_rated_genre(self):
        """El genero mas valorado sale de los generos de las peliculas valoradas."""
        action = Genre.objects.create(name='Action')
        self.movie1.genres.add(action)
        self.movie2.genres.add(action)
        self.assertEqual(get_user_stats(self.user1)['most_rated_genre'], 'Action')


class RevenueEstimateTest(TestCase):
    """Tests para la estimacion de ingresos."""

    def setUp(self):
        self.user1 = User.objects.create_user(username='user1', password='pass')
        self.user2 = User.objects.create_user(username='user2', password='pass')
        self.movie = Movie.objects.create(title='Movie 1', release_year=2020)
        Rating.objects.create(user=self.user1, movie=self.movie, score=5)
        Rating.objects.create(user=self.user2, movie=self.movie, score=3)

    def test_get_revenue_estimate_existing_movie(self):
        """Debe estimar ingresos a partir de la media de las valoraciones."""
        revenue = get_revenue_estimate()
        self.assertEqual(revenue['total_movies'], 1)
        # Media 4.0 * 1_000_000
        self.assertEqual(revenue['avg_revenue_estimate'], 4000000.0)
        self.assertEqual(len(revenue['top_rated_movies']), 1)
        top = revenue['top_rated_movies'][0]
        self.assertEqual(top['title'], 'Movie 1')
        self.assertEqual(top['avg_rating'], 4.0)
        self.assertEqual(top['rating_count'], 2)

    def test_get_revenue_estimate_no_ratings(self):
        """Sin valoraciones no hay estimacion, aunque existan peliculas."""
        Rating.objects.all().delete()
        Movie.objects.create(title='No Ratings', release_year=2021)
        revenue = get_revenue_estimate()
        self.assertEqual(revenue['total_movies'], 2)
        self.assertEqual(revenue['avg_revenue_estimate'], 0.0)
        self.assertEqual(revenue['top_rated_movies'], [])

    def test_get_revenue_estimate_empty(self):
        """Debe retornar ceros cuando no hay nada en la base de datos."""
        Movie.objects.all().delete()
        Rating.objects.all().delete()
        revenue = get_revenue_estimate()
        self.assertEqual(revenue['total_movies'], 0)
        self.assertEqual(revenue['avg_revenue_estimate'], 0.0)
        self.assertEqual(revenue['top_rated_movies'], [])


class StatsViewTest(TestCase):
    """Tests para la vista de estadisticas (``@staff_member_required``)."""

    def setUp(self):
        self.user1 = User.objects.create_user(username='user1', password='pass')
        self.staff = User.objects.create_user(
            username='staffer', password='pass', is_staff=True
        )
        self.plain_user = User.objects.create_user(
            username='plain', password='pass'
        )
        self.movie1 = Movie.objects.create(title='Movie 1', release_year=2020)
        self.movie2 = Movie.objects.create(title='Movie 2', release_year=2019)
        Rating.objects.create(user=self.user1, movie=self.movie1, score=5)
        Rating.objects.create(user=self.user1, movie=self.movie2, score=3)

    def test_stats_view_staff_authenticated(self):
        """Debe mostrar estadisticas a un usuario staff autenticado."""
        self.client.login(username='staffer', password='pass')
        response = self.client.get(reverse('movies:stats'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'movies/stats.html')
        self.assertContains(response, 'Estadisticas Generales de Valoraciones')
        self.assertContains(response, 'Movie 1')

    def test_stats_view_unauthenticated(self):
        """Debe redirigir a login si no autenticado."""
        response = self.client.get(reverse('movies:stats'))
        self.assertEqual(response.status_code, 302)

    def test_stats_view_non_staff_redirects(self):
        """Autenticado pero sin ``is_staff`` tampoco pasa el guard de admin."""
        self.client.login(username='plain', password='pass')
        response = self.client.get(reverse('movies:stats'))
        self.assertEqual(response.status_code, 302)

    def test_stats_view_user_section(self):
        """Un usuario normal autenticado sigue sin ver la seccion de usuario.

        La vista exige ``is_staff``, asi que este test fija que el guard de admin
        se aplica antes que cualquier Consideracion sobre el usuario.
        """
        self.client.login(username='user1', password='pass')
        response = self.client.get(reverse('movies:stats'))
        # user1 no es staff: la vista redirige.
        self.assertEqual(response.status_code, 302)

    def test_stats_view_user_section_for_staff_with_ratings(self):
        """La seccion de usuario se renderiza con los datos de quien mira."""
        self.staff.is_staff = True
        self.staff.save()
        Rating.objects.create(user=self.staff, movie=self.movie1, score=7)
        self.client.login(username='staffer', password='pass')

        response = self.client.get(reverse('movies:stats'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Estadisticas de Usuario')
        self.assertContains(response, 'Genero mas valorado')
        # rating_count del propio staffer: 1 valoracion, media 7.0.
        self.assertEqual(response.context['user_stats']['rating_count'], 1)
        self.assertEqual(response.context['user_stats']['average_rating'], 7.0)
