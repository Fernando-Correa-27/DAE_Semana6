"""
Forms para la aplicacion movies.
"""

from django import forms

from .models import Rating


class RatingForm(forms.ModelForm):
    """Formulario para valoraciones de peliculas."""

    score = forms.IntegerField(
        min_value=1,
        max_value=10,
        label='Puntuacion',
        widget=forms.NumberInput(attrs={'min': 1, 'max': 10, 'step': 1}),
    )

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

    class Meta:
        model = Rating
        fields = ['score']
        widgets = {}

    def clean_score(self) -> int:
        """La puntuacion debe permanecer dentro del rango 1-10."""
        score = self.cleaned_data['score']
        if not 1 <= score <= 10:
            raise forms.ValidationError('La puntuacion debe estar entre 1 y 10.')
        return score

    def save(self, commit=True):
        rating = super().save(commit=False)
        if self.user and self.user.is_authenticated:
            rating.user = self.user
        if commit:
            rating.save()
        return rating


class SearchForm(forms.Form):
    """Formulario de busqueda de peliculas."""

    q = forms.CharField(
        min_length=2,
        max_length=100,
        label='Buscar',
        widget=forms.TextInput(attrs={'placeholder': 'Buscar pelicula...'}),
    )


class ProfileForm(forms.Form):
    """Formulario para editar el perfil del usuario."""

    username = forms.CharField(max_length=150, label='Nombre de usuario')
    email = forms.EmailField(required=False, label='Correo electronico')

    def clean_email(self):
        """Valida que el email sea valido si se proporciona."""
        email = self.cleaned_data.get('email')
        if email:
            # Django's EmailField already validates format, but we add explicit
            # validation for edge cases
            if '@' not in email:
                raise forms.ValidationError('El correo electrónico no es válido.')
        return email


class FavoriteForm(forms.Form):
    """Formulario vacia para enviar peticiones POST de favoritos (solo CSRF)."""

    pass
