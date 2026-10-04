"""
Tests para el formulario de registro (RegisterForm) y la vista RegisterView.

Valida:
- Validacion de longitud minima de username (3) y password (8)
- Coincidencia de contraseñas
- Duplicados de usuario/email
- Visto de registro (GET/POST)
"""

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from movies.accounts.forms import RegisterForm


# ---------------------------------------------------------------------------
# RegisterForm Tests
# ---------------------------------------------------------------------------

class RegisterFormTest(TestCase):
    """Tests para el formulario RegisterForm."""

    # --- Valid submissions ---

    def test_register_form_valid(self):
        """test_register_form_valid: datos validos son aceptados."""
        form = RegisterForm(data={
            'username': 'newuser',
            'email': 'new@test.com',
            'password1': 'securepass123',
            'password2': 'securepass123',
        })
        self.assertTrue(form.is_valid())
        errors = form.errors
        self.assertEqual(len(errors), 0)

    def test_register_form_optional_email(self):
        """test_register_form_optional_email: email opcional es aceptado."""
        form = RegisterForm(data={
            'username': 'newuser',
            'password1': 'securepass123',
            'password2': 'securepass123',
        })
        self.assertTrue(form.is_valid())

    # --- Username validations ---

    def test_register_form_username_too_short_rejected(self):
        """test_register_form_username_too_short_rejected: username de 1 char rechazado."""
        form = RegisterForm(data={
            'username': 'ab',
            'email': 'a@b.com',
            'password1': 'securepass123',
            'password2': 'securepass123',
        })
        self.assertFalse(form.is_valid())
        self.assertIn('username', form.errors)

    def test_register_form_username_min_length_accepted(self):
        """test_register_form_username_min_length_accepted: username de 3 chars aceptado."""
        form = RegisterForm(data={
            'username': 'abc',
            'email': 'a@b.com',
            'password1': 'securepass123',
            'password2': 'securepass123',
        })
        self.assertTrue(form.is_valid())

    def test_register_form_duplicate_username_rejected(self):
        """test_register_form_duplicate_username_rejected: username duplicado rechazado."""
        User.objects.create_user(username='existing', password='existing123')
        form = RegisterForm(data={
            'username': 'existing',
            'email': 'other@test.com',
            'password1': 'securepass123',
            'password2': 'securepass123',
        })
        self.assertFalse(form.is_valid())
        self.assertIn('username', form.errors)

    # --- Password validations ---

    def test_register_form_password_too_short_rejected(self):
        """test_register_form_password_too_short_rejected: password de 7 chars rechazado."""
        form = RegisterForm(data={
            'username': 'newuser',
            'email': 'new@test.com',
            'password1': 'shortpw',
            'password2': 'shortpw',
        })
        self.assertFalse(form.is_valid())
        self.assertIn('password1', form.errors) or self.assertIn('password2', form.errors)

    def test_register_form_password_min_length_accepted(self):
        """test_register_form_password_min_length_accepted: password de 8 chars aceptado."""
        form = RegisterForm(data={
            'username': 'newuser',
            'email': 'new@test.com',
            'password1': 'pass1234',
            'password2': 'pass1234',
        })
        self.assertTrue(form.is_valid())

    def test_register_form_passwords_mismatch_rejected(self):
        """test_register_form_passwords_mismatch_rejected: passwords diferentes rechazado."""
        form = RegisterForm(data={
            'username': 'newuser',
            'email': 'new@test.com',
            'password1': 'securepass123',
            'password2': 'otherpass456',
        })
        self.assertFalse(form.is_valid())
        self.assertIn('password2', form.errors)

    def test_register_form_passwords_match_accepted(self):
        """test_register_form_passwords_match_accepted: passwords iguales aceptado."""
        form = RegisterForm(data={
            'username': 'newuser',
            'email': 'new@test.com',
            'password1': 'mysecurepass',
            'password2': 'mysecurepass',
        })
        self.assertTrue(form.is_valid())

    def test_register_form_password2_short_rejected(self):
        """test_register_form_password2_short_rejected: password2 corto rechazado."""
        form = RegisterForm(data={
            'username': 'newuser',
            'email': 'new@test.com',
            'password1': 'securepass123',
            'password2': 'short',
        })
        self.assertFalse(form.is_valid())
        self.assertIn('password2', form.errors)

    # --- Email validations ---

    def test_register_form_duplicate_email_rejected(self):
        """test_register_form_duplicate_email_rejected: email duplicado rechazado."""
        User.objects.create_user(username='user2', password='user2pass1', email='dup@test.com')
        form = RegisterForm(data={
            'username': 'newuser',
            'email': 'dup@test.com',
            'password1': 'securepass123',
            'password2': 'securepass123',
        })
        self.assertFalse(form.is_valid())
        self.assertIn('email', form.errors)

    def test_register_form_valid_email_accepted(self):
        """test_register_form_valid_email_accepted: email valido aceptado."""
        form = RegisterForm(data={
            'username': 'newuser',
            'email': 'valid@email.com',
            'password1': 'securepass123',
            'password2': 'securepass123',
        })
        self.assertTrue(form.is_valid())

    # --- Empty/missing fields ---

    def test_register_form_empty_username_rejected(self):
        """test_register_form_empty_username_rejected: username vacio rechazado."""
        form = RegisterForm(data={
            'username': '',
            'email': 'new@test.com',
            'password1': 'securepass123',
            'password2': 'securepass123',
        })
        self.assertFalse(form.is_valid())
        self.assertIn('username', form.errors)

    def test_register_form_empty_password_rejected(self):
        """test_register_form_empty_password_rejected: password vacio rechazado."""
        form = RegisterForm(data={
            'username': 'newuser',
            'email': 'new@test.com',
            'password1': '',
            'password2': '',
        })
        self.assertFalse(form.is_valid())

    def test_register_form_all_empty_rejected(self):
        """test_register_form_all_empty_rejected: formulario vacio rechazado."""
        form = RegisterForm(data={})
        self.assertFalse(form.is_valid())
        self.assertGreater(len(form.errors), 0)

    # --- Username max length ---

    def test_register_form_username_max_length(self):
        """test_register_form_username_max_length: username de 151 caracteres rechazado."""
        form = RegisterForm(data={
            'username': 'a' * 151,
            'email': 'new@test.com',
            'password1': 'securepass123',
            'password2': 'securepass123',
        })
        self.assertFalse(form.is_valid())
        self.assertIn('username', form.errors)

    def test_register_form_username_exact_max_length(self):
        """test_register_form_username_exact_max_length: username de 150 chars aceptado."""
        form = RegisterForm(data={
            'username': 'a' * 150,
            'email': 'new@test.com',
            'password1': 'securepass123',
            'password2': 'securepass123',
        })
        self.assertTrue(form.is_valid())


