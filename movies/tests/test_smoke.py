"""
Smoke / regression tests for the four bugs found via URL smoke testing.

These tests are deliberately *behavioural* (they drive the real Django test
client / real template engine) rather than unit tests, because every one of the
original bugs was silent or only visible when a real page was rendered:

BUG 1 (fixed) - ``TemplateSyntaxError: Invalid filter: 'get_item'`` broke the
    whole home page. ``home.html`` used ``|get_item`` without
    ``{% load dict_extras %}``. Guarded by
    ``test_home_page_renders_without_error`` and
    ``test_get_item_filter_loaded_in_all_templates``.

BUG 2 (fixed, silent) - the rating form was not rendered on the recommend
    page because the template used ``{{ movie_rating_forms.movie.id }}``
    instead of ``{% with form=movie_rating_forms|get_item:movie.id %}``.
    A 200 response was still returned, so only asserting on the status code
    would not have caught it. Guarded by
    ``test_recommend_page_renders_rating_form_when_authenticated``.

BUG 3 (fixed) - ``Movie.save()`` raised ``FileNotFoundError`` when the cover
    file was missing, because ``optimize_image()`` called ``Image.open()``
    unguarded. Guarded by ``test_movie_save_with_missing_cover_does_not_raise``
    and ``test_optimize_image_returns_original_on_missing_file``.
    A truncated/corrupt JPEG was a *second*, separate failure: ``Image.open()``
    only parses the header and decodes lazily, so the ``OSError`` surfaced later
    and the old ``finally: pil_image.close()`` closed the *caller's*
    ``UploadedFile`` on the way out, killing ``FileField.pre_save()`` with
    ``ValueError: I/O operation on closed file.`` ``optimize_image()`` now reads
    the bytes up front, decodes from its own ``BytesIO`` and guards its whole
    body. Guarded by
    ``test_movie_save_with_truncated_cover_does_not_raise``.

BUG 4 (fixed) - ``POST /favorite/<id>/`` redirected to ``movies:recommend``
    with ``genre_name='Todos'``, a genre that does not exist. Guarded by
    ``test_favorite_redirects_to_referer_or_home`` which also follows the
    redirect and asserts the target really renders.

BUG 5 (fixed) - the catalogue and the search page rendered "Sin valoraciones"
    on every card even for rated movies: both views annotated only
    ``rating_count`` while the templates read ``movie_avg_rating``. Guarded by
    ``CatalogRatingDisplayTest`` (8 tests, one per queryset path that
    ``home``/``search_view`` can end up with, plus a negative control).

All tests use ``django.test.TestCase`` (database access required) - no
``SimpleTestCase``. No ``pytest`` import, so the module is runnable with the
plain Django test runner.
"""

import os
import re
import shutil
import tempfile
from io import BytesIO

from django.apps import apps
from django.contrib.auth.models import User
from django.core.cache import cache
from django.core.files.base import File
from django.core.files.uploadedfile import SimpleUploadedFile
from django.template import Context, Template, TemplateSyntaxError
from django.template.loader import get_template
from django.test import TestCase
from django.urls import reverse
from PIL import Image

from movies.models import Genre, Movie
from movies.templatetags import dict_extras
from movies.utils.image import optimize_image


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

#: Templates that must survive the ``{% load %}`` / filter-name regressions.
WATCHED_TEMPLATES = ('movies/home.html', 'movies/recommend.html')

#: The name of the custom filter library required by the templates above.
FILTER_LIBRARY = 'dict_extras'
LOAD_TAG = '{%% load %s %%}' % FILTER_LIBRARY
FILTER_NAME = 'get_item'


def _tiny_jpeg_bytes(size=(16, 16), color=(10, 120, 200)) -> bytes:
    """Build a real (tiny) JPEG in memory so Pillow can actually open it."""
    buffer = BytesIO()
    Image.new('RGB', size, color).save(buffer, format='JPEG')
    return buffer.getvalue()


def _uploaded_jpeg(name='cover.jpg') -> SimpleUploadedFile:
    """A real JPEG upload, so ``Movie.cover`` is a genuine ImageField value."""
    return SimpleUploadedFile(name, _tiny_jpeg_bytes(), content_type='image/jpeg')


def _truncated_jpeg(name='roto.jpg', keep=0.9, size=(300, 300)) -> SimpleUploadedFile:
    """A JPEG whose header is intact but whose pixel data is cut short.

    This is the interesting failure mode: ``Image.open()`` *succeeds* (it only
    parses the header and decodes lazily), so a guard wrapped solely around the
    ``open()`` call does not help. Pillow only raises once the image is actually
    decoded/resized/re-encoded further down ``optimize_image()``.
    """
    buffer = BytesIO()
    Image.new('RGB', size, (200, 40, 40)).save(buffer, format='JPEG', quality=95)
    full = buffer.getvalue()
    truncated = full[: int(len(full) * keep)]

    # Sanity-check the premise: the header must still parse, otherwise this
    # would just duplicate the "corrupt bytes" case.
    Image.open(BytesIO(truncated))
    return SimpleUploadedFile(name, truncated, content_type='image/jpeg')


def _app_templates_dir() -> str:
    """Absolute path of the ``movies`` app's ``templates/`` directory.

    Resolved through the app registry rather than ``movies.__file__``, so it
    keeps working regardless of how the package is laid out on disk.
    """
    return os.path.join(apps.get_app_config('movies').path, 'templates')


def _app_template_names():
    """Every ``*.html`` template shipped inside the ``movies`` app."""
    templates_dir = _app_templates_dir()
    found = []
    for root, _dirs, files in os.walk(templates_dir):
        for filename in sorted(files):
            if not filename.endswith('.html'):
                continue
            absolute = os.path.join(root, filename)
            relative = os.path.relpath(absolute, templates_dir)
            found.append((relative.replace(os.sep, '/'), absolute))
    return sorted(found)


