from datetime import date
from django.db.models import Q

def get_filtro_ativos():
    """
    Retorna o objeto Q para filtrar apenas integrantes ativos.
    Regra: (Sem desligamento OU Desligamento Futuro) E (Sem fim previsto OU Fim previsto Futuro)
    """
    hoje = date.today()
    return (
        (Q(data_desligamento__isnull=True) | Q(data_desligamento__gt=hoje)) &
        (Q(data_fim__isnull=True) | Q(data_fim__gte=hoje))
    )