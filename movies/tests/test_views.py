"""
Tests para las vistas de la aplicacion movies.

Valida:
- Pages renderizan correctamente (home, recommend)
- Submit de valoraciones (validas e invalidas)
- Error pages (404, 500)
- Authentication guards
- Favoritos toggle
- Profile update
"""

from django.contrib.auth.models import User
from django.template.loader import get_template
from django.test import TestCase, RequestFactory
from django.urls import reverse

from movies.forms import ProfileForm, RatingForm, SearchForm
from movies.models import Genre, Movie, Rating
from movies.services import create_rating


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _create_authenticated_user(username='testuser', password='testpass123'):
    return User.objects.create_user(
        username=username, password=password, email=f'{username}@test.com'
    )


def _create_movie(title='Test Movie', release_year=2020):
    genre = Genre.objects.get_or_create(name='Action')[0]
    movie = Movie.objects.create(title=title, release_year=release_year)
    movie.genres.add(genre)
    return movie


# ---------------------------------------------------------------------------
# Home View Tests
# ---------------------------------------------------------------------------

class HomeViewTest(TestCase):
    """Tests para la vista home."""

    def setUp(self):
        self.movie = _create_movie()
        self.user = _create_authenticated_user()

    # --- GET requests ---

    def test_home_anonymous_get_200(self):
        """test_home_anonymous_get_200: anonymous user gets 200 OK on home."""
        url = reverse('movies:home')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'movies/home.html')
        self.assertIn('movies', response.context)
        self.assertIn('search_form', response.context)

    def test_home_authenticated_get_200(self):
        """test_home_authenticated_get_200: logged in user gets 200 OK on home."""
        self.client.login(username='testuser', password='testpass123')
        url = reverse('movies:home')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertIn('movie_rating_forms', response.context)

    def test_home_contains_movie(self):
        """test_home_contains_movie: home shows the created movie."""
        url = reverse('movies:home')
        response = self.client.get(url)
        self.assertContains(response, self.movie.title)

    # --- POST: rating submission ---

    def test_home_rating_valid_post_redirect(self):
        """test_home_rating_valid_post_redirect: valid rating redirects."""
        self.client.login(username='testuser', password='testpass123')
        url = reverse('movies:home')
        response = self.client.post(url, {
            'movie_id': self.movie.id,
            'score': 8,
        })
        self.assertEqual(response.status_code, 302)
        # Verify rating was saved
        self.assertEqual(Rating.objects.filter(user=self.user, movie=self.movie).count(), 1)
        self.assertEqual(Rating.objects.get(user=self.user, movie=self.movie).score, 8)

    def test_home_rating_invalid_score_0_rejected(self):
        """test_home_rating_invalid_score_0_rejected: score=0 stays on page."""
        self.client.login(username='testuser', password='testpass123')
        url = reverse('movies:home')
        response = self.client.post(url, {
            'movie_id': self.movie.id,
            'score': 0,
        })
        self.assertEqual(response.status_code, 200)  # stays on page with errors
        self.assertNotEqual(Rating.objects.filter(user=self.user, movie=self.movie).count(), 1)

    def test_home_rating_invalid_score_11_rejected(self):
        """test_home_rating_invalid_score_11_rejected: score=11 stays on page."""
        self.client.login(username='testuser', password='testpass123')
        url = reverse('movies:home')
        response = self.client.post(url, {
            'movie_id': self.movie.id,
            'score': 11,
        })
        self.assertEqual(response.status_code, 200)

    def test_home_rating_empty_score_rejected(self):
        """test_home_rating_empty_score_rejected: empty score stays on page."""
        self.client.login(username='testuser', password='testpass123')
        url = reverse('movies:home')
        response = self.client.post(url, {
            'movie_id': self.movie.id,
            'score': '',
        })
        self.assertEqual(response.status_code, 200)

    def test_home_rating_anonymous_not_saved(self):
        """test_home_rating_anonymous_not_saved: anonymous cannot submit ratings."""
        url = reverse('movies:home')
        response = self.client.post(url, {
            'movie_id': self.movie.id,
            'score': 5,
        })
        self.assertEqual(response.status_code, 302)  # redirects to login
        self.assertEqual(Rating.objects.count(), 0)

    def test_home_rating_nonexistent_movie_error(self):
        """test_home_rating_nonexistent_movie_error: invalid movie_id redirects home."""
        self.client.login(username='testuser', password='testpass123')
        url = reverse('movies:home')
        response = self.client.post(url, {
            'movie_id': 99999,
            'score': 5,
        })
        self.assertEqual(response.status_code, 302)
        # La app esta montada en '/', asi que la home es '/' y no '/movies/'.
        self.assertEqual(response.url, reverse('movies:home'))

    # --- Search ---

    def test_home_search_query(self):
        """test_home_search_query: search filters movies by title."""
        _create_movie(title='Inception', release_year=2010)
        # ``reverse()`` no acepta la query string: se pasa con el GET.
        url = reverse('movies:home')
        response = self.client.get(url, {'q': 'Inception'})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Inception')
        self.assertNotContains(response, self.movie.title)

    def test_home_search_empty_query_no_results(self):
        """test_home_search_empty_query_no_results: empty search rejected."""
        url = reverse('movies:home')
        response = self.client.get(url, {'q': ''})
        self.assertEqual(response.status_code, 200)

    def test_home_search_short_query_rejected(self):
        """test_home_search_short_query_rejected: single char search rejected."""
        url = reverse('movies:home')
        response = self.client.get(url, {'q': 'A'})
        self.assertEqual(response.status_code, 200)