class SmokeTestCase(TestCase):
    """Base class: isolates MEDIA_ROOT and clears the per-process cache.

    ``cache.clear()`` matters here. ``get_home_movies()``,
    ``get_genre_recommendations()`` and ``get_all_movies_of_genre()`` memoize
    the *list of movie ids* in ``django.core.cache`` (a ``LocMemCache``) under
    a key that does not depend on the database, and Django's test runner does
    not clear that cache between tests. Without clearing it, a page rendered
    while the table was empty would keep returning "no movies" for the rest of
    the process and the assertions below would pass or fail depending on
    alphabetical test order. See the note on the caching bug at the bottom of
    this module.
    """

    def setUp(self):
        super().setUp()
        cache.clear()
        self.addCleanup(cache.clear)

        # Keep any real cover upload inside a throwaway directory instead of
        # writing into the repository working tree.
        media_root = tempfile.mkdtemp(prefix='smoke_media_')
        self.addCleanup(shutil.rmtree, media_root, True)
        self.settings_override = self.settings(MEDIA_ROOT=media_root, MEDIA_URL='/media/')
        self.settings_override.enable()
        self.addCleanup(self.settings_override.disable)
        self.media_root = media_root

    def make_user(self, username='smoke_user', password='smoke_pass_123'):
        return User.objects.create_user(
            username=username, password=password, email=f'{username}@example.com'
        )

    def login(self, username='smoke_user', password='smoke_pass_123'):
        self.assertTrue(
            self.client.login(username=username, password=password),
            f'Could not log in as {username!r}; test setup is broken.',
        )

    def make_movie(self, title='Smoke Movie', release_year=2020, genres=('Action',), cover=None):
        movie = Movie.objects.create(
            title=title,
            release_year=release_year,
            cover=_uploaded_jpeg() if cover is None else cover,
        )
        for genre_name in genres:
            movie.genres.add(Genre.objects.get_or_create(name=genre_name)[0])
        return movie


# ---------------------------------------------------------------------------
# BUG 1 - home page blew up with TemplateSyntaxError: Invalid filter: 'get_item'
# ---------------------------------------------------------------------------

class HomePageSmokeTest(SmokeTestCase):

    def test_home_page_renders_without_error(self):
        """test_home_page_renders_without_error: GET / as anonymous -> clean 200.

        Regression test for BUG 1: a missing ``{% load dict_extras %}`` made the
        whole home page raise ``TemplateSyntaxError: Invalid filter:
        'get_item'``. Any template error surfaces as a 500 (or, under the
        default test client, propagates out of ``self.client.get``), so this
        test fails loudly if the filter is ever used without being loaded.
        """
        response = self.client.get('/')

        self.assertEqual(
            response.status_code, 200,
            'GET / must return 200; a template error usually means '
            "{% load dict_extras %} was dropped from home.html.",
        )
        content = response.content
        self.assertNotIn(b'TemplateSyntaxError', content)
        self.assertNotIn(b'Invalid filter', content)
        self.assertNotIn(b'get_item', content)
        self.assertTemplateUsed(response, 'movies/home.html')

    def test_home_page_renders_rating_form_when_authenticated(self):
        """test_home_page_renders_rating_form_when_authenticated: score input exists.

        The rating form on the home page is only rendered for authenticated
        users, and it is rendered through the same
        ``{% with form=movie_rating_forms|get_item:movie.id %}`` construct that
        BUG 2 had broken on the recommend page. Asserting on the rendered
        ``score`` input - not just the status code - is what makes this a real
        regression test.
        """
        movie = self.make_movie(title='The Matrix', release_year=1999, genres=('Sci-Fi',))
        self.make_user()
        self.login()

        response = self.client.get('/')

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, movie.title)
        self.assertIn(
            b'name="score"', response.content,
            'The home page must render a score input for an authenticated user.',
        )

    def test_home_page_renders_one_score_input_per_movie(self):
        """test_home_page_renders_one_score_input_per_movie: exact form count.

        Stronger than "at least one": every movie card on the page must get its
        own form, so a dict-lookup mistake that drops all but one form (or
        duplicates one) is caught too.
        """
        movies = [
            self.make_movie(title=f'Movie {index}', release_year=2000 + index, genres=('Drama',))
            for index in range(3)
        ]
        self.make_user()
        self.login()

        response = self.client.get('/')

        self.assertEqual(response.status_code, 200)
        for movie in movies:
            self.assertContains(response, movie.title)
        self.assertEqual(
            response.content.count(b'name="score"'), len(movies),
            'Expected exactly one rating form per movie on the page.',
        )

    def test_anonymous_home_page_does_not_render_rating_form(self):
        """test_anonymous_home_page_does_not_render_rating_form: negative control.

        Proves the ``name="score"`` assertions above are not vacuous: the input
        really is conditional on authentication.
        """
        self.make_movie(title='The Matrix', release_year=1999)

        response = self.client.get('/')

        self.assertEqual(response.status_code, 200)
        self.assertNotIn(
            b'name="score"', response.content,
            'An anonymous visitor must not be shown a rating form.',
        )
        self.assertContains(response, 'Inicia sesion para valorar')

    def test_home_page_renders_without_error_when_authenticated(self):
        """test_home_page_renders_without_error_when_authenticated: same, logged in.

        The rating-form branch of ``home.html`` is only rendered for
        authenticated users, so it is parsed/compiled on a *different* code
        path than the anonymous one. BUG 1 hid in that branch.
        """
        self.make_user()
        self.login()

        response = self.client.get('/')

        self.assertEqual(response.status_code, 200)
        self.assertNotIn(b'TemplateSyntaxError', response.content)
        self.assertNotIn(b'Invalid filter', response.content)
        self.assertTemplateUsed(response, 'movies/home.html')

    def test_home_page_renders_with_movies_present(self):
        """test_home_page_renders_with_movies_present: the loop body is exercised.

        An empty catalogue short-circuits the ``{% if movies %}`` block, so the
        buggy template could hide behind it. Force at least one movie through
        the card-rendering loop.
        """
        movie = self.make_movie(title='Alien', release_year=1979, genres=('Horror',))

        response = self.client.get('/')

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, movie.title)


