"""
URL configuration for config project.
"""

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path('admin/', admin.site.urls),
    path('accounts/', include('movies.accounts.urls')),
    path('noticias/', include('news.urls')),
    path('', include('movies.urls')),
]

# Servir las portadas subidas a MEDIA_ROOT SOLO en desarrollo. static() ya es un
# no-op con DEBUG=False, y el guardia explicito lo deja inequivoco: en
# produccion los media los sirve el servidor web (nginx, S3, ...), nunca Django.
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