# ---------------------------------------------------------------------------
# RegisterView Tests
# ---------------------------------------------------------------------------

class RegisterViewTest(TestCase):
    """Tests para la vista RegisterView."""

    def setUp(self):
        self.url = reverse('accounts:register')

    def test_register_get_200(self):
        """test_register_get_200: GET a register muestra formulario."""
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'accounts/register.html')
        self.assertIn('form', response.context)

    def test_register_anonymous_only(self):
        """test_register_anonymous_only: usuario logueado redirigido a home."""
        User.objects.create_user(username='existing', password='existing123')
        self.client.login(username='existing', password='existing123')
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)
        # LOGIN_REDIRECT_URL = 'movies:home' y la app esta montada en '/'.
        self.assertEqual(response.url, reverse('movies:home'))

    def test_register_valid_post_creates_user(self):
        """test_register_valid_post_creates_user: registro exitoso crea usuario."""
        response = self.client.post(self.url, {
            'username': 'newuser1',
            'email': 'new1@test.com',
            'password1': 'securepass123',
            'password2': 'securepass123',
        })
        self.assertEqual(response.status_code, 302)
        self.assertTrue(User.objects.filter(username='newuser1').exists())
        user = User.objects.get(username='newuser1')
        self.assertEqual(user.email, 'new1@test.com')

    def test_register_valid_post_auto_login(self):
        """test_register_valid_post_auto_login: login automatico despues de registro."""
        self.client.post(self.url, {
            'username': 'newuser2',
            'email': 'new2@test.com',
            'password1': 'securepass123',
            'password2': 'securepass123',
        })
        self.assertTrue(self.client.session.get('_auth_user_id'))

    def test_register_valid_post_redirect_to_home(self):
        """test_register_valid_post_redirect_to_home: redirige a home despues de registro."""
        response = self.client.post(self.url, {
            'username': 'newuser3',
            'email': 'new3@test.com',
            'password1': 'securepass123',
            'password2': 'securepass123',
        })
        self.assertTrue(User.objects.filter(username='newuser3').exists())
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('movies:home'))

    def test_register_duplicate_username_rejected(self):
        """test_register_duplicate_username_rejected: usuario duplicado en vista."""
        User.objects.create_user(username='duplicate', password='duplicate123')
        response = self.client.post(self.url, {
            'username': 'duplicate',
            'email': 'other@test.com',
            'password1': 'securepass123',
            'password2': 'securepass123',
        })
        self.assertEqual(response.status_code, 200)  # muestra formulario con errores
        self.assertFalse(User.objects.filter(username='duplicate').count() > 1)

    def test_register_passwords_mismatch_rejected(self):
        """test_register_passwords_mismatch_rejected: passwords diferentes en vista."""
        response = self.client.post(self.url, {
            'username': 'newuser4',
            'email': 'new4@test.com',
            'password1': 'pass123456',
            'password2': 'other654321',
        })
        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(username='newuser4').exists())

    def test_register_short_password_rejected(self):
        """test_register_short_password_rejected: password corto en vista."""
        response = self.client.post(self.url, {
            'username': 'newuser5',
            'email': 'new5@test.com',
            'password1': 'shortpw',
            'password2': 'shortpw',
        })
        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(username='newuser5').exists())

    def test_register_short_username_rejected(self):
        """test_register_short_username_rejected: username corto en vista."""
        response = self.client.post(self.url, {
            'username': 'ab',
            'email': 'new6@test.com',
            'password1': 'securepass123',
            'password2': 'securepass123',
        })
        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(username='ab').exists())

    def test_register_duplicate_email_rejected(self):
        """test_register_duplicate_email_rejected: email duplicado en vista."""
        User.objects.create_user(username='user_email', password='user_email123', email='dup@test.com')
        response = self.client.post(self.url, {
            'username': 'newuser6',
            'email': 'dup@test.com',
            'password1': 'securepass123',
            'password2': 'securepass123',
        })
        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(username='newuser6').exists())

    def test_register_form_errors_shown(self):
        """test_register_form_errors_shown: errores se muestran en la pagina."""
        response = self.client.post(self.url, {
            'username': '',
            'email': 'invalid-email',
            'password1': 'short',
            'password2': 'different',
        })
        self.assertEqual(response.status_code, 200)
        form = response.context['form']
        self.assertFalse(form.is_valid())
        # username vacio, email mal formado y password1 corta fallan. 'password2'
        # NO se marca: 'clean_password2' compara contra cleaned_data['password1'],
        # que no existe cuando 'clean_password1' ya fallo, y 'different' si
        # tiene 8+ caracteres. Es el comportamiento normal de Django para campos
        # dependientes, no un fallo de la vista.
        for field in ('username', 'email', 'password1'):
            self.assertIn(field, form.errors)
        self.assertNotIn('password2', form.errors)
        # Y la plantilla tiene que renderizar el mensaje de error de la vista.
        messages = [str(m) for m in response.context['messages']]
        self.assertIn('Por favor corrige los errores del formulario.', messages)
        # Y al menos un error de campo en el HTML (control negativo incluido).
        #
        # El idioma por defecto es 'es' y movies/locale/es/LC_MESSAGES/django.mo
        # traduce los mensajes de validacion propios de Django, asi que se
        # comprueba el contrato real: el error aparece en espanol y la pagina
        # lo muestra. Antes LANGUAGE_CODE era 'en-us' y estos mismos mensajes
        # ("This field is required.", "Enter a valid email address.") salian en
        # ingles dentro de una pagina en espanol.
        rendered = response.content.decode()
        self.assertIn('Este campo es obligatorio.', rendered)
        self.assertIn(
            'Introduzca una dirección de correo electrónico válida.', rendered
        )
        # Y el HTML tiene que contener el error que produce el propio formulario.
        first_error = next(
            str(message)
            for field in ('username', 'email', 'password1')
            for message in form.errors[field]
        )
        self.assertIn(first_error, rendered)


