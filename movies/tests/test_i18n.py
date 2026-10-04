"""
Tests de internacionalizacion: la interfaz esta escrita a mano en espanol, asi
que los mensajes de validacion de Django tienen que salir tambien en espanol.

Regresion del bug "i18n": con LANGUAGE_CODE = 'en-us' los formularios
mostraban "This field is required." bajo un campo etiquetado "Puntuacion".
"""

from django.conf import settings
from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.utils import translation

from movies.accounts.forms import LoginForm, RegisterForm
from movies.forms import ProfileForm, RatingForm, SearchForm


class LanguageSettingsTest(TestCase):
    """El idioma por defecto tiene que ser espanol."""

    def test_language_code_is_spanish(self) -> None:
        """test_language_code_is_spanish: LANGUAGE_CODE debe ser 'es'."""
        self.assertEqual(settings.LANGUAGE_CODE, 'es')

    def test_i18n_is_enabled(self) -> None:
        """test_i18n_is_enabled: USE_I18N debe estar activo."""
        self.assertTrue(settings.USE_I18N)

    def test_spanish_catalog_is_installed(self) -> None:
        """test_spanish_catalog_is_installed: existe el .mo de movies para 'es'."""
        from django.utils.translation import trans_real

        catalog = trans_real.translation('es')._catalog
        self.assertEqual(
            catalog.get('This field is required.'), 'Este campo es obligatorio.'
        )


class TranslatedValidationErrorsTest(TestCase):
    """Los errores de validacion propios de Django se muestran en espanol."""

    def _errors(self, form):
        form.is_valid()
        return [str(message) for messages in form.errors.values() for message in messages]

    def test_required_error_is_spanish(self) -> None:
        """test_required_error_is_spanish: campo obligatorio."""
        self.assertIn('Este campo es obligatorio.', self._errors(ProfileForm(data={})))
        self.assertIn('Este campo es obligatorio.', self._errors(LoginForm(data={})))

    def test_email_error_is_spanish(self) -> None:
        """test_email_error_is_spanish: correo con formato invalido."""
        form = ProfileForm(data={'username': 'juan', 'email': 'no-es-un-correo'})
        self.assertIn(
            'Introduzca una dirección de correo electrónico válida.',
            self._errors(form),
        )

    def test_max_value_error_is_spanish(self) -> None:
        """test_max_value_error_is_spanish: puntuacion por encima del maximo."""
        form = RatingForm(data={'score': 99}, user=None)
        self.assertIn('Este valor debe ser menor o igual que 10.', self._errors(form))

    def test_min_value_error_is_spanish(self) -> None:
        """test_min_value_error_is_spanish: puntuacion por debajo del minimo."""
        form = RatingForm(data={'score': 0}, user=None)
        self.assertIn('Este valor debe ser mayor o igual que 1.', self._errors(form))

    def test_integer_error_is_spanish(self) -> None:
        """test_integer_error_is_spanish: puntuacion no entera."""
        form = RatingForm(data={'score': 'abc'}, user=None)
        self.assertIn('Introduzca un número entero.', self._errors(form))

    def test_min_length_error_is_spanish(self) -> None:
        """test_min_length_error_is_spanish: longitud minima (plural)."""
        form = SearchForm(data={'q': 'x'})
        self.assertIn(
            'Este valor debe tener al menos 2 caracteres (tiene 1).', self._errors(form)
        )

    def test_no_english_leaks_in_any_form(self) -> None:
        """test_no_english_leaks_in_any_form: ningun error queda en ingles."""
        User.objects.create_user(username='duplicado', email='dup@ejemplo.com')
        cases = [
            (ProfileForm, {}),
            (ProfileForm, {'username': 'juan', 'email': 'malo'}),
            (ProfileForm, {'username': 'x' * 300}),
            (RatingForm, {'score': 99}),
            (RatingForm, {'score': 0}),
            (RatingForm, {'score': 'abc'}),
            (RatingForm, {}),
            (SearchForm, {'q': 'x'}),
            (SearchForm, {'q': 'x' * 300}),
            (SearchForm, {}),
            (LoginForm, {}),
            (RegisterForm, {}),
            (RegisterForm, {'username': 'duplicado', 'email': '',
                            'password1': 'Password123!', 'password2': 'Password123!'}),
        ]
        for form_class, data in cases:
            for message in self._errors(form_class(data=data)):
                with self.subTest(form=form_class.__name__, data=data, message=message):
                    # Los placeholders de los labels son ingafes; el texto de
                    # error tiene que traer la cadena en espanol.
                    self.assertIn(' ', message)
                    self.assertNotIn('This field is required.', message)
                    self.assertNotIn('Enter a valid', message)
                    self.assertNotIn('Enter a whole number.', message)
                    self.assertNotIn('Select a valid choice.', message)
                    self.assertNotIn('Ensure this value', message)

    @override_settings(LANGUAGE_CODE='en-us')
    def test_errors_follow_language_code(self) -> None:
        """test_errors_follow_language_code: con 'en-us' vuelve el texto ingles."""
        # Demuestra que la traduccion depende de LANGUAGE_CODE y no de un
        # literal pegado en la plantilla.
        with translation.override('en-us'):
            form = RatingForm(data={'score': 99}, user=None)
            form.is_valid()
            messages = [
                str(m) for errors in form.errors.values() for m in errors
            ]
        self.assertIn('Ensure this value is less than or equal to 10.', messages)
