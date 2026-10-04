"""
Tests para el modulo de autenticacion (Criterion 5).

Cubre:
- Login/Logout/Registro (vistas y formularios)
- Access controls: @login_required, @staff_member_required
- Navigation en base.html segun estado de autenticacion
- Rutas protegidas (profile, favorite, rating, stats)
- Decorador user_not_authenticated
"""

from django.contrib.auth.models import AnonymousUser, User
from django.core.cache import cache
from django.test import TestCase, RequestFactory
from django.urls import reverse

from movies.decorators import user_not_authenticated
from movies.forms import RatingForm
from movies.models import Genre, Movie


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _create_movie(title='Test Movie', release_year=2020, synopsis='', genre='Action'):
    """Crea una pelicula con la API real de ``movies.models.Movie``.

    El modelo expone ``title`` / ``synopsis`` / ``release_year`` / ``cover`` /
    ``genres`` / ``cast``: no existen los campos ``year`` ni ``description`` que
    usaba este archivo antes.

    ``cover`` se deja como cadena vacia (el default implicito de un
    ``FileField``) a proposito. La migracion ``0002`` lo declara NOT NULL, pero
    ``''`` es un valor valido de la columna, asi que la fila se guarda sin
    escribir ficheros en ``MEDIA_ROOT``; y ``Movie.save()`` solo optimiza la
    portada ``if self.cover``, con lo que tampoco hace falta Pillow aqui. Estos
    tests son de autenticacion: la portada es irrelevante y lo unico que
    necesitan es que exista una fila en ``Movie`` para las rutas que laxygen
    ``<int:movie_id>``.
    """
    movie = Movie.objects.create(
        title=title,
        synopsis=synopsis,
        release_year=release_year,
        cover='',
    )
    if genre:
        movie.genres.add(Genre.objects.get_or_create(name=genre)[0])
    return movie


class AuthTestCase(TestCase):
    """Base con cache limpia, para que el orden de los tests no importe.

    ``get_home_movies()``, ``search_movies()`` y ``filter_movies()`` memoizan
    listas de *ids* en un ``LocMemCache`` bajo claves que no dependen de la base
    de datos, y el runner de Django no limpia esa cache entre tests. Una lista
    de ids sembrada por un test (con la BD ya revertida tras su rollback)
    puede, por tanto, filtrar peliculas ajenas a otro test posterior. Con
    ``--shuffle`` eso haria el resultado dependiente del orden.
    """

    def setUp(self):
        super().setUp()
        cache.clear()
        self.addCleanup(cache.clear)


# ---------------------------------------------------------------------------
# Authentication Flow Tests
# ---------------------------------------------------------------------------

class AuthenticationFlowTest(TestCase):
    """Tests para el flujo completo de autenticacion."""

    def setUp(self):
        self.user = User.objects.create_user(
            username='flowtest',
            email='flow@test.com',
            password='flowpass123',
        )

    def test_login_success_redirects_to_home(self):
        """test_login_success_redirects_to_home: login exitoso redirige a home."""
        response = self.client.post(
            reverse('accounts:login'),
            {'username': 'flowtest', 'password': 'flowpass123'},
        )
        self.assertEqual(response.status_code, 302)
        # La app se monta en la raiz del proyecto, asi que la URL de home es "/"
        # (no "/movies/"). Se compara contra ``reverse()`` para no atar el
        # test a un prefijo de montaje concreto.
        self.assertEqual(response.url, reverse('movies:home'))

    def test_login_after_success_has_session(self):
        """test_login_after_success_has_session: sesion creada tras login."""
        self.client.post(
            reverse('accounts:login'),
            {'username': 'flowtest', 'password': 'flowpass123'},
        )
        self.assertTrue('_auth_user_id' in self.client.session)
        response = self.client.get(reverse('movies:home'))
        self.assertEqual(response.status_code, 200)

    def test_logout_clears_session(self):
        """test_logout_clears_session: logout elimina sesion."""
        self.client.login(username='flowtest', password='flowpass123')
        self.assertTrue('_auth_user_id' in self.client.session)
        self.client.post(reverse('accounts:logout'))
        self.assertFalse('_auth_user_id' in self.client.session)

    def test_register_creates_user_and_logs_in(self):
        """test_register_creates_user_and_logs_in: registro crea usuario y loguea."""
        response = self.client.post(reverse('accounts:register'), {
            'username': 'newflowtest',
            'email': 'newflow@test.com',
            'password1': 'newflowpass123',
            'password2': 'newflowpass123',
        })
        self.assertEqual(response.status_code, 302)
        self.assertTrue(User.objects.filter(username='newflowtest').exists())
        self.assertTrue('_auth_user_id' in self.client.session)


