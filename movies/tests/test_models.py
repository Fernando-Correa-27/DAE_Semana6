from django.test import TestCase, RequestFactory
from django.contrib.admin.sites import AdminSite
from django.contrib.auth.models import User, Group, Permission
from django.db.models import Avg

from movies.models import Movie, Genre, Person, Rating
from movies.admin import MovieAdmin, GenreAdmin, PersonAdmin, RatingAdmin
from movies.selectors.movie_selector import get_movie_recommendations, get_movies_by_genre_with_rating


class GenreModelTest(TestCase):
    """Tests para el modelo Genre."""

    def test_create_genre(self) -> None:
        genre = Genre.objects.create(name='Action')
        self.assertEqual(genre.name, 'Action')
        self.assertEqual(str(genre), 'Action')

    def test_genre_unicode(self) -> None:
        genre = Genre.objects.create(name='Science Fiction')
        self.assertEqual(str(genre), 'Science Fiction')

    def test_genre_ordering(self) -> None:
        Genre.objects.create(name='Horror')
        Genre.objects.create(name='Action')
        Genre.objects.create(name='Comedy')
        self.assertEqual(list(Genre.objects.all()), [
            Genre.objects.get(name='Action'),
            Genre.objects.get(name='Comedy'),
            Genre.objects.get(name='Horror'),
        ])

    def test_genre_name_unique(self) -> None:
        Genre.objects.create(name='Action')
        with self.assertRaises(Exception):
            Genre.objects.create(name='Action')


class PersonModelTest(TestCase):
    """Tests para el modelo Person."""

    def test_create_person(self) -> None:
        person = Person.objects.create(name='John Doe', role='Actor')
        self.assertEqual(person.name, 'John Doe')
        self.assertEqual(str(person), 'John Doe')

    def test_person_with_role(self) -> None:
        person = Person.objects.create(name='Jane Doe', role='Director')
        self.assertEqual(person.role, 'Director')
        self.assertEqual(str(person), 'Jane Doe')

    def test_person_ordering(self) -> None:
        Person.objects.create(name='Charlie', role='Actor')
        Person.objects.create(name='Alice', role='Director')
        Person.objects.create(name='Bob', role='Actor')
        self.assertEqual(list(Person.objects.all()), [
            Person.objects.get(name='Alice'),
            Person.objects.get(name='Bob'),
            Person.objects.get(name='Charlie'),
        ])


class MovieModelTest(TestCase):
    """Tests para el modelo Movie."""

    def setUp(self) -> None:
        self.genre = Genre.objects.create(name='Action')

    def test_create_movie(self) -> None:
        movie = Movie.objects.create(
            title='Test Movie',
            synopsis='A test synopsis',
            release_year=2023,
        )
        self.assertEqual(movie.title, 'Test Movie')
        self.assertEqual(str(movie), 'Test Movie (2023)')

    def test_movie_str_format(self) -> None:
        movie = Movie.objects.create(title='Matrix', release_year=1999)
        self.assertEqual(str(movie), 'Matrix (1999)')

    def test_movie_genres_manytomany(self) -> None:
        movie = Movie.objects.create(title='Test', release_year=2020)
        movie.genres.add(self.genre)
        self.assertEqual(movie.genres.count(), 1)
        self.assertIn(self.genre, movie.genres.all())

    def test_movie_cast_manytomany(self) -> None:
        person = Person.objects.create(name='Actor', role='Actor')
        movie = Movie.objects.create(title='Test', release_year=2020)
        movie.cast.add(person)
        self.assertEqual(movie.cast.count(), 1)

    def test_movie_ordering(self) -> None:
        Movie.objects.create(title='A', release_year=2020)
        Movie.objects.create(title='B', release_year=2023)
        Movie.objects.create(title='C', release_year=2023)
        movies = list(Movie.objects.all())
        self.assertEqual(movies[0].title, 'B')
        self.assertEqual(movies[1].title, 'C')

    def test_average_rating_with_ratings(self) -> None:
        movie = Movie.objects.create(title='Test', release_year=2020)
        user1 = User.objects.create_user(username='Reviewer1', password='pass')
        user2 = User.objects.create_user(username='Reviewer2', password='pass')
        Rating.objects.create(movie=movie, score=8, user=user1)
        Rating.objects.create(movie=movie, score=10, user=user2)
        self.assertEqual(movie.average_rating, 9.0)

    def test_average_rating_no_ratings(self) -> None:
        movie = Movie.objects.create(title='Test', release_year=2020)
        self.assertIsNone(movie.average_rating)


