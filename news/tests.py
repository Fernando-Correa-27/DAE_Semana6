from io import BytesIO
from tempfile import TemporaryDirectory

from django.contrib import admin
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from PIL import Image

from news.admin import ArticleAdmin, AuthorAdmin, CategoryAdmin
from news.models import Article, Author, Category


class NewsPortalTests(TestCase):
    def setUp(self):
        self.media_dir = TemporaryDirectory()
        self.media_override = override_settings(MEDIA_ROOT=self.media_dir.name)
        self.media_override.enable()

    def tearDown(self):
        self.media_override.disable()
        self.media_dir.cleanup()

    @classmethod
    def setUpTestData(cls):
        cls.author = Author.objects.create(name='Ana Editora')
        cls.category = Category.objects.create(name='Cultura', slug='cultura')
        cls.article = Article.objects.create(
            title='Noticia de prueba', slug='noticia-prueba',
            summary='Resumen de la noticia para probar la tarjeta.',
            body='Texto con <strong>etiqueta</strong> literal.',
            featured_image=cls.make_image(), author=cls.author,
        )
        cls.article.categories.add(cls.category)

    @staticmethod
    def make_image():
        image = Image.new('RGB', (20, 20), 'navy')
        buffer = BytesIO()
        image.save(buffer, format='JPEG')
        return SimpleUploadedFile('portada.jpg', buffer.getvalue(), content_type='image/jpeg')

    def test_home_includes_shared_card_and_named_links(self):
        response = self.client.get(reverse('news:home'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'news/base.html')
        self.assertContains(response, 'Noticia de prueba')
        self.assertContains(response, reverse('news:detail', args=[self.article.slug]))
        self.assertContains(response, '2026')

    def test_detail_escapes_html_and_serves_uploaded_image(self):
        response = self.client.get(reverse('news:detail', args=[self.article.slug]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '&lt;strong&gt;etiqueta&lt;/strong&gt;')
        self.assertNotContains(response, '<strong>etiqueta</strong>')
        self.assertContains(response, self.article.featured_image.url)

    def test_category_and_empty_states(self):
        response = self.client.get(reverse('news:category', args=[self.category.slug]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Noticia de prueba')
        self.article.is_published = False
        self.article.save(update_fields=['is_published'])
        self.assertContains(self.client.get(reverse('news:home')), 'Todavía no hay noticias publicadas')
        self.assertContains(
            self.client.get(reverse('news:category', args=[self.category.slug])),
            'Esta categoría todavía no tiene noticias publicadas',
        )

    def test_all_news_models_are_registered_in_admin(self):
        self.assertIsInstance(admin.site._registry[Article], ArticleAdmin)
        self.assertIsInstance(admin.site._registry[Author], AuthorAdmin)
        self.assertIsInstance(admin.site._registry[Category], CategoryAdmin)
