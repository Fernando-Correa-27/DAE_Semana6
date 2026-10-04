"""
Regresion: los errores de validacion de puntuacion NUNCA se muestran.

El bug
------
``home`` y ``recommend`` construyen ``movie_rating_forms`` indexado por **int**
(la clave es ``movie.id``), pero al procesar un POST invalido guardaban el
formulario con errores bajo la clave **cruda de ``request.POST``**, que siempre
es ``str``::

    movie_rating_forms[movie.id] = ...          # clave int   -> {16: form}
    movie_rating_forms[movie_id] = rating_form  # clave str   -> {'16': form}

Python no las considera iguales, asi que la entrada con errores era una clave
nueva y huerfana que la plantilla nunca busca. La plantilla resuelve el form con
``{% with form=movie_rating_forms|get_item:movie.id %}`` y ``movie.id`` es un
int, de modo que la tarjeta seguia pintando un ``RatingForm`` *vacio* (sin
errores). El POST fallido se reducia al ``alert-danger`` global: el usuario no
veia que campo habia fallado ni por que. Eso rompe el Criterio 1 (Validation).

Como se demuestra
------------------
Los tests son conductuales: usan el cliente de pruebas real y el motor de
plantillas real, y comprueban el HTML renderizado (``is-invalid`` + el mensaje
de ``form.score.errors``), no el contexto. Comprobarian "verde" con un contexto
correcto y una clave huerfana.

El mensaje esperado no esta escrito a mano: se deriva de un ``RatingForm`` real
construido con la misma entrada, asi que el test sigue siendo valido aunque
Django o la locale cambien el texto. Ademas se asegura de que el formulario
produce al menos un error, para que la derivacion no pueda quedar vacia.

Nota sobre el caso borde de ``recommend``
-----------------------------------------
La ficha de ``recommend`` recorre dos listas: ``recommendations`` (top valoradas
del genero, top-10) y ``all_movies_of_genre`` (todas, incluidas las sin
valorar). ``movie_rating_forms`` se puebla con las dos, asi que una peli que
solo aparece en "Todas las peliculas" - porque no tiene ninguna valoracion, o
porque hay mas de 10 en el genero - si tiene clave. Se cubre con
``test_recommend_error_shown_for_movie_only_in_all_movies_section``, que es
justo el escenario que el diccionario incompleto dejaria sin errores visibles.
"""

import shutil
import tempfile
from io import BytesIO

from django.contrib.auth.models import User
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from PIL import Image

from movies.forms import RatingForm
from movies.models import Genre, Movie, Rating


#: Marcador que ``_movie_card.html`` pone en el input cuando ``form.score.errors``
#: es truthy, y que hace visible el ``invalid-feedback`` de Bootstrap.
INVALID_MARKER = 'is-invalid'

#: Apertura/cierre de cada tarjeta de pelicula, para poder localizar en que
#: tarjeta cae un error concreto.
CARD_OPEN = '<article'
CARD_CLOSE = '</article>'


def _tiny_jpeg() -> SimpleUploadedFile:
    """JPEG real minimo, para que ``Movie.cover`` sea un ImageField de verdad."""
    buffer = BytesIO()
    Image.new('RGB', (16, 16), (10, 120, 200)).save(buffer, format='JPEG')
    return SimpleUploadedFile('cover.jpg', buffer.getvalue(), content_type='image/jpeg')


