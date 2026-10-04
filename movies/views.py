from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Avg, Count, Q
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render

from movies.forms import FavoriteForm, ProfileForm, RatingForm, SearchForm
from movies.models import Genre, Movie
from movies.services import (
    add_favorite,
    create_rating,
    filter_movies,
    get_all_movies_of_genre,
    get_genre_recommendations,
    get_home_movies,
    get_revenue_estimate,
    get_rating_stats,
    get_user_favorite_count,
    get_user_favorites,
    get_user_profile_data,
    get_user_rating_history,
    get_user_stats,
    is_favorite,
    remove_favorite,
    search_movies,
    update_profile,
)


def home(request: HttpRequest) -> HttpResponse:
    """Vista principal: muestra todas las peliculas con sus valoraciones (paginadas)."""
    movies_result = get_home_movies()

    search_form = SearchForm(request.GET or None)
    search_qs = None

    if movies_result.get('success'):
        movies_qs = movies_result.get('movies', Movie.objects.none())
        search_form = SearchForm(request.GET or None)
        if search_form.is_valid():
            query = search_form.cleaned_data['q']
            search_result = search_movies(query)
            if search_result.get('success'):
                movies_qs = search_qs = search_result['movies']
        
        # ``movies_qs`` above comes from three different sources and only one of
        # them (``get_home_movies``) annotates ``movie_avg_rating``: the search
        # branch replaces it with ``search_movies()``'s plain queryset, which
        # carries no average at all. Re-declaring both annotations here makes the
        # average (and the count) independent of the source, so the cards in
        # home.html never fall back to "Sin valoraciones" for a rated movie.
        movies_qs = movies_qs.annotate(
            movie_avg_rating=Avg('rating_set__score'),
            rating_count=Count('rating_set'),
        )

        # Paginate: 12 movies per page
        page_number = request.GET.get('page', 1)
        paginator = Paginator(movies_qs, 12)
        page_obj = paginator.get_page(page_number)

        movie_rating_forms = {}
        for movie in page_obj:
            movie_rating_forms[movie.id] = RatingForm(
                user=request.user if request.user.is_authenticated else None,
            )
            if request.user.is_authenticated:
                fav_result = is_favorite(request.user, movie)
                movie.is_favorite = fav_result.get('is_favorite', False)
            else:
                movie.is_favorite = False
    else:
        messages.error(request, 'Error al cargar las peliculas. Intente nuevamente.')
        page_obj = []
        movie_rating_forms = {}

    if request.method == 'POST' and 'movie_id' in request.POST:
        movie_id = request.POST.get('movie_id')
        try:
            movie_obj = Movie.objects.get(id=movie_id)
        except Movie.DoesNotExist:
            messages.error(request, 'Pelicula no encontrada.')
            return redirect('movies:home')
        rating_form = RatingForm(
            request.POST,
            user=request.user if request.user.is_authenticated else None,
        )
        if rating_form.is_valid():
            score = rating_form.cleaned_data['score']
            rating_result = create_rating(request.user, movie_obj, score)
            if rating_result.get('success'):
                messages.success(request, 'Valoracion guardada correctamente.')
            else:
                messages.error(request, rating_result.get('message', 'Error al guardar la valoracion.'))
            return redirect('movies:home')
        else:
            messages.error(request, 'Error en la valoracion. Corrija los campos marcados.')
            # La clave debe ser ``movie_obj.id`` (un int), NO el ``movie_id``
            # crudo del POST (siempre un str). El diccionario se pobló mas
            # arriba con claves enteras y la plantilla lo resuelve con
            # ``{% with form=movie_rating_forms|get_item:movie.id %}``, donde
            # ``movie.id`` tambien es un int: ``{'16': form}`` y ``{16: form}``
            # son claves distintas, asi que guardar con la clave str dejaba el
            # formulario con errores en una entrada huerfana que la plantilla
            # nunca encuentra. La tarjeta pintaba entonces un ``RatingForm``
            # vacio y el POST fallido se reducia al ``alert-danger`` global,
            # sin que el usuario viera que campo habia fallado ni por que.
            movie_rating_forms[movie_obj.id] = rating_form

    return render(request, 'movies/home.html', {
        'movies': page_obj,
        'genres': Genre.objects.all(),
        'search_form': search_form,
        'movie_rating_forms': movie_rating_forms,
    })