class RatingModelTest(TestCase):
    """Tests para el modelo Rating."""

    def setUp(self) -> None:
        self.movie = Movie.objects.create(title='Test', release_year=2020)
        self.user1 = User.objects.create_user(username='Reviewer1', password='pass')
        self.user2 = User.objects.create_user(username='Reviewer2', password='pass')
        self.user3 = User.objects.create_user(username='A', password='pass')
        self.user4 = User.objects.create_user(username='B', password='pass')
        self.user5 = User.objects.create_user(username='C', password='pass')

    def test_create_rating(self) -> None:
        rating = Rating.objects.create(
            movie=self.movie,
            score=8,
            user=self.user1,
        )
        self.assertEqual(rating.score, 8)
        self.assertEqual(str(rating), 'Test (2020) - 8/10 (Reviewer1)')

    def test_rating_score_validation_1_10(self) -> None:
        Rating.objects.create(movie=self.movie, score=1, user=self.user3)
        Rating.objects.create(movie=self.movie, score=10, user=self.user4)
        with self.assertRaises(Exception):
            Rating.objects.create(movie=self.movie, score=0, user=self.user5)
        with self.assertRaises(Exception):
            Rating.objects.create(movie=self.movie, score=11, user=self.user5)

    def test_unique_reviewer_per_movie(self) -> None:
        Rating.objects.create(movie=self.movie, score=8, user=self.user1)
        with self.assertRaises(Exception):
            Rating.objects.create(movie=self.movie, score=5, user=self.user1)

    def test_rating_foreign_key_cascade(self) -> None:
        rating = Rating.objects.create(movie=self.movie, score=8, user=self.user1)
        rating_id = rating.id
        self.movie.delete()
        self.assertFalse(Rating.objects.filter(id=rating_id).exists())

    def test_rating_ordering(self) -> None:
        Rating.objects.create(movie=self.movie, score=5, user=self.user4)
        Rating.objects.create(movie=self.movie, score=9, user=self.user1)
        Rating.objects.create(movie=self.movie, score=9, user=self.user5)
        ratings = list(Rating.objects.all())
        self.assertEqual(ratings[0].score, 9)
        self.assertEqual(ratings[1].score, 9)


class MovieSelectorTest(TestCase):
    """Tests para el selector de recomendaciones."""

    def setUp(self) -> None:
        self.action = Genre.objects.create(name='Action')
        self.comedy = Genre.objects.create(name='Comedy')
        self.movie1 = Movie.objects.create(title='Movie 1', release_year=2020)
        self.movie1.genres.add(self.action)
        self.movie2 = Movie.objects.create(title='Movie 2', release_year=2023)
        self.movie2.genres.add(self.action)
        self.movie3 = Movie.objects.create(title='Movie 3', release_year=2021)
        self.movie3.genres.add(self.comedy)
        user1 = User.objects.create_user(username='R1', password='pass')
        user2 = User.objects.create_user(username='R2', password='pass')
        user3 = User.objects.create_user(username='R3', password='pass')
        Rating.objects.create(movie=self.movie1, score=9, user=user1)
        Rating.objects.create(movie=self.movie2, score=7, user=user2)
        Rating.objects.create(movie=self.movie2, score=10, user=user3)

    def test_get_recommendations_returns_sorted(self) -> None:
        recommendations = get_movie_recommendations('Action', limit=10)
        self.assertEqual(len(recommendations), 2)
        self.assertEqual(recommendations[0].title, 'Movie 1')
        self.assertEqual(recommendations[1].title, 'Movie 2')

    def test_get_recommendations_ignores_no_ratings(self) -> None:
        self.movie3.genres.add(self.action)
        recommendations = get_movie_recommendations('Action', limit=10)
        # Movie 3 has no ratings, so should be excluded
        self.assertEqual(len(recommendations), 2)

    def test_get_recommendations_with_limit(self) -> None:
        recommendations = get_movie_recommendations('Action', limit=1)
        self.assertEqual(len(recommendations), 1)

    def test_get_movies_by_genre_with_rating_includes_all(self) -> None:
        self.movie3.genres.add(self.action)
        all_movies = get_movies_by_genre_with_rating('Action')
        self.assertEqual(len(all_movies), 3)

    def test_annotation_includes_average_rating(self) -> None:
        recommendations = get_movie_recommendations('Action', limit=10)
        for movie in recommendations:
            self.assertIsNotNone(movie.rating_avg)