# ---------------------------------------------------------------------------
# LoginView Tests
# ---------------------------------------------------------------------------

class LoginViewTest(TestCase):
    """Tests para la vista LoginView."""

    def setUp(self):
        self.url = reverse('accounts:login')
        User.objects.create_user(username='logintest', password='loginpass123')

    def test_login_get_200(self):
        """test_login_get_200: GET a login muestra formulario."""
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'accounts/login.html')

    def test_login_valid_credentials_success(self):
        """test_login_valid_credentials_success: credenciales validas exitosas."""
        response = self.client.post(self.url, {
            'username': 'logintest',
            'password': 'loginpass123',
        })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('movies:home'))

    def test_login_invalid_credentials_rejected(self):
        """test_login_invalid_credentials_rejected: credenciales invalidas rechazadas."""
        response = self.client.post(self.url, {
            'username': 'logintest',
            'password': 'wrongpassword',
        })
        self.assertEqual(response.status_code, 200)  # muestra formulario con error

    def test_login_nonexistent_user_rejected(self):
        """test_login_nonexistent_user_rejected: usuario inexistente rechazado."""
        response = self.client.post(self.url, {
            'username': 'nobody',
            'password': 'anything',
        })
        self.assertEqual(response.status_code, 200)

    def test_login_authenticated_redirects_home(self):
        """test_login_authenticated_redirects_home: usuario logueado redirigido."""
        self.client.login(username='logintest', password='loginpass123')
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('movies:home'))


