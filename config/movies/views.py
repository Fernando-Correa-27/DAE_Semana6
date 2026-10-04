from django.db.models import Avg
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render

from movies.models import Genre, Movie
from movies.selectors.movie_selector import (
    get_movie_recommendations,
    get_movies_by_genre_with_rating,
)


def home(request: HttpRequest) -> HttpResponse:
    """Vista principal: muestra todas las peliculas con sus valoraciones."""
    movies = (
        Movie.objects
        .prefetch_related('genres')
        .annotate(movie_avg_rating=Avg('rating_set__score'))
        .order_by('-release_year', 'title')
    )
    return render(request, 'movies/home.html', {
        'movies': movies,
        'genres': Genre.objects.all(),
    })


def recommend(request: HttpRequest, genre_name: str) -> HttpResponse:
    """Vista de recomendacion: peliculas del mismo genero priorizadas por valoracion."""
    recommendations = get_movie_recommendations(genre_name, limit=10)
    all_movies_of_genre = get_movies_by_genre_with_rating(genre_name)

    context = {
        'genre_name': genre_name,
        'recommendations': recommendations,
        'all_movies': all_movies_of_genre,
        'genres': Genre.objects.all(),
    }
    return render(request, 'movies/recommend.html', context)
