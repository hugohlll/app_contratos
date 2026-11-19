from django.conf import settings


def app_version(request):
    """
    Context processor que injeta a versão oficial do SISCONT
    em todos os templates da aplicação.
    """
    return {
        'APP_VERSION': getattr(settings, 'SISCONT_VERSION', '2.2.0'),
    }


def alertas_aci(request):
    """Habilita o sino de alertas (e o contador inicial) apenas para usuários da ACI."""
    from contratos.services.alertas_aci import eh_destinatario_aci, nao_lidas

    user = getattr(request, 'user', None)
    if not eh_destinatario_aci(user):
        return {'ALERTAS_ACI': False}
    return {'ALERTAS_ACI': True, 'ALERTAS_ACI_NAO_LIDAS': nao_lidas(user).count()}


def contratos_a_classificar(request):
    """Contador de contratos do Contratos.gov.br à espera da OM beneficiada (só Administradores)."""
    from contratos.models import ContratoCatalogo
    from contratos.utils import is_admin

    user = getattr(request, 'user', None)
    if not (user and is_admin(user)):
        return {}
    return {'CONTRATOS_A_CLASSIFICAR': ContratoCatalogo.objects.filter(situacao=ContratoCatalogo.PENDENTE).count()}
