from django.conf import settings
from django.db import models
from django.urls import reverse
from django.utils import timezone


class Author(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name='editorial_author', verbose_name='cuenta asociada',
    )
    name = models.CharField(max_length=120, verbose_name='nombre')
    email = models.EmailField(blank=True, verbose_name='correo electrónico')
    biography = models.TextField(blank=True, verbose_name='biografía')

    class Meta:
        ordering = ['name']
        verbose_name = 'autor'
        verbose_name_plural = 'autores'

    def __str__(self):
        return self.name


class Category(models.Model):
    name = models.CharField(max_length=80, unique=True, verbose_name='nombre')
    description = models.CharField(max_length=240, blank=True, verbose_name='descripción')
    slug = models.SlugField(max_length=90, unique=True)

    class Meta:
        ordering = ['name']
        verbose_name = 'categoría'
        verbose_name_plural = 'categorías'

    def __str__(self):
        return self.name


class Tag(models.Model):
    name = models.CharField(max_length=60, unique=True, verbose_name='nombre')
    slug = models.SlugField(max_length=70, unique=True)

    class Meta:
        ordering = ['name']
        verbose_name = 'etiqueta'
        verbose_name_plural = 'etiquetas'

    def __str__(self):
        return self.name


class Article(models.Model):
    class Status(models.TextChoices):
        DRAFT = 'draft', 'Borrador'
        PENDING = 'pending', 'Pendiente de revisión'
        PUBLISHED = 'published', 'Publicada'

    title = models.CharField(max_length=180, verbose_name='título')
    slug = models.SlugField(max_length=200, unique=True)
    summary = models.CharField(max_length=280, verbose_name='resumen')
    body = models.TextField(verbose_name='cuerpo')
    featured_image = models.ImageField(upload_to='news/articles/', verbose_name='imagen destacada')
    published_at = models.DateTimeField(default=timezone.now, verbose_name='fecha de publicación')
    author = models.ForeignKey(Author, on_delete=models.PROTECT, related_name='articles')
    categories = models.ManyToManyField(Category, related_name='articles')
    tags = models.ManyToManyField(Tag, through='ArticleTag', related_name='articles', blank=True)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.DRAFT, db_index=True)

    class Meta:
        ordering = ['-published_at', '-pk']
        verbose_name = 'noticia'
        verbose_name_plural = 'noticias'
        permissions = [
            ('review_article', 'Puede revisar noticias'),
            ('publish_article', 'Puede publicar noticias'),
            ('view_unpublished_article', 'Puede consultar noticias no publicadas'),
        ]

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return reverse('news:detail', kwargs={'slug': self.slug})

    @property
    def is_published(self):
        """Compatibilidad de lectura para integraciones previas al flujo editorial."""
        return self.status == self.Status.PUBLISHED


class ArticleTag(models.Model):
    article = models.ForeignKey(Article, on_delete=models.CASCADE, related_name='tag_links')
    tag = models.ForeignKey(Tag, on_delete=models.PROTECT, related_name='article_links')
    associated_at = models.DateTimeField(auto_now_add=True, verbose_name='fecha de asociación')
    position = models.PositiveSmallIntegerField(default=0, verbose_name='orden')

    class Meta:
        ordering = ['position', 'pk']
        verbose_name = 'asociación de etiqueta'
        verbose_name_plural = 'asociaciones de etiquetas'
        constraints = [models.UniqueConstraint(fields=['article', 'tag'], name='unique_article_tag')]

    def __str__(self):
        return f'{self.tag} · {self.article}'


class UserProfile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='profile')
    display_name = models.CharField(max_length=120, blank=True, verbose_name='nombre público')
    biography = models.TextField(blank=True, verbose_name='biografía')

    class Meta:
        verbose_name = 'perfil'
        verbose_name_plural = 'perfiles'

    def __str__(self):
        return self.display_name or self.user.get_username()

    @property
    def public_name(self):
        return self.display_name or self.user.get_full_name() or self.user.get_username()
