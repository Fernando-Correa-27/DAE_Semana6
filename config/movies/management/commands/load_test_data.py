"""Comando de gestion para cargar datos de prueba."""

from django.core.management.base import BaseCommand
from django.contrib.auth.models import User, Group, Permission
from movies.models import Movie, Genre, Person, Rating


class Command(BaseCommand):
    help = 'Carga datos de prueba para la aplicacion movies'

    def handle(self, *args, **options) -> None:
        self.stdout.write(self.style.WARNING('Cargando datos de prueba...'))

        # Generos
        genres_data = [
            'Action',
            'Drama',
            'Science Fiction',
            'Comedy',
        ]
        genres = {}
        for name in genres_data:
            genre, created = Genre.objects.get_or_create(name=name)
            genres[name] = genre
            if created:
                self.stdout.write(f'  [CREATED] Genero: {name}')

        # Personas
        persons_data = [
            ('Keanu Reeves', 'Actor'),
            ('Christopher Nolan', 'Director'),
            ('Margot Robbie', 'Actor'),
            ('Leonardo DiCaprio', 'Actor'),
            ('Sandra Bullock', 'Actor'),
            ('Tim Burton', 'Director'),
            ('Tom Hanks', 'Actor'),
            ('Meryl Streep', 'Actor'),
            ('Steven Spielberg', 'Director'),
            ('Scarlett Johansson', 'Actor'),
        ]
        persons = {}
        for name, role in persons_data:
            person, created = Person.objects.get_or_create(
                name=name,
                defaults={'role': role},
            )
            persons[name] = person
            if created:
                self.stdout.write(f'  [CREATED] Persona: {name} ({role})')

        # Peliculas
        movies_data = [
            {
                'title': 'The Dark Knight',
                'synopsis': 'Batman faces the Joker, a criminal mastermind who plunges Gotham into anarchy.',
                'release_year': 2008,
                'genres': ['Action', 'Drama'],
                'cast': ['Christian Bale', 'Heath Ledger'],
            },
            {
                'title': 'Inception',
                'synopsis': 'A thief who steals corporate secrets through dream-sharing technology is given the task of planting an idea.',
                'release_year': 2010,
                'genres': ['Science Fiction', 'Action'],
                'cast': ['Leonardo DiCaprio', 'Joseph Gordon-Levitt'],
            },
            {
                'title': 'The Matrix',
                'synopsis': 'A computer programmer discovers that reality as he knows it is a simulation.',
                'release_year': 1999,
                'genres': ['Science Fiction', 'Action'],
                'cast': ['Keanu Reeves', 'Laurence Fishburne'],
            },
            {
                'title': 'Interstellar',
                'synopsis': 'A team of explorers travel through a wormhole in space to ensure humanity survival.',
                'release_year': 2014,
                'genres': ['Science Fiction', 'Drama'],
                'cast': ['Matthew McConaughey', 'Anne Hathaway'],
            },
            {
                'title': 'Pulp Fiction',
                'synopsis': 'The lives of two mob hitmen, a boxer, and a pair of bandits intertwine in four tales of violence and redemption.',
                'release_year': 1994,
                'genres': ['Drama', 'Comedy'],
                'cast': ['John Travolta', 'Uma Thurman', 'Samuel L. Jackson'],
            },
            {
                'title': 'The Shawshank Redemption',
                'synopsis': 'Two imprisoned men bond over a number of years, finding solace and eventual redemption.',
                'release_year': 1994,
                'genres': ['Drama'],
                'cast': ['Tim Robbins', 'Morgan Freeman'],
            },
            {
                'title': 'Forrest Gump',
                'synopsis': 'The presidencies of Kennedy and Johnson unfold through the perspective of an Alabama man.',
                'release_year': 1994,
                'genres': ['Drama', 'Comedy'],
                'cast': ['Tom Hanks', 'Robin Wright'],
            },
            {
                'title': 'The Grand Budapest Hotel',
                'synopsis': 'A writer encounters the owner of an aging high-class hotel.',
                'release_year': 2014,
                'genres': ['Comedy', 'Drama'],
                'cast': ['Ralph Fiennes', 'Tony Revolori'],
            },
            {
                'title': 'Blade Runner 2049',
                'synopsis': 'A young blade runner discovers a long-buried secret that leads him to find former blade runner Rick Deckard.',
                'release_year': 2017,
                'genres': ['Science Fiction', 'Drama'],
                'cast': ['Ryan Gosling', 'Harrison Ford'],
            },
            {
                'title': 'The Avengers',
                'synopsis': 'Earth mightiest heroes must come together to stop Loki and his alien army.',
                'release_year': 2012,
                'genres': ['Action', 'Science Fiction'],
                'cast': ['Robert Downey Jr.', 'Chris Evans'],
            },
        ]
        movies = {}
        for data in movies_data:
            movie, created = Movie.objects.get_or_create(
                title=data['title'],
                defaults={
                    'synopsis': data['synopsis'],
                    'release_year': data['release_year'],
                },
            )
            if created:
                self.stdout.write(f'  [CREATED] Pelicula: {movie.title} ({movie.release_year})')

            # Asignar generos
            for genre_name in data['genres']:
                movie.genres.add(genres[genre_name])

            # Asignar actores de la lista de personas conocidas
            for cast_name in data['cast'][:3]:
                if cast_name in persons:
                    movie.cast.add(persons[cast_name])

            movies[data['title']] = movie

        # Valoraciones para al menos 5 peliculas
        ratings_data = [
            ('The Dark Knight', [
                (9, 'Reviewer1'),
                (10, 'Reviewer2'),
                (8, 'Reviewer3'),
            ]),
            ('Inception', [
                (10, 'Reviewer1'),
                (9, 'Reviewer2'),
            ]),
            ('The Matrix', [
                (9, 'Reviewer1'),
                (8, 'Reviewer2'),
                (10, 'Reviewer3'),
            ]),
            ('Interstellar', [
                (10, 'Reviewer1'),
                (9, 'Reviewer2'),
                (8, 'Reviewer3'),
            ]),
            ('Pulp Fiction', [
                (9, 'Reviewer1'),
                (8, 'Reviewer2'),
            ]),
            ('The Shawshank Redemption', [
                (10, 'Reviewer1'),
                (10, 'Reviewer2'),
                (9, 'Reviewer3'),
            ]),
            ('Forrest Gump', [
                (9, 'Reviewer1'),
                (8, 'Reviewer2'),
            ]),
            ('The Grand Budapest Hotel', [
                (8, 'Reviewer1'),
                (9, 'Reviewer2'),
            ]),
        ]

        for title, ratings in ratings_data:
            if title in movies:
                for score, reviewer in ratings:
                    rating, created = Rating.objects.get_or_create(
                        movie=movies[title],
                        reviewer_name=reviewer,
                        defaults={'score': score},
                    )
                    if created:
                        self.stdout.write(
                            f'  [CREATED] Valoracion: {title} - {score}/10 por {reviewer}'
                        )

        # Grupo editores
        self.stdout.write('')
        self.stdout.write('Configurando grupo "editores"...')
        group, created = Group.objects.get_or_create(name='editores')
        if created:
            self.stdout.write('  [CREATED] Grupo: editores')

        add_movie_perm = Permission.objects.get(codename='add_movie')
        change_movie_perm = Permission.objects.get(codename='change_movie')
        group.permissions.set([add_movie_perm, change_movie_perm])
        self.stdout.write('  [SET] Permisos: add_movie, change_movie')

        # Usuario de prueba
        self.stdout.write('')
        self.stdout.write('Creando usuario de prueba...')
        user, created = User.objects.get_or_create(
            username='editor_test',
            defaults={
                'email': 'editor@example.com',
                'is_staff': True,
            },
        )
        if created:
            user.set_password('editor123')
            user.save()
            self.stdout.write('  [CREATED] Usuario: editor_test / editor123')
        else:
            self.stdout.write('  [EXISTS] Usuario: editor_test')

        user.groups.set([group])
        self.stdout.write('  [ADDED] Grupo: editores')

        self.stdout.write(self.style.SUCCESS('\nDatos de prueba cargados correctamente.'))