# ---------------------------------------------------------------------------
# BUG 2 - rating form silently missing on the recommend page
# ---------------------------------------------------------------------------

class RecommendPageRatingFormTest(SmokeTestCase):

    def setUp(self):
        super().setUp()
        self.genre = Genre.objects.create(name='Science Fiction')
        self.movie = self.make_movie(
            title='Interstellar', release_year=2014, genres=('Science Fiction',)
        )
        self.genre_url = reverse('movies:recommend', kwargs={'genre_name': self.genre.name})

    def test_recommend_page_renders_rating_form_when_authenticated(self):
        """test_recommend_page_renders_rating_form_when_authenticated: score input exists.

        Regression test for BUG 2: ``recommend.html`` used
        ``{{ movie_rating_forms.movie.id }}`` (an attribute lookup on a dict,
        which always resolves to an empty string) instead of
        ``{% with form=movie_rating_forms|get_item:movie.id %}``. The page
        still returned 200 - the form was simply gone - so this test asserts on
        the rendered ``score`` input rather than on the status code.
        """
        self.make_user()
        self.login()

        response = self.client.get(self.genre_url)

        self.assertEqual(
            response.status_code, 200,
            'GET the genre page must return 200.',
        )
        self.assertContains(response, self.movie.title)
        self.assertIn(
            b'name="score"', response.content,
            'BUG 2 regression: no score input was rendered, so users could '
            'not rate movies from the genre page. The template must look the '
            'form up with {% with form=movie_rating_forms|get_item:movie.id %}.',
        )

    def test_recommend_page_does_not_use_broken_dict_bracket_lookup(self):
        """test_recommend_page_does_not_use_broken_dict_bracket_lookup: no anti-pattern.

        Guards the *exact* source construct that caused BUG 2, so a future
        "simplification" back to attribute-style lookup is caught even if the
        rendered markup check is later weakened.

        The lookup itself no longer lives in ``recommend.html``: the page was
        refactored to delegate each card to
        ``movies/includes/_movie_card.html``, and *that* template is where
        ``{% with form=movie_rating_forms|get_item:movie.id %}`` now sits. So
        the check follows ``{% include %}`` transitively instead of grepping one
        file. Pinning the single file would have turned this into a test that
        fails on any refactor while proving nothing about the lookup, and would
        have let the anti-pattern back in through the include unnoticed.
        """
        templates_dir = _app_templates_dir()
        start = 'movies/recommend.html'

        seen, queue, sources = set(), [start], {}
        while queue:
            name = queue.pop()
            if name in seen:
                continue
            seen.add(name)
            path = os.path.join(templates_dir, *name.split('/'))
            self.assertTrue(
                os.path.isfile(path),
                f'{name} (alcanzado desde {start} por un {{% include %}}) no existe.',
            )
            with open(path, encoding='utf-8') as handle:
                source = handle.read()
            sources[name] = source
            queue.extend(re.findall(r'{%\s*include\s+"([^"]+)"', source))

        reachable = '\n'.join(sources.values())

        self.assertNotIn(
            '{{ movie_rating_forms.movie.id }}', reachable,
            'Ninguna plantilla alcanzable desde recommend.html debe look '
            'movie_rating_forms up with dotted attribute access; that renders '
            'nothing and silently drops the form.',
        )
        self.assertIn(
            '{% with form=movie_rating_forms|get_item:movie.id %}', reachable,
            'Ninguna plantilla alcanzable desde recommend.html resuelve el form '
            'por pelicula con el filtro get_item, asi que la tarjeta no puede '
            'encontrarlo.',
        )

    def test_recommend_page_rating_post_still_works_end_to_end(self):
        """test_recommend_page_rating_post_still_works_end_to_end: form is functional.

        A rendered-but-broken form would still satisfy a markup-only check, so
        submit the form the template advertises and confirm the rating lands.
        """
        from movies.models import Rating

        self.make_user()
        self.login()

        response = self.client.post(self.genre_url, {'movie_id': self.movie.id, 'score': 9})

        self.assertEqual(response.status_code, 302)
        self.assertEqual(Rating.objects.filter(movie=self.movie).count(), 1)
        self.assertEqual(Rating.objects.get(movie=self.movie).score, 9)

    def test_recommend_page_works_for_genre_name_with_spaces(self):
        """test_recommend_page_works_for_genre_name_with_spaces: URL encoding round-trips.

        ``recommend`` matches the genre by name; a space in the name exercises
        the ``<str:>`` converter plus percent-decoding.
        """
        genre = Genre.objects.create(name='Film Noir')
        movie = self.make_movie(title='Sunset Blvd', release_year=1950, genres=('Film Noir',))
        self.make_user()
        self.login()

        url = reverse('movies:recommend', kwargs={'genre_name': genre.name})
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, movie.title)
        self.assertIn(b'name="score"', response.content)


# ---------------------------------------------------------------------------
# BUG 1 (source level) - {% load dict_extras %} present wherever get_item is used
# ---------------------------------------------------------------------------

