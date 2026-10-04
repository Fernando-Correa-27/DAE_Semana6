import logging

from django.db import models
from django.db.models.signals import m2m_changed, post_delete
from django.dispatch import receiver

from movies.utils.image import optimize_image

logger = logging.getLogger(__name__)


class AuditedModel(models.Model):
    """Modelo base con campos de auditoria automatica."""

    created_at = models.DateTimeField(auto_now_add=True, verbose_name='fecha de creacion')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='ultima modificacion')

    class Meta:
        abstract = True


class Genre(models.Model):
    """Representa un genero cinematografico."""

    name = models.CharField(max_length=50, unique=True, verbose_name='nombre del genero')

    class Meta:
        verbose_name = 'genero'
        verbose_name_plural = 'generos'
        ordering = ['name']

    def __str__(self) -> str:
        return self.name


class Person(models.Model):
    """Representa una persona relacionada con peliculas (actor, director, etc.)."""

    name = models.CharField(max_length=100, verbose_name='nombre')
    role = models.CharField(
        max_length=50,
        blank=True,
        default='',
        verbose_name='rol en la pelicula'
    )

    class Meta:
        verbose_name = 'persona'
        verbose_name_plural = 'personas'
        ordering = ['name']

    def __str__(self) -> str:
        return self.name


class Movie(AuditedModel):
    """Representa una pelicula cinematografica."""

    title = models.CharField(max_length=200, verbose_name='titulo')
    synopsis = models.TextField(blank=True, default='', verbose_name='sinopsis')
    release_year = models.PositiveIntegerField(verbose_name='ano de lanzamiento')
    cover = models.ImageField(
        upload_to='movie_covers/',
        max_length=500,
        verbose_name='imagen de portada'
    )
    genres = models.ManyToManyField(Genre, related_name='movies', verbose_name='generos')
    cast = models.ManyToManyField(Person, blank=True, related_name='movies', verbose_name='reparto')

    class Meta:
        verbose_name = 'pelicula'
        verbose_name_plural = 'peliculas'
        ordering = ['-release_year', 'title']
        constraints = [
            models.CheckConstraint(
                condition=models.Q(release_year__gte=1888),
                name='release_year_must_be_valid',
            ),
        ]
        indexes = [
            models.Index(fields=['-release_year', 'title']),
            models.Index(fields=['title'], name='movies_movie_title_idx'),
        ]

    def __str__(self) -> str:
        return f"{self.title} ({self.release_year})"

    def save(self, *args, **kwargs):
        """Guarda la pelicula optimizando la portada si se ha proporcionado."""
        if self.cover:
            try:
                self.cover = optimize_image(self.cover)
            except Exception:
                logger.warning(
                    'No se pudo optimizar la portada de %r; se guarda sin optimizar.',
                    self.title,
                    exc_info=True,
                )
        super().save(*args, **kwargs)
        # The cached movie lists must never outlive a write, otherwise a new or
        # edited movie stays hidden for the whole TTL (5-10 min). The same
        # applies to the cached search/filter results, which are keyed by the
        # query and not by the data.
        self._invalidate_movie_caches()
        self._invalidate_search_caches()

    def delete(self, *args, **kwargs):
        """Elimina la pelicula invalidando las listas de peliculas cacheadas."""
        # Genres must be read *before* the row (and its m2m rows) disappear.
        genre_names = self._genre_names_for_cache()
        result = super().delete(*args, **kwargs)
        self._invalidate_movie_caches(genre_names)
        self._invalidate_search_caches()
        return result

    def _genre_names_for_cache(self) -> list[str]:
        """Generos de la pelicula, para invalidar las claves por genero."""
        if not self.pk:
            return []
        try:
            return [str(name) for name in self.genres.values_list('name', flat=True)]
        except Exception:
            # Cache invalidation must never break a save/delete.
            logger.debug(
                'No se pudieron leer los generos de %r para invalidar la cache.',
                self.title, exc_info=True,
            )
            return []

    def _invalidate_movie_caches(self, genre_names=None) -> None:
        """Invalidate cached movie lists. Best-effort: never raises."""
        if genre_names is None:
            genre_names = self._genre_names_for_cache()
        try:
            from movies.services.movie_service import invalidate_movie_caches
            invalidate_movie_caches(genre_names)
        except Exception:
            # Runs for every save/delete, including migrations and data
            # loading, so a cache problem must stay silent.
            logger.debug('No se pudo invalidar la cache de peliculas.', exc_info=True)

    def _invalidate_search_caches(self) -> None:
        """Invalidate cached search/filter results. Best-effort: never raises.

        Any movie write can change what ``/search/`` and the filtered lists
        match (a new title, a rename, a new year), and the cached keys depend
        only on the query, so they have to be dropped as well.
        """
        try:
            from movies.services.search_service import invalidate_search_caches
            invalidate_search_caches()
        except Exception:
            logger.debug('No se pudo invalidar la cache de busqueda.', exc_info=True)

    @property
    def average_rating(self) -> float | None:
        """Calcula la valoracion media de la pelicula sin queries adicionales.

        Si la instancia ya tiene 'movie_avg_rating' o 'rating_avg' anotado,
        lo usa directamente sin hacer queries adicionales.
        """
        if hasattr(self, 'movie_avg_rating') or hasattr(self, 'rating_avg'):
            avg = getattr(self, 'movie_avg_rating', None) or getattr(self, 'rating_avg', None)
            if avg is not None:
                return round(float(avg), 2)
            return None
        result = self.rating_set.aggregate(avg=models.Avg('score'))
        avg = result['avg']
        if avg is None:
            return None
        return round(float(avg), 2)