# ---------------------------------------------------------------------------
# Access Control Tests - Protected Routes
# ---------------------------------------------------------------------------

class AccessControlTest(AuthTestCase):
    """Tests para controls de acceso en rutas protegidas."""

    def setUp(self):
        super().setUp()
        self.user = User.objects.create_user(
            username='acctest',
            password='acctestpass123',
        )

    # --- profile_view ---

    def test_profile_requires_login(self):
        """test_profile_requires_login: profile redirige si no hay login."""
        response = self.client.get(reverse('movies:profile'))
        self.assertEqual(response.status_code, 302)
        self.assertIn('accounts/login', response.url)

    def test_profile_accessible_when_authenticated(self):
        """test_profile_accessible_when_authenticated: profile accesible con login."""
        self.client.login(username='acctest', password='acctestpass123')
        response = self.client.get(reverse('movies:profile'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'movies/profile.html')

    # --- favorite ---

    def test_favorite_requires_login(self):
        """test_favorite_requires_login: favorite redirige si no hay login."""
        movie = _create_movie(title='Test Movie', release_year=2024, synopsis='A test movie')
        response = self.client.get(reverse('movies:favorite', args=[movie.id]))
        self.assertEqual(response.status_code, 302)
        self.assertIn('accounts/login', response.url)

    def test_favorite_accessible_when_authenticated(self):
        """test_favorite_accessible_when_authenticated: favorite accesible con login."""
        movie = _create_movie(title='Test Movie 2', release_year=2024, synopsis='Another test movie')
        self.client.login(username='acctest', password='acctestpass123')
        response = self.client.get(reverse('movies:favorite', args=[movie.id]))
        self.assertEqual(response.status_code, 302)  # redirects after toggle

    # --- rating form ---

    def test_rating_form_anonymous_user(self):
        """test_rating_form_anonymous_user: form de rating para anonimo sin user."""
        form = RatingForm()
        self.assertIsNone(form.fields['score'].initial)

    def test_rating_form_authenticated_user(self):
        """test_rating_form_authenticated_user: form de rating con user logueado."""
        self.client.login(username='acctest', password='acctestpass123')
        _create_movie(title='Test Movie 3', release_year=2024, synopsis='Yet another test')
        response = self.client.get(reverse('movies:home'))
        self.assertEqual(response.status_code, 200)

    # --- stats_view (staff only) ---

    def test_stats_requires_staff(self):
        """test_stats_requires_staff: stats solo accesible para staff."""
        # Regular user should be redirected
        self.client.login(username='acctest', password='acctestpass123')
        response = self.client.get(reverse('movies:stats'))
        self.assertEqual(response.status_code, 302)

    def test_stats_accessible_by_staff(self):
        """test_stats_accessible_by_staff: stats accesible para staff."""
        staff_user = User.objects.create_user(
            username='stafftest',
            password='staffpass123',
            is_staff=True,
        )
        self.client.login(username='stafftest', password='staffpass123')
        response = self.client.get(reverse('movies:stats'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'movies/stats.html')

    def test_stats_accessible_by_superuser(self):
        """test_stats_accessible_by_superuser: stats accesible para superusuario."""
        super_user = User.objects.create_superuser(
            username='superadmin',
            password='superpass123',
        )
        self.client.login(username='superadmin', password='superpass123')
        response = self.client.get(reverse('movies:stats'))
        self.assertEqual(response.status_code, 200)

    # --- register view blocks authenticated ---

    def test_register_blocked_for_authenticated(self):
        """test_register_blocked_for_authenticated: registro bloqueado para usuarios logueados."""
        self.client.login(username='acctest', password='acctestpass123')
        response = self.client.get(reverse('accounts:register'))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('movies:home'))

    # --- login view blocks authenticated ---

    def test_login_blocked_for_authenticated(self):
        """test_login_blocked_for_authenticated: login bloqueado para usuarios logueados."""
        self.client.login(username='acctest', password='acctestpass123')
        response = self.client.get(reverse('accounts:login'))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('movies:home'))