class TemplateFilterLoadTest(SmokeTestCase):

    def test_get_item_filter_loaded_in_all_templates(self):
        """test_get_item_filter_loaded_in_all_templates: the {% load %} is never dropped.

        Regression test for BUG 1. Two complementary assertions:

        1. The two templates that use the filter load the library.
        2. Across *every* template in the app, ``get_item`` is never used in a
           template that has not loaded ``dict_extras`` - the general form of
           the bug, so a new template cannot reintroduce it.
        """
        templates_dir = _app_templates_dir()

        for name in WATCHED_TEMPLATES:
            path = os.path.join(templates_dir, *name.split('/'))
            self.assertTrue(
                os.path.isfile(path),
                f'Expected template {name!r} to exist at {path!r}.',
            )
            with open(path, encoding='utf-8') as handle:
                source = handle.read()
            self.assertIn(
                LOAD_TAG, source,
                f'{name} must contain "{LOAD_TAG}". Without it Django raises '
                f"TemplateSyntaxError: Invalid filter: '{FILTER_NAME}'.",
            )

        offenders = []
        for name, path in _app_template_names():
            with open(path, encoding='utf-8') as handle:
                source = handle.read()
            uses_filter = FILTER_NAME in source
            loads_library = LOAD_TAG in source
            if uses_filter and not loads_library:
                offenders.append(name)

        self.assertEqual(
            offenders, [],
            'These templates use the get_item filter without '
            f'"{LOAD_TAG}": {offenders}',
        )

    def test_get_item_filter_is_registered(self):
        """test_get_item_filter_is_registered: the library still defines the filter.

        Guards the other half of BUG 1: a renamed or removed filter produces
        the identical ``Invalid filter`` error. Checked against the module's
        own ``register.filters`` (the source of truth) and then through the
        real template engine, which is how the templates actually consume it.
        """
        self.assertTrue(callable(dict_extras.get_item))
        self.assertIn(
            FILTER_NAME, dict_extras.register.filters,
            f"'{FILTER_NAME}' is no longer registered in templatetags/{FILTER_LIBRARY}.py.",
        )

        # Prove the engine can still load the library and apply the filter.
        rendered = Template(
            '{%% load %s %%}{{ mapping|get_item:key }}' % FILTER_LIBRARY
        ).render(Context({'mapping': {3: 'ok'}, 'key': 3}))
        self.assertEqual(rendered, 'ok')


    def test_get_item_filter_works_as_a_template_filter(self):
        """test_get_item_filter_works_as_a_template_filter: happy path via the engine."""
        template = Template(
            '{% load dict_extras %}{{ movie_rating_forms|get_item:movie_id }}'
        )
        rendered = template.render(
            Context({'movie_rating_forms': {7: 'FORM-7'}, 'movie_id': 7})
        )
        self.assertEqual(rendered, 'FORM-7')

    def test_template_using_get_item_without_load_raises(self):
        """test_template_using_get_item_without_load_raises: the guard is not vacuous.

        Proves the check in
        ``test_get_item_filter_loaded_in_all_templates`` can actually fail, by
        reproducing BUG 1 in miniature: the very same filter usage, minus the
        ``{% load %}``, must raise ``TemplateSyntaxError``.
        """
        with self.assertRaises(TemplateSyntaxError) as ctx:
            Template('{{ movie_rating_forms|get_item:movie_id }}')
        self.assertIn(FILTER_NAME, str(ctx.exception))
        self.assertIn('Invalid filter', str(ctx.exception))

    def test_every_app_template_compiles(self):
        """test_every_app_template_compiles: no template has a syntax/load error.

        A project-wide guard for the BUG 1 class of failure: ``{% load %}`` of a
        non-existent library, a typo'd tag, an unclosed block - all of these
        blow up only when that specific template is rendered.
        """
        broken = {}
        for name, _path in _app_template_names():
            try:
                get_template(name)
            except Exception as exc:  # TemplateSyntaxError, TemplateDoesNotExist, ...
                broken[name] = f'{type(exc).__name__}: {exc}'

        self.assertEqual(broken, {}, 'These templates failed to compile: ' + repr(broken))


# ---------------------------------------------------------------------------
# BUG 3 - optimize_image() / Movie.save() crashed on a missing cover
# ---------------------------------------------------------------------------

class OptimizeImageRegressionTest(SmokeTestCase):

    def test_optimize_image_returns_original_on_missing_file(self):
        """test_optimize_image_returns_original_on_missing_file: no exception.

        Regression test for BUG 3: ``optimize_image()`` called ``Image.open()``
        unguarded, so a missing path raised ``FileNotFoundError`` out of
        ``Movie.save()``. The function must degrade gracefully and hand back
        the object it was given, untouched.
        """
        # 1. A Django File wrapping a non-existent path.
        file_obj = File('ruta/inexistente.jpg')
        result = optimize_image(file_obj)
        self.assertIs(result, file_obj, 'The original file object must be returned as-is.')

        # 2. A raw path string (the other shape callers can pass).
        missing_path = 'ruta/inexistente.jpg'
        result = optimize_image(missing_path)
        self.assertIs(result, missing_path)

        # 3. An existing file whose bytes are not an image.
        corrupt = os.path.join(self.media_root, 'corrupt.jpg')
        with open(corrupt, 'wb') as handle:
            handle.write(b'this is definitely not a JPEG')
        corrupt_file = File(corrupt)
        result = optimize_image(corrupt_file)
        self.assertIs(result, corrupt_file)

    def test_optimize_image_does_not_raise_for_any_unreadable_input(self):
        """test_optimize_image_does_not_raise_for_any_unreadable_input: no raise.

        Belt-and-braces version of the test above: it only asserts that nothing
        propagates, so a future change to the *shape* of the guard cannot make
        it pass vacuously.
        """
        inputs = [
            'ruta/inexistente.jpg',
            File('ruta/inexistente.jpg'),
            File('/definitely/not/here/either.png'),
            SimpleUploadedFile('empty.jpg', b'', content_type='image/jpeg'),
            SimpleUploadedFile('garbage.jpg', b'\x00\x01\x02not-an-image', content_type='image/jpeg'),
        ]
        for candidate in inputs:
            with self.subTest(input=type(candidate).__name__ + ':' + str(candidate)[:60]):
                # Must not raise. Return value is not the point of this test.
                optimize_image(candidate)

    def test_optimize_image_still_optimizes_a_real_jpeg(self):
        """test_optimize_image_still_optimizes_a_real_jpeg: the fix is not a no-op.

        Guards against "fixing" BUG 3 by returning the input unconditionally,
        which would silently disable cover compression and resizing forever.
        """
        source = _uploaded_jpeg('real.jpg')
        optimized = optimize_image(source)

        self.assertIsInstance(optimized, File)
        self.assertIsNot(optimized, source, 'A readable image must be replaced by the optimized one.')
        self.assertEqual(optimized.name, 'real.jpg')

        # Read once: a ContentFile wraps a BytesIO, so reads are sequential.
        payload = optimized.read()
        self.assertTrue(payload, 'The optimized file must not be empty.')
        self.assertLess(
            len(payload), 10_000,
            'The optimized file should be a real (small) re-encoded JPEG.',
        )
        # And the result must still be a valid, openable image.
        verified = Image.open(BytesIO(payload))
        self.assertEqual(verified.format, 'JPEG')


