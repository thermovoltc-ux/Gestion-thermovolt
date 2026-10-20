def is_admin(request):
    if request.user.is_authenticated:
        return {
            'is_admin': (
                request.user.is_staff
                or request.user.is_superuser
                or request.user.groups.filter(name__in=['Admin', 'Supervisor']).exists()
            )
        }
    return {
        'is_admin': False
    }