# ---------------------------------------------------------------------------
# Navigation Tests - base.html auth-dependent links
# ---------------------------------------------------------------------------

class NavigationAuthTest(TestCase):
    """Tests para la navegacion en base.html segun autenticacion."""

    def setUp(self):
        self.user = User.objects.create_user(
            username='navtest',
            password='navtestpass123',
        )

    def test_anonymous_sees_login_register_links(self):
        """test_anonymous_sees_login_register_links: anonimo ve links de login/registro."""
        response = self.client.get(reverse('movies:home'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Iniciar sesion')
        self.assertContains(response, 'Registrarse')
        self.assertNotContains(response, 'Mis valoraciones')
        self.assertNotContains(response, 'Editar perfil')

    def test_authenticated_sees_profile_logout_links(self):
        """test_authenticated_sees_profile_logout_links: autenticado ve perfil/logout."""
        self.client.login(username='navtest', password='navtestpass123')
        response = self.client.get(reverse('movies:home'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'navtest')  # username in nav
        self.assertContains(response, 'Cerrar sesion')
        self.assertContains(response, 'Editar perfil')

    def test_authenticated_nav_has_logout_form(self):
        """test_authenticated_nav_has_logout_form: logout es un formulario POST.

        El assert anterior buscaba el literal ``'accounts:logout'``, que es
        imposible de satisfacer: ``{% url 'accounts:logout' %}`` no imprime el
        nombre de la ruta sino la URL ya resuelta, y el HTML renderizado no
        contiene el nombre del patron en ningun sitio. Lo que importa de verdad
        es que el logout del nav sea un POST con la URL de logout y token CSRF
        (``LogoutView.post()`` es la unica rama que cierra la sesion; un GET
        solo muestra una pagina de confirmacion).
        """
        self.client.login(username='navtest', password='navtestpass123')
        response = self.client.get(reverse('movies:home'))
        self.assertEqual(response.status_code, 200)

        logout_url = reverse('accounts:logout')
        content = response.content.decode()

        # La URL de logout, ya resuelta.
        self.assertContains(response, f'action="{logout_url}"')
        # Un <form method="post"> apuntando ahi: no un enlace GET.
        self.assertIn(
            f'<form method="post" action="{logout_url}"', content,
            'El logout del nav debe ser un <form method="post">, no un enlace GET.',
        )
        # Salida real de {% csrf_token %}: el input hidden, no el tag del template.
        self.assertIn('name="csrfmiddlewaretoken"', content)
        self.assertNotContains(response, '{% csrf_token %}')

    def test_anonymous_user_object_in_template(self):
        """test_anonymous_user_object_in_template: user anonimo en contexto."""
        response = self.client.get(reverse('movies:home'))
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context['user'].is_authenticated)

    def test_authenticated_user_object_in_template(self):
        """test_authenticated_user_object_in_template: user logueado en contexto."""
        self.client.login(username='navtest', password='navtestpass123')
        response = self.client.get(reverse('movies:home'))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['user'].is_authenticated)
        self.assertEqual(response.context['user'].username, 'navtest')


# ---------------------------------------------------------------------------
# Decorator Tests
# ---------------------------------------------------------------------------

class DecoratorTest(TestCase):
    """Tests para el decorador user_not_authenticated."""

    def test_decorator_redirects_authenticated(self):
        """test_decorator_redirects_authenticated: decorador redirige si hay auth."""
        User.objects.create_user(
            username='dectest',
            password='dectestpass123',
        )
        self.client.login(username='dectest', password='dectestpass123')
        response = self.client.get(reverse('accounts:register'))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('movies:home'))

    def test_decorator_allows_anonymous(self):
        """test_decorator_allows_anonymous: decorador permite anonimos."""
        response = self.client.get(reverse('accounts:register'))
        self.assertEqual(response.status_code, 200)

    def test_decorator_function_based_view(self):
        """test_decorator_function_based_view: funciona con FBV."""
        from movies.decorators import user_not_authenticated

        @user_not_authenticated()
        def dummy_view(request):
            return type('Response', (), {'status_code': 200})()

        factory = RequestFactory()
        # Anonymous user. Desde Django 2.0 ``is_authenticated`` es una propiedad
        # de solo lectura sobre ``User`` (y ``True`` como clase), asi que no se
        # puede "desactivar" con ``user.is_authenticated = False``: la forma
        # correcta de montar una peticion anonima es un ``AnonymousUser()``.
        anon_request = factory.get('/')
        anon_request.user = AnonymousUser()
        self.assertFalse(anon_request.user.is_authenticated)
        result = dummy_view(anon_request)
        self.assertEqual(result.status_code, 200)

        # Authenticated user
        auth_user = User.objects.create_user(
            username='authuser',
            password='authuser123',
        )
        auth_request = factory.get('/')
        auth_request.user = auth_user
        self.assertTrue(auth_request.user.is_authenticated)
        result = dummy_view(auth_request)
        self.assertEqual(result.status_code, 302)


