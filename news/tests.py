from io import BytesIO
from tempfile import TemporaryDirectory

from django.contrib import admin
from django.contrib.auth.models import Permission, User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.files.storage import default_storage
from django.contrib.staticfiles import finders
from django.db.models.deletion import ProtectedError
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from PIL import Image

from news.admin import ArticleAdmin, AuthorAdmin, CategoryAdmin
from news.models import Article, ArticleTag, Author, Category, Tag, UserProfile


class NewsPortalTests(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.media_dir = TemporaryDirectory()
        cls.media_override = override_settings(MEDIA_ROOT=cls.media_dir.name)
        cls.media_override.enable()
        super().setUpClass()

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        cls.media_override.disable()
        cls.media_dir.cleanup()

    @classmethod
    def setUpTestData(cls):
        cls.author = Author.objects.create(name='Ana Editora')
        cls.category = Category.objects.create(name='Cultura', slug='cultura')
        cls.tag = Tag.objects.create(name='Comunidad', slug='comunidad')
        cls.article = Article.objects.create(
            title='Noticia de prueba', slug='noticia-prueba',
            summary='Resumen de la noticia para probar la tarjeta.',
            body='Texto con <strong>etiqueta</strong> literal.',
            featured_image=cls.make_image(), author=cls.author,
            status=Article.Status.PUBLISHED,
        )
        cls.article.categories.add(cls.category)
        ArticleTag.objects.create(article=cls.article, tag=cls.tag, position=0)

    @staticmethod
    def make_image():
        image = Image.new('RGB', (20, 20), 'navy')
        buffer = BytesIO()
        image.save(buffer, format='JPEG')
        return SimpleUploadedFile('portada.jpg', buffer.getvalue(), content_type='image/jpeg')

    @staticmethod
    def add_permissions(user, *codenames):
        for codename in codenames:
            user.user_permissions.add(Permission.objects.get(codename=codename, content_type__app_label='news'))

    def make_redactor(self, username='redactor'):
        user = User.objects.create_user(username, password='A-safe-test-pass-77')
        self.add_permissions(user, 'add_article', 'change_article', 'delete_article', 'view_unpublished_article')
        author = Author.objects.create(name=username.title(), user=user)
        return user, author

    def test_public_home_detail_category_and_autoescaped_body(self):
        response = self.client.get(reverse('news:home'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'news/base.html')
        self.assertContains(response, 'Noticia de prueba')
        self.assertContains(response, reverse('news:detail', args=[self.article.slug]))
        detail_response = self.client.get(reverse('news:detail', args=[self.article.slug]))
        self.assertContains(detail_response, '&lt;strong&gt;etiqueta&lt;/strong&gt;')
        self.assertNotContains(detail_response, '<strong>etiqueta</strong>')
        self.assertContains(detail_response, self.article.featured_image.url)
        self.assertTrue(default_storage.exists(self.article.featured_image.name))
        self.assertTrue(finders.find('news/css/news.css'))
        self.assertTrue(finders.find('news/js/theme.js'))
        self.assertContains(response, 'data-theme-toggle')
        category_response = self.client.get(reverse('news:category', args=[self.category.slug]))
        self.assertContains(category_response, 'Noticia de prueba')
        tag_response = self.client.get(reverse('news:tag', args=[self.tag.slug]))
        self.assertContains(tag_response, 'Noticia de prueba')
        self.assertContains(detail_response, reverse('news:tag', args=[self.tag.slug]))

    def test_empty_states_and_pagination(self):
        self.article.status = Article.Status.DRAFT
        self.article.save(update_fields=['status'])
        self.assertContains(self.client.get(reverse('news:home')), 'Todavía no hay noticias publicadas')
        self.assertContains(
            self.client.get(reverse('news:category', args=[self.category.slug])),
            'Esta categoría todavía no tiene noticias publicadas',
        )
        self.article.status = Article.Status.PUBLISHED
        self.article.save(update_fields=['status'])
        for index in range(10):
            article = Article.objects.create(
                title=f'Paginación {index}', slug=f'paginacion-{index}', summary='Resumen.',
                body='Cuerpo.', featured_image=self.make_image(), author=self.author,
                status=Article.Status.PUBLISHED,
            )
            article.categories.add(self.category)
        paginated = self.client.get(reverse('news:home'))
        self.assertTrue(paginated.context['page_obj'].has_next())
        self.assertContains(paginated, 'Siguiente')

    def test_registration_login_logout_and_reader_gets_no_editorial_permission(self):
        response = self.client.post(reverse('news:register'), {
            'username': 'reader', 'email': 'reader@example.com',
            'password1': 'A-safe-reader-pass-77', 'password2': 'A-safe-reader-pass-77',
        })
        self.assertRedirects(response, reverse('news:home'))
        user = User.objects.get(username='reader')
        self.assertTrue(user.check_password('A-safe-reader-pass-77'))
        self.assertFalse(user.has_perm('news.add_article'))
        self.assertTrue(UserProfile.objects.filter(user=user).exists())
        self.assertEqual(user.profile.user, user)
        self.assertTrue(user.groups.filter(name='Usuarios registrados').exists())
        self.client.post(reverse('news:logout'))
        self.assertNotIn('_auth_user_id', self.client.session)
        self.assertTrue(self.client.login(username='reader', password='A-safe-reader-pass-77'))
        self.assertEqual(self.client.get(reverse('news:article_create')).status_code, 403)

    def test_invalid_registration_and_bad_login(self):
        response = self.client.post(reverse('news:register'), {
            'username': 'bad', 'email': 'not-an-email', 'password1': 'same', 'password2': 'different',
        })
        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(username='bad').exists())
        self.assertEqual(self.client.post(reverse('news:login'), {'username': 'absent', 'password': 'x'}).status_code, 200)

    def test_csrf_protects_registration_and_logout(self):
        secure_client = Client(enforce_csrf_checks=True)
        registration = secure_client.get(reverse('news:register'))
        self.assertContains(registration, 'csrfmiddlewaretoken')
        self.assertEqual(secure_client.post(reverse('news:register'), {}).status_code, 403)
        secure_client.force_login(User.objects.create_user('csrf-user', password='A-safe-test-pass-77'))
        self.assertEqual(secure_client.post(reverse('news:logout')).status_code, 403)

    def test_redactor_create_edit_and_cannot_access_another_authors_draft(self):
        redactor, author = self.make_redactor()
        self.client.force_login(redactor)
        response = self.client.post(reverse('news:article_create'), {
            'title': 'Nueva historia', 'slug': 'nueva-historia', 'summary': 'Resumen suficiente.',
            'body': 'Contenido de prueba.', 'categories': [self.category.pk], 'tags': [self.tag.pk],
            'featured_image': self.make_image(),
        })
        self.assertRedirects(response, reverse('news:detail', args=['nueva-historia']))
        created = Article.objects.get(slug='nueva-historia')
        self.assertEqual(created.author, author)
        self.assertEqual(created.status, Article.Status.DRAFT)
        self.assertEqual(created.tags.get(), self.tag)
        self.assertEqual(self.client.get(reverse('news:detail', args=[created.slug])).status_code, 200)
        edited = self.client.post(reverse('news:article_edit', args=[created.slug]), {
            'title': 'Historia editada', 'slug': created.slug, 'summary': 'Resumen actualizado.',
            'body': 'Contenido actualizado.', 'categories': [self.category.pk], 'tags': [self.tag.pk],
        })
        self.assertRedirects(edited, reverse('news:detail', args=[created.slug]))
        created.refresh_from_db()
        self.assertEqual(created.title, 'Historia editada')
        self.assertEqual(self.client.get(reverse('news:article_edit', args=[self.article.slug])).status_code, 403)
        self.assertEqual(self.client.post(reverse('news:article_transition', args=[created.slug]), {'action': 'submit'}).status_code, 302)
        created.refresh_from_db()
        self.assertEqual(created.status, Article.Status.PENDING)

    def test_redactor_can_reorder_tags_and_reviewer_without_change_permission_cannot_edit(self):
        redactor, author = self.make_redactor('tagredactor')
        second_tag = Tag.objects.create(name='Ciudad', slug='ciudad')
        article = Article.objects.create(
            title='Etiquetas ordenadas', slug='etiquetas-ordenadas', summary='Resumen.',
            body='Cuerpo.', featured_image=self.make_image(), author=author,
        )
        ArticleTag.objects.create(article=article, tag=self.tag, position=0)
        ArticleTag.objects.create(article=article, tag=second_tag, position=1)
        self.client.force_login(redactor)
        response = self.client.post(reverse('news:article_edit', args=[article.slug]), {
            'title': article.title, 'slug': article.slug, 'summary': article.summary,
            'body': article.body, 'categories': [self.category.pk],
            'tags': [second_tag.pk, self.tag.pk],
        })
        self.assertRedirects(response, reverse('news:detail', args=[article.slug]))
        self.assertEqual(list(article.tag_links.values_list('tag_id', 'position')), [
            (second_tag.pk, 0), (self.tag.pk, 1),
        ])

        reviewer = User.objects.create_user('review-only', password='A-safe-test-pass-77')
        self.add_permissions(reviewer, 'review_article', 'view_unpublished_article')
        self.client.force_login(reviewer)
        self.assertEqual(self.client.get(reverse('news:article_edit', args=[article.slug])).status_code, 403)

    def test_review_permission_alone_does_not_expose_unpublished_articles(self):
        redactor, author = self.make_redactor('privateauthor')
        draft = Article.objects.create(
            title='Borrador privado', slug='borrador-privado', summary='Resumen.',
            body='Cuerpo.', featured_image=self.make_image(), author=author,
        )
        reviewer = User.objects.create_user('review-only-private', password='A-safe-test-pass-77')
        self.add_permissions(reviewer, 'review_article', 'change_article')
        self.client.force_login(reviewer)
        self.assertEqual(self.client.get(reverse('news:detail', args=[draft.slug])).status_code, 404)
        self.assertEqual(self.client.get(reverse('news:article_edit', args=[draft.slug])).status_code, 403)
        self.assertEqual(self.client.get(reverse('news:my_articles')).status_code, 403)

    def test_editor_can_publish_pending_article(self):
        editor = User.objects.create_user('editor', password='A-safe-test-pass-77')
        self.add_permissions(editor, 'publish_article', 'review_article', 'view_unpublished_article', 'change_article')
        self.article.status = Article.Status.PENDING
        self.article.save(update_fields=['status'])
        self.client.force_login(editor)
        response = self.client.post(reverse('news:article_transition', args=[self.article.slug]), {'action': 'publish'})
        self.assertRedirects(response, reverse('news:detail', args=[self.article.slug]))
        self.article.refresh_from_db()
        self.assertEqual(self.article.status, Article.Status.PUBLISHED)

    def test_deletion_requires_post_and_permission(self):
        redactor, author = self.make_redactor()
        owned = Article.objects.create(
            title='Borrador propio', slug='borrador-propio', summary='Resumen.', body='Cuerpo.',
            featured_image=self.make_image(), author=author, status=Article.Status.DRAFT,
        )
        self.client.force_login(redactor)
        confirm = self.client.get(reverse('news:article_delete', args=[owned.slug]))
        self.assertEqual(confirm.status_code, 200)
        self.assertTrue(Article.objects.filter(pk=owned.pk).exists())
        response = self.client.post(reverse('news:article_delete', args=[owned.slug]))
        self.assertRedirects(response, reverse('news:my_articles'))
        self.assertFalse(Article.objects.filter(pk=owned.pk).exists())
        self.assertEqual(self.client.post(reverse('news:article_delete', args=[self.article.slug])).status_code, 403)

    def test_admin_models_and_related_relationships(self):
        self.assertIsInstance(admin.site._registry[Article], ArticleAdmin)
        self.assertIsInstance(admin.site._registry[Author], AuthorAdmin)
        self.assertIsInstance(admin.site._registry[Category], CategoryAdmin)
        self.assertEqual(self.tag.articles.get(), self.article)
        self.assertEqual(self.category.articles.get(), self.article)
        self.assertEqual(self.article.tag_links.get().position, 0)

    def test_admin_editorial_queryset_and_forms_respect_redactor_ownership(self):
        redactor, author = self.make_redactor('staffredactor')
        redactor.is_staff = True
        redactor.save(update_fields=['is_staff'])
        owned = Article.objects.create(
            title='Noticia interna propia', slug='noticia-interna-propia', summary='Resumen.',
            body='Cuerpo.', featured_image=self.make_image(), author=author,
            status=Article.Status.DRAFT,
        )
        self.client.force_login(redactor)
        changelist = self.client.get(reverse('admin:news_article_changelist'))
        self.assertEqual(changelist.status_code, 200)
        self.assertContains(changelist, owned.title)
        self.assertNotContains(changelist, self.article.title)
        change_form = self.client.get(reverse('admin:news_article_change', args=[owned.pk]))
        self.assertEqual(change_form.status_code, 200)

    def test_on_delete_policies_preserve_referenced_data(self):
        with self.assertRaises(ProtectedError):
            self.author.delete()
        category = Category.objects.create(name='Temporal', slug='temporal')
        self.article.categories.add(category)
        category.delete()
        self.assertTrue(Article.objects.filter(pk=self.article.pk).exists())
        self.assertFalse(self.article.categories.filter(pk=category.pk).exists())
        with self.assertRaises(ProtectedError):
            self.tag.delete()
        article = Article.objects.create(
            title='Temporal', slug='temporal', summary='Resumen.', body='Cuerpo.',
            featured_image=self.make_image(), author=self.author,
        )
        ArticleTag.objects.create(article=article, tag=self.tag)
        article_id = article.pk
        article.delete()
        self.assertFalse(ArticleTag.objects.filter(article_id=article_id).exists())
        profile_user = User.objects.create_user('profile', password='A-safe-test-pass-77')
        UserProfile.objects.create(user=profile_user)
        profile_user_id = profile_user.pk
        profile_user.delete()
        self.assertFalse(UserProfile.objects.filter(user_id=profile_user_id).exists())
        linked_user = User.objects.create_user('linked-author', password='A-safe-test-pass-77')
        linked_author = Author.objects.create(name='Linked author', user=linked_user)
        linked_article = Article.objects.create(
            title='Cuenta desasociada', slug='cuenta-desasociada', summary='Resumen.',
            body='Cuerpo.', featured_image=self.make_image(), author=linked_author,
        )
        linked_user.delete()
        linked_author.refresh_from_db()
        self.assertIsNone(linked_author.user_id)
        self.assertTrue(Article.objects.filter(pk=linked_article.pk).exists())
