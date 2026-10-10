from django.contrib import admin
from django.core.exceptions import PermissionDenied

from .models import Article, ArticleTag, Author, Category, Tag, UserProfile


class ArticleTagInline(admin.TabularInline):
    model = ArticleTag
    extra = 1
    autocomplete_fields = ('tag',)
    readonly_fields = ('associated_at',)


@admin.register(Article)
class ArticleAdmin(admin.ModelAdmin):
    list_display = ('title', 'author', 'status', 'published_at')
    list_filter = ('status', 'published_at', 'categories', 'tags')
    search_fields = ('title', 'summary', 'body', 'author__name')
    ordering = ('-published_at', '-pk')
    date_hierarchy = 'published_at'
    list_select_related = ('author',)
    prepopulated_fields = {'slug': ('title',)}
    filter_horizontal = ('categories',)
    autocomplete_fields = ('author',)
    inlines = (ArticleTagInline,)
    fieldsets = (
        ('Contenido', {'fields': ('title', 'slug', 'summary', 'body', 'featured_image')}),
        ('Clasificación', {'fields': ('categories', 'status')}),
        ('Autoría y publicación', {'fields': ('author', 'published_at')}),
    )

    def get_readonly_fields(self, request, obj=None):
        readonly = []
        if not request.user.is_superuser and not request.user.has_perm('news.review_article'):
            readonly.append('author')
        if not request.user.is_superuser and not request.user.has_perm('news.publish_article'):
            readonly.append('status')
        return tuple(readonly)

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        if request.user.is_superuser or (
            request.user.has_perm('news.review_article')
            and request.user.has_perm('news.view_unpublished_article')
        ):
            return queryset
        if request.user.has_perm('news.view_unpublished_article'):
            return queryset.filter(author__user=request.user)
        return queryset.filter(status=Article.Status.PUBLISHED)

    def has_change_permission(self, request, obj=None):
        allowed = super().has_change_permission(request, obj)
        if not allowed or obj is None or request.user.is_superuser or request.user.has_perm('news.review_article'):
            return allowed
        return obj.author.user_id == request.user.pk

    def has_delete_permission(self, request, obj=None):
        allowed = super().has_delete_permission(request, obj)
        if not allowed or obj is None or request.user.is_superuser or request.user.has_perm('news.review_article'):
            return allowed
        return obj.author.user_id == request.user.pk

    def save_model(self, request, obj, form, change):
        if not change and not request.user.has_perm('news.review_article') and not request.user.is_superuser:
            author, _ = Author.objects.get_or_create(
                user=request.user,
                defaults={'name': request.user.get_full_name() or request.user.get_username(), 'email': request.user.email},
            )
            obj.author = author
            obj.status = Article.Status.DRAFT
        elif change and not request.user.has_perm('news.review_article') and not request.user.is_superuser:
            original = self.get_queryset(request).get(pk=obj.pk)
            if obj.author_id != original.author_id:
                raise PermissionDenied
            obj.status = Article.Status.DRAFT
        elif not request.user.is_superuser and not request.user.has_perm('news.publish_article'):
            if not change:
                obj.status = Article.Status.DRAFT
            else:
                obj.status = self.get_queryset(request).get(pk=obj.pk).status
        super().save_model(request, obj, form, change)


@admin.register(Author)
class AuthorAdmin(admin.ModelAdmin):
    list_display = ('name', 'email', 'user')
    search_fields = ('name', 'email', 'user__username')
    autocomplete_fields = ('user',)
    list_select_related = ('user',)


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug')
    search_fields = ('name', 'description')
    prepopulated_fields = {'slug': ('name',)}


@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug')
    search_fields = ('name', 'slug')
    prepopulated_fields = {'slug': ('name',)}


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('public_name', 'user')
    search_fields = ('display_name', 'user__username', 'user__email')
    autocomplete_fields = ('user',)


admin.site.site_header = 'DAE Noticias · Administración'
admin.site.site_title = 'Administración editorial'
admin.site.index_title = 'Gestión del portal'
