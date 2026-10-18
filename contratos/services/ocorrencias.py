from datetime import date, timedelta
from django.core.exceptions import ValidationError
from django.utils import timezone

from contratos.models import ControleExecucao, Contrato


class OcorrenciasService:
    @staticmethod
    def get_meses_visiveis(hoje=None):
        """
        Retorna os dois meses visíveis e gerenciáveis pelo fiscal:
        Mês anterior (X) e Mês corrente (X+1).
        Retorna lista de tuplas [(mes_X, ano_X), (mes_X1, ano_X1)].
        """
        if hoje is None:
            hoje = timezone.localdate()

        primeiro_dia_mes_atual = hoje.replace(day=1)
        ultimo_dia_mes_anterior = primeiro_dia_mes_atual - timedelta(days=1)

        mes_x = ultimo_dia_mes_anterior.month
        ano_x = ultimo_dia_mes_anterior.year

        mes_x1 = hoje.month
        ano_x1 = hoje.year

        return [(mes_x, ano_x), (mes_x1, ano_x1)]

    @staticmethod
    def livro_editavel(controle):
        """
        Um Livro do Fiscal é editável pelo fiscal enquanto não estiver atestado ('entregue')
        ou finalizado em conformidade ('ok').
        Estados abertos: rascunho, pendente, correcao (ou None/inexistente).
        """
        if controle is None:
            return True
        return controle.status not in ('entregue', 'ok')

    @classmethod
    def resolver_livro_para_data(cls, contrato, data_hora, hoje=None):
        """
        Valida a data_hora da constatação e localiza/cria o ControleExecucao correspondente.

        Regras acordadas:
        1. data_hora não pode estar no futuro.
        2. O mês/ano de data_hora deve ser o mês corrente (X+1) ou mês anterior (X).
        3. O Livro do mês correspondente não pode estar em status 'entregue' ou 'ok'.
        """
        agora = timezone.now()
        if timezone.is_naive(data_hora):
            data_hora = timezone.make_aware(data_hora)

        if data_hora > agora:
            raise ValidationError("A data e horário da constatação não podem estar no futuro.")

        dt_local = timezone.localtime(data_hora)
        mes_alvo = dt_local.month
        ano_alvo = dt_local.year

        meses_permitidos = cls.get_meses_visiveis(hoje)
        if (mes_alvo, ano_alvo) not in meses_permitidos:
            mes_x, ano_x = meses_permitidos[0]
            mes_x1, ano_x1 = meses_permitidos[1]
            raise ValidationError(
                f"O Livro do Fiscal de {mes_alvo:02d}/{ano_alvo} já foi atestado. Para incluir esta ocorrência, contate a ACI."
            )

        controle = ControleExecucao.objects.filter(
            contrato=contrato,
            mes_referencia=mes_alvo,
            ano_referencia=ano_alvo
        ).order_by('-id').first()

        if controle and not cls.livro_editavel(controle):
            raise ValidationError(
                f"O Livro do Fiscal de {mes_alvo:02d}/{ano_alvo} já foi atestado. Para incluir esta ocorrência, contate a ACI."
            )

        if not controle:
            controle = ControleExecucao.objects.create(
                contrato=contrato,
                mes_referencia=mes_alvo,
                ano_referencia=ano_alvo,
                status='rascunho',
                omap='GAP-BR',
                unidade_gestora='120006 - GAP-BR'
            )

        return controle