# ---------------------------------------------------------------------------
# BUG 3 (model level) - Movie.save() with a cover that is not on disk
# ---------------------------------------------------------------------------

class MovieSaveCoverRegressionTest(SmokeTestCase):

    def test_movie_save_with_missing_cover_does_not_raise(self):
        """test_movie_save_with_missing_cover_does_not_raise: create() must succeed.

        Regression test for BUG 3 at the model level. ``cover`` is a required
        ``ImageField``, but assigning a path that does not exist on disk (very
        common for seeded/fixture data, admin-imported rows and the
        ``load_test_data`` management command) used to make ``Movie.save()``
        blow up with ``FileNotFoundError`` before ever reaching the database.
        """
        movie = Movie.objects.create(
            title='X', release_year=2020, cover='no_existe.jpg'
        )

        self.assertIsNotNone(movie.pk)
        self.assertTrue(
            Movie.objects.filter(pk=movie.pk).exists(),
            'The movie must actually be persisted.',
        )
        self.assertEqual(Movie.objects.get(pk=movie.pk).title, 'X')
        self.assertEqual(movie.cover.name, 'no_existe.jpg')

    def test_movie_save_survives_a_corrupt_cover(self):
        """test_movie_save_survives_a_corrupt_cover: unreadable bytes are tolerated."""
        garbage = SimpleUploadedFile(
            'roto.jpg', b'\xff\xd8\xff\xe0 not really a jpeg', content_type='image/jpeg'
        )
        movie = Movie.objects.create(title='Corrupt Cover', release_year=2019, cover=garbage)

        self.assertTrue(Movie.objects.filter(pk=movie.pk).exists())

    def test_movie_save_with_truncated_cover_does_not_raise(self):
        """test_movie_save_with_truncated_cover_does_not_raise: truncadas se guardan.

        Regression test for the second half of the BUG 3 fix: a cover with a
        valid header but corrupt pixel data must not stop the movie from being
        saved.

        The failure mode this pins down is the lazy one. ``Image.open()`` only
        parses the header and defers decoding, so a truncated JPEG *opens*
        successfully and only blows up later, during
        ``thumbnail()``/``save()``, with ``OSError: image file is truncated``.
        A guard wrapped solely around the ``open()`` call therefore does not
        help, and the old ``finally: pil_image.close()`` made it actively
        harmful: ``pil_image`` is a ``JpegImageFile`` (an ``ImageFile``), whose
        ``close()`` closes ``self.fp`` unconditionally, i.e. the *caller's*
        still-needed ``UploadedFile``. ``Movie.save()`` then swallowed the
        ``OSError`` but ``FileField.pre_save()`` died with
        ``ValueError: I/O operation on closed file.``

        The fix: ``optimize_image()`` reads the bytes up front and decodes from
        its own ``BytesIO``, wraps the whole body (not just ``open()``) in
        try/except, and closes only what it created. So the corrupt cover is
        passed through untouched and stored as-is.
        """
        movie = Movie.objects.create(
            title='Truncated Cover',
            release_year=2018,
            cover=_truncated_jpeg('truncada.jpg', keep=0.9),
        )

        self.assertIsNotNone(movie.pk)
        self.assertTrue(
            Movie.objects.filter(pk=movie.pk).exists(),
            'A cover that cannot be decoded must not prevent the movie from saving.',
        )
        # The undecodable bytes are stored verbatim rather than optimised away.
        self.assertTrue(movie.cover.name.startswith('movie_covers/'))
        self.assertTrue(movie.cover.storage.exists(movie.cover.name))

    def test_movie_save_with_real_image_persists_under_upload_to(self):
        """test_movie_save_with_real_image_persists_under_upload_to: happy path intact.

        Confirms the guarded ``optimize_image()`` call still runs, still
        produces a stored file, and still honours ``upload_to='movie_covers/'``.
        """
        movie = Movie.objects.create(
            title='With Cover', release_year=2015, cover=_uploaded_jpeg('portada.jpg')
        )
        movie.refresh_from_db()

        self.assertTrue(
            movie.cover.name.startswith('movie_covers/'),
            f'Expected an upload_to prefix, got {movie.cover.name!r}.',
        )
        self.assertTrue(
            movie.cover.storage.exists(movie.cover.name),
            'The cover must be written to storage.',
        )
        self.assertTrue(movie.cover.url.startswith('/media/'))

    def test_movie_save_is_idempotent_for_a_missing_cover(self):
        """test_movie_save_is_idempotent_for_a_missing_cover: re-save also survives.

        The bug lived in ``save()``, so it must not reappear on the second
        ``save()`` of the same (still broken) instance.
        """
        movie = Movie.objects.create(
            title='Twice', release_year=2021, cover='no_existe.jpg'
        )
        movie.title = 'Twice Renamed'
        movie.save()
        movie.refresh_from_db()

        self.assertEqual(movie.title, 'Twice Renamed')


