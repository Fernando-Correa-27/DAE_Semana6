from django.urls import path
from . import views

app_name = 'news'

urlpatterns = [
    path('', views.home, name='home'),
    path('categoria/<slug:slug>/', views.category_list, name='category'),
    path('<slug:slug>/', views.detail, name='detail'),
]