def recommend(request: HttpRequest, genre_name: str) -> HttpResponse:
    """Vista de recomendacion: peliculas del mismo genero priorizadas por valoracion."""
    recommendations_result = get_genre_recommendations(genre_name, limit=10)
    all_movies_result = get_all_movies_of_genre(genre_name)

    recommendations = recommendations_result.get('recommendations', [])
    all_movies_of_genre = all_movies_result.get('movies', [])

    if not recommendations_result.get('success'):
        messages.error(request, recommendations_result.get('message', 'Error al obtener recomendaciones.'))
    if not all_movies_result.get('success'):
        messages.error(request, all_movies_result.get('message', 'Error al obtener peliculas del genero.'))

    # Annotate recommendations with avg rating and rating count
    if recommendations:
        recommendations = Movie.objects.filter(id__in=[m.id for m in recommendations]).annotate(
            rating_avg=Avg('rating_set__score'),
            rating_count=Count('rating_set'),
        )
    else:
        recommendations = Movie.objects.none()

    # Annotate all_movies_of_genre with avg rating and rating count
    if all_movies_of_genre:
        all_movies_of_genre = Movie.objects.filter(id__in=[m.id for m in all_movies_of_genre]).annotate(
            rating_avg=Avg('rating_set__score'),
            rating_count=Count('rating_set'),
        )
    else:
        all_movies_of_genre = Movie.objects.none()

    all_movies = list(recommendations) + list(all_movies_of_genre)

    movie_rating_forms = {}
    for movie in all_movies:
        movie_rating_forms[movie.id] = RatingForm(
            user=request.user if request.user.is_authenticated else None,
        )
        if request.user.is_authenticated:
            fav_result = is_favorite(request.user, movie)
            movie.is_favorite = fav_result.get('is_favorite', False)
        else:
            movie.is_favorite = False

    if request.method == 'POST' and 'movie_id' in request.POST:
        movie_id = request.POST.get('movie_id')
        try:
            movie_obj = Movie.objects.get(id=movie_id)
        except Movie.DoesNotExist:
            messages.error(request, 'Pelicula no encontrada.')
            return redirect('movies:recommend', genre_name=genre_name)
        rating_form = RatingForm(
            request.POST,
            user=request.user if request.user.is_authenticated else None,
        )
        if rating_form.is_valid():
            score = rating_form.cleaned_data['score']
            rating_result = create_rating(request.user, movie_obj, score)
            if rating_result.get('success'):
                messages.success(request, 'Valoracion guardada correctamente.')
            else:
                messages.error(request, rating_result.get('message', 'Error al guardar la valoracion.'))
            return redirect('movies:recommend', genre_name=genre_name)
        else:
            messages.error(request, 'Error en la valoracion. Corrija los campos marcados.')
            # Misma clave que en ``home``: ``movie_obj.id`` (int), nunca el
            # ``movie_id`` crudo del POST (str), o la tarjeta no encontraria
            # el formulario con errores. Ver el comentario de ``home``.
            #
            # No hace falta anadir la peli a ``recommendations`` ni a
            # ``all_movies_of_genre``: el diccionario de arriba se puebla con
            # ``all_movies = list(recommendations) + list(all_movies_of_genre)``
            # y ``all_movies_of_genre`` (``get_movies_by_genre_with_rating``)
            # incluye *todas* las peliculas del genero, tambien las que no
            # tienen ninguna valoracion (que es justo lo que
            # ``get_movie_recommendations`` filtra con ``rating_avg__isnull
            # =False``) y las que quedan fuera de su top-10. Es decir, toda
            # peli cuya tarjeta se ha pintado en esta pagina tiene clave.
            movie_rating_forms[movie_obj.id] = rating_form

    profile_form = ProfileForm()
    if request.user.is_authenticated:
        profile_form = ProfileForm(initial={
            'username': request.user.get_username(),
            'email': request.user.email,
        })

    if request.method == 'POST' and 'profile_submit' in request.POST:
        profile_form = ProfileForm(request.POST)
        if profile_form.is_valid() and request.user.is_authenticated:
            profile_result = update_profile(request.user, profile_form.cleaned_data)
            if profile_result.get('success'):
                messages.success(request, 'Perfil actualizado correctamente.')
                return redirect('movies:recommend', genre_name=genre_name)
            else:
                messages.error(request, profile_result.get('message', 'Error al actualizar el perfil.'))

    context = {
        'genre_name': genre_name,
        'recommendations': recommendations,
        'all_movies': all_movies_of_genre,
        'genres': Genre.objects.all(),
        'movie_rating_forms': movie_rating_forms,
        'profile_form': profile_form,
    }
    return render(request, 'movies/recommend.html', context)


@login_required
def favorite(request: HttpRequest, movie_id: int) -> HttpResponse:
    """Toggle favorite status for a movie."""

    try:
        movie = Movie.objects.get(id=movie_id)
    except Movie.DoesNotExist:
        messages.error(request, 'Pelicula no encontrada.')
        return redirect('movies:home')

    fav_check = is_favorite(request.user, movie)
    if fav_check.get('is_favorite', False):
        remove_favorite(request.user, movie)
        messages.success(request, f'{movie.title} eliminada de favoritas.')
    else:
        add_favorite(request.user, movie)
        messages.success(request, f'{movie.title} agregada a favoritas.')

    return redirect(request.META.get('HTTP_REFERER') or 'movies:home')