class RatingErrorTestCase(TestCase):
    """Base: cache limpia, MEDIA_ROOT desechable, movie y usuario de apoyo.

    ``cache.clear()`` es obligatorio: ``get_home_movies()``,
    ``get_genre_recommendations()`` y ``get_all_movies_of_genre()`` memorizan la
    *lista de ids* en un ``LocMemCache`` bajo una clave que no depende de la
    base de datos, y el runner no la limpia entre tests. Sin esto, una pagina
    renderizada con el catalogo vacio seguiria devolviendo "no hay peliculas"
    durante el resto del proceso.
    """

    def setUp(self):
        super().setUp()
        cache.clear()
        self.addCleanup(cache.clear)

        media_root = tempfile.mkdtemp(prefix='rating_errors_media_')
        self.addCleanup(shutil.rmtree, media_root, True)
        self.settings_override = self.settings(MEDIA_ROOT=media_root, MEDIA_URL='/media/')
        self.settings_override.enable()
        self.addCleanup(self.settings_override.disable)

        self.user = User.objects.create_user(
            username='rater', password='rate_pass_123', email='rater@example.com'
        )
        self.assertTrue(
            self.client.login(username='rater', password='rate_pass_123'),
            'No se pudo iniciar sesion; el setup del test esta roto.',
        )

    # -- helpers de datos ---------------------------------------------------

    def make_movie(self, title, genre_name, release_year=2020):
        genre = Genre.objects.get_or_create(name=genre_name)[0]
        movie = Movie.objects.create(
            title=title, release_year=release_year, cover=_tiny_jpeg()
        )
        movie.genres.add(genre)
        return movie

    def rate(self, movie, score, username='someone_else'):
        """Crea una valoracion ajena, para que la peli entre en ``recommendations``."""
        voter = User.objects.create_user(
            username=username, password='voter_pass_123', email=f'{username}@example.com'
        )
        return Rating.objects.create(movie=movie, user=voter, score=score)

    # -- helpers de asercion -----------------------------------------------

    def expected_score_errors(self, payload):
        """Los mensajes que ``RatingForm`` produce para ``payload``.

        Se derivan del formulario real en vez de escribirse a mano: el texto
        depende de la locale activa, y lo que interesa es que la vista muestre
        *el* error del form, no una cadena literal. El ``assertTrue`` evita que
        una derivacion vacia convierta el test en un tautologia.
        """
        form = RatingForm(payload)
        self.assertFalse(
            form.is_valid(),
            f'Renguna validacion posible: {payload!r} es un POST valido, asi que '
            'este test no comprobaria nada.',
        )
        errors = list(form.errors.get('score', []))
        self.assertTrue(
            errors,
            f'Rengun error en el campo "score" para {payload!r}; el setup esta roto.',
        )
        return errors

    def cards(self, response):
        """El HTML de cada tarjeta de pelicula de la pagina, por separado."""
        html = response.content.decode()
        return [
            CARD_OPEN + chunk.split(CARD_CLOSE)[0]
            for chunk in html.split(CARD_OPEN)[1:]
        ]

    def assertNoInlineError(self, response, why):
        """Control negativo: la pagina no debe traer ningun ``is-invalid``."""
        self.assertNotIn(
            INVALID_MARKER, response.content.decode(),
            f'{why}: la pagina trae "{INVALID_MARKER}" aunque no hay ningun POST '
            'fallido. Las aserciones de este modulo no serian concluyentes.',
        )

    def assertInlineError(self, response, message, movie=None):
        """El HTML debe marcar el input como invalido y mostrar ``message``."""
        html = response.content.decode()

        self.assertIn(
            INVALID_MARKER, html,
            'El POST fue rechazado pero el HTML no marca ningun input como '
            f'"{INVALID_MARKER}": el formulario con errores no llego a la '
            'plantilla, asi que el usuario no ve que campo fallo ni por que. '
            'Revisar la clave con la que la vista guarda el form en '
            'movie_rating_forms (debe ser movie.id, un int).',
        )
        self.assertIn(
            message, html,
            f'El input se marca como invalido pero el mensaje {message!r} no '
            'aparece en la pagina: la plantilla no esta pintando form.score.errors.',
        )

        if movie is not None:
            self.assert_error_is_on_movie_card(response, movie, message)

    def assert_error_is_on_movie_card(self, response, movie, message):
        """El error tiene que caer en la tarjeta de *esa* peli, no en otra.

        No se exige "exactamente una tarjeta marcada" porque ``recommend.html``
        pinta cada peli *dos* veces -en "Recomendadas" y en "Todas las peliculas
        del genero"-, asi que la misma peli puede tener dos tarjetas marcadas y
        ambas son correctas. Lo que si debe cumplirse es que **toda** tarjeta
        marcada sea de la peli del POST, que es lo que distingue un enlace
        correcto de un error pintado en la tarjeta de al lado.
        """
        cards = self.cards(response)
        with_error = [card for card in cards if INVALID_MARKER in card]
        marker = f'name="movie_id" value="{movie.id}"'

        self.assertTrue(
            with_error,
            f'Ninguna tarjeta de {movie.title!r} (id={movie.id}) aparece '
            f'marcada con "{INVALID_MARKER}".',
        )
        for card in with_error:
            self.assertIn(
                marker, card,
                f'El error aparece en la tarjeta de otra pelicula: hay una '
                f'tarjeta con "{INVALID_MARKER}" cuyo movie_id no es '
                f'{movie.id} ({movie.title!r}).',
            )
            self.assertIn(movie.title, card)
            self.assertIn(message, card)

    def assert_card_has_no_error(self, response, movie):
        """La tarjeta de una peli que no se posted no debe marcarse invalida."""
        for card in self.cards(response):
            if f'name="movie_id" value="{movie.id}"' in card:
                self.assertNotIn(
                    INVALID_MARKER, card,
                    f'La tarjeta de {movie.title!r} (id={movie.id}) aparece '
                    'marcada como invalida sin que se le haya enviado un POST.',
                )
                return
        self.fail(f'No se encontro la tarjeta de {movie.title!r} (id={movie.id}).')


