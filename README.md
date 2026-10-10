# DAE Noticias

Portal de noticias desarrollado con Django. Permite consultar noticias publicadas por categoría y etiqueta, registrar cuentas lectoras y gestionar contenido mediante un flujo editorial con borradores, revisión y publicación.

## Índice

- [Funcionalidades](#funcionalidades)
- [Tecnologías y requisitos](#tecnologías-y-requisitos)
- [Instalación y configuración](#instalación-y-configuración)
- [Variables de entorno](#variables-de-entorno)
- [Ejecución](#ejecución)
- [Administración y permisos](#administración-y-permisos)
- [Arquitectura](#arquitectura)
- [Modelos y relaciones](#modelos-y-relaciones)
- [Rutas principales](#rutas-principales)
- [Pruebas](#pruebas)
- [Solución de problemas](#solución-de-problemas)
- [Estado y documentación adicional](#estado-y-documentación-adicional)

## Funcionalidades

- Portada con noticias publicadas y paginación de nueve elementos por página.
- Consulta de detalles, categorías y etiquetas. Los listados públicos solo incluyen noticias publicadas.
- Registro, inicio y cierre de sesión con formularios y autenticación nativos de Django. El registro crea una cuenta lectora y no otorga permisos editoriales.
- Perfil personal editable para el usuario autenticado.
- Gestión editorial con borradores, envío a revisión y publicación, sujeta a permisos y propiedad comprobados en el servidor.
- Creación, edición y eliminación de noticias. El borrado se confirma en una página y solo se ejecuta mediante POST.
- Carga de imagen destacada validada mediante `ImageField` y Pillow.
- Selector de tema claro/oscuro que sigue la preferencia del sistema inicialmente y recuerda la elección local.
- Panel Django Admin personalizado para noticias, autores, categorías, etiquetas y perfiles; usuarios y grupos se administran con el Admin nativo.

## Tecnologías y requisitos

| Componente | Configuración del proyecto |
| --- | --- |
| Python | El entorno usado para esta documentación ejecuta Python 3.14.4. Use una versión compatible con Django 5.2. |
| Django | `Django>=5.2,<6.0` en `requirements.txt`; instalado en el entorno inspeccionado: 5.2.18. |
| Base de datos | SQLite, archivo predeterminado `db.sqlite3` en la raíz. |
| Imágenes | Pillow (`Pillow>=10.0`); versión instalada en el entorno inspeccionado: 12.3.0. |
| Interfaz | Plantillas de Django, CSS, JavaScript y SVG. No se declara Bootstrap ni una biblioteca de iconos como dependencia. |

Se necesita Python, `pip` y PowerShell para seguir los comandos de instalación de esta guía. La aplicación no declara otras dependencias en `requirements.txt`.

## Instalación y configuración

Ejecute los comandos desde la raíz del proyecto, donde está `manage.py`:

```powershell
cd DAE_Semana_6
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

Si PowerShell bloquea la activación del entorno virtual, puede invocar directamente `\.venv\Scripts\python.exe` en lugar de cambiar la política de ejecución del sistema.

Prepare el esquema y los grupos editoriales:

```powershell
python manage.py migrate
python manage.py setup_editorial_roles
```

Para cargar el conjunto de noticias de ejemplo, ejecute:

```powershell
python manage.py load_news_data
```

Este comando crea o actualiza las seis noticias incluidas en el código, sus tres categorías, sus tres autores y las imágenes de portada que falten. Es opcional; no es necesario para iniciar el sitio vacío. También existe el fixture `news/fixtures/news_data.json`, que se puede cargar en una base preparada con:

```powershell
python manage.py loaddata news_data
```

El fixture y el comando son alternativas de inicialización; no cargue el fixture sobre una base con claves primarias coincidentes sin revisar primero sus datos.

## Variables de entorno

La configuración las lee directamente desde el entorno del proceso; no hay un cargador de archivos `.env` configurado.

| Variable | Uso y valor predeterminado | Requisito |
| --- | --- | --- |
| `DJANGO_DEBUG` | Activa depuración solo cuando su valor, sin distinguir mayúsculas, es `true`. Predeterminado: `True`. | Opcional; en producción debe ser `False`. |
| `DJANGO_SECRET_KEY` | Clave secreta de Django. En desarrollo, si falta, se genera una clave temporal al iniciar el proceso. | Necesaria cuando `DJANGO_DEBUG=False`. No reutilice ni publique una clave real. |
| `DJANGO_ALLOWED_HOSTS` | Lista de hosts separados por comas. Predeterminado: `localhost,127.0.0.1`. | Opcional para desarrollo; en producción configure los hosts concretos. |
| `DJANGO_DB_NAME` | Nombre o ruta del archivo SQLite. Predeterminado: `db.sqlite3` en la raíz del proyecto. | Opcional. |
| `DJANGO_TIME_ZONE` | Zona horaria. Predeterminado: `America/Bogota`. | Opcional. |

Ejemplo de configuración temporal para la sesión actual de PowerShell:

```powershell
$env:DJANGO_DEBUG = "True"
$env:DJANGO_TIME_ZONE = "America/Bogota"
```

No es necesario definir `DJANGO_SECRET_KEY` para el uso local predeterminado. Para cualquier despliegue, use una clave protegida fuera del código, desactive `DEBUG`, configure hosts, HTTPS y un servicio apropiado para archivos estáticos y multimedia. La configuración actual marca las cookies de sesión y CSRF como seguras cuando `DEBUG=False`, pero no sustituye una configuración completa de producción. La ruta de archivos multimedia servida por Django solo se agrega con depuración activa.

El historial remoto anterior contiene una clave de desarrollo Django con prefijo `django-insecure` en una versión antigua de la configuración. La versión actual ya no la usa y no se reescribirá el historial del repositorio. No reutilice esa clave; si se utilizó en algún entorno distinto del desarrollo local, reemplácela allí.

## Ejecución

Inicie el servidor local de desarrollo:

```powershell
python manage.py runserver
```

- Portal: <http://127.0.0.1:8000/>
- Administración: <http://127.0.0.1:8000/admin/>

El servidor `runserver` es exclusivamente para desarrollo, no para producción.

## Administración y permisos

Después de aplicar migraciones, prepare los grupos editoriales y cree manualmente la primera cuenta administrativa:

```powershell
python manage.py setup_editorial_roles
python manage.py createsuperuser
```

El comando `createsuperuser` solicita usuario y contraseña; no se crea una cuenta ni una credencial por defecto. Acceda luego a `/admin/`.

`setup_editorial_roles` crea o actualiza estos grupos de Django:

| Grupo | Capacidades configuradas |
| --- | --- |
| `Usuarios registrados` | Sin permisos editoriales; identifica las cuentas creadas por el registro público. |
| `Redactores` | Permisos de creación, cambio y eliminación de noticias, consulta editorial y consulta de contenido no publicado. Las vistas limitan sus acciones a noticias propias. |
| `Editores` | Permisos editoriales de revisión y publicación, además de gestión de categorías y etiquetas. |

La asignación de una cuenta a un grupo se realiza desde una cuenta administrativa. Para que un redactor ingrese al Admin también necesita `is_staff`, que no se concede en el registro público. Los permisos se comprueban en el servidor; el grupo por sí solo no omite las reglas de propiedad de las vistas.

El Admin personalizado registra `Article`, `Author`, `Category`, `Tag` y `UserProfile`. Las noticias ofrecen columnas, filtros, búsqueda, navegación por fecha, selección/autocompletado de relaciones y edición tabular de las asociaciones de etiquetas. Los modelos `User` y `Group` usan el Admin nativo de Django.

## Arquitectura

```text
.
├── manage.py
├── requirements.txt
├── config/
│   ├── settings.py       # Configuración Django, base de datos y archivos
│   ├── urls.py           # Admin y rutas de news
│   ├── asgi.py
│   └── wsgi.py
├── news/
│   ├── models.py         # Noticias y entidades editoriales
│   ├── views.py          # Consultas públicas, autenticación y operaciones editoriales
│   ├── forms.py          # Formularios de registro, noticias y perfil
│   ├── urls.py           # Rutas con namespace news
│   ├── admin.py          # ModelAdmin e inline de etiquetas
│   ├── tests.py          # Suite automatizada
│   ├── migrations/       # Historial del esquema
│   ├── fixtures/         # Datos de ejemplo serializados
│   ├── management/commands/
│   │   ├── setup_editorial_roles.py
│   │   └── load_news_data.py
│   ├── templates/
│   │   ├── news/         # Páginas y fragmentos reutilizables
│   │   └── registration/ # Inicio de sesión y registro
│   └── static/news/      # CSS, JavaScript y SVG
├── media/                # Imágenes cargadas o de muestra
├── docs/                 # Documentación y evidencias del laboratorio
└── design-system/        # Tokens y guía visual del portal
```

La configuración principal vive en `config`. La aplicación `news` mantiene en un solo módulo sus modelos, formularios, vistas y rutas. Las plantillas heredan de `news/base.html` y reutilizan tarjetas y paginación mediante `{% include %}`. Los estilos y el control de tema están en `news/static/news/`.

## Modelos y relaciones

- **`Article`** contiene título, slug, resumen, cuerpo, imagen destacada, fecha de publicación y estado (`draft`, `pending` o `published`). Se relaciona con un autor, varias categorías y varias etiquetas.
- **`Author`** almacena nombre, correo y biografía. Su enlace opcional uno a uno con el usuario permite mantener autores editoriales sin cuenta; desde el usuario asociado se consulta como `user.editorial_author`.
- **`Category`** y **`Tag`** clasifican noticias y exponen la relación inversa `articles`.
- **`ArticleTag`** es el modelo intermedio de `Article.tags`. Guarda fecha de asociación y posición, evita parejas duplicadas con una restricción única y expone `article.tag_links` / `tag.article_links`.
- **`UserProfile`** se vincula uno a uno con el usuario mediante `user.profile` e incluye nombre público y biografía.
- Para cuentas, grupos y permisos, el proyecto usa `django.contrib.auth.models.User`, `Group` y `Permission`; no define un modelo de usuario personalizado.

Políticas de eliminación (`on_delete`): eliminar una noticia elimina sus enlaces de etiquetas (`CASCADE`); una categoría se puede eliminar y se quitan sus asociaciones muchos a muchos; no se puede eliminar un autor que tenga noticias (`PROTECT`); al borrar un usuario, su perfil se elimina (`CASCADE`) y el autor asociado conserva sus publicaciones con el vínculo a la cuenta en `NULL` (`SET_NULL`); no se puede borrar una etiqueta mientras existan asociaciones (`PROTECT`). La suite comprueba estas reglas con datos de prueba aislados.

## Rutas principales

| Ruta | Función |
| --- | --- |
| `/` | Portada de noticias publicadas. |
| `/cuenta/registro/` | Registro de lector. |
| `/cuenta/ingresar/` | Inicio de sesión. |
| `/cuenta/salir/` | Cierre de sesión mediante POST. |
| `/cuenta/perfil/` | Edición del perfil propio. |
| `/editorial/mis-noticias/` | Listado editorial según permisos. |
| `/editorial/nueva/` | Creación de borrador. |
| `/editorial/<slug>/editar/` | Edición autorizada. |
| `/editorial/<slug>/eliminar/` | Confirmación GET y eliminación POST. |
| `/editorial/<slug>/estado/` | Transición editorial mediante POST. |
| `/categoria/<slug>/` | Noticias publicadas de una categoría. |
| `/etiqueta/<slug>/` | Noticias publicadas de una etiqueta. |
| `/<slug>/` | Detalle de noticia visible para el usuario. |
| `/admin/` | Django Admin. |

Los segmentos `<slug>` representan valores dinámicos. Los borradores no se incluyen en listados públicos y el detalle devuelve no encontrado cuando el visitante no está autorizado a ver el contenido.

## Pruebas

Ejecute las comprobaciones desde la raíz del proyecto:

```powershell
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py test
```

La suite de `news/tests.py` contiene 13 pruebas y cubre consulta pública, estados vacíos y paginación, registro e inicio/cierre de sesión, CSRF, control editorial y propiedad, transiciones de estado, borrado POST, Admin, relaciones y políticas `on_delete`. También comprueba plantillas, CSS, JavaScript e imágenes. Django crea una base de datos temporal para estas pruebas; no es necesario borrar ni reiniciar `db.sqlite3`.

## Solución de problemas

- **No se reconoce `python` o `py`:** instale Python y verifique que el ejecutable esté disponible en PowerShell; active `.venv` antes de instalar o ejecutar comandos.
- **Falta Django o Pillow:** active el entorno virtual e instale `python -m pip install -r requirements.txt`.
- **Faltan tablas o permisos/grupos:** ejecute `python manage.py migrate` y luego `python manage.py setup_editorial_roles`.
- **`createsuperuser` no puede iniciar sesión en el Admin:** compruebe que se creó con el comando de Django y que la cuenta tiene `is_staff`; use `is_superuser` solo para una cuenta administrativa de confianza.
- **Error de host no permitido:** agregue el host de desarrollo o despliegue a `DJANGO_ALLOWED_HOSTS`, separado por comas.
- **No se ven imágenes locales:** confirme que el archivo exista bajo `media/` y que `DJANGO_DEBUG` esté en `True`; la configuración de desarrollo sirve media solo en ese modo.
- **`makemigrations --check --dry-run` detecta cambios:** revise los modelos y las migraciones antes de aplicarlas; no elimine la base ni el historial para ocultar la diferencia.

## Estado y documentación adicional

La documentación describe las capacidades encontradas en el código actual. Categorías y etiquetas se gestionan editorialmente desde Django Admin; no hay interfaz pública CRUD para ellas ni sistema de comentarios implementado. La edición pública del perfil no permite cambiar correo o contraseña; Django ofrece sus pantallas administrativas nativas para la gestión de cuenta.

Para el detalle del laboratorio, decisiones de seguridad, permisos y pruebas, consulte [docs/LABORATORIO_NOTICIAS.md](docs/LABORATORIO_NOTICIAS.md). Los tokens y reglas visuales están descritos en [design-system/dae-noticias/MASTER.md](design-system/dae-noticias/MASTER.md).
