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
        """Valida que el nombre de usuario no exista y tenga minimo 3 caracteres."""
        username = self.cleaned_data.get('username')
        if username and len(username) < 3:
            raise forms.ValidationError('El nombre de usuario debe tener al menos 3 caracteres.')
        if username and User.objects.filter(username=username).exists():
            raise forms.ValidationError('Este nombre de usuario ya esta en uso.')
        return username

    def clean_email(self):
        """Valida que el correo no exista (si se proporciono)."""
        email = self.cleaned_data.get('email')
        if email and User.objects.filter(email=email).exists():
            raise forms.ValidationError('Este correo electronico ya esta registrado.')
        return email

    def clean_password1(self):
        """Valida que la contraseña tenga minimo 8 caracteres."""
        password1 = self.cleaned_data.get('password1')
        if password1 and len(password1) < 8:
            raise forms.ValidationError('La contraseña debe tener al menos 8 caracteres.')
        return password1

    def clean_password2(self):
        """Valida que ambas contraseñas coincidan y cumplan los requisitos."""
        password1 = self.cleaned_data.get('password1')
        password2 = self.cleaned_data.get('password2')
        if password1 and password2 and password1 != password2:
            raise forms.ValidationError('Las contraseñas no coinciden.')
        if password2 and len(password2) < 8:
            raise forms.ValidationError('La contraseña debe tener al menos 8 caracteres.')
        return password2