@login_required
def profile_view(request: HttpRequest) -> HttpResponse:
    """Vista de perfil: muestra y edita los datos del usuario."""

    profile_result = get_user_profile_data(request.user)
    rating_history_result = get_user_rating_history(request.user)

    profile_data_inner = profile_result.get('profile_data', {}) if profile_result.get('success') else {}
    rating_history = rating_history_result.get('history', []) if rating_history_result.get('success') else []

    profile_form = ProfileForm(initial=profile_data_inner)

    if request.method == 'POST' and 'profile_submit' in request.POST:
        profile_form = ProfileForm(request.POST)
        if profile_form.is_valid() and request.user.is_authenticated:
            profile_update_result = update_profile(request.user, profile_form.cleaned_data)
            if profile_update_result.get('success'):
                messages.success(request, 'Perfil actualizado correctamente.')
                profile_data_inner = get_user_profile_data(request.user).get('profile_data', {})
                profile_form = ProfileForm(initial=profile_data_inner)
                rating_history = get_user_rating_history(request.user).get('history', [])
            else:
                messages.error(request, profile_update_result.get('message', 'Error al actualizar el perfil.'))
                profile_form = ProfileForm(request.POST)

    context = {
        'profile_form': profile_form,
        'profile_data': profile_data_inner,
        'rating_history': rating_history,
        'genres': Genre.objects.all(),
    }
    return render(request, 'movies/profile.html', context)


def search_view(request: HttpRequest) -> HttpResponse:
    """Vista de busqueda: filtra y busca peliculas."""
    search_form = SearchForm(request.GET or None)
    movies_qs = Movie.objects.prefetch_related('genres')

    if search_form.is_valid():
        query = search_form.cleaned_data.get('q', '')
        if query:
            search_result = search_movies(query)
            if search_result.get('success'):
                movies_qs = search_result['movies']
            else:
                messages.error(request, search_result.get('message', 'Error en la busqueda.'))

    min_rating = request.GET.get('min_rating')
    year_min = request.GET.get('year_min')
    year_max = request.GET.get('year_max')
    genres = request.GET.getlist('genres')

    if min_rating:
        try:
            min_rating_val = float(min_rating)
        except ValueError:
            min_rating_val = None
    else:
        min_rating_val = None

    if year_min:
        try:
            year_min_val = int(year_min)
        except ValueError:
            year_min_val = None
    else:
        year_min_val = None

    if year_max:
        try:
            year_max_val = int(year_max)
        except ValueError:
            year_max_val = None
    else:
        year_max_val = None

    if genres or min_rating_val is not None or year_min_val is not None or year_max_val is not None:
        filter_result = filter_movies(
            genres=genres or None,
            year_min=year_min_val,
            year_max=year_max_val,
            min_rating=min_rating_val,
        )
        if filter_result.get('success'):
            filter_qs = filter_result['movies']
            # Combine: intersection with search results if any
            movies_qs_ids = set(movies_qs.values_list('pk', flat=True))
            filter_qs_ids = set(filter_qs.values_list('pk', flat=True))
            combined_ids = movies_qs_ids & filter_qs_ids
            if combined_ids:
                movies_qs = Movie.objects.filter(pk__in=combined_ids).prefetch_related('genres')
            else:
                movies_qs = Movie.objects.none()
        else:
            messages.error(request, filter_result.get('message', 'Error al filtrar peliculas.'))

    # None of the querysets above (``Movie.objects.prefetch_related('genres')``,
    # ``search_movies()``'s result, nor the intersection rebuilt just above)
    # carries an average: ``search_service.filter_movies`` annotates
    # ``rating_avg``, not ``movie_avg_rating``, and only on the queryset it
    # filters internally, never on the one it returns. search.html reads
    # ``movie_avg_rating``, so it has to be declared here or every card shows
    # "Sin valoraciones".
    movies_qs = movies_qs.annotate(
        movie_avg_rating=Avg('rating_set__score'),
        rating_count=Count('rating_set'),
    )

    for movie in movies_qs:
        if request.user.is_authenticated:
            movie.is_favorite = is_favorite(request.user, movie).get('is_favorite', False)
        else:
            movie.is_favorite = False

    context = {
        'search_form': search_form,
        'movies': movies_qs,
        'genres': Genre.objects.all(),
        'selected_genres': genres,
        'selected_min_rating': min_rating,
        'selected_year_min': year_min,
        'selected_year_max': year_max,
    }
    return render(request, 'movies/search.html', context)


@staff_member_required
def stats_view(request: HttpRequest) -> HttpResponse:
    """Vista de estadisticas: muestra reportes generales y por usuario."""
    rating_stats = get_rating_stats()
    revenue_estimate = get_revenue_estimate()

    user_stats = {}
    if request.user.is_authenticated:
        user_stats = get_user_stats(request.user)

    context = {
        'rating_stats': rating_stats,
        'revenue_estimate': revenue_estimate,
        'user_stats': user_stats,
        'genres': Genre.objects.all(),
    }
    return render(request, 'movies/stats.html', context)
