from django.contrib.auth.models import Group, Permission
from django.core.management.base import BaseCommand
from django.contrib.contenttypes.models import ContentType

from news.models import Article, Category, Tag


class Command(BaseCommand):
    help = 'Crea o actualiza los grupos y permisos editoriales de Django.'

    def handle(self, *args, **options):
        permission_map = {
            'Usuarios registrados': [],
            'Redactores': [
                'add_article', 'change_article', 'delete_article',
                'view_article', 'view_unpublished_article',
            ],
            'Editores': [
                'add_article', 'change_article', 'delete_article', 'view_article',
                'view_unpublished_article', 'review_article', 'publish_article',
                'add_category', 'change_category', 'delete_category', 'view_category',
                'add_tag', 'change_tag', 'delete_tag', 'view_tag',
            ],
        }
        permissions = {}
        for model in (Article, Category, Tag):
            content_type = ContentType.objects.get_for_model(model)
            permissions[model] = {
                permission.codename: permission
                for permission in Permission.objects.filter(content_type=content_type)
            }
        for name, codenames in permission_map.items():
            group, _ = Group.objects.get_or_create(name=name)
            group_permissions = []
            for codename in codenames:
                permission = next((mapping[codename] for mapping in permissions.values() if codename in mapping), None)
                if permission:
                    group_permissions.append(permission)
            group.permissions.set(group_permissions)
            self.stdout.write(f'{name}: {len(group_permissions)} permisos')
        self.stdout.write(self.style.SUCCESS('Roles editoriales listos.'))
