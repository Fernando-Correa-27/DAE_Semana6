from django.shortcuts import get_object_or_404, render

from .models import Article, Category


def home(request):
    articles = Article.objects.filter(is_published=True).select_related('author').prefetch_related('categories')
    return render(request, 'news/home.html', {'articles': articles, 'nav_categories': Category.objects.all()})


def detail(request, slug):
    article = get_object_or_404(
        Article.objects.filter(is_published=True).select_related('author').prefetch_related('categories'),
        slug=slug,
    )
    return render(request, 'news/detail.html', {'article': article, 'nav_categories': Category.objects.all()})


def category_list(request, slug):
    category = get_object_or_404(Category, slug=slug)
    articles = category.articles.filter(is_published=True).select_related('author').prefetch_related('categories')
    return render(request, 'news/category.html', {
        'category': category, 'articles': articles, 'nav_categories': Category.objects.all(),
    })