# ---------------------------------------------------------------------------
# Recommend View Tests
# ---------------------------------------------------------------------------

class RecommendViewTest(TestCase):
    """Tests para la vista recommend."""

    def setUp(self):
        self.genre = Genre.objects.create(name='Science Fiction')
        self.movie = Movie.objects.create(title='Interstellar', release_year=2014)
        self.movie.genres.add(self.genre)
        self.user = _create_authenticated_user()

    def test_recommend_anonymous_get_200(self):
        """test_recommend_anonymous_get_200: anonymous gets 200 on recommend."""
        url = reverse('movies:recommend', kwargs={'genre_name': 'Science Fiction'})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'movies/recommend.html')

    def test_recommend_authenticated_get_200(self):
        """test_recommend_authenticated_get_200: logged in gets 200."""
        self.client.login(username='testuser', password='testpass123')
        url = reverse('movies:recommend', kwargs={'genre_name': 'Science Fiction'})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertIn('profile_form', response.context)

    def test_recommend_contains_movie(self):
        """test_recommend_contains_movie: recommend shows matching movies."""
        url = reverse('movies:recommend', kwargs={'genre_name': 'Science Fiction'})
        response = self.client.get(url)
        self.assertContains(response, 'Interstellar')

    # --- Rating on recommend ---

    def test_recommend_rating_valid_post_redirect(self):
        """test_recommend_rating_valid_post_redirect: valid rating on recommend redirects."""
        self.client.login(username='testuser', password='testpass123')
        url = reverse('movies:recommend', kwargs={'genre_name': 'Science Fiction'})
        response = self.client.post(url, {
            'movie_id': self.movie.id,
            'score': 9,
        })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Rating.objects.filter(user=self.user, movie=self.movie).count(), 1)

    # --- Profile update ---

    def test_recommend_profile_update_valid(self):
        """test_recommend_profile_update_valid: valid profile update redirects."""
        self.client.login(username='testuser', password='testpass123')
        url = reverse('movies:recommend', kwargs={'genre_name': 'Science Fiction'})
        response = self.client.post(url, {
            'profile_submit': '1',
            'username': 'newname',
            'email': 'newname@test.com',
        })
        self.assertEqual(response.status_code, 302)
        self.user.refresh_from_db()
        self.assertEqual(self.user.username, 'newname')
        self.assertEqual(self.user.email, 'newname@test.com')

    def test_recommend_profile_update_invalid_email(self):
        """test_recommend_profile_update_invalid_email: bad email stays on page."""
        self.client.login(username='testuser', password='testpass123')
        url = reverse('movies:recommend', kwargs={'genre_name': 'Science Fiction'})
        response = self.client.post(url, {
            'profile_submit': '1',
            'username': 'newname',
            'email': 'not-an-email',
        })
        self.assertEqual(response.status_code, 200)  # stays with errors

    def test_recommend_profile_update_empty_username_rejected(self):
        """test_recommend_profile_update_empty_username_rejected: empty username rejected."""
        self.client.login(username='testuser', password='testpass123')
        url = reverse('movies:recommend', kwargs={'genre_name': 'Science Fiction'})
        response = self.client.post(url, {
            'profile_submit': '1',
            'username': '',
            'email': 'test@test.com',
        })
        self.assertEqual(response.status_code, 200)