# ---------------------------------------------------------------------------
# Login Form Tests
# ---------------------------------------------------------------------------

class LoginFormTest(TestCase):
    """Tests para el formulario LoginForm."""

    def test_login_form_valid(self):
        """test_login_form_valid: formulario de login valido."""
        from movies.accounts.forms import LoginForm
        form = LoginForm(data={'username': 'testuser', 'password': 'testpass123'})
        self.assertTrue(form.is_valid())

    def test_login_form_empty_username(self):
        """test_login_form_empty_username: username vacio rechazado."""
        from movies.accounts.forms import LoginForm
        form = LoginForm(data={'username': '', 'password': 'testpass123'})
        self.assertFalse(form.is_valid())

    def test_login_form_empty_password(self):
        """test_login_form_empty_password: password vacio rechazado."""
        from movies.accounts.forms import LoginForm
        form = LoginForm(data={'username': 'testuser', 'password': ''})
        self.assertFalse(form.is_valid())


# ---------------------------------------------------------------------------
# Password Hashing Tests
# ---------------------------------------------------------------------------

class PasswordHashingTest(TestCase):
    """Tests para verificacion de passwords con check_password."""

    def test_check_password_correct(self):
        """test_check_password_correct: check_password con password correcto."""
        from django.contrib.auth.hashers import make_password, check_password
        raw = 'mysecretpass'
        hashed = make_password(raw)
        self.assertTrue(check_password(raw, hashed))

    def test_check_password_incorrect(self):
        """test_check_password_incorrect: check_password con password incorrecto."""
        from django.contrib.auth.hashers import make_password, check_password
        raw = 'mysecretpass'
        hashed = make_password(raw)
        self.assertFalse(check_password('wrongpass', hashed))

    def test_login_uses_check_password(self):
        """test_login_uses_check_password: login usa check_password correctamente."""
        user = User.objects.create_user(
            username='passtest',
            password='correctpass123',
        )
        response = self.client.post(reverse('accounts:login'), {
            'username': 'passtest',
            'password': 'correctpass123',
        })
        self.assertEqual(response.status_code, 302)

    def test_login_rejects_wrong_password(self):
        """test_login_rejects_wrong_password: login rechaza password incorrecto."""
        user = User.objects.create_user(
            username='passtest2',
            password='correctpass123',
        )
        response = self.client.post(reverse('accounts:login'), {
            'username': 'passtest2',
            'password': 'wrongpassword',
        })
        self.assertEqual(response.status_code, 200)  # muestra formulario con error


