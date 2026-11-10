"""
Alertas da ACI sobre ocorrências do Livro do Fiscal: geração por evento, agrupamento,
ausência de ruído no reenvio do Livro e acesso restrito ao grupo 'Auditores'.
"""
import json
from datetime import date, timedelta

from django.contrib.auth.models import Group, User
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from contratos.models import (
    Agente, Comissao, Contrato, ControleExecucao, Empresa, Funcao, Integrante,
    NotificacaoACI, OcorrenciaContratual, PostoGraduacao,
)


class AlertasACIBase(TestCase):
    def setUp(self):
        self.client = Client()
        grupo = Group.objects.create(name='Auditores')
        self.aci1 = User.objects.create_user(username='aci1', password='pwd123')
        self.aci2 = User.objects.create_user(username='aci2', password='pwd123')
        inativo = User.objects.create_user(username='aci_inativo', password='pwd123', is_active=False)
        for u in (self.aci1, self.aci2, inativo):
            u.groups.add(grupo)
        self.admin = User.objects.create_superuser(username='admin_alertas', password='pwd123')
        self.comum = User.objects.create_user(username='comum', password='pwd123')

        posto = PostoGraduacao.objects.create(sigla='Cap', descricao='Capitão', senioridade=3)
        self.agente = Agente.objects.create(
            nome_completo='Fiscal Alerta', nome_de_guerra='Alerta', posto=posto, saram='778899'
        )
        self.empresa = Empresa.objects.create(razao_social='Empresa Alerta', cnpj='44.555.666/0001-77')
        self.contrato = Contrato.objects.create(
            numero='400/2026', objeto='Manutenção', tipo='DESPESA', empresa=self.empresa,
            vigencia_inicio=date(2026, 1, 1), vigencia_fim=date(2027, 12, 31), valor_total=1000
        )
        comissao = Comissao.objects.create(
            contrato=self.contrato, tipo='FISCALIZACAO', ativa=True, data_inicio=date(2026, 1, 1)
        )
        Integrante.objects.create(
            comissao=comissao, agente=self.agente, funcao=Funcao.objects.create(titulo='Fiscal Titular'),
            data_inicio=date(2026, 1, 1), portaria_numero='400', portaria_data=date(2026, 1, 1)
        )
        hoje = timezone.localdate()
        self.controle = ControleExecucao.objects.create(
            contrato=self.contrato, mes_referencia=hoje.month, ano_referencia=hoje.year
        )

    def _ocorrencia(self, **kwargs):
        dados = {'controle': self.controle, 'descricao': 'Equipe incompleta no posto de serviço.'}
        dados.update(kwargs)
        return OcorrenciaContratual.objects.create(**dados)


class GeracaoAlertasTests(AlertasACIBase):
    def test_criacao_gera_um_alerta_por_auditor_ativo(self):
        oc = self._ocorrencia()
        alertas = NotificacaoACI.objects.filter(evento='OCORRENCIA_CRIADA', ocorrencia=oc)
        self.assertEqual(
            sorted(alertas.values_list('destinatario__username', flat=True)), ['aci1', 'aci2']
        )
        dados = alertas.first().dados
        self.assertEqual(dados['contrato_numero'], '400/2026')
        self.assertEqual(dados['empresa'], 'Empresa Alerta')
        self.assertIn('Cap Alerta', dados['responsaveis'])
        self.assertEqual(alertas.first().contrato, self.contrato)

    def test_administrador_fora_do_grupo_nao_recebe(self):
        self._ocorrencia()
        self.assertFalse(NotificacaoACI.objects.filter(destinatario=self.admin).exists())

    def test_mudanca_de_status_gera_alerta_com_antes_e_depois(self):
        oc = self._ocorrencia()
        oc.status_ocorrencia = 'saneamento'
        oc.save()
        alerta = NotificacaoACI.objects.get(destinatario=self.aci1, evento='OCORRENCIA_ATUALIZADA')
        self.assertEqual(alerta.titulo, 'Status alterado: Em Aberto → Em Saneamento (Prazo 5d úteis)')
        self.assertEqual(alerta.dados['mudancas'][0]['antes'], 'Em Aberto')

    def test_campos_chave_geram_alerta(self):
        oc = self._ocorrencia()
        oc.notificacao_emitida = True
        oc.save()
        self.assertEqual(
            NotificacaoACI.objects.get(destinatario=self.aci1, evento='OCORRENCIA_ATUALIZADA').titulo,
            'Notificação formal emitida',
        )
        NotificacaoACI.objects.update(lida_em=timezone.now())
        oc.tramite_arc = True
        oc.save()
        self.assertTrue(NotificacaoACI.objects.filter(
            destinatario=self.aci1, titulo='Encaminhada à ARC/PAAI', lida_em__isnull=True
        ).exists())

    def test_edicao_somente_de_texto_nao_gera_alerta(self):
        oc = self._ocorrencia()
        oc.descricao = 'Texto corrigido.'
        oc.local = 'Bloco B'
        oc.save()
        self.assertFalse(NotificacaoACI.objects.filter(evento='OCORRENCIA_ATUALIZADA').exists())

    def test_exclusao_direta_gera_alerta_com_retrato(self):
        oc = self._ocorrencia()
        oc_id = oc.pk
        oc.delete()
        alerta = NotificacaoACI.objects.get(destinatario=self.aci1, evento='OCORRENCIA_EXCLUIDA')
        self.assertIsNone(alerta.ocorrencia)
        self.assertEqual(alerta.dados['ocorrencia_id'], oc_id)
        self.assertEqual(alerta.dados['controle_id'], self.controle.pk)
        # O alerta de criação perde o vínculo, mas permanece
        self.assertTrue(NotificacaoACI.objects.filter(evento='OCORRENCIA_CRIADA', ocorrencia__isnull=True).exists())

    def test_exclusao_em_cascata_do_contrato_nao_gera_alerta(self):
        self._ocorrencia()
        self.contrato.delete()
        self.assertFalse(NotificacaoACI.objects.filter(evento='OCORRENCIA_EXCLUIDA').exists())
        self.assertTrue(NotificacaoACI.objects.filter(evento='OCORRENCIA_CRIADA', contrato__isnull=True).exists())