class MovieAdminTest(TestCase):
    """Tests para la configuracion del MovieAdmin."""

    def setUp(self) -> None:
        self.site = AdminSite()
        self.admin = MovieAdmin(Movie, self.site)

    def test_list_display_fields(self) -> None:
        self.assertIn('title', self.admin.list_display)
        self.assertIn('release_year', self.admin.list_display)
        self.assertIn('created_at', self.admin.list_display)

    def test_list_filter_fields(self) -> None:
        self.assertIn('genres', self.admin.list_filter)

    def test_search_fields(self) -> None:
        self.assertIn('title', self.admin.search_fields)

    def test_readonly_fields(self) -> None:
        self.assertIn('created_at', self.admin.readonly_fields)
        self.assertIn('updated_at', self.admin.readonly_fields)

    def test_has_inline(self) -> None:
        self.assertTrue(len(self.admin.inlines) > 0)


class GenreAdminTest(TestCase):
    """Tests para la configuracion del GenreAdmin."""

    def setUp(self) -> None:
        self.site = AdminSite()
        self.admin = GenreAdmin(Genre, self.site)

    def test_list_display(self) -> None:
        self.assertIn('name', self.admin.list_display)

    def test_search_fields(self) -> None:
        self.assertIn('name', self.admin.search_fields)


class PersonAdminTest(TestCase):
    """Tests para la configuracion del PersonAdmin."""

    def setUp(self) -> None:
        self.site = AdminSite()
        self.admin = PersonAdmin(Person, self.site)

    def test_list_display(self) -> None:
        self.assertIn('name', self.admin.list_display)

    def test_search_fields(self) -> None:
        self.assertIn('name', self.admin.search_fields)

    def test_list_filter(self) -> None:
        self.assertIn('role', self.admin.list_filter)


class RatingAdminTest(TestCase):
    """Tests para la configuracion del RatingAdmin."""

    def setUp(self) -> None:
        self.site = AdminSite()
        self.admin = RatingAdmin(Rating, self.site)

    def test_list_display(self) -> None:
        self.assertIn('movie', self.admin.list_display)
        self.assertIn('score', self.admin.list_display)

    def test_search_fields(self) -> None:
        self.assertIn('movie__title', self.admin.search_fields)

    def test_readonly_fields(self) -> None:
        self.assertIn('created_at', self.admin.readonly_fields)


class PermissionGroupTest(TestCase):
    """Tests para la configuracion de grupos y permisos."""

    def setUp(self) -> None:
        self.group = Group.objects.create(name='editores')
        add_permission = Permission.objects.get(codename='add_movie')
        change_permission = Permission.objects.get(codename='change_movie')
        self.group.permissions.add(add_permission, change_permission)

        self.user = User.objects.create_user(
            username='editor_test',
            password='testpass123',
            is_staff=True,
        )
        self.user.groups.add(self.group)

    def test_editor_can_add_movie(self) -> None:
        self.assertTrue(
            self.user.has_perm('movies.add_movie')
        )

    def test_editor_can_change_movie(self) -> None:
        self.assertTrue(
            self.user.has_perm('movies.change_movie')
        )

    def test_editor_cannot_delete_movie(self) -> None:
        self.assertFalse(
            self.user.has_perm('movies.delete_movie')
        )

    def test_editor_cannot_add_genre(self) -> None:
        self.assertFalse(
            self.user.has_perm('movies.add_genre')
        )

    def test_user_is_staff(self) -> None:
        self.assertTrue(self.user.is_staff)

    def test_user_belongs_to_group(self) -> None:
        self.assertIn(self.group, self.user.groups.all())


class AdminReadonlyFieldsTest(TestCase):
    """Tests para que los campos de auditoria sean de solo lectura en el admin."""

    def setUp(self) -> None:
        self.site = AdminSite()
        self.movie_admin = MovieAdmin(Movie, self.site)
        self.rating_admin = RatingAdmin(Rating, self.site)

    def test_movie_created_at_readonly(self) -> None:
        self.assertIn('created_at', self.movie_admin.readonly_fields)

    def test_movie_updated_at_readonly(self) -> None:
        self.assertIn('updated_at', self.movie_admin.readonly_fields)

    def test_rating_created_at_readonly(self) -> None:
        self.assertIn('created_at', self.rating_admin.readonly_fields)

    def test_movie_fieldsets_include_auditoria(self) -> None:
        fieldsets = self.movie_admin.fieldsets
        fieldset_names = [name for name, _ in fieldsets if name]
        self.assertIn('Auditoria', fieldset_names)
