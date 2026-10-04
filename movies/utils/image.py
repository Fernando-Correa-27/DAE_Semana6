"""
Utilidades de optimizacion de imagenes.

Comprime y redimensiona imagenes usando Pillow para optimizar el almacenamiento
y el tiempo de carga en el frontend.
"""

import logging
import os
from io import BytesIO

from django.core.files.base import ContentFile
from PIL import Image

logger = logging.getLogger(__name__)


def _read_source_bytes(image) -> bytes:
    """Devuelve los bytes de ``image`` sin apropiarse de su descriptor.

    Leer los bytes *antes* de darselos a Pillow es obligatorio. ``Image.open()``
    guarda una referencia al objeto fichero que recibe y ``ImageFile.close()``
    la cierra sin mirar si la posee o no (Pillow asume que se le ha cedido en
    exclusiva). Si se le entrega el ``UploadedFile`` del llamante,
    ``optimize_image()`` acabaria cerrando un fichero ajeno y
    ``FileField.pre_save()`` fallaria despues con
    ``ValueError: I/O operation on closed file.``

    Args:
        image: Un fichero de Django (``File``/``UploadedFile``) o una ruta.

    Returns:
        Los bytes integros de la imagen.

    Raises:
        Exception: Cualquier fallo de lectura (ruta inexistente, permisos,
            objeto sin ``read``, etc.) se propaga al llamante, que decide.
    """
    source = image
    if not callable(getattr(source, 'read', None)):
        # El proxy ``File``/``FileProxyMixin`` de Django guarda el objeto real en
        # ``.file`` y le delega el resto de atributos, asi que ``File('/x.jpg')``
        # no tiene ``read`` hasta que se le pasa un fichero de verdad. Desenvolver
        # aqui mantiene el diagnostico correcto (FileNotFoundError, no TypeError).
        inner = getattr(source, 'file', None)
        if inner is not None:
            source = inner

    read = getattr(source, 'read', None)
    if callable(read):
        data = read()
        # Rebobinar para dejar el handle del llamante tal y como estaba.
        try:
            source.seek(0)
        except Exception:  # pragma: no cover - rebobinado defensivo
            logger.debug('No se pudo rebobinar la imagen de entrada.', exc_info=True)
        return data

    # Ruta (str o Path): se abre un handle privado, que se cierra aqui.
    with open(os.fspath(source), 'rb') as handle:
        return handle.read()


def _to_rgb(image: Image.Image) -> Image.Image:
    """Devuelve ``image`` en modo RGB, aplanando la transparencia sobre blanco.

    JPEG no soporta ni canal alfa ni paleta, asi que una portada PNG con
    transparencia hay que componerla antes de re-codificarla.
    """
    if image.mode in ('RGBA', 'P', 'LA'):
        background = Image.new('RGB', image.size, (255, 255, 255))
        if image.mode == 'P':
            image = image.convert('RGBA')
        if 'transparency' in image.info:
            background.paste(image, mask=image.split()[-1])
        else:
            background.paste(image)
        return background
    if image.mode != 'RGB':
        return image.convert('RGB')
    return image


def _close_quietly(resource) -> None:
    """Cierra ``resource`` sin propagar excepciones (cierre defensivo)."""
    if resource is None:
        return
    try:
        resource.close()
    except Exception:  # pragma: no cover - cierre defensivo
        logger.debug('No se pudo cerrar un recurso de Pillow tras optimizar.', exc_info=True)


def optimize_image(image, quality: int = 85, max_width: int = 1200, max_height: int = 1200):
    """
    Comprime y redimensiona una imagen.

    Los bytes se leen primero a memoria y Pillow decodifica desde un ``BytesIO``
    propio, de modo que nunca toca (ni cierra) el descriptor del llamante. Todo
    el cuerpo va protegido: si la imagen no puede leerse, abrirse, decodificarse
    o re-codificarse (ruta inexistente, fichero corrupto o truncado, formato no
    soportado, etc.) se registra un warning y se devuelve la entrada original sin
    modificar. Esta funcion nunca propaga la excepcion.

    Args:
        image: Un Django InMemoryUploadedImage o ImageField file.
        quality: Calidad de compresion JPEG (1-100, por defecto 85).
        max_width: Ancho maximo despues de redimensionar.
        max_height: Altura maxima despues de redimensionar.

    Returns:
        Un ContentFile con la imagen optimizada, o el ``image`` original si no
        se pudo optimizar.
    """
    # Todo lo que hay que cerrar al salir. Solo contiene recursos creados aqui,
    # nunca el handle que nos paso el llamante.
    source_buffer = None
    opened_image = None
    converted_image = None
    output_buffer = None

    try:
        # 1. Copia en memoria. A partir de aqui Pillow es dueño de sus propios
        #    buffers y el fichero del llamante queda intacto.
        source_buffer = BytesIO(_read_source_bytes(image))
        opened_image = Image.open(source_buffer)

        # 2. JPEG no admite transparencia: componer sobre fondo blanco.
        converted_image = _to_rgb(opened_image)

        # 3. Redimensionar si la imagen excede las dimensiones maximas. Este es
        #    tambien el punto donde un JPEG truncado delata su ``OSError``:
        #    ``Image.open()`` solo parsea la cabecera y decodifica de forma
        #    perezosa, asi que un fichero con cabecera valida y pixeles
        #    corruptos se abre sin error y revienta aqui.
        converted_image.thumbnail((max_width, max_height), Image.LANCZOS)

        # 4. Guardar en un buffer con compresion optimizada.
        output_buffer = BytesIO()
        converted_image.save(output_buffer, format='JPEG', quality=quality, optimize=True)
        payload = output_buffer.getvalue()
    except Exception as exc:
        name = getattr(image, 'name', image)
        logger.warning(
            'No se pudo optimizar la imagen %r (%s: %s); se conserva sin optimizar.',
            name,
            type(exc).__name__,
            exc,
        )
        return image
    finally:
        # Cerrar unicamente lo que esta funcion posee. En particular, el
        # descriptor del llamante NO se cierra: Pillow nunca lo ha tenido.
        _close_quietly(converted_image)
        _close_quietly(opened_image)
        _close_quietly(output_buffer)
        _close_quietly(source_buffer)

    # Determinar el nombre del archivo
    original_name = image.name if hasattr(image, 'name') else 'optimized_image.jpg'
    filename = original_name.rsplit('.', 1)[0] + '.jpg'

    return ContentFile(payload, name=filename)
