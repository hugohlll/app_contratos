from django.conf import settings


def app_version(request):
    """
    Context processor que injeta a versão oficial do SISCONT
    em todos os templates da aplicação.
    """
    return {
        'APP_VERSION': getattr(settings, 'SISCONT_VERSION', '2.2.0'),
    }