# ---------------------------------------------------------------------------
# LogoutView Tests
# ---------------------------------------------------------------------------

class LogoutViewTest(TestCase):
    """Tests para la vista LogoutView."""

    def setUp(self):
        self.user = User.objects.create_user(username='logouttest', password='logoutpass123')
        self.get_url = reverse('accounts:logout')
        self.post_url = reverse('accounts:logout')

    def test_logout_get_requires_auth(self):
        """test_logout_get_requires_auth: logout GET requiere autenticacion."""
        response = self.client.get(self.get_url)
        self.assertEqual(response.status_code, 302)
        self.assertIn('accounts/login', response.url)

    def test_logout_get_authenticated_shows_confirm(self):
        """test_logout_get_authenticated_shows_confirm: muestra pagina de confirmacion."""
        self.client.login(username='logouttest', password='logoutpass123')
        response = self.client.get(self.get_url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'accounts/logout_confirm.html')

    def test_logout_postlogs_out_and_redirects(self):
        """test_logout_postlogs_out_and_redirects: POST cierra sesion."""
        self.client.login(username='logouttest', password='logoutpass123')
        response = self.client.post(self.post_url)
        self.assertEqual(response.status_code, 302)
        # LogoutView redirige a 'movies:home' (montada en '/'), no a /accounts/.
        self.assertEqual(response.url, reverse('movies:home'))
        # Session should be cleared
        self.assertFalse('_auth_user_id' in self.client.session)
