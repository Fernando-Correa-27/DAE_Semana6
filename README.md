# Catálogo de Películas

Aplicación web académica construida con Django que combina la gestión de un
catálogo cinematográfico con un sistema de valoración, favoritos y perfiles de
usuario.

El proyecto aplica una arquitectura por capas, optimización de consultas sobre
el ORM, sistema de autenticación y autorización, y una interfaz responsive
construida sobre Bootstrap 5.

---

## Índice

- [Requisitos](#requisitos)
- [Instalación](#instalacion)
- [Acceso y credenciales](#acceso-y-credenciales)
- [Rutas de la aplicación](#rutas-de-la-aplicacion)
- [Arquitectura](#arquitectura)
- [Modelo de datos](#modelo-de-datos)
- [Frontend](#frontend)
- [Rendimiento](#rendimiento)
- [Pruebas](#pruebas)
- [Comandos de gestión](#comandos-de-gestion)
- [Configuración](#configuracion)
- [Notas de diseño](#notas-de-diseno)

---

## Requisitos

| Componente | Versión |
|---|---|
| Python | 3.10 o superior (probado en 3.14.4) |
| Django | 5.2 o superior (probado en 5.2.17) |
| Pillow | 10.0 o superior (probado en 12.3.0) |
| Base de datos | SQLite 3 (incluida en Python) |

Dependencias declaradas en `requirements.txt`:

```
Django>=5.2,<6.0
Pillow>=10.0
```

No se requiere servidor de base de datos externo. El proyecto no depende de
servicios de red en tiempo de ejecución: Bootstrap e iconos están vendorizados
en el repositorio.

---

## Instalación

### Windows (PowerShell)

```powershell
# Crear el entorno virtual
python -m venv venv

# Activar el entorno virtual
.\venv\Scripts\Activate.ps1

# Instalar dependencias
.\venv\Scripts\python.exe -m pip install -r requirements.txt

# Aplicar migraciones
.\venv\Scripts\python.exe manage.py migrate

# Cargar el catalogo de ejemplo (opcional pero recomendado)
.\venv\Scripts\python.exe manage.py load_test_data

# Crear un usuario administrador
.\venv\Scripts\python.exe manage.py createsuperuser

# Arrancar el servidor de desarrollo
.\venv\Scripts\python.exe manage.py runserver
```

### Linux y macOS

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py load_test_data
python manage.py createsuperuser
python manage.py runserver
```

### Instalación mínima sin datos de ejemplo

Si se prefiere un catálogo vacío, omitir el paso `load_test_data`. El comando
`createsuperuser` es obligatorio para poder acceder al panel de administración
y a la página de estadísticas, que exigen un usuario con permiso `staff`.

---

## Acceso y credenciales

| Ubicación | URL |
|---|---|
| Catálogo público | `http://127.0.0.1:8000/` |
| Panel de administración | `http://127.0.0.1:8000/admin/` |

### Credenciales de ejemplo

El comando `load_test_data` deja el proyecto listo para probar los distintos
niveles de acceso:

| Usuario | Contraseña | Permisos | Uso |
|---|---|---|---|
| `admin` | la que defina en `createsuperuser` | superusuario | Control total, incluido el borrado |
| `editor_test` | `editor123` | `is_staff`, miembro del grupo `editores` | Acceso al admin con permisos de creación y edición |
| `Reviewer1`, `Reviewer2`, `Reviewer3` | ninguna | solo `is_active` | Autores de las valoraciones de ejemplo |

Los tres usuarios `Reviewer` se crean sin contraseña utilizable, por lo que no
pueden iniciar sesión. Existen únicamente para atribuir las valoraciones del
catálogo de ejemplo.

El grupo `editores` tiene asignado `add_movie` y `change_movie`. No incluye
`delete_movie` ni `view_movie`, por lo que un editor puede crear y modificar
películas pero no eliminarlas. Como `is_staff` es verdadero, `editor_test` sí
puede abrir el panel de administración y la página de `/stats/`.

### Consideraciones de seguridad

Las credenciales anteriores son exclusivamente para desarrollo. Antes de
desplegar en un entorno real se debe:

- Eliminar la cuenta `editor_test` o cambiar su contraseña.
- Sustituir `SECRET_KEY` por un valor generado aleatoriamente.
- Establecer `DEBUG=False` y definir `ALLOWED_HOSTS` con los dominios reales.
- Desactivar el servicio de ficheros estáticos de `config/urls.py`, que solo
  se activa cuando `DEBUG` es verdadero.

---

## Rutas de la aplicación

### Catálogo y contenido

| Método | Ruta | Vista | Acceso | Descripción |
|---|---|---|---|---|
| GET, POST | `/` | `movies:home` | Público | Catálogo paginado, buscador y valoración |
| GET, POST | `/genre/<genre_name>/` | `movies:recommend` | Público | Películas de un género priorizadas por valoración media |
| GET | `/search/` | `movies:search` | Público | Búsqueda y filtros combinados |
| POST | `/favorite/<movie_id>/` | `movies:favorite` | Autenticado | Añade o quita una película de favoritos |

### Perfil de usuario

| Método | Ruta | Vista | Acceso | Descripción |
|---|---|---|---|---|
| GET, POST | `/profile/` | `movies:profile` | Autenticado | Edita el perfil y muestra el historial de valoraciones |

### Cuentas

| Método | Ruta | Vista | Acceso | Descripción |
|---|---|---|---|---|
| GET, POST | `/accounts/login/` | `accounts:login` | Público | Inicio de sesión |
| POST | `/accounts/logout/` | `accounts:logout` | Autenticado | Cierre de sesión |
| GET, POST | `/accounts/register/` | `accounts:register` | Público | Alta de cuenta |

### Administración y estadísticas

| Método | Ruta | Vista | Acceso | Descripción |
|---|---|---|---|---|
| GET | `/stats/` | `movies:stats` | Solo staff | Reportes de valoración, ingresos estimados y actividad |
| GET | `/admin/` | Admin de Django | Solo staff | Gestión de modelos |

### Páginas de error

| Código | Ruta | Descripción |
|---|---|---|
| 404 | Cualquier ruta inexistente | Plantilla personalizada en `templates/404.html` |
| 500 | Error no controlado | Plantilla personalizada en `templates/500.html` |

---

## Arquitectura

El proyecto sigue una separación de responsabilidades en capas. Ninguna capa
importa a una capa superior, lo que permite sustituir cualquiera de ellas sin
afectar al resto.

```
Peticion HTTP
     |
     v
[urls.py]  Enrutamiento
     |
     v
[views.py]  Coordinacion: valida la peticion, invoca un servicio,
     |       compone el contexto. No contiene logica de negocio.
     |
     +---> [forms.py]     Validacion de entrada y forms
     |
     v
[services/]  Logica de negocio. Retorna diccionarios con las claves
     |       'success' (bool) y 'message' (str). Nunca lanza excepciones
     |       al frontend.
     |
     +---> [selectors/]   Construccion de querysets reutilizables
     |       |
     |       v
     |   [models.py]  Definicion de entidades y reglas de dominio
     |
     v
[cache_registry.py]  Invalidacion de cache en escritura
     |
     v
[templates/]  Presentacion
```

### Capas y su responsabilidad

| Capa | Fichero | Responsabilidad | No debe contener |
|---|---|---|---|
| Modelos | `models.py` | Entidades, relaciones, constraints, índices | Consultas de negocio |
| Selectors | `selectors/movie_selector.py` | QuerySets parametrizables y anotaciones | Decisiones de negocio |
| Servicios | `services/*.py` | Reglas de negocio, orquestación, cache | HTML, HTTP, redirecciones |
| Vistas | `views.py` | Coordinación HTTP, mensajes, redirecciones | Consultas SQL, reglas de negocio |
| Forms | `forms.py` | Validación de entrada | Acceso a base de datos |
| Admin | `admin.py` | Configuración del panel | Reglas de negocio |
| Templates | `templates/` | Presentación únicamente | Lógica de negocio |

### Módulos de la capa de servicios

| Módulo | Responsabilidad |
|---|---|
| `movies/services/rating_service.py` | Crear, consultar y eliminar valoraciones |
| `movies/services/favorite_service.py` | Marcar y desmarcar favoritos |
| `movies/services/search_service.py` | Búsqueda por texto y filtros combinados |
| `movies/services/profile_service.py` | Lectura y actualización del perfil del usuario |
| `movies/services/movie_service.py` | Consultas del catálogo con cache |
| `movies/services/report_service.py` | Estadísticas agregadas para `/stats/` y el perfil |
| `movies/services/cache_registry.py` | Registro de claves de cache para invalidación en escritura |

La capa de selectores expone dos funciones públicas: `get_movie_recommendations()`
para el orden por valoración media de un género y
`get_movies_by_genre_with_rating()` para el listado simple.

### Módulos auxiliares

| Ruta | Responsabilidad |
|---|---|
| `movies/accounts/` | Vistas, forms y plantillas de autenticación |
| `movies/decorators.py` | Decoradores propios, como `user_not_authenticated` |
| `movies/templatetags/dict_extras.py` | Filtro `get_item` para diccionarios en plantillas |
| `movies/utils/image.py` | Compresión y redimensionado de imágenes con Pillow |
| `movies/locale/` | Traducciones al español de mensajes de validación |
| `movies/management/commands/` | Comandos de gestión |

### Contrato de retorno de los servicios

Todos los servicios de dominio devuelven un diccionario con una forma estable.
Esto evita que las vistas tengan que conocer detalles de implementación y
permite que un fallo se muestre como mensaje de interfaz en lugar de como error
500.

```python
{
    'success': True,          # bool
    'message': 'OK',          # str, mensaje para el usuario
    'movies': <QuerySet>,     # clave variable segun el servicio
}
```

Los servicios capturan sus excepciones, registran el error con `logger.error` y
devuelven `success=False` con un mensaje en lugar de propagar la excepción. La
invalidación de cache se ejecuta en los mismos caminos de escritura y nunca
propaga excepciones.

Nota: en los servicios de escritura, el camino de error devuelve el texto de la
excepción al usuario con el prefijo `Error interno:`. Es práctico durante el
desarrollo, pero en un despliegue real conviene registrar la excepción completa
y sustituirla por un mensaje genérico, para no filtrar nombres de tabla,
consultas ni rutas del sistema de ficheros.

---

## Modelo de datos

```
Genre  <--M2M--  Movie  >--M2M--  Person
                   |
                   |1:N
                   v
                Rating --> auth.User

auth.User  <--1:N--  Favorite --> Movie
```

| Modelo | Campos principales | Relaciones |
|---|---|---|
| `Movie` | `title`, `synopsis`, `release_year`, `cover` | M2M a `Genre` y `Person`, 1:N desde `Rating` |
| `Genre` | `name` (único) | Inversa de `Movie.genres` |
| `Person` | `name`, `role` | Inversa de `Movie.cast` |
| `Rating` | `score`, `created_at` | FK a `Movie` y a `auth.User` |
| `Favorite` | `created_at`, `updated_at` | FK a `Movie` y a `auth.User` |

`Genre.name` es único, por lo que el catálogo no admite géneros duplicados.
`Person.name` no es único de forma intencionada: una misma persona puede
aparecer en varias películas y con distinto rol.

### Auditoría

`Movie` y `Favorite` heredan de la clase abstracta `AuditedModel`, que añade
`created_at` y `updated_at` de forma automática. `Rating` define `created_at`
propio por no necesitar fecha de modificación. `Genre` y `Person` son datos de
referencia sin auditoría.

### Restricciones a nivel de base de datos

Las reglas de integridad se delegan en la base de datos en lugar de depender
únicamente de la capa de aplicación.

| Modelo | Restricción | Nombre | Motivo |
|---|---|---|---|
| `Movie` | `release_year >= 1888` | `release_year_must_be_valid` | La primera película de la historia es de 1888 |
| `Rating` | `score` entre 1 y 10 | `score_between_1_and_10` | Escala de valoración |
| `Rating` | Único por `(movie, user)` | `unique_reviewer_per_movie` | Un usuario no puede valorar dos veces la misma película |
| `Favorite` | Único por `(user, movie)` | `unique_favorite_per_user_movie` | Un usuario no puede favoritar dos veces la misma película |

### Campo `cover`

`Movie.cover` no declara `blank=True`, por lo que el campo es obligatorio en los
formularios y en el panel de administración. A nivel de ORM, no obstante,
Django le asigna la cadena vacía como valor por defecto, de modo que una película
puede existir sin portada. Las plantillas contemplan ambos casos y muestran un
placeholder cuando la portada está vacía, que es la situación de las películas
del comando `load_test_data`.

### Índices

| Índice | Modelo | Campos | Origen |
|---|---|---|---|
| `movies_movi_release_272a12_idx` | `Movie` | `-release_year`, `title` | Declarado en `Meta.indexes` |
| `movies_movie_title_idx` | `Movie` | `title` | Declarado en `Meta.indexes` |
| `movies_rating_movie_idx` | `Rating` | `movie` | Declarado en `Meta.indexes` |
| `movies_rating_movie_id_697b1621` | `Rating` | `movie` | Implícito de la FK `movie` |
| `movies_rating_user_id_30a94f7b` | `Rating` | `user` | Implícito de la FK `user` |
| `movies_favorite_user_id_99780e1c` | `Favorite` | `user` | Implícito de la FK `user` |
| `movies_favorite_movie_id_a7df9107` | `Favorite` | `movie` | Implícito de la FK `movie` |
| `sqlite_autoindex_movies_rating_1` | `Rating` | `movie`, `user` | `UniqueConstraint` |
| `sqlite_autoindex_movies_favorite_1` | `Favorite` | `user`, `movie` | `UniqueConstraint` |

Django crea un índice automáticamente por cada clave foránea, y además uno por
cada `UniqueConstraint`. Los nombres con sufijo numérico son los que genera el
propio Django, y solo se mantienen estables mientras no se añada el nombre
explícito en `Meta.indexes`.

---

## Frontend

### Stack

| Tecnología | Versión | Ubicación |
|---|---|---|
| Bootstrap | 5.3.8 | `movies/static/movies/vendor/` |
| Bootstrap Icons | 1.13.1 | `movies/static/movies/vendor/` |
| CSS propio | - | `movies/static/movies/css/main.css` |
| JavaScript propio | - | `movies/static/movies/js/main.js` |

Las librerías están vendorizadas en el repositorio. No hay peticiones a CDNs
externos, por lo que la aplicación funciona sin conexión a internet.

### Sistema de diseño

La paleta se define mediante variables CSS en `movies/static/movies/css/main.css`.
La regla del sistema es que los tonos pastel se emplean en superficies y bordes,
mientras que el texto y los botones usan la variante oscura del mismo tono.
Ningún color pastel se utiliza como color de texto.

| Rol | Variable | Valor | Sobre | Contraste |
|---|---|---|---|---|
| Fondo de página | `--c-canvas` | `#F6F5FA` | - | - |
| Superficie de tarjeta | `--c-surface` | `#FFFFFF` | - | - |
| Texto principal | `--c-ink` | `#1E1B2E` | superficie | 16.78:1 |
| Texto secundario | `--c-ink-2` | `#4A4560` | superficie | 9.09:1 |
| Texto atenuado | `--c-ink-3` | `#6B6683` | superficie | 5.45:1 |
| Primario, texto y botón | `--c-primary-600` | `#4C4FC4` | superficie | 6.52:1 |
| Primario, hover | `--c-primary-700` | `#3B3E9E` | superficie | 8.87:1 |
| Fondo de la barra de navegación | `--c-primary-900` | `#23255C` | - | - |
| Texto de la barra de navegación | blanco | `#FFFFFF` | barra | 14.09:1 |
| Texto de valoración | `--c-star-600` | `#8A5A05` | superficie | 5.92:1 |
| Texto de favoritos | `--c-rose-700` | `#9C1C4A` | superficie | 7.84:1 |
| Texto de éxito | `--c-success-700` | `#1B6B3A` | superficie | 6.54:1 |
| Texto de aviso | `--c-warning-700` | `#8A5A05` | superficie | 5.92:1 |
| Texto de error | `--c-danger-700` | `#9E2A2B` | superficie | 7.45:1 |
| Texto de información | `--c-info-700` | `#0B5A7A` | superficie | 7.61:1 |

Todos los pares de color que portan texto cumplen el nivel AA de WCAG 2.1, con
un mínimo de 4.5:1 para texto normal. Los ratios están calculados con la
fórmula de luminancia relativa de WCAG, sobre el fondo que cada color usa en la
interfaz.

Dos variables están deliberadamente por debajo de ese umbral y solo se usan con
fines decorativos, nunca para mostrar texto:

| Variable | Valor | Contraste | Uso |
|---|---|---|---|
| `--c-primary-400` | `#8B93E8` | 2.82:1 | Bordes, halos y elementos sin texto |
| `--c-canvas` frente a `--c-border` | `#F6F5FA` / `#E4E1EF` | 1.14:1 | Separadores visibles solo por color |

Bootstrap 5.3 define sus colores mediante variables por componente, por lo que
sobrescribir `--bs-primary` en `:root` no sería efectivo. Los valores se
aplican directamente sobre `.btn-primary`, `.alert-*` y otros componentes
concretos.

### Diseño responsive

La interfaz se adapta a seis rangos de anchura mediante las utilidades de
Bootstrap.

| Anchura | Navegación | Columnas de películas | Contenedor del catálogo |
|---|---|---|---|
| 320 px | Menú desplegable | 1 | `container-xl` a ancho completo |
| 576 px | Menú desplegable | 2 | `container-xl` a ancho completo |
| 768 px | Menú desplegable | 3 | `container-xl` a ancho completo |
| 992 px | Barra completa | 3 | `container-xl` a ancho completo |
| 1200 px | Barra completa con desplegable de géneros | 4 | `container-xl` (1140 px útiles) |
| 1400 px | Barra completa con desplegable de géneros | 4 | `container-xl` (1320 px útiles) |

La barra de navegación usa `navbar-expand-lg`, de modo que colapsa en un menú
lateral por debajo de 992 px. La cabecera y el área de contenido usan
`container`, mientras que el catálogo y la búsqueda añaden un `container-xl`
para aprovechar mejor las pantallas anchas. Las tablas de perfil y estadísticas
se envuelven en un contenedor con desplazamiento horizontal para evitar
desbordamientos en pantallas estrechas.

### Accesibilidad

| Práctica | Implementación |
|---|---|
| Enlace de salto al contenido | `.skip-link`, oculto hasta recibir foco |
| Foco visible | `:focus-visible` con contorno de 2 px y desplazamiento de 2 px |
| Objetivos táctiles | Altura mínima de 44 px en botones, enlaces y campos de formulario |
| Navegación por teclado | Bootstrap JS gestiona `aria-expanded` en los desplegables de usuario y de géneros |
| Estados sin depender del color | Los mensajes combinan icono, texto y color; los campos con error incluyen `invalid-feedback` y `aria-describedby` |
| Animaciones | Se desactivan bajo `prefers-reduced-motion: reduce` |
| Errores de formulario | `is-invalid` más `invalid-feedback` con texto explícito, no solo el borde rojo |
| Idioma | `<html lang="es">` y `<meta name="color-scheme">` declarados |

### Iconos

Toda la interfaz utiliza iconos de Bootstrap Icons mediante clases `bi`. El
proyecto no emplea emojis en botones, menús, tarjetas, mensajes ni elementos
decorativos.

### Plantillas reutilizables

| Plantilla | Uso |
|---|---|
| `movies/templates/movies/includes/_movie_card.html` | Tarjeta de película, usada por el catálogo, el género, la búsqueda y el perfil |
| `movies/templates/movies/includes/_pagination.html` | Paginación con conservación de parámetros de consulta |
| `movies/templates/movies/includes/_profile_form.html` | Formulario de perfil, compartido por el perfil y la página de género |

Las plantillas de autenticación de `movies/templates/accounts/` no usan includes:
cada una envuelve su formulario en una tarjeta centrada propia.

La tarjeta de película estaba replicada en varias plantillas. Al extraerla a un
único include se eliminó el marcado repetido y se evita que el diseño diverja
entre vistas.

---

## Rendimiento

### Optimización de consultas

Las vistas y los selectores evitan el problema de consultas N+1 mediante
anotaciones y prefetch.

| Técnica | Aplicación |
|---|---|
| `annotate(Avg(...))` | Calcula la valoración media en la base de datos, sin una consulta por película |
| `annotate(Count(...))` | Calcula el número de valoraciones en la misma consulta |
| `prefetch_related('genres')` | Carga los géneros en una segunda consulta en lugar de una por película |
| `prefetch_related('genres', 'rating_set')` | En los selectores de género, carga también las valoraciones |
| `select_related('movie')` | Resuelve la clave foránea de la película en la misma consulta SQL |
| `list_select_related` | Aplicado en `RatingAdmin` para el panel de administración |
| `filter_horizontal` | Selector de relaciones M2M en el admin de películas |

La propiedad `Movie.average_rating` comprueba si la instancia ya tiene anotada
la media, con `movie_avg_rating` o con `rating_avg`, y en ese caso la devuelve
sin lanzar ninguna consulta. Solo consulta la base de datos cuando la instancia
llega sin anotación.

### Cache

La capa de servicios utiliza el backend `LocMemCache`, configurado con
`LOCATION = 'movies-cache'` y un `TIMEOUT` por defecto de 300 segundos. Las
operaciones que necesitan una vigencia mayor la amplían de forma explícita:

| Operación | Constante | TTL |
|---|---|---|
| Listado de la página de inicio | `CACHE_TTL_MEDIUM` | 600 s |
| Recomendaciones por género | `CACHE_TTL_SHORT` | 300 s |
| Películas de un género | `CACHE_TTL_SHORT` | 300 s |
| Resultados de búsqueda | `CACHE_TTL_SHORT` | 300 s |
| Resultados de filtros | `CACHE_TTL_SHORT` | 300 s |

`LocMemCache` vive en el proceso de Python, de modo que la cache se vacía cada
vez que se reinicia el servidor y no se comparte entre procesos. Es la opción
adecuada para un único proceso de desarrollo; con varios procesos o
contenedores habría que migrar a Redis o Memcached.

La cache almacena listas de identificadores, no instancias de modelos. De este
modo un acierto de cache no devuelve objetos obsoletos y el conjunto de datos
se reconstruye siempre con el estado actual de la base de datos.

### Invalidación de cache

Un acierto de cache no puede provocar que un dato nuevo quede invisible, por lo
que existe una invalidación explícita en todos los caminos de escritura.

| Disparador | Qué se invalida |
|---|---|
| `Movie.save()` | Inicio, género y búsqueda |
| `Movie.delete()` | Inicio, género y búsqueda |
| `Rating.objects.create` y `delete` | Inicio, género y búsqueda |
| `m2m_changed` en `Movie.genres` | Género y búsqueda |
| `post_delete` en `Movie` | Inicio, género y búsqueda |

Como las claves de cache incluyen parámetros variables, el módulo
`cache_registry.py` mantiene un registro de las claves generadas. La
invalidación se implementa con claves deterministas más el registro, dado que
Django no ofrece borrado por patrón en su backend de cache en memoria.

### Optimización de imágenes

`movies/utils/image.py` procesa toda portada antes de guardarla:

- Redimensiona a un máximo de 1200 x 1200 px conservando la proporción.
- Convierte a RGB cuando la imagen tiene canal alfa, ya que JPEG no admite
  transparencia.
- Recomprime a JPEG con calidad 85 y optimización de cabecera.
- Cierra los descriptores de fichero que Pillow abre, sin cerrar el
  descriptor que aporta el llamante.

Si la imagen no puede procesarse, por estar ausente, corrupta o en un formato no
soportado, se registra una advertencia y se conserva el valor original. La
función nunca interrumpe el guardado del modelo.

### Paginación

La página de inicio muestra 12 películas por página. Los enlaces de paginación
conservan los parámetros de búsqueda activos mediante `{% querystring %}`, de
modo que cambiar de página no pierde el filtro aplicado.

---

## Pruebas

### Ejecución

```powershell
.\venv\Scripts\python.exe manage.py test
```

Resultado actual: **445 pruebas, 0 fallos, 0 errores**.

### Distribución

| Módulo | Pruebas | Cobertura |
|---|---|---|
| `tests/test_services.py` | 60 | Servicios de valoración, favoritos, búsqueda, perfil y reportes |
| `tests/test_models.py` | 47 | Modelos, constraints, relaciones y selectores |
| `tests/test_views.py` | 41 | Vistas, paginación, errores 404 y 500 |
| `accounts/tests/test_auth.py` | 39 | Autenticación, autorización y rutas protegidas |
| `tests/test_smoke.py` | 39 | Recorrido completo de las rutas y renderizado de plantillas |
| `tests/test_registration.py` | 36 | Formulario de registro y validación de contraseña |
| `tests/test_forms.py` | 21 | Validación de todos los formularios |
| `tests/test_search_cache_invalidation.py` | 19 | Invalidación de cache de búsqueda y filtros |
| `tests/test_reports.py` | 17 | Estadísticas agregadas y estimación de ingresos |
| `tests/test_cache_invalidation.py` | 15 | Invalidación de cache en escritura |
| `tests/test_favorite.py` | 14 | Alta y baja de favoritos |
| `tests/test_search.py` | 14 | Búsqueda y filtros combinados |
| `tests/test_profile.py` | 13 | Perfil e historial del usuario |
| `tests/test_rating_errors.py` | 12 | Errores de validación de valoración en línea |
| `tests/test_i18n.py` | 11 | Traducción de mensajes al español |
| `config/movies/tests/` | 47 | Copia histórica de `test_models.py` |
| **Total** | **445** | |

### Comandos útiles

```powershell
# Un modulo concreto, con detalle
.\venv\Scripts\python.exe manage.py test movies.tests.test_smoke -v 2

# La aplicacion completa, sin la copia historica
.\venv\Scripts\python.exe manage.py test movies

# Orden aleatorio, para detectar acoplamiento entre pruebas
.\venv\Scripts\python.exe manage.py test --shuffle

# Verificacion de integridad del proyecto
.\venv\Scripts\python.exe manage.py check
.\venv\Scripts\python.exe manage.py makemigrations --check --dry-run
```

### Nota sobre `config/movies/`

El directorio `config/movies/tests/` contiene una copia obsoleta de
`test_models.py` que data de antes de la migración de la lógica de consulta a la
capa de selectores. Django lo descubre y ejecuta, y sus 47 pruebas pasan, pero
duplican la cobertura de `movies/tests/test_models.py`. Puede eliminarse el
directorio sin impacto funcional.

---

## Comandos de gestión

### load_test_data

Carga un catálogo de ejemplo y configura los permisos del proyecto.

```powershell
.\venv\Scripts\python.exe manage.py load_test_data
```

Contenido que genera:

- 4 géneros: Action, Drama, Science Fiction, Comedy
- 10 personas de reparto y dirección
- 10 películas con sinopsis, géneros y reparto
- 3 usuarios de prueba: `Reviewer1`, `Reviewer2` y `Reviewer3`
- 20 valoraciones distribuidas entre 8 películas
- Grupo `editores` con los permisos `add_movie` y `change_movie`
- Usuario `editor_test` con contraseña `editor123`, miembro del grupo `editores`

Las películas se crean sin portada, ya que el comando no genera imágenes. El
campo es obligatorio en los formularios, pero la plantilla muestra un
placeholder cuando está vacío.

El comando es idempotente: puede ejecutarse varias veces sin duplicar registros.

### createsuperuser

```powershell
.\venv\Scripts\python.exe manage.py createsuperuser
```

---

## Configuración

### Variables de entorno

| Variable | Valor por defecto | Propósito |
|---|---|---|
| `DJANGO_DEBUG` | `True` | Debe ser `False` en producción |
| `DJANGO_ALLOWED_HOSTS` | `localhost,127.0.0.1` | Lista de dominios separados por comas |
| `DJANGO_SECRET_KEY` | valor de desarrollo | Clave de firma; cambiar en producción |

### Ajustes relevantes

| Ajuste | Valor | Propósito |
|---|---|---|
| `LANGUAGE_CODE` | `es` | Idioma de la interfaz y los mensajes de validación |
| `USE_I18N` | `True` | Activa el sistema de traducción |
| `CACHES` | `LocMemCache` | Cache en memoria, con vaciado al reiniciar el proceso |
| `MEDIA_URL` | `/media/` | Prefijo de las portadas de película |
| `MEDIA_ROOT` | `BASE_DIR / 'media'` | Directorio de almacenamiento de portadas |
| `LOGIN_URL` | `accounts:login` | Destino de las vistas protegidas |
| `LOGIN_REDIRECT_URL` | `movies:home` | Destino tras iniciar sesión |
| `LOGOUT_REDIRECT_URL` | `movies:home` | Destino tras cerrar sesión |

### Registro

Los mensajes de validación de Django se traduzen al español mediante un
catálogo propio en `movies/locale/es/LC_MESSAGES/`. El archivo `django.mo` está
versionado para no depender de las herramientas GNU gettext en el momento de la
instalación.

El proyecto define dos registradores. El logger `movies` trabaja a nivel `INFO`
y escribe en consola y en el fichero `movies.log`, recogiendo los eventos de la
capa de servicios: valoraciones creadas, favoritos modificados, perfiles
actualizados y resultados de cache. El logger `django` se limita a `WARNING` y
solo escribe en consola, para no duplicar en el fichero los avisos internos del
framework.

---

## Notas de diseño

### Capas

No se introdujeron capas artificiales. Los servicios y los selectores existen
porque concentran responsabilidades concretas y verificables, no por simetría
arquitectónica. Los servicios de lectura complexa y los de escritura se
separaron porque los primeros se benefician de cache y los segundos deben
garantizar la invalidación.

### Consultas

La lógica de consulta reside en `selectors/movie_selector.py` y en la capa de
servicios. Las vistas no construyen querysets complejos, lo que permite que las
mismas consultas se reutilicen desde la página de inicio, la de género y la de
búsqueda sin duplicar código.

### Integridad

Las reglas de integridad se aplican con `CheckConstraint` y `UniqueConstraint`
en lugar de validar únicamente en Python. Una restricción que solo existe en la
capa de aplicación puede eludirse con el shell de Django o con una importación
de datos.

### Estado del form

El contexto de las plantillas entrega un diccionario `movie_rating_forms`
indexado por identificador de película. Cuando una valoración se rechaza, el
formulario con los errores se reindexa con el identificador entero
correspondiente para que la tarjeta correcta lo muestre en línea. Si se usara
la clave en forma de cadena, el índice no coincidiría con el que recorren las
plantillas y los errores de validación no se mostrarían nunca.

Los formularios de búsqueda y de filtros usan `method="get"`, por lo que
pertenecen al flujo de navegación y no requieren token CSRF. Los formularios
que modifican datos, como la valoración, el favorito y el perfil, usan `POST`
con CSRF obligatorio.

### Plantillas

La tarjeta de película se delega en un único include parametrizado. El
parámetro `form_action` permite que cada vista indique su propia ruta de
destino del formulario de valoración, de modo que una valoración realizada
desde la página de un género devuelve al usuario a esa misma página.

### Interfaz

La paleta pastel se aplica únicamente a superficies y bordes. El texto usa la
variante oscura de cada tono para mantener el contraste por encima del nivel AA
de WCAG 2.1. Los estados de la interfaz se comunican con icono y texto
acompañados de color, nunca mediante color en exclusiva.

### Enfoque de las pruebas

Las pruebas de humo recorren todas las rutas con usuarios anónimos,
autenticados y con permisos de staff, y verifican el HTML renderizado.

Las pruebas de invalidación de cache calientan la cache, provocan una
escritura y comprueban que la siguiente lectura ya refleja el cambio. Ese
recorrido detectaría una invalidación ausente, porque la lectura cacheada
seguiría devolviendo el estado anterior.