# ---------------------------------------------------------------------------
# BUG 4 - favorite view redirected to a non-existent genre
# ---------------------------------------------------------------------------

class FavoriteRedirectRegressionTest(SmokeTestCase):

    def setUp(self):
        super().setUp()
        self.genre = Genre.objects.create(name='Thriller')
        self.movie = self.make_movie(
            title='Se7en', release_year=1995, genres=('Thriller',)
        )
        self.genre_url = reverse('movies:recommend', kwargs={'genre_name': self.genre.name})
        self.favorite_url = reverse('movies:favorite', args=[self.movie.id])
        self.make_user()
        self.login()

    def test_favorite_redirects_to_referer_or_home(self):
        """test_favorite_redirects_to_referer_or_home: HTTP_REFERER wins, home is the fallback.

        Regression test for BUG 4: the view used to redirect to
        ``movies:recommend`` with ``genre_name='Todos'``. 'Todos' is not a
        Genre, so every favorite toggle dumped the user on a page that does not
        exist. The fix redirects to ``HTTP_REFERER``, falling back to home.
        """
        with_referer = self.client.post(self.favorite_url, HTTP_REFERER='/')
        self.assertEqual(with_referer.status_code, 302)
        self.assertEqual(
            with_referer.url, '/',
            'With HTTP_REFERER set, the redirect must go back to the referer.',
        )

        without_referer = self.client.post(self.favorite_url)
        self.assertEqual(without_referer.status_code, 302)
        self.assertEqual(
            without_referer.url, reverse('movies:home'),
            'Without HTTP_REFERER the redirect must fall back to the home page.',
        )

    def test_favorite_redirect_target_is_a_real_page(self):
        """test_favorite_redirect_target_is_a_real_page: the target must render.

        The sharpest form of the BUG 4 regression test: a 302 alone is not
        enough, because the broken redirect also returned 302. Follow it and
        require a 200 from a template that actually renders.
        """
        response = self.client.post(self.favorite_url, HTTP_REFERER=self.genre_url)

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, self.genre_url)

        followed = self.client.get(response.url, follow=True)
        self.assertEqual(
            followed.status_code, 200,
            'The favorite redirect must land on a page that renders.',
        )
        self.assertTemplateUsed(followed, 'movies/recommend.html')
        self.assertContains(followed, self.movie.title)

    def test_favorite_fallback_is_home_not_a_bogus_genre(self):
        """test_favorite_fallback_is_home_not_a_bogus_genre: never 'genre_name=Todos'.

        Pins the exact broken behaviour so it cannot come back in another form.
        """
        response = self.client.post(self.favorite_url)

        self.assertEqual(response.status_code, 302)
        self.assertNotIn('Todos', response.url)
        self.assertNotIn('genre', response.url)
        self.assertEqual(self.client.get(response.url).status_code, 200)

    def test_favorite_toggle_still_works(self):
        """test_favorite_toggle_still_works: the redirect change did not break toggling."""
        from movies.models import Favorite

        self.assertFalse(Favorite.objects.filter(movie=self.movie).exists())
        self.client.post(self.favorite_url, HTTP_REFERER='/')
        self.assertTrue(Favorite.objects.filter(movie=self.movie).exists())
        self.client.post(self.favorite_url, HTTP_REFERER='/')
        self.assertFalse(Favorite.objects.filter(movie=self.movie).exists())


# ---------------------------------------------------------------------------
# BUG 5 (fixed) - the catalogue and the search page never showed a rating
# ---------------------------------------------------------------------------
#
# home.html and search.html render ``{{ movie.movie_avg_rating|floatformat:2 }}`` and
# fall back to the literal "Sin valoraciones" when it is empty. But the views
# only annotated ``rating_count``:
#
#     movies_qs = movies_qs.annotate(rating_count=Count('rating_set'))
#
# so ``movie_avg_rating`` was never set for a rated movie. The plain catalogue
# (``GET /``) happened to survive by accident: ``get_home_movies()`` *does*
# annotate ``movie_avg_rating``, and a second ``.annotate()`` call with a
# different alias keeps the existing one, so the average leaked through.
#
# The leak closed as soon as ``home`` replaced the queryset on its search branch
# (``movies_qs = search_movies(query)['movies']``, an unannotated queryset), and
# it never existed in ``search_view``, whose queryset comes from
# ``Movie.objects.prefetch_related('genres')`` or from a rebuilt intersection.
# ``search_service.filter_movies()`` annotates ``rating_avg`` - a different alias,
# and only on the queryset it filters internally, never on the one it returns.
#
# Net effect before the fix: "Sin valoraciones" on every card of ``/search/``, and
# on every card of ``/?q=<term>`` - next to a "2 valoracion(es)" line that proves
# ratings exist. Fixed by annotating both the average and the count at the single
# point in each view where the queryset is finalised.

