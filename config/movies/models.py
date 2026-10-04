from django.db import models


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
        blank=True,
        null=True,
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
        ]

    def __str__(self) -> str:
        return f"{self.title} ({self.release_year})"

    @property
    def average_rating(self) -> float | None:
        """Calcula la valoracion media de la pelicula sin queries adicionales."""
        result = self.rating_set.aggregate(avg=models.Avg('score'))
        avg = result['avg']
        if avg is None:
            return None
        return round(avg, 2)


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

    def __str__(self) -> str:
        return f"{self.movie.title} ({self.movie.release_year}) - {self.score}/10 ({self.user.username if self.user else 'Anonymous'})"