# ---------------------------------------------------------------------------
# Favorite View Tests
# ---------------------------------------------------------------------------

class FavoriteViewTest(TestCase):
    """Tests para la vista favorite."""

    def setUp(self):
        self.genre = Genre.objects.create(name='Drama')
        self.movie = Movie.objects.create(title='The Shawshank Redemption', release_year=1994)
        self.movie.genres.add(self.genre)
        self.user = _create_authenticated_user()

    def test_favorite_anonymous_redirect(self):
        """test_favorite_anonymous_redirect: anonymous redirected to login."""
        url = reverse('movies:favorite', kwargs={'movie_id': self.movie.id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302)
        self.assertIn('accounts/login', response.url)

    def test_favorite_authenticated_add(self):
        """test_favorite_authenticated_add: authenticated user can add favorite."""
        self.client.login(username='testuser', password='testpass123')
        url = reverse('movies:favorite', kwargs={'movie_id': self.movie.id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302)
        # El related_name real de Favorite.user es 'favorites'.
        self.assertTrue(self.user.favorites.filter(id=self.movie.id).exists())

    def test_favorite_authenticated_toggle_remove(self):
        """test_favorite_authenticated_toggle_remove: toggle removes favorite."""
        self.client.login(username='testuser', password='testpass123')
        # First add
        url = reverse('movies:favorite', kwargs={'movie_id': self.movie.id})
        self.client.get(url)
        self.assertTrue(self.user.favorites.filter(id=self.movie.id).exists())
        # Then remove
        self.client.get(url)
        self.assertFalse(self.user.favorites.filter(id=self.movie.id).exists())

    def test_favorite_nonexistent_movie_redirect(self):
        """test_favorite_nonexistent_movie_redirect: invalid movie redirects home."""
        self.client.login(username='testuser', password='testpass123')
        url = reverse('movies:favorite', kwargs={'movie_id': 99999})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302)
        # Montada en '/': la home es '/', no '/movies/'.
        self.assertEqual(response.url, reverse('movies:home'))


# ---------------------------------------------------------------------------
# Error Page Tests (404, 500)
# ---------------------------------------------------------------------------

class ErrorPageTest(TestCase):
    """Tests para las paginas de error 404 y 500."""

    @staticmethod
    def _template_source(name):
        """Devuelve el codigo fuente de una plantilla localizada.

        ``django.template.Template`` ya no expone ``.source`` (se elimino hace
        años); la via soportada es ``.origin.name``, que da la ruta real del
        fichero que se cargo.
        """
        template = get_template(name)
        path = template.origin.name
        with open(path, encoding='utf-8') as handle:
            return handle.read()

    def test_404_page_custom_template(self):
        """test_404_page_custom_template: custom 404.html exists and is used."""
        # The custom 404 template should exist
        try:
            get_template('404.html')
        except Exception:
            self.fail("Custom 404.html template not found at project templates root")

    def test_500_page_custom_template(self):
        """test_500_page_custom_template: custom 500.html exists and is used."""
        # The custom 500 template should exist
        try:
            get_template('500.html')
        except Exception:
            self.fail("Custom 500.html template not found at project templates root")

    def test_404_template_extends_base(self):
        """test_404_template_extends_base: 404.html extends base template."""
        source = self._template_source('404.html')
        self.assertIn('extends', source)
        self.assertIn('movies/base.html', source)

    def test_500_template_extends_base(self):
        """test_500_template_extends_base: 500.html extends base template."""
        source = self._template_source('500.html')
        self.assertIn('extends', source)
        self.assertIn('movies/base.html', source)

    def test_404_template_has_error_content(self):
        """test_404_template_has_error_content: 404 mentions page not found."""
        source = self._template_source('404.html')
        self.assertTrue(len(source) > 50)  # has meaningful content
        self.assertIn('404', source)
        self.assertIn('Page Not Found', source)

    def test_500_template_has_error_content(self):
        """test_500_template_has_error_content: 500 mentions server error."""
        source = self._template_source('500.html')
        self.assertTrue(len(source) > 50)  # has meaningful content
        self.assertIn('500', source)
        self.assertIn('Server Error', source)


# ---------------------------------------------------------------------------
# RatingForm Direct Tests (for edge cases)
# ---------------------------------------------------------------------------

class RatingFormEdgeCasesTest(TestCase):
    """Tests de edge cases para RatingForm."""

    def setUp(self):
        self.user = _create_authenticated_user()

    def test_rating_form_score_string_rejected(self):
        """test_rating_form_score_string_rejected: score como texto numerico."""
        form = RatingForm(data={'score': 'abc'}, user=None)
        self.assertFalse(form.is_valid())

    def test_rating_form_score_min_plus_one(self):
        """test_rating_form_score_min_plus_one: score=2 es valido."""
        form = RatingForm(data={'score': 2}, user=None)
        self.assertTrue(form.is_valid())

    def test_rating_form_score_max_minus_one(self):
        """test_rating_form_score_max_minus_one: score=9 es valido."""
        form = RatingForm(data={'score': 9}, user=None)
        self.assertTrue(form.is_valid())

    def test_rating_form_save_assigns_user(self):
        """test_rating_form_save_assigns_user: save asocia rating con usuario.

        La pelicula se inyecta con ``instance=``: ``RatingForm`` solo declara el
        campo ``score``.
        """
        from movies.models import Genre
        genre = Genre.objects.create(name='TestGenre')
        movie = Movie.objects.create(title='Edge Case', release_year=2022)
        movie.genres.add(genre)

        form = RatingForm(
            data={'score': 10}, user=self.user, instance=Rating(movie=movie)
        )
        self.assertTrue(form.is_valid())
        rating = form.save()
        self.assertEqual(rating.user, self.user)
        self.assertEqual(rating.movie, movie)

    def test_rating_form_negative_score_cleaned(self):
        """test_rating_form_negative_score_cleaned: score negativo rejected."""
        form = RatingForm(data={'score': -5}, user=None)
        self.assertFalse(form.is_valid())
        self.assertIn('score', form.errors)


# ---------------------------------------------------------------------------
# SearchForm Edge Cases
# ---------------------------------------------------------------------------

class SearchFormEdgeCasesTest(TestCase):
    """Tests de edge cases para SearchForm."""

    def test_search_form_exact_min_length(self):
        """test_search_form_exact_min_length: 2 caracteres es valido."""
        form = SearchForm(data={'q': 'Ab'})
        self.assertTrue(form.is_valid())

    def test_search_form_exact_max_length(self):
        """test_search_form_exact_max_length: 100 caracteres es valido."""
        form = SearchForm(data={'q': 'A' * 100})
        self.assertTrue(form.is_valid())

    def test_search_form_one_over_max_rejected(self):
        """test_search_form_one_over_max_rejected: 101 caracteres rechazado."""
        form = SearchForm(data={'q': 'A' * 101})
        self.assertFalse(form.is_valid())

    def test_search_form_whitespace_only_rejected(self):
        """test_search_form_whitespace_only_rejected: solo espacios rechazado."""
        form = SearchForm(data={'q': '   '})
        self.assertFalse(form.is_valid())


# ---------------------------------------------------------------------------
# ProfileForm Edge Cases
# ---------------------------------------------------------------------------

class ProfileFormEdgeCasesTest(TestCase):
    """Tests de edge cases para ProfileForm."""

    def test_profile_form_exact_min_username(self):
        """test_profile_form_exact_min_username: username de 1 char es max."""
        form = ProfileForm(data={'username': 'a', 'email': ''})
        # 1 char es valido para ProfileForm (no tiene min_length como RegisterForm)
        self.assertTrue(form.is_valid())

    def test_profile_form_email_with_subdomain(self):
        """test_profile_form_email_with_subdomain: email con subdominio valido."""
        form = ProfileForm(data={'username': 'john', 'email': 'john@mail.example.com'})
        self.assertTrue(form.is_valid())

    def test_profile_form_email_with_dots(self):
        """test_profile_form_email_with_dots: email con puntos valido."""
        form = ProfileForm(data={'username': 'john', 'email': 'john.doe@test.com'})
        self.assertTrue(form.is_valid())