# ---------------------------------------------------------------------------
# 1-3  POST invalido en home -> el error se ve en la tarjeta
# ---------------------------------------------------------------------------

class HomeRatingInlineErrorTest(RatingErrorTestCase):

    def setUp(self):
        super().setUp()
        self.movie = self.make_movie('Alien', 'Horror', release_year=1979)
        self.other = self.make_movie('Aliens', 'Horror', release_year=1986)

    def test_home_invalid_score_shows_inline_error(self):
        """test_home_invalid_score_shows_inline_error: score=99 -> error visible.

        El caso que reporto el bug: 99 supera el ``max_value=10`` de
        ``RatingForm.score``, asi que el form es invalido, la vista no redirige
        y debe re-renderizar la pagina con el error pegado a la tarjeta.
        """
        payload = {'movie_id': self.movie.id, 'score': 99}
        (message,) = self.expected_score_errors(payload)

        response = self.client.post(reverse('movies:home'), payload)

        self.assertEqual(
            response.status_code, 200,
            'Un POST invalido debe re-renderizar la pagina, no redirigir: si '
            'redirige, el usuario pierde el contexto por completo.',
        )
        self.assertTemplateUsed(response, 'movies/home.html')
        self.assertInlineError(response, message, movie=self.movie)
        self.assert_card_has_no_error(response, self.other)
        self.assertFalse(
            Rating.objects.filter(movie=self.movie).exists(),
            'Un POST invalido no debe crear ninguna valoracion.',
        )

    def test_home_missing_score_shows_inline_error(self):
        """test_home_missing_score_shows_inline_error: sin campo score -> error.

        El input de la tarjeta lleva ``required``, asi que el navegador no
        dejaria enviar el form vacio; pero el POST existe (curl, tests,
        atajos de teclado, bots) y la vista no puede asumir el ``required``.
        """
        payload = {'movie_id': self.movie.id}
        (message,) = self.expected_score_errors(payload)

        response = self.client.post(reverse('movies:home'), payload)

        self.assertEqual(response.status_code, 200)
        self.assertInlineError(response, message, movie=self.movie)
        self.assertFalse(Rating.objects.filter(movie=self.movie).exists())

    def test_home_non_numeric_score_shows_inline_error(self):
        """test_home_non_numeric_score_shows_inline_error: score=abc -> error.

        ``score`` es un ``IntegerField``: una entrada no numerica falla en
        ``to_python`` antes incluso de chegar a ``clean_score``.
        """
        payload = {'movie_id': self.movie.id, 'score': 'abc'}
        (message,) = self.expected_score_errors(payload)

        response = self.client.post(reverse('movies:home'), payload)

        self.assertEqual(response.status_code, 200)
        self.assertInlineError(response, message, movie=self.movie)
        self.assertFalse(Rating.objects.filter(movie=self.movie).exists())

    def test_home_valid_score_shows_no_inline_error(self):
        """test_home_valid_score_shows_no_inline_error: control negativo.

        Sin este control, ``is-invalid`` podria aparecer siempre (por ejemplo si
        el campo quedara marcado por el estado de error global) y las pruebas
        anteriores no probarian nada.
        """
        response = self.client.get(reverse('movies:home'))

        self.assertEqual(response.status_code, 200)
        self.assertNoInlineError(response, 'Un GET simple de la home')