class Rating(models.Model):
    """Representa una valoracion de una pelicula por un usuario."""

    movie = models.ForeignKey(
        Movie,
        on_delete=models.CASCADE,
        related_name='rating_set',
        verbose_name='pelicula'
    )
    score = models.PositiveSmallIntegerField(
        verbose_name='puntuacion'
    )
    user = models.ForeignKey(
        'auth.User',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='ratings',
        verbose_name='usuario'
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='fecha de creacion')

    class Meta:
        verbose_name = 'valoracion'
        verbose_name_plural = 'valoraciones'
        ordering = ['-score', 'user__username']
        constraints = [
            models.CheckConstraint(
                condition=models.Q(score__gte=1) & models.Q(score__lte=10),
                name='score_between_1_and_10',
            ),
            models.UniqueConstraint(
                fields=['movie', 'user'],
                name='unique_reviewer_per_movie',
            ),
        ]
        indexes = [
            models.Index(fields=['movie'], name='movies_rating_movie_idx'),
        ]

    def __str__(self) -> str:
        return f"{self.movie.title} ({self.movie.release_year}) - {self.score}/10 ({self.user.username if self.user else 'Anonymous'})"


class Favorite(AuditedModel):
    """Representa una pelicula guardada como favorita por un usuario."""

    user = models.ForeignKey(
        'auth.User',
        on_delete=models.CASCADE,
        related_name='favorites',
        verbose_name='usuario',
    )
    movie = models.ForeignKey(
        Movie,
        on_delete=models.CASCADE,
        related_name='favorite_set',
        verbose_name='pelicula',
    )

    class Meta:
        verbose_name = 'favorito'
        verbose_name_plural = 'favoritos'
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(
                fields=['user', 'movie'],
                name='unique_favorite_per_user_movie',
            ),
        ]

    def __str__(self) -> str:
        return f"{self.user.username} -> {self.movie.title} ({self.movie.release_year})"


# ---------------------------------------------------------------------------
# Cache invalidation for the movie <-> genre relation
# ---------------------------------------------------------------------------
# ``Movie.save()`` runs *before* the admin form (and any ``genres.add(...)``)
# writes the m2m rows, so a brand new movie has no genres yet when its own save
# invalidates the cache. This signal closes that window; without it the
# per-genre keys would only expire with their 5 minute TTL. It also invalidates
# the search/filter keys, because filtering by genre changes with the m2m rows.
@receiver(m2m_changed, sender=Movie.genres.through)
def invalidate_movie_caches_on_genre_change(
    sender, instance, action, reverse, model, pk_set, **kwargs
):
    """Invalidate cached movie lists when a movie's genres change."""
    if action not in {'post_add', 'post_remove', 'post_clear'}:
        return
    try:
        from movies.services.movie_service import invalidate_movie_caches

        if reverse:
            # instance is the Genre; its own movie lists are the affected ones.
            genre_names = [instance.name]
        elif pk_set:
            genre_names = list(Genre.objects.filter(pk__in=pk_set).values_list('name', flat=True))
        else:
            # post_clear: the removed genres are unknown, so over-invalidate.
            genre_names = list(Genre.objects.values_list('name', flat=True))

        invalidate_movie_caches(genre_names)
    except Exception:
        logger.debug('No se pudo invalidar la cache tras un cambio de generos.', exc_info=True)
    try:
        from movies.services.search_service import invalidate_search_caches

        invalidate_search_caches()
    except Exception:
        logger.debug('No se pudo invalidar la cache de busqueda tras un cambio de generos.', exc_info=True)


# ---------------------------------------------------------------------------
# Cache invalidation for bulk deletes
# ---------------------------------------------------------------------------
# ``Movie.objects.filter(...).delete()`` (and the cascade deletes Django fires
# around it) never goes through ``Movie.delete()``, so the cached search and
# filter results would survive the row. Those keys need no genre context, so
# they can be dropped straight away; the per-genre movie lists are left to
# ``Movie.delete()``, which can still read the genres of each instance.
@receiver(post_delete, sender=Movie)
def invalidate_search_caches_on_movie_delete(sender, instance, **kwargs):
    """Invalidate cached search/filter results when a movie row is deleted."""
    try:
        from movies.services.search_service import invalidate_search_caches

        invalidate_search_caches()
    except Exception:
        logger.debug('No se pudo invalidar la cache de busqueda tras un borrado.', exc_info=True)
