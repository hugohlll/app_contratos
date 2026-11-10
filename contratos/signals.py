"""
Signals que alimentam os alertas da ACI a partir de qualquer caminho de gravação de
OcorrenciaContratual (AJAX, Livro do Fiscal, registro tempestivo, Django Admin).
"""
from django.db.models.signals import post_delete, post_save, pre_delete, pre_save
from django.dispatch import receiver

from contratos.models import OcorrenciaContratual
from contratos.services import alertas_aci


@receiver(pre_save, sender=OcorrenciaContratual, dispatch_uid='alertas_aci_pre_save')
def _guardar_estado_anterior(sender, instance, raw=False, **kwargs):
    if raw or not instance.pk:
        instance._alertas_aci_anterior = None
        return
    anterior = sender.objects.filter(pk=instance.pk).values(*alertas_aci.CAMPOS_MONITORADOS).first()
    instance._alertas_aci_anterior = anterior


@receiver(post_save, sender=OcorrenciaContratual, dispatch_uid='alertas_aci_post_save')
def _alertar_gravacao(sender, instance, created, raw=False, **kwargs):
    if raw:
        return
    anterior = getattr(instance, '_alertas_aci_anterior', None)
    if created or anterior is None:
        alertas_aci.registrar_criacao(instance)
    else:
        alertas_aci.registrar_atualizacao(instance, anterior)
    instance._alertas_aci_anterior = alertas_aci.estado_monitorado(instance)


def _exclusao_direta(origin):
    """Só alerta quando a própria ocorrência foi excluída, não em cascata de Livro/Contrato."""
    if isinstance(origin, OcorrenciaContratual):
        return True
    return getattr(origin, 'model', None) is OcorrenciaContratual


@receiver(pre_delete, sender=OcorrenciaContratual, dispatch_uid='alertas_aci_pre_delete')
def _preparar_exclusao(sender, instance, origin=None, **kwargs):
    instance._alertas_aci_exclusao = (
        alertas_aci.preparar_exclusao(instance) if _exclusao_direta(origin) else None
    )


@receiver(post_delete, sender=OcorrenciaContratual, dispatch_uid='alertas_aci_post_delete')
def _alertar_exclusao(sender, instance, **kwargs):
    alertas_aci.registrar_exclusao(getattr(instance, '_alertas_aci_exclusao', None))