# ---------------------------------------------------------------------------
# 4  POST invalido en recommend -> el error se ve en la tarjeta
# ---------------------------------------------------------------------------

class RecommendRatingInlineErrorTest(RatingErrorTestCase):

    def setUp(self):
        super().setUp()
        self.genre = Genre.objects.create(name='Science Fiction')
        self.top_rated = self.make_movie('Interstellar', 'Science Fiction', 2014)
        self.rate(self.top_rated, 9, username='rater_interstellar')
        self.genre_url = reverse(
            'movies:recommend', kwargs={'genre_name': self.genre.name}
        )

    def test_recommend_invalid_score_shows_inline_error(self):
        """test_recommend_invalid_score_shows_inline_error: mismo bug, otra vista.

        ``recommend`` duplica la logica de ``home`` (copia-pega del bloque de
        POST), asi que el bug venia en dos. El POST va por el ``action`` que la
        tarjeta recibe via ``form_action``, asi que es la misma peticion real.
        """
        payload = {'movie_id': self.top_rated.id, 'score': 99}
        (message,) = self.expected_score_errors(payload)

        response = self.client.post(self.genre_url, payload)

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'movies/recommend.html')
        self.assertInlineError(response, message, movie=self.top_rated)
        self.assertFalse(Rating.objects.filter(user=self.user).exists())

    def test_recommend_error_shown_for_movie_only_in_all_movies_section(self):
        """test_recommend_error_shown_for_movie_only_in_all_movies_section: la ficha sin nota.

        Caso borde que el reporte senalo: ``recommendations`` se construye con
        ``get_movie_recommendations``, que filtra ``rating_avg__isnull=False``, y
        ademas esta limitada a 10. Una peli sin ninguna valoracion no aparece
        nunca ahi; solo sale en "Todas las peliculas del genero". Si el
        diccionario se poblara solo con ``recommendations``, su formulario con
        errores seria invisible. ``all_movies = list(recommendations) +
        list(all_movies_of_genre)`` es justamente lo que lo evita, y este test
        lo fija.
        """
        unrated = self.make_movie('Dune', 'Science Fiction', 2021)
        self.assertFalse(Rating.objects.filter(movie=unrated).exists())

        payload = {'movie_id': unrated.id, 'score': 99}
        (message,) = self.expected_score_errors(payload)

        response = self.client.post(self.genre_url, payload)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, unrated.title)
        self.assertInlineError(response, message, movie=unrated)

    def test_recommend_valid_score_shows_no_inline_error(self):
        """test_recommend_valid_score_shows_no_inline_error: control negativo."""
        response = self.client.get(self.genre_url)

        self.assertEqual(response.status_code, 200)
        self.assertNoInlineError(response, 'Un GET simple de la pagina de genero')


# ---------------------------------------------------------------------------
# 5  Control negativo: un POST valido redirige y no deja errores
# ---------------------------------------------------------------------------

class ValidRatingNoErrorTest(RatingErrorTestCase):

    def setUp(self):
        super().setUp()
        self.movie = self.make_movie('Arrival', 'Science Fiction', 2016)
        self.home_url = reverse('movies:home')
        self.genre_url = reverse(
            'movies:recommend', kwargs={'genre_name': 'Science Fiction'}
        )

    def test_valid_rating_redirects_without_errors(self):
        """test_valid_rating_redirects_without_errors: 302, sin is-invalid, con nota.

        El camino feliz no puede haber sido roto por el arreglo. Ademas sigue el
        302 para confirmar que la pagina de destino (que es la que el usuario
        ve de verdad) se renderiza sin marcar ningun campo.
        """
        response = self.client.post(self.home_url, {'movie_id': self.movie.id, 'score': 8})

        self.assertEqual(
            response.status_code, 302,
            'Un POST valido debe redirigir (PRG).',
        )
        self.assertEqual(response.url, self.home_url)

        rating = Rating.objects.get(movie=self.movie, user=self.user)
        self.assertEqual(rating.score, 8)

        followed = self.client.get(response.url, follow=True)
        self.assertEqual(followed.status_code, 200)
        self.assertNoInlineError(followed, 'La home tras un POST valido')

    def test_valid_rating_redirects_without_errors_on_recommend(self):
        """test_valid_rating_redirects_without_errors_on_recommend: idem en recommend."""
        response = self.client.post(self.genre_url, {'movie_id': self.movie.id, 'score': 7})

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, self.genre_url)
        self.assertEqual(Rating.objects.get(movie=self.movie, user=self.user).score, 7)

        followed = self.client.get(response.url, follow=True)
        self.assertEqual(followed.status_code, 200)
        self.assertNoInlineError(followed, 'La pagina de genero tras un POST valido')


