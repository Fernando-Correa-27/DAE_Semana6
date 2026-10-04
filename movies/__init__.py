"""
Aplicacion movies.

Este ``__init__.py`` es imprescindible: sin el, ``movies/`` solo es un *namespace
package* y ``unittest`` lo descarta en silencio durante el descubrimiento, de modo
que ``manage.py test`` se ejecutaba contra la copia obsoleta de
``config/movies/tests/`` y la suite real de ``movies/tests/`` nunca corria.
"""
