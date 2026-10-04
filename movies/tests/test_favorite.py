"""
Tests para la funcionalidad de favoritos.
"""

from django.contrib.auth.models import AnonymousUser, User
from django.test import TestCase
from django.urls import reverse

from movies.models import Favorite, Movie, Genre
from movies.services import add_favorite, get_user_favorites, get_user_favorite_count, is_favorite, remove_favorite


class FavoriteViewTest(TestCase):
    """Tests para la vista de favoritos."""

    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='pass')
        self.genre = Genre.objects.create(name='Action')
        self.movie = Movie.objects.create(title='Test Movie', release_year=2020)
        self.movie.genres.add(self.genre)

    def test_favorite_requires_authentication(self):
        """Debe redirigir si el usuario no esta autenticado."""
        response = self.client.post(reverse('movies:favorite', args=[self.movie.id]))
        self.assertEqual(response.status_code, 302)
        self.assertIn('login', response.url)

    def test_favorite_add(self):
        """Debe agregar a favoritos."""
        self.client.login(username='testuser', password='pass')
        response = self.client.post(reverse('movies:favorite', args=[self.movie.id]))
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Favorite.objects.filter(user=self.user, movie=self.movie).exists())

    def test_favorite_remove(self):
        """Debe eliminar de favoritos."""
        self.client.login(username='testuser', password='pass')
        Favorite.objects.create(user=self.user, movie=self.movie)
        response = self.client.post(reverse('movies:favorite', args=[self.movie.id]))
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Favorite.objects.filter(user=self.user, movie=self.movie).exists())

    def test_favorite_movie_not_found(self):
        """Debe manejar pelicula no encontrada.

        La vista ya esta autenticada, asi que no redirige a 'login': avisa con
        un mensaje y vuelve a la home (la app esta montada en '/', no en
        '/movies/').
        """
        self.client.login(username='testuser', password='pass')
        response = self.client.post(reverse('movies:favorite', args=[999999]))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('movies:home'))

        followed = self.client.get(response.url)
        rendered = [str(m) for m in followed.context['messages']]
        self.assertIn('Pelicula no encontrada.', rendered)


class FavoriteServiceTest(TestCase):
    """Tests para los servicios de favoritos."""

    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='pass')
        self.movie = Movie.objects.create(title='Test Movie', release_year=2020)

    def test_add_favorite(self):
        """Debe agregar una pelicula a favoritos."""
        result = add_favorite(self.user, self.movie)
        self.assertTrue(result['success'])
        self.assertTrue(Favorite.objects.filter(user=self.user, movie=self.movie).exists())

    def test_add_favorite_duplicate(self):
        """Debe manejar agregar favorito duplicado."""
        add_favorite(self.user, self.movie)
        result = add_favorite(self.user, self.movie)
        self.assertFalse(result['success'])

    def test_remove_favorite(self):
        """Debe eliminar una pelicula de favoritos."""
        fav = Favorite.objects.create(user=self.user, movie=self.movie)
        result = remove_favorite(self.user, self.movie)
        self.assertTrue(result['success'])
        self.assertFalse(Favorite.objects.filter(pk=fav.pk).exists())

    def test_remove_favorite_not_exists(self):
        """Debe manejar eliminacion de favorito que no existe."""
        result = remove_favorite(self.user, self.movie)
        self.assertFalse(result['success'])

    def test_is_favorite_true(self):
        """Debe retornar True si es favorito."""
        Favorite.objects.create(user=self.user, movie=self.movie)
        result = is_favorite(self.user, self.movie)
        self.assertTrue(result['is_favorite'])

    def test_is_favorite_false(self):
        """Debe retornar False si no es favorito."""
        result = is_favorite(self.user, self.movie)
        self.assertFalse(result['is_favorite'])

    def test_get_user_favorites(self):
        """Debe retornar los favoritos del usuario."""
        movie2 = Movie.objects.create(title='Movie 2', release_year=2021)
        Favorite.objects.create(user=self.user, movie=self.movie)
        Favorite.objects.create(user=self.user, movie=movie2)
        result = get_user_favorites(self.user)
        self.assertEqual(len(result['favorites']), 2)

    def test_get_user_favorite_count(self):
        """Debe retornar el conteo de favoritos."""
        Movie.objects.create(title='Movie 2', release_year=2021)
        Favorite.objects.create(user=self.user, movie=self.movie)
        Movie.objects.create(title='Movie 3', release_year=2022)
        Favorite.objects.create(user=self.user, movie=Movie.objects.get(title='Movie 3'))
        result = get_user_favorite_count(self.user)
        self.assertEqual(result['count'], 2)

    def test_get_user_favorites_unauthenticated(self):
        """Debe retornar lista vacia para usuario no autenticado.

        ``User.is_authenticated`` es una propiedad de solo lectura: para
        representar a un visitante sin sesion hay que usar ``AnonymousUser``.
        """
        result = get_user_favorites(AnonymousUser())
        self.assertEqual(result['favorites'], [])

    def test_add_favorite_unauthenticated(self):
        """Debe rechadar agregar favorito sin autenticacion."""
        result = add_favorite(AnonymousUser(), self.movie)
        self.assertFalse(result['success'])
