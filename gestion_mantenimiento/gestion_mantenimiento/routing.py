# gestion_mantenimiento/routing.py
from django.urls import path
from solicitudes.consumers import KanbanConsumer

websocket_urlpatterns = [
    path('ws/kanban/', KanbanConsumer.as_asgi()),
]
