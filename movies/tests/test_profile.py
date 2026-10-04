"""
Tests para la funcionalidad de perfil y edicion de usuario.
"""

from django.contrib.auth.models import AnonymousUser, User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from movies.forms import ProfileForm
from movies.models import Movie, Rating
from movies.services import get_user_profile_data, get_user_rating_history, update_profile


class ProfileViewTest(TestCase):
    """Tests para la vista de perfil."""

    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser', password='pass123', email='test@example.com',
            first_name='Test', last_name='User'
        )

    def test_profile_view_requires_authentication(self):
        """Debe redirigir si el usuario no esta autenticado."""
        response = self.client.get(reverse('movies:profile'))
        self.assertEqual(response.status_code, 302)
        self.assertIn('login', response.url)

    def test_profile_view_authenticated(self):
        """Debe mostrar la pagina de perfil para usuarios autenticados."""
        self.client.login(username='testuser', password='pass123')
        response = self.client.get(reverse('movies:profile'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Mi Perfil')

    def test_profile_view_shows_rating_history(self):
        """Debe mostrar el historial de valoraciones."""
        self.client.login(username='testuser', password='pass123')
        movie = Movie.objects.create(title='Test Movie 1', release_year=2020)
        Rating.objects.create(user=self.user, movie=movie, score=8)
        response = self.client.get(reverse('movies:profile'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Test Movie 1')
        self.assertContains(response, '8')

    def test_profile_view_shows_user_data(self):
        """Debe mostrar los datos del usuario."""
        self.client.login(username='testuser', password='pass123')
        response = self.client.get(reverse('movies:profile'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'testuser')


class ProfileServiceTest(TestCase):
    """Tests para los servicios de perfil."""

    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser', password='pass123',
            first_name='Test', last_name='User'
        )

    def test_get_user_profile_data_authenticated(self):
        """Debe devolver los datos del perfil para usuario autenticado."""
        data = get_user_profile_data(self.user)
        self.assertTrue(data['success'])
        self.assertEqual(data['profile_data']['username'], 'testuser')
        self.assertEqual(data['profile_data']['first_name'], 'Test')
        self.assertEqual(data['profile_data']['last_name'], 'User')

    def test_get_user_profile_data_unauthenticated(self):
        """Debe devolver dict vacio para usuario no autenticado.

        ``is_authenticated`` es de solo lectura, asi que un usuario anonimo se
        representa con ``AnonymousUser()``.
        """
        data = get_user_profile_data(AnonymousUser())
        self.assertTrue(data['success'])
        self.assertEqual(data['profile_data'], {})

    def test_get_user_rating_history(self):
        """Debe devolver el historial de valoraciones."""
        movie = Movie.objects.create(title='Movie 1', release_year=2020)
        Rating.objects.create(user=self.user, movie=movie, score=8)
        history_result = get_user_rating_history(self.user)
        self.assertTrue(history_result['success'])
        self.assertEqual(len(history_result['history']), 1)
        self.assertEqual(history_result['history'][0]['movie_title'], 'Movie 1')

    def test_get_user_rating_history_empty(self):
        """Debe devolver lista vacia sin calificaciones."""
        history_result = get_user_rating_history(self.user)
        self.assertTrue(history_result['success'])
        self.assertEqual(history_result['history'], [])

    def test_update_profile(self):
        """Debe actualizar el perfil correctamente."""
        result = update_profile(self.user, {'username': 'newuser', 'email': 'new@example.com'})
        self.assertTrue(result['success'])
        self.user.refresh_from_db()
        self.assertEqual(self.user.username, 'newuser')
        self.assertEqual(self.user.email, 'new@example.com')

    def test_update_profile_rejects_unauthenticated(self):
        """Debe rechazar la actualizacion para un usuario no autenticado.

        El servicio no lanza excepcion: devuelve ``success=False`` con un
        mensaje. El nombre anterior de este test decia "raises ValueError" y ya
        no describia lo que hacia.
        """
        result = update_profile(AnonymousUser(), {'username': 'newuser'})
        self.assertFalse(result['success'])
        self.assertIn('message', result)


class ProfileFormTest(TestCase):
    """Tests para el formulario de perfil."""

    def test_profile_form_valid(self):
        """Debe ser valido con datos correctos."""
        form = ProfileForm(data={'username': 'testuser', 'email': 'test@example.com'})
        self.assertTrue(form.is_valid())

    def test_profile_form_empty_username(self):
        """Debe ser invalido con username vacio."""
        form = ProfileForm(data={'username': '', 'email': 'test@example.com'})
        self.assertFalse(form.is_valid())

    def test_profile_form_invalid_email(self):
        """Debe ser invalido con email invalido."""
        form = ProfileForm(data={'username': 'testuser', 'email': 'notanemail'})
        self.assertFalse(form.is_valid())
