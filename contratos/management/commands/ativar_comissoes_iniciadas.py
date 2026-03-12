from django.core.management.base import BaseCommand
from datetime import date
from contratos.models import Comissao


class Command(BaseCommand):
    help = 'Ativa automaticamente comissões inativas cuja data de início chegou.'

    def handle(self, *args, **kwargs):
        hoje = date.today()

        # Busca comissões que estão INATIVAS mas com data_inicio igual ou anterior a hoje
        comissoes_para_ativar = Comissao.objects.filter(
            ativa=False,
            data_inicio__lte=hoje,
        ).exclude(
            # Não reativa comissões que já expiraram (data_fim no passado)
            data_fim__lt=hoje,
        )
        total = comissoes_para_ativar.count()

        if total == 0:
            self.stdout.write(self.style.SUCCESS('Nenhuma comissão para ativar hoje.'))
            return

        self.stdout.write(self.style.WARNING(f'Iniciando ativação de {total} comissão(ões)...'))

        for comissao in comissoes_para_ativar:
            comissao.ativa = True
            comissao.save()
            msg = (
                f'[OK] Comissão {comissao.id} '
                f'(Contrato {comissao.contrato.numero}) ativada. '
                f'Início: {comissao.data_inicio}'
            )
            self.stdout.write(msg)

        self.stdout.write(self.style.SUCCESS(f'Processo concluído. {total} comissão(ões) ativada(s).'))
