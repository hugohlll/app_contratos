import json
from datetime import date, timedelta
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from django.contrib.auth.models import User, Group

from contratos.models import (
    Contrato, Agente, PostoGraduacao, Comissao, Integrante, Empresa, Funcao,
    ControleExecucao, OcorrenciaContratual, CalendarioPrestacao, PrestacaoContas
)


class ControleExecucaoTests(TestCase):
    def setUp(self):
        # 1. Usuários e Grupos
        self.group_admin = Group.objects.create(name='Administradores')
        self.group_auditor = Group.objects.create(name='Auditores')

        self.user_auditor = User.objects.create_user(
            username='auditor1', password='password123'
        )
        self.user_auditor.groups.add(self.group_auditor)

        self.user_admin = User.objects.create_superuser(
            username='admin1', password='password123'
        )

        # 2. Dados Básicos (Posto, Agente, Empresa, Contrato, Função)
        self.posto = PostoGraduacao.objects.create(sigla='CAP', descricao='Capitão', senioridade=5)
        self.agente = Agente.objects.create(
            nome_completo='João da Silva',
            nome_de_guerra='Silva',
            posto=self.posto,
            saram='1234567',
            cpf='11122233344'
        )
        self.empresa = Empresa.objects.create(
            razao_social='Empresa Teste LTDA',
            cnpj='11222333000199'
        )
        self.funcao = Funcao.objects.create(titulo='Fiscal Titular')

        self.contrato = Contrato.objects.create(
            numero='55/2026',
            tipo='DESPESA',
            pag='67100.0055/2026-10',
            objeto='Prestação de serviço de manutenção predial',
            empresa=self.empresa,
            vigencia_inicio=date.today() - timedelta(days=180),
            vigencia_fim=date.today() + timedelta(days=365),
            valor_total=100000.00
        )

        # 3. Comissão de Fiscalização Ativa
        self.comissao = Comissao.objects.create(
            contrato=self.contrato,
            portaria_numero='Portaria 100/2026',
            boletim_numero='BInt 10/2026',
            tipo='FISCALIZACAO',
            ativa=True
        )
        self.integrante = Integrante.objects.create(
            comissao=self.comissao,
            agente=self.agente,
            funcao=self.funcao,
            data_inicio=date(2026, 1, 1),
            portaria_data=date(2026, 1, 1)
        )

    def test_acesso_portal_execucao_publico(self):
        """Testa se as rotas antigas do portal de execução redirecionam para o portal de prestação de contas."""
        response_index = self.client.get(reverse('portal_execucao_index'))
        self.assertEqual(response_index.status_code, 302)
        self.assertEqual(response_index.url, reverse('portal_prestacao_index'))

        response_fiscais = self.client.get(reverse('portal_execucao_fiscais'))
        self.assertEqual(response_fiscais.status_code, 302)
        self.assertEqual(response_fiscais.url, reverse('portal_prestacao_fiscais'))

    def test_numeracao_sequencial_livro_npa009(self):
        """Testa a numeração sequencial <mês>/<ano>/<D|R>/<contrato> para despesa e receita."""
        ctrl_despesa = ControleExecucao.objects.create(
            contrato=self.contrato,
            mes_referencia=9,
            ano_referencia=2026,
            status='rascunho'
        )
        self.assertEqual(ctrl_despesa.numero_livro, '09/2026/D/55/2026')
        self.assertEqual(ctrl_despesa.unidade_gestora, '120006 - GAP-BR')

        ct_receita = Contrato.objects.create(
            numero='02/2026',
            tipo='RECEITA',
            objeto='Cessão de uso de espaço para lanchonete',
            empresa=self.empresa,
            vigencia_inicio=date.today(),
            vigencia_fim=date.today() + timedelta(days=365),
            valor_total=50000.00
        )
        ctrl_receita = ControleExecucao.objects.create(
            contrato=ct_receita,
            mes_referencia=9,
            ano_referencia=2026,
            status='entregue'
        )
        self.assertEqual(ctrl_receita.numero_livro, '09/2026/R/02/2026')

    def test_preenchimento_formulario_livro_fiscal_npa009(self):
        """Testa a submissão completa do formulário do Livro do Fiscal conforme NPA 009."""
        url = reverse('formulario_execucao', kwargs={'contrato_id': self.contrato.id})
        response_get = self.client.get(url)
        self.assertEqual(response_get.status_code, 200)
        self.assertContains(response_get, "120006 - GAP-BR")

        ocorrencias_payload = [
            {
                'data_hora': '2026-05-10T09:30',
                'local': 'Canteiro de Obras Principal',
                'tipo': 'OBRAS',
                'descricao': 'Operários trabalhando sem EPI adequado.',
                'dispositivo_violado': 'Cláusula 14.2 do Contrato',
                'evidencias': 'Relatório Fotográfico 01/2026',
                'notificacao_emitida': True,
                'notificacao_numero': '001/GAP-BR/2026',
                'prazo_dias_uteis': 5,
                'ciencia_preposto': 'assinado',
                'tramite_arc': False,
                'status_ocorrencia': 'saneamento',
                'acao_fiscal': 'Paralisação imediata dos serviços até adequação.'
            }
        ]

        post_data = {
            'mes_referencia': 5,
            'ano_referencia': 2026,
            'agente': self.agente.id,
            'omap': 'GAP-BR',
            'unidade_gestora': '120006 - GAP-BR',
            'preposto_nome': 'Marcos Preposto',
            'preposto_cargo': 'Engenheiro Residente',
            'preposto_cpf': '987.654.321-11',
            'preposto_telefone': '(61) 98888-7777',
            'preposto_email': 'marcos@empresa.com.br',
            'eh_obra_engenharia': 'on',
            'condicoes_climaticas': 'Sem chuvas ou paralisações.',
            'efetivo_trabalhadores': '8 pedreiros, 4 serventes, 1 engenheiro.',
            'maquinario_equipamentos': '1 betoneira, 1 andaime fachadeiro.',
            'art_rrt': 'ART 2026/001 CREA-DF',
            'matricula_cei_cno': 'CNO 12345678',
            'seguranca_trabalho_cat': 'EPIs em uso integral. Sem acidentes.',
            'sem_ocorrencias_periodo': False,
            'observacao': 'Serviços em andamento regular.',
            'ocorrencias_json': json.dumps(ocorrencias_payload),
            'acao': 'finalizar'
        }

        response = self.client.post(url, post_data)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('upload_prestacao', kwargs={'contrato_id': self.contrato.id}))

        # Verificar se salvou no BD
        self.assertEqual(ControleExecucao.objects.count(), 1)
        ctrl = ControleExecucao.objects.first()
        self.assertEqual(ctrl.contrato, self.contrato)
        self.assertEqual(ctrl.agente, self.agente)
        self.assertEqual(ctrl.status, 'entregue')
        self.assertEqual(ctrl.preposto_nome, 'Marcos Preposto')
        self.assertTrue(ctrl.eh_obra_engenharia)
        self.assertEqual(ctrl.art_rrt, 'ART 2026/001 CREA-DF')

        # Verificar ocorrência salva com 10 campos
        self.assertEqual(ctrl.ocorrencias.count(), 1)
        oc1 = ctrl.ocorrencias.first()
        self.assertEqual(oc1.tipo, 'OBRAS')
        self.assertEqual(oc1.local, 'Canteiro de Obras Principal')
        self.assertEqual(oc1.notificacao_numero, '001/GAP-BR/2026')
        self.assertTrue(oc1.notificacao_emitida)
        self.assertEqual(oc1.prazo_dias_uteis, 5)

    def test_salvar_rascunho_tempestivo(self):
        """Testa salvar como rascunho (lançamento tempestivo durante o mês)."""
        url = reverse('formulario_execucao', kwargs={'contrato_id': self.contrato.id})
        post_data = {
            'mes_referencia': 5,
            'ano_referencia': 2026,
            'agente': self.agente.id,
            'preposto_nome': 'Preposto Temporario',
            'sem_ocorrencias_periodo': True,
            'acao': 'rascunho'
        }
        response = self.client.post(url, post_data)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('formulario_execucao', kwargs={'contrato_id': self.contrato.id}))

        ctrl = ControleExecucao.objects.first()
        self.assertEqual(ctrl.status, 'rascunho')

    def test_preenchimento_automatico_preposto_mes_anterior(self):
        """Testa se o preposto do mês anterior é sugerido automaticamente no novo mês."""
        ControleExecucao.objects.create(
            contrato=self.contrato,
            mes_referencia=4,
            ano_referencia=2026,
            status='ok',
            preposto_nome='Ana Paula Preposta',
            preposto_cargo='Diretora Operacional',
            preposto_telefone='(61) 91111-2222',
            preposto_email='ana@empresa.com'
        )

        from contratos.forms import ControleExecucaoForm
        form = ControleExecucaoForm(contrato=self.contrato)
        self.assertEqual(form.initial.get('preposto_nome'), 'Ana Paula Preposta')
        self.assertEqual(form.initial.get('preposto_cargo'), 'Diretora Operacional')
        self.assertEqual(form.initial.get('preposto_telefone'), '(61) 91111-2222')
        self.assertEqual(form.initial.get('preposto_email'), 'ana@empresa.com')

    def test_salvar_ocorrencia_tempestiva_ajax(self):
        """Testa o endpoint AJAX para gravar ocorrência tempestiva no dia a dia."""
        url = reverse('salvar_ocorrencia_tempestiva')
        payload = {
            'contrato_id': self.contrato.id,
            'mes_referencia': 6,
            'ano_referencia': 2026,
            'data_hora': '2026-06-15T10:00',
            'local': 'Setor Administrativo',
            'tipo': 'ADMINISTRATIVA',
            'descricao': 'Falta de entrega de certidão de regularidade fiscal.',
            'dispositivo_violado': 'Cláusula 12.1',
            'notificacao_emitida': True,
            'notificacao_numero': '010/GAP-BR/2026',
            'prazo_dias_uteis': 5,
            'status_ocorrencia': 'aberto'
        }

        response = self.client.post(
            url, data=json.dumps(payload), content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)
        resp_json = response.json()
        self.assertTrue(resp_json['success'])
        self.assertIn('notificacao_pdf_url', resp_json['ocorrencia'])

        ctrl = ControleExecucao.objects.filter(contrato=self.contrato, mes_referencia=6, ano_referencia=2026).first()
        self.assertIsNotNone(ctrl)
        self.assertEqual(ctrl.status, 'rascunho')
        self.assertEqual(ctrl.ocorrencias.count(), 1)
        self.assertEqual(ctrl.ocorrencias.first().notificacao_numero, '010/GAP-BR/2026')

    def test_workflow_auditoria_aci_status(self):
        """Testa homologação (ok) e pedido de correção da ACI no Livro do Fiscal."""
        ctrl = ControleExecucao.objects.create(
            contrato=self.contrato,
            agente=self.agente,
            mes_referencia=5,
            ano_referencia=2026,
            status='entregue'
        )

        url_ok = reverse('alterar_status_execucao', kwargs={'pk': ctrl.id, 'novo_status': 'ok'})
        res_no_auth = self.client.get(url_ok)
        self.assertEqual(res_no_auth.status_code, 302)

        self.client.login(username="auditor1", password="password123")
        res_ok = self.client.get(url_ok)
        self.assertEqual(res_ok.status_code, 302)
        ctrl.refresh_from_db()
        self.assertEqual(ctrl.status, 'ok')

        url_corr = reverse('alterar_status_execucao', kwargs={'pk': ctrl.id, 'novo_status': 'correcao'})
        res_corr = self.client.post(url_corr, {'justificativa': 'Complementar descrição da ocorrência.'})
        self.assertEqual(res_corr.status_code, 302)
        ctrl.refresh_from_db()
        self.assertEqual(ctrl.status, 'correcao')
        self.assertEqual(ctrl.apontamentos.count(), 1)
        self.assertEqual(ctrl.apontamentos.first().descricao, 'Complementar descrição da ocorrência.')

    def test_upload_prestacao_desbloqueado_slides_modular(self):
        """Testa que o envio de slides não é bloqueado pelo Livro do Fiscal devido à chave modular."""
        url = reverse('upload_prestacao', kwargs={'contrato_id': self.contrato.id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

        # A flag modular deve ser False
        self.assertFalse(response.context['execucao_bloqueia_slides'])

    def test_exportar_execucao_csv(self):
        """Testa exportação de CSV dos Livros do Fiscal."""
        ControleExecucao.objects.create(
            contrato=self.contrato,
            agente=self.agente,
            mes_referencia=5,
            ano_referencia=2026,
            status='entregue',
            preposto_nome='Carlos Preposto'
        )
        self.client.login(username="auditor1", password="password123")
        url = reverse('exportar_execucao_csv') + '?mes=5&ano=2026'
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'text/csv; charset=utf-8')
        content = response.content.decode('utf-8-sig')
        self.assertIn('Número do Livro', content)
        self.assertIn('05/2026/D/55/2026', content)
        self.assertIn('120006 - GAP-BR', content)
        self.assertIn('Carlos Preposto', content)

    def test_exclusao_publica_e_admin(self):
        """Testa exclusão pública pelo fiscal e exclusão por administrador."""
        hoje = date.today()
        primeiro_dia_mes_atual = hoje.replace(day=1)
        ultimo_dia_mes_anterior = primeiro_dia_mes_atual - timedelta(days=1)
        mes_p = ultimo_dia_mes_anterior.month
        ano_p = ultimo_dia_mes_anterior.year

        ctrl = ControleExecucao.objects.create(
            contrato=self.contrato,
            mes_referencia=mes_p,
            ano_referencia=ano_p,
            status='rascunho'
        )
        url_del_pub = reverse('excluir_controle_execucao_publico', kwargs={'contrato_id': self.contrato.id})
        res_del = self.client.get(url_del_pub)
        self.assertEqual(res_del.status_code, 302)
        self.assertEqual(ControleExecucao.objects.count(), 0)

        ctrl2 = ControleExecucao.objects.create(
            contrato=self.contrato,
            mes_referencia=mes_p,
            ano_referencia=ano_p,
            status='rascunho'
        )
        self.client.login(username="admin1", password="password123")
        url_admin_del = reverse('excluir_controle_execucao', kwargs={'pk': ctrl2.pk})
        res_adm = self.client.get(url_admin_del)
        self.assertEqual(res_adm.status_code, 302)
        self.assertEqual(ControleExecucao.objects.count(), 0)
