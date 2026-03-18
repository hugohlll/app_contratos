from django.core.management.base import BaseCommand
from datetime import date, timedelta
from django.db import models
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
            
            # Garante que a data_fim da comissão seja mantida.
            # Se for nula (o que não deveria ocorrer para expiradas), força para hoje - 1.
            if not comissao.data_fim:
                comissao.data_fim = hoje - timedelta(days=1)
                
            comissao.save()
            
            # Atualiza os integrantes: se a data_fim do integrante for maior que a da comissão,
            # ou se for nula, ajusta para a data_fim da comissão.
            integrantes_ativos = comissao.integrantes.filter(
                models.Q(data_fim__gt=comissao.data_fim) | models.Q(data_fim__isnull=True)
            )
            for integrante in integrantes_ativos:
                integrante.data_fim = comissao.data_fim
                integrante.save(update_fields=['data_fim'])

            msg = f'[OK] Comissão {comissao.id} (Contrato {comissao.contrato.numero}) desativada. Fim da vigência: {comissao.data_fim}'
            self.stdout.write(msg)

        self.stdout.write(self.style.SUCCESS(f'Processo concluído. {total} comissões foram desativadas.'))
