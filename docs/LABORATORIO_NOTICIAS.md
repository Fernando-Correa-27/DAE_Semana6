# DAE Laboratorio 6 — Portal de noticias

## Estado inicial y alcance

La carpeta de trabajo es la raíz independiente `DAE_Laboratorio_6`; no hay repositorio Git inicializado en esta ubicación. El proyecto contiene `manage.py`, `config/`, la aplicación `news/`, una base SQLite propia, migraciones, estilos, seis imágenes y documentación del laboratorio anterior. Se revisaron antes de modificar `settings.py`, las rutas, modelos, vistas, Admin, plantillas, dependencias, migración inicial y registros existentes. No se encontró `.opencode/` ni una bóveda/carpeta de agentes dentro del proyecto.

La configuración declara Django 5.2.x, SQLite, Admin, autenticación nativa, Pillow, estáticos y multimedia en desarrollo. El entorno disponible durante esta revisión ejecuta Python 3.14.4 y Django 6.1.1, por lo que las verificaciones se ejecutaron allí; no se instaló ni validó la versión declarada en un entorno virtual separado. La base activa es `db.sqlite3`; conserva seis noticias, tres categorías y tres autores. Las páginas públicas, fragmento de tarjeta y Admin básico ya existían, al igual que las mejoras descritas abajo. Esta revisión no modificó datos de la base ni generó migraciones nuevas.

## Implementación

### Autenticación y permisos

- Registro mediante `UserCreationForm`, inicio mediante `AuthenticationForm` y cierre de sesión mediante `LogoutView` con POST y CSRF.
- El registro crea usuario lector, `UserProfile` y `Author` asociado. No asigna permisos editoriales.
- `setup_editorial_roles` crea/actualiza los grupos `Usuarios registrados`, `Redactores` y `Editores` con permisos de Django. Asigna cuentas a los grupos desde Admin. Los grupos lectores no tienen permisos editoriales.
- Las vistas comprueban permisos y propiedad en servidor. Un redactor solo ve y gestiona noticias asociadas a su cuenta. El editor puede revisar y publicar. Los visitantes solo consultan registros publicados.
- La revisión/editorial no sustituye el permiso `change_article`: las vistas requieren ambos para cambiar contenido. Publicar requiere además `publish_article`. Categorías y etiquetas se pueden explorar públicamente mediante `/categoria/<slug>/` y `/etiqueta/<slug>/`.
- `/editorial/mis-noticias/`, crear, editar, confirmación/eliminación, envío a revisión, edición de perfil y CRUD público de noticias requieren sesión y permiso. El borrado solo se ejecuta con POST.

### Flujo editorial

`Article.status` admite `draft`, `pending` y `published`. Los redactores crean borradores y pueden enviarlos a revisión; editar un pendiente lo devuelve a borrador. Un usuario con `publish_article` publica únicamente pendientes. Inicio, categoría y acceso anónimo al detalle filtran por estado publicado. El autor y editor pueden consultar su contenido de trabajo según permisos.

La migración `0002` añadió `status`, convirtió `is_published=True` en `published` y los valores falsos en `draft`, y luego retiró el campo anterior. Los seis artículos existentes quedaron publicados. No se vació ni recreó la base. La propiedad de lectura `is_published` se conserva por compatibilidad de código, pero las escrituras deben usar `status`.

### Modelos y reglas de relaciones

| Relación | Acceso inverso | `on_delete` | Efecto probado |
|---|---|---|---|
| `Article.author → Author` (`ForeignKey`) | `author.articles` | `PROTECT` | No se elimina un autor que tiene noticias. |
| `Article.categories → Category` (`ManyToManyField`) | `category.articles` | Tabla de asociación implícita | Al eliminar una categoría se eliminan sus enlaces, no las noticias. |
| `Article.tags → Tag` (`ManyToManyField` con `through=ArticleTag`) | `tag.articles` | Ver modelo intermedio | La pareja noticia/etiqueta es única; se guarda fecha y posición. |
| `ArticleTag.article → Article` | `article.tag_links` | `CASCADE` | Eliminar una noticia elimina sus asociaciones de etiqueta. |
| `ArticleTag.tag → Tag` | `tag.article_links` | `PROTECT` | No se elimina una etiqueta vinculada; primero hay que desvincularla. |
| `Author.user → User` (`OneToOneField`) | `user.editorial_author` | `SET_NULL` | Eliminar la cuenta conserva las noticias y desasocia la identidad. |
| `UserProfile.user → User` (`OneToOneField`) | `user.profile` | `CASCADE` | El perfil personal se elimina con su cuenta. |

Los casos de `on_delete` se prueban con datos aislados en la base temporal de Django TestCase; no se borran datos locales para demostrarlos.

### Administración

`ArticleAdmin` presenta estado, fecha, autor y categorías; incluye filtros, búsqueda, jerarquía de fechas, orden, `select_related`, autocompletado de autor y un inline tabular para `ArticleTag`. Los redactores que ingresan a Admin deben ser `is_staff`, solo consultan su propio ámbito y no pueden modificar autor/estado arbitrariamente. `AuthorAdmin`, `CategoryAdmin`, `TagAdmin` y `UserProfileAdmin` tienen búsqueda/listados adecuados. Usuarios, grupos y permisos usan el Admin nativo.

