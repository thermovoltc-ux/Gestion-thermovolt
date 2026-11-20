from django.urls import path

from . import views

app_name = 'almacen'

urlpatterns = [
    path('inventario/', views.lista_productos, name='lista_productos'),
    path('producto/<int:producto_id>/editar/', views.editar_producto, name='editar_producto'),
    path('herramientas/', views.lista_herramientas, name='lista_herramientas'),
    path(
        'herramienta/<int:herramienta_id>/asignar/',
        views.asignar_herramienta,
        name='asignar_herramienta',
    ),
    path(
        'herramienta/<int:herramienta_id>/devolver/',
        views.devolver_herramienta,
        name='devolver_herramienta',
    ),
    path('movimientos/', views.lista_movimientos, name='lista_movimientos'),
    path('entrada/', views.registrar_movimiento, {'tipo': 'entrada'}, name='registrar_entrada'),
    path('salida/', views.registrar_movimiento, {'tipo': 'salida'}, name='registrar_salida'),
]
