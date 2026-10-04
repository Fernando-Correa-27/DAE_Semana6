from django.urls import path
from . import views

app_name = 'movies'

urlpatterns = [
    path('', views.home, name='home'),
    path('genre/<str:genre_name>/', views.recommend, name='recommend'),
    path('favorite/<int:movie_id>/', views.favorite, name='favorite'),
    path('profile/', views.profile_view, name='profile'),
    path('search/', views.search_view, name='search'),
    path('stats/', views.stats_view, name='stats'),
]