class AgrupamentoAlertasTests(AlertasACIBase):
    def test_mudancas_seguidas_sao_agrupadas_no_alerta_nao_lido(self):
        oc = self._ocorrencia()
        oc.status_ocorrencia = 'saneamento'
        oc.save()
        oc.status_ocorrencia = 'resolvido'
        oc.save()
        alertas = NotificacaoACI.objects.filter(destinatario=self.aci1, evento='OCORRENCIA_ATUALIZADA')
        self.assertEqual(alertas.count(), 1)
        self.assertEqual(alertas.first().titulo, 'Status alterado: Em Aberto → Resolvido')

    def test_alerta_lido_nao_e_reaproveitado(self):
        oc = self._ocorrencia()
        oc.status_ocorrencia = 'saneamento'
        oc.save()
        NotificacaoACI.objects.filter(destinatario=self.aci1).update(lida_em=timezone.now())
        oc.status_ocorrencia = 'resolvido'
        oc.save()
        self.assertEqual(
            NotificacaoACI.objects.filter(destinatario=self.aci1, evento='OCORRENCIA_ATUALIZADA').count(), 2
        )
        # aci2 não leu: continua com um único alerta agrupado
        self.assertEqual(
            NotificacaoACI.objects.filter(destinatario=self.aci2, evento='OCORRENCIA_ATUALIZADA').count(), 1
        )

    def test_fora_da_janela_gera_novo_alerta(self):
        oc = self._ocorrencia()
        oc.status_ocorrencia = 'saneamento'
        oc.save()
        NotificacaoACI.objects.update(atualizado_em=timezone.now() - timedelta(minutes=6))
        oc.status_ocorrencia = 'resolvido'
        oc.save()
        self.assertEqual(
            NotificacaoACI.objects.filter(destinatario=self.aci1, evento='OCORRENCIA_ATUALIZADA').count(), 2
        )

    def test_reversao_dentro_da_janela_remove_alerta(self):
        oc = self._ocorrencia()
        oc.status_ocorrencia = 'saneamento'
        oc.save()
        oc.status_ocorrencia = 'aberto'
        oc.save()
        self.assertFalse(NotificacaoACI.objects.filter(evento='OCORRENCIA_ATUALIZADA').exists())


class CaminhosDeGravacaoTests(AlertasACIBase):
    def test_salvar_ocorrencia_ajax_gera_alerta(self):
        payload = {
            'contrato_id': self.contrato.id,
            'data_hora': timezone.localtime().strftime('%Y-%m-%dT%H:%M'),
            'tipo': 'TECNICA',
            'descricao': 'Registro via AJAX.',
            'status_ocorrencia': 'aberto',
        }
        resp = self.client.post(reverse('salvar_ocorrencia'), json.dumps(payload), content_type='application/json')
        self.assertTrue(resp.json()['success'])
        self.assertEqual(NotificacaoACI.objects.filter(evento='OCORRENCIA_CRIADA').count(), 2)

    def test_excluir_ocorrencia_ajax_gera_alerta(self):
        oc = self._ocorrencia()
        resp = self.client.post(reverse('excluir_ocorrencia', args=[oc.pk]))
        self.assertTrue(resp.json()['success'])
        self.assertEqual(NotificacaoACI.objects.filter(evento='OCORRENCIA_EXCLUIDA').count(), 2)

    def test_reenvio_sem_alteracao_nao_gera_alerta(self):
        """O salvamento do Livro regrava todas as ocorrências; sem mudança, sem alerta."""
        oc = self._ocorrencia(status_ocorrencia='saneamento')
        NotificacaoACI.objects.all().delete()
        for _ in range(3):
            oc = OcorrenciaContratual.objects.get(pk=oc.pk)
            oc.save()
        self.assertFalse(NotificacaoACI.objects.exists())


