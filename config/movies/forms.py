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


class SearchForm(forms.Form):
    """Formulario de busqueda de peliculas por titulo."""

    q = forms.CharField(
        min_length=2,
        label='Buscar',
        widget=forms.TextInput(attrs={'placeholder': 'Buscar por titulo...', 'class': 'search-input'}),
    )


class ProfileForm(forms.Form):
    """Formulario para editar el perfil del usuario."""

    username = forms.CharField(
        max_length=150,
        label='Nombre de usuario',
        widget=forms.TextInput(attrs={'class': 'profile-input'}),
    )

    email = forms.EmailField(
        required=False,
        label='Email',
        widget=forms.EmailInput(attrs={'class': 'profile-input'}),
    )


class FavoriteForm(forms.Form):
    """Formulario CSRF para agregar favoritos (el movie_id se envia en POST)."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
