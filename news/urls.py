from django.urls import path

from . import views

app_name = 'news'

urlpatterns = [
    path('', views.home, name='home'),
    path('cuenta/registro/', views.register, name='register'),
    path('cuenta/ingresar/', views.PortalLoginView.as_view(), name='login'),
    path('cuenta/salir/', views.PortalLogoutView.as_view(), name='logout'),
    path('cuenta/perfil/', views.profile, name='profile'),
    path('editorial/mis-noticias/', views.my_articles, name='my_articles'),
    path('editorial/nueva/', views.article_create, name='article_create'),
    path('editorial/<slug:slug>/editar/', views.article_edit, name='article_edit'),
    path('editorial/<slug:slug>/eliminar/', views.article_delete, name='article_delete'),
    path('editorial/<slug:slug>/estado/', views.article_transition, name='article_transition'),
    path('categoria/<slug:slug>/', views.category_list, name='category'),
    path('etiqueta/<slug:slug>/', views.tag_list, name='tag'),
    path('<slug:slug>/', views.detail, name='detail'),
]