class AcessoNotificacoesTests(AlertasACIBase):
    def test_lista_e_resumo_restritos_ao_grupo_auditores(self):
        for url in (reverse('notificacoes_lista'), reverse('notificacoes_resumo')):
            self.client.force_login(self.comum)
            self.assertEqual(self.client.get(url).status_code, 403)
            self.client.force_login(self.admin)
            self.assertEqual(self.client.get(url).status_code, 403)
            self.client.force_login(self.aci1)
            self.assertEqual(self.client.get(url).status_code, 200)

    def test_anonimo_e_redirecionado_para_login(self):
        resp = self.client.get(reverse('notificacoes_lista'))
        self.assertEqual(resp.status_code, 302)

    def test_resumo_traz_contador_e_itens(self):
        self._ocorrencia()
        self.client.force_login(self.aci1)
        data = self.client.get(reverse('notificacoes_resumo')).json()
        self.assertEqual(data['nao_lidas'], 1)
        self.assertEqual(data['itens'][0]['contrato'], '400/2026')

    def test_abrir_marca_lida_e_redireciona_para_ocorrencia(self):
        oc = self._ocorrencia()
        alerta = NotificacaoACI.objects.get(destinatario=self.aci1)
        self.client.force_login(self.aci1)
        resp = self.client.get(reverse('notificacao_abrir', args=[alerta.pk]))
        self.assertRedirects(
            resp, reverse('visualizar_controle_execucao', args=[self.controle.pk]) + f"#oc-{oc.pk}",
            fetch_redirect_response=False,
        )
        alerta.refresh_from_db()
        self.assertIsNotNone(alerta.lida_em)
        # O alerta do outro auditor segue não lido
        self.assertTrue(NotificacaoACI.objects.filter(destinatario=self.aci2, lida_em__isnull=True).exists())

    def test_abrir_alerta_de_ocorrencia_excluida_vai_para_o_livro(self):
        self._ocorrencia().delete()
        alerta = NotificacaoACI.objects.get(destinatario=self.aci1, evento='OCORRENCIA_EXCLUIDA')
        self.client.force_login(self.aci1)
        resp = self.client.get(reverse('notificacao_abrir', args=[alerta.pk]))
        self.assertRedirects(
            resp, reverse('visualizar_controle_execucao', args=[self.controle.pk]), fetch_redirect_response=False
        )

    def test_nao_abre_alerta_de_outro_auditor(self):
        self._ocorrencia()
        alerta = NotificacaoACI.objects.get(destinatario=self.aci2)
        self.client.force_login(self.aci1)
        self.assertEqual(self.client.get(reverse('notificacao_abrir', args=[alerta.pk])).status_code, 404)

    def test_marcar_todas_afeta_apenas_o_proprio_usuario(self):
        self._ocorrencia()
        self._ocorrencia()
        self.client.force_login(self.aci1)
        self.client.post(reverse('notificacoes_marcar_todas'))
        self.assertFalse(NotificacaoACI.objects.filter(destinatario=self.aci1, lida_em__isnull=True).exists())
        self.assertEqual(NotificacaoACI.objects.filter(destinatario=self.aci2, lida_em__isnull=True).count(), 2)

    def test_filtros_da_lista(self):
        oc = self._ocorrencia()
        oc.status_ocorrencia = 'resolvido'
        oc.save()
        self.client.force_login(self.aci1)
        resp = self.client.get(reverse('notificacoes_lista'), {'status': 'todas', 'evento': 'OCORRENCIA_ATUALIZADA'})
        self.assertEqual(len(resp.context['pagina'].object_list), 1)
        resp = self.client.get(reverse('notificacoes_lista'), {'status': 'lidas'})
        self.assertEqual(len(resp.context['pagina'].object_list), 0)

    def test_sino_aparece_somente_para_aci(self):
        self.client.force_login(self.aci1)
        self.assertContains(self.client.get(reverse('portal_home')), 'id="alertas-aci"')
        self.client.force_login(self.admin)
        self.assertNotContains(self.client.get(reverse('portal_home')), 'id="alertas-aci"')