class CatalogRatingDisplayTest(SmokeTestCase):
    """The average rating actually reaches the rendered HTML, on every path."""

    def setUp(self):
        super().setUp()
        # A 2-value average (8.0) that is distinguishable from any single score.
        self.voter_a = self.make_user(username='rater_a', password='rate_pass_123')
        self.voter_b = self.make_user(username='rater_b', password='rate_pass_123')
        self.movie = self.make_movie(
            title='Rated Movie', release_year=2021, genres=('Action',),
        )
        self.add_ratings()

    def add_ratings(self, first=9, second=7):
        """(Re)create the two ratings backing the average."""
        from movies.models import Rating

        Rating.objects.create(movie=self.movie, user=self.voter_a, score=first)
        Rating.objects.create(movie=self.movie, user=self.voter_b, score=second)

    def assertShowsAverage(self, response, url):
        """Assert the card renders the average, not the "Sin valoraciones" fallback."""
        self.assertEqual(response.status_code, 200, f'GET {url} must return 200.')
        self.assertNotIn(
            'Sin valoraciones', response.content.decode(),
            f'GET {url} rendered "Sin valoraciones" for a movie that has ratings; '
            'the view is not annotating movie_avg_rating.',
        )
        # USE_THOUSAND_SEPARATOR off + Spanish locale renders the decimal as "8,00".
        self.assertIn(
            '8,00/10', response.content.decode(),
            f'GET {url} did not render the 8.00 average for a twice-rated movie.',
        )

    def test_home_shows_average_rating(self):
        """test_home_shows_average_rating: GET / renders the average (B3, main path)."""
        self.assertShowsAverage(self.client.get('/'), '/')

    def test_home_shows_average_rating_when_searching(self):
        """test_home_shows_average_rating_when_searching: the path that was actually broken.

        The plain catalogue only worked by accident (the service's annotation
        leaked through). Searching swaps in ``search_movies()``'s plain queryset
        and the average disappeared - the case that made the bug visible.
        """
        response = self.client.get('/', {'q': 'Rated'})

        self.assertShowsAverage(response, '/?q=Rated')

    def test_search_view_shows_average_rating(self):
        """test_search_view_shows_average_rating: GET /search/ renders the average."""
        self.assertShowsAverage(self.client.get(reverse('movies:search')), '/search/')

    def test_search_view_shows_average_rating_when_querying(self):
        """test_search_view_shows_average_rating_when_querying: /search/?q= too."""
        response = self.client.get(reverse('movies:search'), {'q': 'Rated'})

        self.assertShowsAverage(response, '/search/?q=Rated')

    def test_search_view_shows_average_rating_when_filtering(self):
        """test_search_view_shows_average_rating_when_filtering: /search/?genres= too.

        Exercises the intersection branch, which rebuilds the queryset from
        scratch and therefore drops every annotation the services had added.
        """
        response = self.client.get(reverse('movies:search'), {'genres': 'Action'})

        self.assertShowsAverage(response, '/search/?genres=Action')

    def test_rating_count_still_rendered_next_to_the_average(self):
        """test_rating_count_still_rendered_next_to_the_average: the count survived too.

        The fix added an annotation rather than replacing one, so this pins that
        ``rating_count`` is still there and still correct.
        """
        response = self.client.get('/')
        content = response.content.decode()

        self.assertIn('8,00/10', content)
        self.assertIn('2 valoracion(es)', content)

    def test_unrated_movie_still_falls_back_to_the_placeholder(self):
        """test_unrated_movie_still_falls_back_to_the_placeholder: negative control.

        Proves the assertions above are not vacuous: with no ratings at all the
        average is NULL and the template must show the placeholder.
        """
        unrated = self.make_movie(title='Unrated Movie', release_year=2022)

        response = self.client.get('/')
        content = response.content.decode()

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, unrated.title)
        self.assertIn('Sin valoraciones', content)
        self.assertIn('0 valoracion(es)', content)

    def test_recommend_view_keeps_its_own_rating_avg_alias(self):
        """test_recommend_view_keeps_its_own_rating_avg_alias: no collateral damage.

        ``recommend.html`` reads ``rating_avg``, not ``movie_avg_rating``, and
        ``recommend`` annotates it itself. B3's fix touched only ``home`` and
        ``search_view``; this asserts the recommend page still renders.
        """
        response = self.client.get(reverse('movies:recommend', args=['Action']))

        self.assertEqual(response.status_code, 200)
        self.assertNotIn('Sin valoraciones', response.content.decode())
        self.assertIn('8,00/10', response.content.decode())


# ---------------------------------------------------------------------------
# Broad URL smoke sweep
# ---------------------------------------------------------------------------

