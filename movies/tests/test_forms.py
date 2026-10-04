"""
Tests para los formularios de la aplicacion movies.
"""

from django import forms
from django.contrib.auth.models import User
from django.test import TestCase, RequestFactory

from movies.forms import ProfileForm, RatingForm, SearchForm
from movies.models import Genre, Movie, Rating


class RatingFormTest(TestCase):
    """Tests para el formulario RatingForm."""

    def test_rating_form_valid_score(self) -> None:
        """Test rating_form_valid_score_valid: score entre 1-10 es valido."""
        form = RatingForm(data={'score': 5}, user=None)
        self.assertTrue(form.is_valid())
        self.assertEqual(form.cleaned_data['score'], 5)

    def test_rating_form_score_min(self) -> None:
        """Test rating_form_score_min_boundary: score=1 es el minimo valido."""
        form = RatingForm(data={'score': 1}, user=None)
        self.assertTrue(form.is_valid())
        self.assertEqual(form.cleaned_data['score'], 1)

    def test_rating_form_score_max(self) -> None:
        """Test rating_form_score_max_boundary: score=10 es el maximo valido."""
        form = RatingForm(data={'score': 10}, user=None)
        self.assertTrue(form.is_valid())
        self.assertEqual(form.cleaned_data['score'], 10)

    def test_rating_form_score_zero_rejected(self) -> None:
        """Test rating_form_score_zero_rejected: score=0 debe ser rechazado."""
        form = RatingForm(data={'score': 0}, user=None)
        self.assertFalse(form.is_valid())
        self.assertIn('score', form.errors)

    def test_rating_form_score_negative_rejected(self) -> None:
        """Test rating_form_score_negative_rejected: score negativo debe ser rechazado."""
        form = RatingForm(data={'score': -1}, user=None)
        self.assertFalse(form.is_valid())
        self.assertIn('score', form.errors)

    def test_rating_form_score_eleven_rejected(self) -> None:
        """Test rating_form_score_eleven_rejected: score=11 debe ser rechazado."""
        form = RatingForm(data={'score': 11}, user=None)
        self.assertFalse(form.is_valid())
        self.assertIn('score', form.errors)

    def test_rating_form_score_max_boundary_rejected(self) -> None:
        """Test rating_form_score_max_boundary_rejected: score=11 excede maximo."""
        form = RatingForm(data={'score': 11}, user=None)
        self.assertFalse(form.is_valid())
        self.assertTrue(len(form.errors) > 0)

    def test_rating_form_empty_score_rejected(self) -> None:
        """Test rating_form_empty_score_rejected: score vacio debe ser rechazado."""
        form = RatingForm(data={}, user=None)
        self.assertFalse(form.is_valid())
        self.assertIn('score', form.errors)

    def test_rating_form_float_score_rejected(self) -> None:
        """Test rating_form_float_score_rejected: score decimal debe ser rechazado."""
        form = RatingForm(data={'score': 5.5}, user=None)
        self.assertFalse(form.is_valid())

    def test_rating_form_saves_with_user(self) -> None:
        """Test rating_form_saves_with_user: save asigna usuario si esta autenticado.

        ``RatingForm`` solo expone el campo ``score``, asi que la pelicula se
        inyecta con ``instance=Rating(movie=...)``: es la unica via que admite la
        API actual, ya que ``movie`` no es un campo del formulario y las vistas
        la fijan aparte (vienen del ``movie_id`` del POST).
        """
        user = User.objects.create_user(username='testuser', password='pass')
        genre = Genre.objects.create(name='Action')
        movie = Movie.objects.create(title='Test', release_year=2020)
        movie.genres.add(genre)

        form = RatingForm(
            data={'score': 8}, user=user, instance=Rating(movie=movie)
        )
        self.assertTrue(form.is_valid())
        rating = form.save()
        self.assertEqual(rating.user, user)
        self.assertEqual(rating.score, 8)
        self.assertEqual(rating.movie, movie)

    def test_rating_form_without_user(self) -> None:
        """Test rating_form_without_user: save sin usuario deja ``user`` a NULL."""
        genre = Genre.objects.create(name='Horror')
        movie = Movie.objects.create(title='Test2', release_year=2021)
        movie.genres.add(genre)

        form = RatingForm(
            data={'score': 7}, user=None, instance=Rating(movie=movie)
        )
        self.assertTrue(form.is_valid())
        rating = form.save()
        self.assertIsNone(rating.user)
        # ``Rating.user`` es opcional: la fila se guarda con NULL, no revienta.
        self.assertIsNone(Rating.objects.get(pk=rating.pk).user)


class SearchFormTest(TestCase):
    """Tests para el formulario SearchForm."""

    def test_search_form_valid(self) -> None:
        """Test search_form_valid: query de longitud valida es aceptado."""
        form = SearchForm(data={'q': 'Matrix'})
        self.assertTrue(form.is_valid())
        self.assertEqual(form.cleaned_data['q'], 'Matrix')

    def test_search_form_empty_rejected(self) -> None:
        """Test search_form_empty_rejected: query vacio es rechazado."""
        form = SearchForm(data={'q': ''})
        self.assertFalse(form.is_valid())

    def test_search_form_too_short_rejected(self) -> None:
        """Test search_form_too_short_rejected: query de 1 caracter es rechazado."""
        form = SearchForm(data={'q': 'A'})
        self.assertFalse(form.is_valid())

    def test_search_form_too_long_rejected(self) -> None:
        """Test search_form_too_long_rejected: query de 101 caracteres es rechazado."""
        form = SearchForm(data={'q': 'A' * 101})
        self.assertFalse(form.is_valid())


class ProfileFormTest(TestCase):
    """Tests para el formulario ProfileForm."""

    def test_profile_form_valid(self) -> None:
        """Test profile_form_valid: datos validos son aceptados."""
        form = ProfileForm(data={'username': 'john', 'email': 'john@example.com'})
        self.assertTrue(form.is_valid())

    def test_profile_form_username_required(self) -> None:
        """Test profile_form_username_required: username vacio es rechazado."""
        form = ProfileForm(data={'username': '', 'email': 'john@example.com'})
        self.assertFalse(form.is_valid())
        self.assertIn('username', form.errors)

    def test_profile_form_email_optional(self) -> None:
        """Test profile_form_email_optional: email vacio es aceptado."""
        form = ProfileForm(data={'username': 'john', 'email': ''})
        self.assertTrue(form.is_valid())

    def test_profile_form_email_validation(self) -> None:
        """Test profile_form_email_validation: email invalido es rechazado."""
        form = ProfileForm(data={'username': 'john', 'email': 'not-an-email'})
        self.assertFalse(form.is_valid())
        self.assertIn('email', form.errors)

    def test_profile_form_email_special_chars(self) -> None:
        """Test profile_form_email_special_chars: email sin @ es rechazado."""
        form = ProfileForm(data={'username': 'john', 'email': 'invalidemail.com'})
        self.assertFalse(form.is_valid())
        self.assertIn('email', form.errors)

    def test_profile_form_username_max_length(self) -> None:
        """Test profile_form_username_max_length: username muy largo es rechazado."""
        form = ProfileForm(data={'username': 'a' * 200, 'email': ''})
        self.assertFalse(form.is_valid())
        self.assertIn('username', form.errors)
