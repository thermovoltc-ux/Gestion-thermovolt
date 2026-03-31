from django.urls import path
from .views import register, custom_login, dashboard, logout_view

urlpatterns = [
    path('register/', register, name='register'),
    path('login/', custom_login, name='custom_login'),
    path('dashboard/', dashboard, name='dashboard'),
    path('logout/', logout_view, name='logout'),
]