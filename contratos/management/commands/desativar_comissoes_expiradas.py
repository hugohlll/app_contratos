from django.core.management.base import BaseCommand
from datetime import date
from contratos.models import Comissao

class Command(BaseCommand):
    help = 'Desativa automaticamente comissões cuja data de fim já expirou.'

    def handle(self, *args, **kwargs):
        hoje = date.today()
        
        # Busca comissões que estão ATIVAS mas com data_fim ANTERIOR a hoje
        comissoes_expiradas = Comissao.objects.filter(ativa=True, data_fim__lt=hoje)
        total = comissoes_expiradas.count()

        if total == 0:
            self.stdout.write(self.style.SUCCESS('Nenhuma comissão expirada encontrada para desativar hoje.'))
            return

        self.stdout.write(self.style.WARNING(f'Iniciando desativação de {total} comissões expiradas...'))

        for comissao in comissoes_expiradas:
            comissao.ativa = False
            comissao.save()
            msg = f'[OK] Comissão {comissao.id} (Contrato {comissao.contrato.numero}) desativada. Fim da vigência: {comissao.data_fim}'
            self.stdout.write(msg)

        self.stdout.write(self.style.SUCCESS(f'Processo concluído. {total} comissões foram desativadas.'))
