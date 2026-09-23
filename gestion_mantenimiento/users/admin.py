from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import User

from .models import Cliente, PerfilUsuario

admin.site.unregister(User)
admin.site.register(User, UserAdmin)
admin.site.register(Cliente)
admin.site.register(PerfilUsuario)
