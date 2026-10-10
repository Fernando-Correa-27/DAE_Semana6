from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.models import Group
from django.contrib.auth.views import LoginView, LogoutView
from django.core.paginator import Paginator
from django.db import transaction
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.views.decorators.http import require_http_methods, require_POST

from .forms import ArticleForm, ProfileForm, RegistrationForm
from .models import Article, Author, Category, Tag, UserProfile


def nav_context():
    return {'nav_categories': Category.objects.all()}


def render_portal(request, template, context=None):
    return render(request, template, {**nav_context(), **(context or {})})


def visible_articles_for(user):
    published = Article.objects.filter(status=Article.Status.PUBLISHED)
    if not user.is_authenticated:
        return published
    if user.has_perm('news.view_unpublished_article') and user.has_perm('news.review_article'):
        return Article.objects.all()
    if user.has_perm('news.view_unpublished_article'):
        return Article.objects.filter(author__user=user) | published
    return published


def home(request):
    articles = Article.objects.filter(status=Article.Status.PUBLISHED).select_related('author').prefetch_related('categories', 'tags')
    page = Paginator(articles, 9).get_page(request.GET.get('page'))
    return render_portal(request, 'news/home.html', {'articles': page, 'page_obj': page})


def detail(request, slug):
    articles = visible_articles_for(request.user).select_related('author').prefetch_related('categories', 'tags')
    article = get_object_or_404(articles, slug=slug)
    return render_portal(request, 'news/detail.html', {'article': article})


def category_list(request, slug):
    category = get_object_or_404(Category, slug=slug)
    articles = category.articles.filter(status=Article.Status.PUBLISHED).select_related('author').prefetch_related('categories', 'tags')
    page = Paginator(articles, 9).get_page(request.GET.get('page'))
    return render_portal(request, 'news/category.html', {
        'category': category, 'articles': page, 'page_obj': page,
    })


def tag_list(request, slug):
    tag = get_object_or_404(Tag, slug=slug)
    articles = tag.articles.filter(status=Article.Status.PUBLISHED).select_related('author').prefetch_related('categories', 'tags')
    page = Paginator(articles, 9).get_page(request.GET.get('page'))
    return render_portal(request, 'news/tag.html', {
        'tag': tag, 'articles': page, 'page_obj': page,
    })


def register(request):
    if request.user.is_authenticated:
        return redirect('news:home')
    form = RegistrationForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        with transaction.atomic():
            user = form.save()
            reader_group, _ = Group.objects.get_or_create(name='Usuarios registrados')
            user.groups.add(reader_group)
            UserProfile.objects.create(user=user)
            Author.objects.create(
                user=user,
                name=user.get_full_name() or user.get_username(),
                email=user.email,
            )
        login(request, user)
        messages.success(request, 'Tu cuenta está lista. El registro no concede permisos editoriales.')
        return redirect('news:home')
    return render_portal(request, 'registration/register.html', {'form': form})


class PortalLoginView(LoginView):
    template_name = 'registration/login.html'
    authentication_form = AuthenticationForm
    redirect_authenticated_user = True

    def get_success_url(self):
        return reverse_lazy('news:home')

    def get_context_data(self, **kwargs):
        return {**super().get_context_data(**kwargs), **nav_context()}


class PortalLogoutView(LogoutView):
    next_page = reverse_lazy('news:home')


@login_required
@permission_required('news.add_article', raise_exception=True)
def article_create(request):
    form = ArticleForm(request.POST or None, request.FILES or None)
    if request.method == 'POST' and form.is_valid():
        form.instance.author = get_or_create_author(request.user)
        form.instance.status = Article.Status.DRAFT
        article = form.save()
        messages.success(request, 'La noticia se guardó como borrador.')
        return redirect('news:detail', slug=article.slug)
    return render_portal(request, 'news/article_form.html', {'form': form, 'heading': 'Crear noticia'})


