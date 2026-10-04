"""
Vistas para el modulo de cuentas (login, logout, registro).
"""

from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.hashers import make_password, check_password
from django.contrib import messages
from django.contrib.auth.decorators import login_required as django_login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.utils.decorators import method_decorator
from django.views.generic import View

from movies.decorators import user_not_authenticated

from .forms import LoginForm, RegisterForm


class LoginView(View):
    """Vista para inicio de sesion."""

    template_name = 'accounts/login.html'

    def get(self, request: HttpRequest) -> HttpResponse:
        """Muestra el formulario de login."""
        if request.user.is_authenticated:
            return redirect('movies:home')
        form = LoginForm()
        return render(request, self.template_name, {'form': form})

    def post(self, request: HttpRequest) -> HttpResponse:
        """Procesa el formulario de login."""
        form = LoginForm(request.POST)
        if form.is_valid():
            username = form.cleaned_data['username']
            password = form.cleaned_data['password']

            # Verificar password con check_password (compatible con make_password)
            from django.contrib.auth.models import User
            try:
                user = User.objects.get(username=username)
                if check_password(password, user.password):
                    login(request, user)
                    messages.success(request, f'Bienvenido, {user.username}!')
                    return redirect('movies:home')
                else:
                    messages.error(request, 'Credenciales incorrectas.')
            except User.DoesNotExist:
                messages.error(request, 'Credenciales incorrectas.')
        else:
            messages.error(request, 'Nombre de usuario o contraseña incorrectos.')

        return render(request, self.template_name, {'form': form})


class LogoutView(View):
    """Vista para cerrar sesion."""

    def get(self, request: HttpRequest) -> HttpResponse:
        """Muestra pagina de confirmacion de logout."""
        if not request.user.is_authenticated:
            return redirect('accounts:login')
        return render(request, 'accounts/logout_confirm.html')

    def post(self, request: HttpRequest) -> HttpResponse:
        """Cierra sesion y redirige."""
        if request.user.is_authenticated:
            logout(request)
            messages.info(request, 'Has cerrado sesion correctamente.')
        return redirect('movies:home')


@method_decorator(user_not_authenticated(), name='dispatch')
class RegisterView(View):
    """Vista para registro de nuevos usuarios."""

    template_name = 'accounts/register.html'

    def get(self, request: HttpRequest) -> HttpResponse:
        """Muestra el formulario de registro."""
        form = RegisterForm()
        return render(request, self.template_name, {'form': form})

    def post(self, request: HttpRequest) -> HttpResponse:
        """Procesa el formulario de registro."""
        form = RegisterForm(request.POST)
        if form.is_valid():
            username = form.cleaned_data['username']
            email = form.cleaned_data.get('email', '')
            password1 = form.cleaned_data['password1']

            # Crear usuario con create_user (usa make_password internamente)
            from django.contrib.auth.models import User
            user = User.objects.create_user(
                username=username,
                email=email,
                password=password1,
            )

            # Login automatico despues del registro
            login(request, user)
            messages.success(request, f'Cuenta creada exitosamente. Bienvenido, {user.username}!')
            return redirect('movies:home')
        else:
            messages.error(request, 'Por favor corrige los errores del formulario.')

        return render(request, self.template_name, {'form': form})
