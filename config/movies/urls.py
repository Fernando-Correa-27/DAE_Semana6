from django.urls import path
from . import views

app_name = 'movies'

urlpatterns = [
    path('', views.home, name='home'),
    path('genre/<str:genre_name>/', views.recommend, name='recommend'),
]