### Plantillas y presentación

- `news/base.html` centraliza HTML, navegación, mensajes, cuenta, estáticos y sidebar; páginas derivadas usan `{% extends %}` y bloques.
- `news/includes/_article_card.html` se reutiliza en portada y categoría. `_pagination.html` centraliza paginación.
- Las vistas preparan las consultas; las plantillas presentan modelos con `{% for %}`, `{% empty %}`, `{% if %}`, `{% url %}`, `date`, `truncatewords` y `default` donde aplica.
- `news.css` define una interfaz editorial responsive y un sistema completo de tema claro y oscuro mediante variables semánticas. Lavanda y salvia aportan acentos; grafito, gris cálido y superficies separadas construyen el tema oscuro. El tema sigue la preferencia del sistema al inicio, cambia con el control SVG accesible y se recuerda en `localStorage` sin parpadeo al navegar.
- Formularios, navegación, mensajes, tarjetas, etiquetas, estados editoriales y paginación consumen los tokens de ambos temas. Los breakpoints móviles convierten las columnas en una sola, mantienen los controles táctiles y reordenan la barra lateral sin desbordar el documento. El estilo usa foco visible, contraste por estado y `prefers-reduced-motion`.
- El proyecto no trae Bootstrap ni una biblioteca de iconos. Se conserva el CSS grid/flex existente para evitar descargar un framework redundante; el único icono nuevo es SVG inline y no requiere dependencia.
- Imágenes usan `ImageField` y `article.featured_image.url`; CSS usa `{% load static %}` y `{% static %}`. El servidor de medios solo se configura con `DEBUG=True`.
- Las variables de plantilla mantienen autoescape. El cuerpo con `<strong>…</strong>` se presenta como texto escapado; no se aplica `safe` al contenido editorial.

## Datos y ejecución local

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python manage.py migrate
python manage.py setup_editorial_roles
python manage.py load_news_data
python manage.py createsuperuser
python manage.py runserver
```

Admin está en `/admin/`; portada en `/`. `load_news_data` es repetible e instala seis noticias, tres categorías, tres autores y portadas. Alternativamente, `python manage.py loaddata news_data` importa el fixture, que usa los estados nuevos. Crea una cuenta administrativa con `createsuperuser`; asigna grupos y, si se requiere acceso al Admin, marca `is_staff` solo desde esa cuenta. No guardes claves reales en el repositorio.

Variables existentes: `DJANGO_SECRET_KEY`, `DJANGO_DEBUG`, `DJANGO_ALLOWED_HOSTS`, `DJANGO_TIME_ZONE`; `DJANGO_DB_NAME` permite seleccionar otro archivo SQLite. En desarrollo, si no se define `DJANGO_SECRET_KEY`, se genera una clave temporal y `America/Bogota` es la zona horaria predeterminada. Con `DJANGO_DEBUG=False` la aplicación exige una clave secreta propia y marca las cookies de sesión y CSRF como seguras. En producción configura también hosts concretos, HTTPS y servicio de media/estáticos apropiado.

## Casos verificados

Comandos ejecutados en el proyecto:

```powershell
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py migrate
python manage.py setup_editorial_roles
python manage.py test
```

La suite ejecuta 13 pruebas y cubre registro válido/inválido, inicio/cierre, lector sin permisos, creación, edición y envío de borrador por redactor, bloqueo sobre noticia ajena y sobre borradores sin permiso de lectura, publicación por editor, orden de etiquetas, confirmación y borrado POST, detalle y filtros públicos, escapado, estados vacíos, paginación, CSS/JS/media, relaciones y reglas de borrado. `news/__init__.py` permite que el descubrimiento genérico encuentre la suite. El esquema aplicado conserva seis artículos publicados; el portal y Admin se verificaron con el cliente de pruebas.

## Limitaciones conocidas

- No se crea un superusuario automáticamente; se debe ejecutar `createsuperuser`.
- La versión instalada para esta sesión (Django 6.1.1) difiere del rango declarado (Django 5.2.x); `check`, migraciones en seco y pruebas pasaron con la versión instalada, pero hace falta repetir las mismas comprobaciones con las dependencias instaladas desde `requirements.txt`.
- El sitio se ha verificado mediante comprobaciones Django y pruebas automatizadas, no mediante una sesión visual en distintos dispositivos. Las tres capturas que ya estaban en `docs/evidencias/` pertenecen a la versión anterior y no deben considerarse evidencia visual de esta nueva interfaz.
- No se añadieron comentarios ni gestión pública de categorías/etiquetas. El alcance editorial de este proyecto administra esas entidades desde Django Admin, con permisos de editor.
- Esta carpeta no tiene `.git`; no se crearon commits ni se publicó el contenido. La entrega queda como árbol de archivos para revisión y configuración posterior del repositorio.