# ---------------------------------------------------------------------------
# Auth URLs Configuration Tests
# ---------------------------------------------------------------------------

class AuthURLsTest(TestCase):
    """Tests para la configuracion de URLs de autenticacion."""

    def test_login_url_resolves(self):
        """test_login_url_resolves: url de login resuelve correctamente."""
        self.assertEqual(reverse('accounts:login'), '/accounts/login/')

    def test_logout_url_resolves(self):
        """test_logout_url_resolves: url de logout resuelve correctamente."""
        self.assertEqual(reverse('accounts:logout'), '/accounts/logout/')

    def test_register_url_resolves(self):
        """test_register_url_resolves: url de registro resuelve correctamente."""
        self.assertEqual(reverse('accounts:register'), '/accounts/register/')

    def test_auth_urls_included_in_main(self):
        """test_auth_urls_included_in_main: URLs de auth incluidas en config principal."""
        from django.urls import resolve
        self.assertIsNotNone(resolve('/accounts/login/'))
        self.assertIsNotNone(resolve('/accounts/logout/'))
        self.assertIsNotNone(resolve('/accounts/register/'))


# ---------------------------------------------------------------------------
# Cross-Feature Auth Tests
# ---------------------------------------------------------------------------

class CrossFeatureAuthTest(AuthTestCase):
    """Tests de autenticacion cruzada con otras funcionalidades."""

    def setUp(self):
        super().setUp()
        self.user = User.objects.create_user(
            username='crossuser',
            password='crosspass123',
        )
        self.genre = Genre.objects.create(name='TestGenre')
        self.movie = _create_movie(
            title='Cross Movie',
            release_year=2024,
            synopsis='Cross feature test movie',
            genre=None,  # el genero se enlaza abajo, como hacia el fixture
        )
        self.movie.genres.add(self.genre)

    def test_home_accessible_anonymous(self):
        """test_home_accessible_anonymous: home accesible sin login."""
        response = self.client.get(reverse('movies:home'))
        self.assertEqual(response.status_code, 200)

    def test_search_accessible_anonymous(self):
        """test_search_accessible_anonymous: search accesible sin login."""
        response = self.client.get(reverse('movies:search'))
        self.assertEqual(response.status_code, 200)

    def test_recommend_accessible_anonymous(self):
        """test_recommend_accessible_anonymous: recommend accesible sin login."""
        response = self.client.get(reverse('movies:recommend', args=['TestGenre']))
        self.assertEqual(response.status_code, 200)

    def test_profile_not_in_anonymous_nav(self):
        """test_profile_not_in_anonymous_nav: profile no visible en nav anonimo."""
        response = self.client.get(reverse('movies:home'))
        self.assertEqual(response.status_code, 200)
        # Anonymous user should NOT see profile link text
        self.assertNotContains(response, 'Editar perfil')

    def test_user_stats_empty_for_regular_user(self):
        """test_user_stats_empty_for_regular_user: stats usuario regular sin access."""
        self.client.login(username='crossuser', password='crosspass123')
        response = self.client.get(reverse('movies:stats'))
        self.assertEqual(response.status_code, 302)  # redirigido, no staff