# ---------------------------------------------------------------------------
# 6  El formulario con errores esta enlazado a la peli correcta
# ---------------------------------------------------------------------------

class ErrorFormBindingTest(RatingErrorTestCase):

    def setUp(self):
        super().setUp()
        # home ordena por -release_year: 'Zeta' (2021) sale antes que 'Alfa' (2001).
        self.newer = self.make_movie('Zeta', 'Drama', 2021)
        self.older = self.make_movie('Alfa', 'Drama', 2001)

    def test_error_form_is_bound_to_the_right_movie(self):
        """test_error_form_is_bound_to_the_right_movie: el error cae en su tarjeta.

        Con dos peliculas en la pagina hay dos formularios ``name="score"`` y
        solo uno puede llevar el error. La tarjeta correcta se identifica por su
        ``<input type="hidden" name="movie_id" value="...">`` y por su titulo,
        de modo que un error pintado en la tarjeta de al lado se detecta.
        """
        payload = {'movie_id': self.older.id, 'score': 99}
        (message,) = self.expected_score_errors(payload)

        response = self.client.post(reverse('movies:home'), payload)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.content.count(b'name="score"'), 2,
            'Se esperaban dos formularios de valoracion (uno por pelicula).',
        )
        # En la home cada peli aparece una sola vez, asi que aqui si se puede
        # exigir un unico marcado (a diferencia de recommend.html).
        self.assertEqual(
            sum(1 for card in self.cards(response) if INVALID_MARKER in card), 1,
            'Con dos peliculas distintas en la pagina, solo una puede quedar '
            f'marcada con "{INVALID_MARKER}".',
        )
        self.assert_error_is_on_movie_card(response, self.older, message)
        self.assert_card_has_no_error(response, self.newer)

    def test_error_form_is_stored_under_the_movie_id_key(self):
        """test_error_form_is_stored_under_the_movie_id_key: la clave es el id.

        Test de mecanismo, sobre el contexto y no sobre el HTML: es el
        constructo exacto que rompia el bug (``movie_rating_forms[movie_id]`` con
        ``movie_id`` siendo el ``str`` crudo del POST). Si la clave se vuelve a
        guardar como texto, la plantilla - que busca con ``movie.id``, un int -
        no la encontrara, y esto falla aunque el HTML se renders bien por otra
        razon.
        """
        response = self.client.post(
            reverse('movies:home'), {'movie_id': self.older.id, 'score': 99}
        )

        forms = response.context['movie_rating_forms']

        # ``sorted(forms)`` no serviria: con la clave str colada, comparar un
        # int con un str lanza TypeError y el fallo seria del test, no del bug.
        # Se ordenan las reprs, que si son comparables entre si.
        present = sorted(repr(key) for key in forms)
        self.assertIn(
            self.older.id, forms,
            'movie_rating_forms no tiene la clave movie.id del POST. '
            f'Claves presentes: {present}',
        )
        self.assertNotIn(
            str(self.older.id), forms,
            'La clave guardada es el string crudo de request.POST. La plantilla '
            'la busca con movie.id (int), asi que el form con errores nunca se '
            'pinta. Este es el bug.',
        )
        self.assertTrue(forms[self.older.id].errors.get('score'))

    def test_every_card_key_is_an_int(self):
        """test_every_card_key_is_an_int: homogeneousmente indexado por int.

        La plantilla hace ``movie_rating_forms|get_item:movie.id`` con un int en
        las dos vistas, asi que cualquier clave ``str`` en el diccionario es
        inalcanzable: un error o un formulario vacio donde deberia haber uno.
        """
        response = self.client.get(reverse('movies:home'))

        forms = response.context['movie_rating_forms']

        self.assertEqual(len(forms), 2)
        for key in forms:
            self.assertIsInstance(
                key, int,
                f'La clave {key!r} es un {type(key).__name__}, no un int: la '
                'plantilla nunca la encontrara.',
            )
