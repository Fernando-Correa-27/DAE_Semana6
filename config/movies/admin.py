from django.contrib import admin
from .models import Movie, Genre, Person, Rating


class RatingInline(admin.TabularInline):
    """Inline para gestionar valoraciones desde el formulario de pelicula."""

    model = Rating
    extra = 1
    max_num = 50
    fields = ('reviewer_name', 'score', 'created_at')
    readonly_fields = ('created_at',)
    ordering = ('-score', 'reviewer_name')


@admin.register(Genre)
class GenreAdmin(admin.ModelAdmin):
    """Configuracion del panel de administracion para Generos."""

    list_display = ('name',)
    search_fields = ('name',)
    ordering = ('name',)


@admin.register(Person)
class PersonAdmin(admin.ModelAdmin):
    """Configuracion del panel de administracion para Personas."""

    list_display = ('name', 'role')
    search_fields = ('name', 'role')
    list_filter = ('role',)
    ordering = ('name',)


@admin.register(Movie)
class MovieAdmin(admin.ModelAdmin):
    """Configuracion del panel de administracion para Peliculas."""

    list_display = ('title', 'release_year', 'average_rating_display', 'created_at', 'updated_at')
    list_filter = ('genres', 'release_year')
    search_fields = ('title', 'synopsis')
    ordering = ('-release_year', 'title')
    readonly_fields = ('created_at', 'updated_at')

    filter_horizontal = ('genres', 'cast')
    inlines = [RatingInline]

    fieldsets = (
        (None, {
            'fields': ('title', 'synopsis', 'release_year', 'cover')
        }),
        ('Relaciones', {
            'fields': ('genres', 'cast')
        }),
        ('Auditoria', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )

    def average_rating_display(self, obj: Movie) -> str | None:
        """Muestra la valoracion media en list_display."""
        avg = obj.average_rating
        if avg is None:
            return 'Sin valoraciones'
        return f'{avg}/10'

    average_rating_display.short_description = 'valoracion media'


@admin.register(Rating)
class RatingAdmin(admin.ModelAdmin):
    """Configuracion del panel de administracion para Valoraciones."""

    list_display = ('movie', 'reviewer_name', 'score', 'created_at')
    list_filter = ('score', 'movie')
    search_fields = ('movie__title', 'reviewer_name')
    ordering = ('-score', 'reviewer_name')
    readonly_fields = ('created_at',)
    list_select_related = ('movie',)