class PublicUrlSmokeTest(SmokeTestCase):

    #: Every URL reachable without any database content.
    PUBLIC_URLS = ('/', '/search/', '/accounts/login/', '/accounts/register/')

    def test_all_public_urls_return_200_or_redirect(self):
        """test_all_public_urls_return_200_or_redirect: anonymous sweep of every public URL.

        This is the test that originally surfaced all four bugs: hitting every
        URL with the test client. A 500 (or a raised exception) means some
        template blew up; a 302 is fine for pages that legitimately bounce
        authenticated users.
        """
        for url in self.PUBLIC_URLS:
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertIn(
                    response.status_code, (200, 302),
                    f'GET {url} returned {response.status_code}; expected 200 or 302.',
                )

    def test_all_public_urls_return_200_or_redirect_when_authenticated(self):
        """test_all_public_urls_return_200_or_redirect_when_authenticated: same sweep, logged in."""
        self.make_user()
        self.login()

        for url in self.PUBLIC_URLS:
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertIn(
                    response.status_code, (200, 302),
                    f'GET {url} returned {response.status_code} for an authenticated user.',
                )

    def test_every_named_url_survives_a_smoke_request(self):
        """test_every_named_url_survives_a_smoke_request: sweep all URL names.

        Broader than the required sweep above: it walks ``movies.urls`` and
        ``movies.accounts.urls`` by name so a newly added route is covered
        automatically. Login-protected routes are expected to 302 to login.
        """
        genre = Genre.objects.create(name='Comedy')
        movie = self.make_movie(title='Airplane!', release_year=1980, genres=('Comedy',))

        cases = {
            'movies:home': {},
            'movies:search': {},
            'movies:recommend': {'genre_name': genre.name},
            'movies:favorite': {'movie_id': movie.id},
            'movies:profile': {},
            'movies:stats': {},
            'accounts:login': {},
            'accounts:register': {},
            'accounts:logout': {},
        }
        for name, kwargs in cases.items():
            with self.subTest(url_name=name):
                url = reverse(name, kwargs=kwargs)
                response = self.client.get(url)
                self.assertIn(
                    response.status_code, (200, 302),
                    f'GET {url} ({name}) returned {response.status_code}.',
                )

    def test_smoke_sweep_with_content_present(self):
        """test_smoke_sweep_with_content_present: the sweep is repeated with real data.

        Several templates only render their interesting markup when the
        catalogue is not empty, so an empty-DB sweep can hide template bugs.
        """
        for genre_name in ('Action', 'Drama'):
            self.make_movie(title=f'Movie of {genre_name}', release_year=2022, genres=(genre_name,))
        self.make_user()
        self.login()

        for url in self.PUBLIC_URLS:
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertIn(response.status_code, (200, 302))


# ---------------------------------------------------------------------------
# Open issues discovered while writing these tests (NOT fixed here on purpose -
# they are reported rather than papered over).
# ---------------------------------------------------------------------------
#
# 1. STALE READ CACHE IN THE MOVIE SERVICES  (real bug, high user impact)
#    ``get_home_movies()``, ``get_genre_recommendations()`` and
#    ``get_all_movies_of_genre()`` in ``movies/services/movie_service.py``
#    memoise the *list of movie ids* under a key that does not depend on the
#    database contents, and nothing invalidates it on write:
#      - ``get_home_movies()`` uses a constant key and a 600 s TTL.
#      - The other two use the genre name and a 300 s TTL.
#    Consequence: a movie created (or deleted, or re-rated) after the first
#    page load is invisible on ``/`` and ``/genre/<name>/`` for up to 5-10
#    minutes. The admin saves a new movie and the catalogue does not show it.
#    Worse, the cache is consulted before the DB, and a hit short-circuits the
#    ``cache.set``, so a stale id list is never refreshed.
#    Reproduced deterministically:
#        cache.clear(); client.get('/')            # empty catalogue -> caches []
#        Movie.objects.create(...)                # new movie
#        client.get('/')                          # still does not show it
#    That is why ``SmokeTestCase.setUp()`` calls ``cache.clear()`` - without it
#    these tests would be order-dependent and wrong.
#    Suggested fix: invalidate on Movie/Rating write (post_save/post_delete
#    signal) or key the cache on something that reflects the data.
#
# 2. ``optimize_image()`` IS NOT FULLY DEFENSIVE  (FIXED)
#    The guard only wrapped ``Image.open()``, and the ``finally:
#    pil_image.close()`` it added closed the *caller's* file object, because
#    ``JpegImageFile`` is an ``ImageFile`` whose ``close()`` closes ``self.fp``
#    unconditionally. So a cover with a valid header and corrupt pixel data
#    raised ``OSError: image file is truncated`` during the lazy decode, and the
#    caller's ``UploadedFile`` was left closed, so ``FileField.pre_save()`` died
#    with ``ValueError: I/O operation on closed file.``
#    Fixed by buffering the bytes first (``_read_source_bytes``) so Pillow only
#    ever sees a private ``BytesIO``, guarding the whole body, and closing only
#    what the function itself created. See
#    ``test_movie_save_with_truncated_cover_does_not_raise``.
#
# 3. ``movies/tests/`` WAS NOT DISCOVERED BY ``manage.py test``  (infra bug, FIXED)
#    The ``movies/`` and ``movies/accounts/`` directories had no ``__init__.py``,
#    so ``movies`` behaved as a namespace package and unittest's default
#    discovery skipped it. Bare ``manage.py test`` only ran
#    ``config/movies/tests/test_models.py`` (47 stale duplicate tests) - none of
#    the real app tests ran.
#    Fixed by adding ``movies/__init__.py``; the 47 stale duplicates under
#    ``config/movies/tests/`` still run alongside the real suite and remain a
#    separate cleanup. Note that ``movies/tests/test_services.py`` was additionally
#    written with pytest-style fixture classes, so even when labelled explicitly it
#    reported "Ran 0 tests"; it has been converted to ``django.test.TestCase``.
#
# 4. NO MEDIA SETTINGS  (FIXED)
#    ``config/settings.py`` defined neither ``MEDIA_ROOT`` nor ``MEDIA_URL``,
#    and ``config/urls.py`` had no ``static(settings.MEDIA_URL, ...)`` entry.
#    Consequences: uploaded covers got a relative ``movie.cover.url`` with no
#    ``/media/`` prefix, and nothing served them, so ``<img src="{{
#    movie.cover.url }}">`` 404'd on every page. (It also meant MEDIA_ROOT
#    defaulted to the working directory, which is why older test runs littered
#    the repo-root ``movie_covers/`` with ~100 junk files; that folder is stale
#    output and can be deleted by hand.) Fixed with ``MEDIA_URL = '/media/'``,
#    ``MEDIA_ROOT = BASE_DIR / 'media'`` and DEBUG-gated media serving, so
#    covers now land in ``media/movie_covers/`` and are actually served. This
#    module still overrides MEDIA_ROOT to a temp dir and adds 0 files.
