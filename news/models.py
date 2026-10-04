from django.db import models
from django.urls import reverse
from django.utils import timezone


class Author(models.Model):
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


class Article(models.Model):
    title = models.CharField(max_length=180, verbose_name='título')
    slug = models.SlugField(max_length=200, unique=True)
    summary = models.CharField(max_length=280, verbose_name='resumen')
    body = models.TextField(verbose_name='cuerpo')
    featured_image = models.ImageField(upload_to='news/articles/', verbose_name='imagen destacada')
    published_at = models.DateTimeField(default=timezone.now, verbose_name='fecha de publicación')
    author = models.ForeignKey(Author, on_delete=models.PROTECT, related_name='articles')
    categories = models.ManyToManyField(Category, related_name='articles')
    is_published = models.BooleanField(default=True, verbose_name='publicado')

    class Meta:
        ordering = ['-published_at', '-pk']
        verbose_name = 'noticia'
        verbose_name_plural = 'noticias'

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return reverse('news:detail', kwargs={'slug': self.slug})