@login_required
def my_articles(request):
    if not request.user.has_perm('news.view_unpublished_article'):
        return HttpResponseForbidden('No tienes permiso para consultar noticias editoriales.')
    articles = Article.objects.all() if request.user.has_perm('news.review_article') else Article.objects.filter(author__user=request.user)
    return render_portal(request, 'news/my_articles.html', {'articles': articles.select_related('author')})


def can_manage_article(user, article):
    if not user.has_perm('news.change_article'):
        return False
    if article.status != Article.Status.PUBLISHED and not user.has_perm('news.view_unpublished_article'):
        return False
    return user.has_perm('news.review_article') or article.author.user_id == user.pk


@login_required
def article_edit(request, slug):
    article = get_object_or_404(Article, slug=slug)
    if not can_manage_article(request.user, article):
        return HttpResponseForbidden('No tienes permiso para modificar esta noticia.')
    form = ArticleForm(request.POST or None, request.FILES or None, instance=article)
    if request.method == 'POST' and form.is_valid():
        form.save()
        if not request.user.has_perm('news.review_article') and article.status != Article.Status.DRAFT:
            article.status = Article.Status.DRAFT
            article.save(update_fields=['status'])
        messages.success(request, 'Los cambios se guardaron.')
        return redirect('news:detail', slug=article.slug)
    return render_portal(request, 'news/article_form.html', {'form': form, 'heading': 'Editar noticia', 'article': article})


@login_required
@require_http_methods(['GET', 'POST'])
def article_delete(request, slug):
    article = get_object_or_404(Article, slug=slug)
    if not can_manage_article(request.user, article) or not request.user.has_perm('news.delete_article'):
        return HttpResponseForbidden('No tienes permiso para eliminar esta noticia.')
    if request.method == 'POST':
        article.delete()
        messages.success(request, 'La noticia se eliminó.')
        return redirect('news:my_articles')
    return render_portal(request, 'news/article_confirm_delete.html', {'article': article})


@login_required
@require_POST
def article_transition(request, slug):
    article = get_object_or_404(Article, slug=slug)
    action = request.POST.get('action')
    if action == 'submit' and article.author.user_id == request.user.pk and request.user.has_perm('news.view_unpublished_article') and request.user.has_perm('news.change_article'):
        if article.status == Article.Status.DRAFT:
            article.status = Article.Status.PENDING
            article.save(update_fields=['status'])
            messages.success(request, 'La noticia se envió a revisión.')
    elif action == 'publish' and request.user.has_perm('news.view_unpublished_article') and request.user.has_perm('news.change_article') and request.user.has_perm('news.publish_article'):
        if article.status == Article.Status.PENDING:
            article.status = Article.Status.PUBLISHED
            article.published_at = timezone_now()
            article.save(update_fields=['status', 'published_at'])
            messages.success(request, 'La noticia se publicó.')
    elif action == 'return' and request.user.has_perm('news.view_unpublished_article') and request.user.has_perm('news.change_article') and request.user.has_perm('news.review_article'):
        article.status = Article.Status.DRAFT
        article.save(update_fields=['status'])
        messages.success(request, 'La noticia volvió a borrador.')
    else:
        return HttpResponseForbidden('No tienes permiso para realizar este cambio editorial.')
    return redirect('news:detail', slug=article.slug)


@login_required
def profile(request):
    profile_obj, _ = UserProfile.objects.get_or_create(user=request.user)
    form = ProfileForm(request.POST or None, instance=profile_obj)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Tu perfil se actualizó.')
        return redirect('news:profile')
    return render_portal(request, 'news/profile.html', {'form': form})


def get_or_create_author(user):
    author, _ = Author.objects.get_or_create(
        user=user,
        defaults={'name': user.get_full_name() or user.get_username(), 'email': user.email},
    )
    return author


def timezone_now():
    from django.utils import timezone
    return timezone.now()
