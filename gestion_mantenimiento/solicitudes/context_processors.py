from django.contrib.auth.models import Group

def is_admin(request):
    if request.user.is_authenticated:
        return {
            'is_admin': request.user.groups.filter(name='Admin').exists()
        }
    return {
        'is_admin': False
    }