# Laboratorio: Plantillas y Administrador de Django

## Diagnóstico de partida

El repositorio recibido era el portal de películas del laboratorio anterior (`movies`), en la rama `main`, con remoto `origin` apuntando a `DAE_Semana_5`. Ya incluía Django Admin personalizado, herencia de plantillas, includes, estáticos, Pillow y manejo de multimedia. La ruta `/` estaba ocupada por el catálogo de películas. Se conservó esa aplicación y se añadió `news` como módulo independiente, accesible desde `/noticias/`.

La configuración inicial ya tenía `templates/`, `STATIC_URL`, `MEDIA_ROOT` y el servicio de medios condicional a `DEBUG` en `config/urls.py`; se reutilizaron sin duplicarlos. La base de datos local ya tenía un superusuario. La copia histórica `config/movies/`, los archivos de Obsidian y los agentes de `.opencode/` se conservaron.

## Puesta en marcha

```powershell
# Desde la raíz del repositorio
python -m pip install -r requirements.txt
python manage.py migrate
python manage.py createsuperuser  # solo si aún no existe uno
python manage.py load_news_data
python manage.py runserver
```

- Portal de noticias: <http://127.0.0.1:8000/noticias/>
- Administración: <http://127.0.0.1:8000/admin/>
- Los datos de ejemplo crean tres categorías, tres autores y seis noticias, con portadas en `media/news/articles/`.
- El comando `load_news_data` puede repetirse sin duplicar las noticias de demostración.
- Pillow ya estaba declarado en `requirements.txt` e instalado en el entorno usado para verificar.

## Organización y funcionamiento

| Elemento | Responsabilidad |
|---|---|
| `news/models.py` | `Article`, `Category`, `Author`, sus campos y relaciones |
| `news/admin.py` | Búsqueda, filtros, columnas y edición de relaciones desde Admin |
| `news/views.py` | Selección de noticias publicadas y preparación de contexto |
| `news/urls.py` | Rutas nombradas `news:home`, `news:detail`, `news:category` |
| `news/templates/news/base.html` | Estructura compartida, navegación y bloques `title`, `content`, `sidebar` |
| `news/templates/news/includes/_article_card.html` | Fragmento compartido por la portada y el listado de categoría |
| `news/static/news/css/news.css` | Estilos del portal de noticias |
| `news/management/commands/load_news_data.py` | Contenido e imágenes reproducibles para el laboratorio |

Las plantillas de portada, detalle y categoría heredan con `{% extends %}`. Las tarjetas muestran variables del modelo, usan `{% for %}`, filtros `date` y `truncatewords`, y enlaces con `{% url %}`. Portada y categoría usan `{% empty %}`. El contenido se publica al cambiarlo en Admin, sin editar las plantillas.

Las imágenes se guardan bajo `MEDIA_ROOT` y se enlazan mediante `article.featured_image.url`. `config/urls.py` sirve multimedia solo con `DEBUG=True`. El CSS se referencia con `{% load static %}` y `{% static %}`.

## Casos de prueba y observaciones

1. Ejecutar `python manage.py load_news_data` y comprobar en `/admin/news/` que hay seis noticias, tres categorías y tres autores.
2. Abrir `/noticias/`: aparecen las seis tarjetas, con título, resumen recortado, fecha, autor, categorías e imagen.
3. Abrir una categoría desde la navegación; por ejemplo `/noticias/categoria/tecnologia/`. La misma tarjeta se incluye desde esa plantilla.
4. Abrir una noticia y comprobar imagen destacada, resumen, cuerpo, fecha, autor y categorías.
5. Para comprobar estados vacíos sin cambiar las plantillas, despublicar temporalmente todas las noticias en Admin. Portada mostrará el texto del bloque `{% empty %}`; una categoría sin noticias publicadas mostrará su propio estado vacío. Después se pueden volver a publicar.
6. Editar una noticia desde Admin y volver al portal: la modificación aparece desde el modelo, sin tocar HTML.
7. En la noticia **Prueba del escapado automático de HTML**, el cuerpo contiene literalmente `<strong>este texto se guarda como contenido y se muestra escapado</strong>`. La página muestra esos caracteres como texto ordinario; el navegador no convierte el fragmento en negrita. Django escapa automáticamente las variables de plantilla para reducir el riesgo de inyección de HTML. No se usa `safe` ni se desactiva el escape.

Pruebas automatizadas del nuevo módulo:

```powershell
python manage.py test news
```

Verificaciones realizadas en este entorno: `manage.py check`, migraciones aplicadas y sin cambios pendientes, las cuatro pruebas de `news` y las 445 pruebas de la suite completa pasaron, portada/detalle/categoría responden 200, CSS e imagen multimedia sirven correctamente, Admin está registrado para las tres entidades, existe un superusuario local y el texto HTML aparece escapado.

## Evidencias

- [Portada con seis noticias](evidencias/portada-noticias.png)
- [Detalle y prueba de escapado HTML](evidencias/detalle-escapado-html.png)
- [Listado de categoría](evidencias/categoria-tecnologia.png)

Las capturas se generaron desde la aplicación servida localmente. Las cuentas, base de datos y ficheros bajo `media/` son datos locales ignorados por Git; el comando de carga vuelve a crear el conjunto de demostración al preparar otro entorno.

## Estado de Git y entrega

Los cambios se registraron en commits descriptivos y pequeños. El remoto `origin` sigue siendo `DAE_Semana_5`; no se ha hecho push ni se ha redirigido a ese repositorio. El destino aún no tiene una URL configurada en este checkout; antes de publicar en `DAE_Semana6`, se debe enlazar el repositorio nuevo con una historia independiente. El árbol de código del laboratorio no reemplaza ni elimina el portal de películas.
