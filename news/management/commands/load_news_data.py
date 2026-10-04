from io import BytesIO

from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand
from PIL import Image, ImageDraw, ImageFont

from news.models import Article, Author, Category


SAMPLES = [
    {
        'slug': 'laboratorio-abierto-innovacion',
        'title': 'El laboratorio abre sus puertas a nuevas ideas',
        'summary': 'Estudiantes y docentes comparten proyectos que conectan aprendizaje, tecnología y comunidad.',
        'author': 'Laura Méndez', 'categories': ['Comunidad', 'Tecnología'],
        'body': 'La jornada reunió a estudiantes y docentes para presentar prototipos desarrollados durante el semestre.\n\nCada equipo explicó el problema que buscaba resolver y recibió comentarios de sus compañeros. La actividad continuará con nuevas sesiones abiertas a toda la comunidad.',
    },
    {
        'slug': 'aprendizaje-colaborativo-en-aula',
        'title': 'Aprender en equipo cambia la conversación en el aula',
        'summary': 'Una experiencia de trabajo colaborativo demuestra el valor de escuchar, debatir y construir en grupo.',
        'author': 'Andrés Rojas', 'categories': ['Educación'],
        'body': 'Los grupos organizaron sus ideas, repartieron tareas y compararon distintas formas de resolver un mismo reto.\n\nEl ejercicio destacó que explicar un concepto a otra persona también ayuda a comprenderlo mejor.',
    },
    {
        'slug': 'herramientas-digitales-con-proposito',
        'title': 'Herramientas digitales al servicio de proyectos locales',
        'summary': 'El curso presentó soluciones pequeñas y útiles para mejorar la difusión de iniciativas del barrio.',
        'author': 'Camila Torres', 'categories': ['Tecnología', 'Comunidad'],
        'body': 'Los equipos diseñaron prototipos web y discutieron cómo hacerlos accesibles desde distintos dispositivos.\n\nLa selección de herramientas partió de las necesidades de las personas y no de la tecnología disponible.',
    },
    {
        'slug': 'semillero-presenta-resultados',
        'title': 'El semillero comparte sus primeros resultados',
        'summary': 'La muestra recoge avances de investigación y abre espacio para nuevas preguntas.',
        'author': 'Laura Méndez', 'categories': ['Educación'],
        'body': 'Durante la presentación, el semillero describió su proceso de búsqueda, análisis y validación.\n\nLos asistentes dejaron preguntas que orientarán la siguiente fase del trabajo.',
    },
    {
        'slug': 'seguridad-digital-cotidiana',
        'title': 'Cinco hábitos para cuidar la información personal',
        'summary': 'Una guía práctica resume medidas sencillas para navegar y compartir información con mayor cuidado.',
        'author': 'Andrés Rojas', 'categories': ['Tecnología'],
        'body': 'Usar contraseñas distintas, activar la verificación en dos pasos y revisar los permisos de las aplicaciones son hábitos fáciles de incorporar.\n\nLa seguridad mejora cuando las decisiones se convierten en parte de la rutina.',
    },
    {
        'slug': 'prueba-escapado-html',
        'title': 'Prueba del escapado automático de HTML',
        'summary': 'Esta noticia permite comprobar cómo Django muestra texto HTML introducido en el cuerpo.',
        'author': 'Camila Torres', 'categories': ['Educación', 'Tecnología'],
        'body': 'Prueba de seguridad: <strong>este texto se guarda como contenido y se muestra escapado</strong>.\n\nDjango autoescapa las variables de plantilla, por lo que las etiquetas aparecen como texto y no se ejecutan como marcado HTML.',
    },
]


class Command(BaseCommand):
    help = 'Crea tres categorías, tres autores y seis noticias de demostración.'

    def handle(self, *args, **options):
        categories = {
            slug: Category.objects.update_or_create(
                slug=slug,
                defaults={'name': name, 'description': description},
            )[0]
            for slug, name, description in [
                ('comunidad', 'Comunidad', 'Historias y actividades de nuestra comunidad.'),
                ('educacion', 'Educación', 'Ideas y experiencias de aprendizaje.'),
                ('tecnologia', 'Tecnología', 'Proyectos y herramientas digitales.'),
            ]
        }
        authors = {
            name: Author.objects.update_or_create(
                name=name,
                defaults={'email': email, 'biography': biography},
            )[0]
            for name, email, biography in [
                ('Laura Méndez', 'laura@example.com', 'Docente y editora de historias comunitarias.'),
                ('Andrés Rojas', 'andres@example.com', 'Interesado en educación y cultura digital.'),
                ('Camila Torres', 'camila@example.com', 'Estudiante y colaboradora del laboratorio.'),
            ]
        }
        for index, data in enumerate(SAMPLES, 1):
            article, _ = Article.objects.update_or_create(
                slug=data['slug'],
                defaults={
                    'title': data['title'], 'summary': data['summary'], 'body': data['body'],
                    'author': authors[data['author']], 'is_published': True,
                },
            )
            article.categories.set(categories[slugify_name(name)] for name in data['categories'])
            if not article.featured_image:
                image = self.make_cover(index)
                article.featured_image.save(f"{data['slug']}.jpg", image, save=True)
        self.stdout.write(self.style.SUCCESS(
            f'Datos listos: {Category.objects.count()} categorías, '
            f'{Author.objects.count()} autores y {Article.objects.count()} noticias.'
        ))

    @staticmethod
    def make_cover(index):
        colors = [('#17324d', '#efb45d'), ('#27485c', '#b6d7c3'), ('#4c3c61', '#e8bb78')]
        background, accent = colors[(index - 1) % len(colors)]
        image = Image.new('RGB', (900, 900), background)
        draw = ImageDraw.Draw(image)
        draw.rectangle((0, 0, 900, 24), fill=accent)
        draw.ellipse((430, -80, 1010, 500), fill=accent)
        draw.rectangle((78, 590, 822, 594), fill=accent)
        draw.text((78, 630), 'DAE  /  NEWS', fill='white', font=ImageFont.load_default(size=42))
        draw.text((78, 700), f'EDITION  {index:02d}', fill=accent, font=ImageFont.load_default(size=30))
        stream = BytesIO()
        image.save(stream, format='JPEG', quality=88)
        return ContentFile(stream.getvalue())


def slugify_name(name):
    return {'Comunidad': 'comunidad', 'Educación': 'educacion', 'Tecnología': 'tecnologia'}[name]
