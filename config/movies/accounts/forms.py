"""
Forms para el modulo de cuentas.
"""

from django import forms
from django.contrib.auth.models import User


class LoginForm(forms.Form):
    """Formulario de inicio de sesion."""

    username = forms.CharField(
        label='Nombre de usuario',
        max_length=150,
        widget=forms.TextInput(attrs={
            'class': 'form-input',
            'placeholder': 'Usuario',
            'autofocus': True,
        }),
    )
    password = forms.CharField(
        label='Contraseña',
        widget=forms.PasswordInput(attrs={
            'class': 'form-input',
            'placeholder': 'Contraseña',
        }),
    )


class RegisterForm(forms.Form):
    """Formulario de registro de nuevos usuarios."""

    username = forms.CharField(
        label='Nombre de usuario',
        max_length=150,
        widget=forms.TextInput(attrs={
            'class': 'form-input',
            'placeholder': 'Usuario',
            'autofocus': True,
        }),
    )
    email = forms.EmailField(
        label='Correo electronico (opcional)',
        required=False,
        widget=forms.EmailInput(attrs={
            'class': 'form-input',
            'placeholder': 'correo@ejemplo.com',
        }),
    )
    password1 = forms.CharField(
        label='Contraseña',
        widget=forms.PasswordInput(attrs={
            'class': 'form-input',
            'placeholder': 'Contraseña',
        }),
    )
    password2 = forms.CharField(
        label='Confirmar contraseña',
        widget=forms.PasswordInput(attrs={
            'class': 'form-input',
            'placeholder': 'Confirmar contraseña',
        }),
    )

    def clean_username(self):
        """Valida que el nombre de usuario no exista."""
        username = self.cleaned_data.get('username')
        if username and User.objects.filter(username=username).exists():
            raise forms.ValidationError('Este nombre de usuario ya esta en uso.')
        return username

    def clean_email(self):
        """Valida que el correo no exista (si se proporciono)."""
        email = self.cleaned_data.get('email')
        if email and User.objects.filter(email=email).exists():
            raise forms.ValidationError('Este correo electronico ya esta registrado.')
        return email

    def clean_password2(self):
        """Valida que ambas contraseñas coincidan."""
        password1 = self.cleaned_data.get('password1')
        password2 = self.cleaned_data.get('password2')
        if password1 and password2 and password1 != password2:
            raise forms.ValidationError('Las contraseñas no coinciden.')
        return password2
