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
        # Atenção: Se data_fim for nulo, a comissão NÃO será excluída (ou seja, será ativada).
        # Isso atende comissões por tempo indeterminado.
        total_candidatas = comissoes_para_ativar.count()

        if total_candidatas == 0:
            self.stdout.write(self.style.SUCCESS('Nenhuma comissão para ativar hoje.'))
            return

        self.stdout.write(self.style.WARNING(f'{total_candidatas} comissão(ões) candidata(s) encontrada(s). Verificando duplicatas...'))

        ativadas = 0
        ignoradas = 0

        for comissao in comissoes_para_ativar:
            # REGRA DE NEGÓCIO: Não permitir duas comissões ativas do mesmo tipo
            # para o mesmo contrato (comissões de contrato)
            if comissao.contrato:
                ja_existe_ativa = Comissao.objects.filter(
                    contrato=comissao.contrato,
                    tipo=comissao.tipo,
                    ativa=True,
                ).exclude(pk=comissao.pk).exists()

                if ja_existe_ativa:
                    ignoradas += 1
                    msg = (
                        f'[IGNORADA] Comissão {comissao.id} '
                        f'({comissao.get_tipo_display()} - Contrato {comissao.contrato.numero}) '
                        f'não ativada: já existe outra comissão ativa do mesmo tipo para este contrato.'
                    )
                    self.stdout.write(self.style.WARNING(msg))
                    continue

            comissao.ativa = True
            comissao.save()
            ativadas += 1

            contrato_info = f'Contrato {comissao.contrato.numero}' if comissao.contrato else f'{comissao.get_tipo_display()}'
            msg = (
                f'[OK] Comissão {comissao.id} '
                f'({contrato_info}) ativada. '
                f'Início: {comissao.data_inicio}'
            )
            self.stdout.write(msg)

        resumo = f'Processo concluído. {ativadas} comissão(ões) ativada(s).'
        if ignoradas:
            resumo += f' {ignoradas} comissão(ões) ignorada(s) por conflito de duplicidade.'
        self.stdout.write(self.style.SUCCESS(resumo))
