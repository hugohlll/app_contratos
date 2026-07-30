import json
from datetime import date, timedelta
from django.test import TestCase
from django.urls import reverse
from django.contrib.auth.models import User, Group

from contratos.models import (
    Contrato, Agente, PostoGraduacao, Comissao, Integrante, Empresa, Funcao,
    ControleExecucao, RegistroFatura, OcorrenciaContratual, CalendarioPrestacao
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

        # 2. Dados Basicos (Posto, Agente, Empresa, Contrato, Funcao)
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
            objeto='Prestação de serviço de manutenção predial',
            empresa=self.empresa,
            vigencia_inicio=date(2026, 1, 1),
            vigencia_fim=date(2026, 12, 31),
            valor_total=100000.00
        )

        # 3. Comissão de Fiscalização Ativa
        self.comissao = Comissao.objects.create(
            contrato=self.contrato,
            portaria_numero='Portaria 100/2026',
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
        """Testa se a landing page e a lista de contratos do portal de execução são acessíveis sem login."""
        response_index = self.client.get(reverse('portal_execucao_index'))
        self.assertEqual(response_index.status_code, 200)
        self.assertContains(response_index, "Controle de Execução Contratual")

        response_fiscais = self.client.get(reverse('portal_execucao_fiscais'))
        self.assertEqual(response_fiscais.status_code, 200)
        self.assertContains(response_fiscais, "55/2026")

    def test_preenchimento_formulario_livro_fiscal(self):
        """Testa a submissão completa do formulário do Livro do Fiscal com faturas e ocorrências."""
        url = reverse('formulario_execucao', kwargs={'contrato_id': self.contrato.id})
        response_get = self.client.get(url)
        self.assertEqual(response_get.status_code, 200)
        self.assertContains(response_get, "Livro do Fiscal Digital")

        faturas_payload = [
            {'numero_nf': 'NF-1001', 'valor': 1500.50, 'numero_ob': '2026OB8001'},
            {'numero_nf': 'NF-1002', 'valor': 3200.00, 'numero_ob': '2026OB8002'}
        ]

        ocorrencias_payload = [
            {
                'data': '2026-05-10',
                'tipo': 'reuniao',
                'descricao': 'Reunião de alinhamento mensal de resultados.',
                'acao_fiscal': 'Solicitada readequação no cronograma.',
                'prazo': '5 dias úteis'
            }
        ]

        post_data = {
            'mes_referencia': 5,
            'ano_referencia': 2026,
            'agente': self.agente.id,
            'houve_substituicao': 'sim',
            'substituicao_entrega_formal': 'sim',
            'substituicao_obs': 'Passagem de serviço realizada sem pendências.',
            'confirmacao_siloms_assinatura': 'sim',
            'confirmacao_siloms_vigencia': 'sim',
            'confirmacao_siloms_execucao': 'sim',
            'possibilidade_aditivo': 'na',
            'tratativas_120_dias': 'na',
            'coordenacao_doc_scon': 'sim',
            'notas_empenho': '2026NE000123',
            'cronograma_fisico_financeiro': 'conforme',
            'detalhamento_cronograma': 'Execução normal conforme planejado.',
            'imr_aplicado': 'nao',
            'ocorrencias_ativas_empresa': 'nao',
            'necessidade_paai': 'nao',
            'relatorio_ocorrencias': 'Consolidado da reunião mensal.',
            'observacao': 'Tudo conforme as normas.',
            'faturas_json': json.dumps(faturas_payload),
            'ocorrencias_json': json.dumps(ocorrencias_payload)
        }

        response = self.client.post(url, post_data)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('portal_execucao_index'))

        # Verificar se salvou no BD
        self.assertEqual(ControleExecucao.objects.count(), 1)
        ctrl = ControleExecucao.objects.first()
        self.assertEqual(ctrl.contrato, self.contrato)
        self.assertEqual(ctrl.agente, self.agente)
        self.assertEqual(ctrl.status, 'entregue')
        self.assertTrue(ctrl.houve_substituicao)

        # Verificar faturas relacionadas
        self.assertEqual(ctrl.faturas.count(), 2)
        f1 = ctrl.faturas.first()
        self.assertEqual(f1.numero_nf, "NF-1001")

        # Verificar ocorrências relacionadas
        self.assertEqual(ctrl.ocorrencias.count(), 1)
        oc1 = ctrl.ocorrencias.first()
        self.assertEqual(oc1.tipo, "reuniao")

    def test_workflow_auditoria_aci_status(self):
        """Testa aprovação e pedido de correção da ACI no Livro do Fiscal."""
        ctrl = ControleExecucao.objects.create(
            contrato=self.contrato,
            agente=self.agente,
            mes_referencia=5,
            ano_referencia=2026,
            status='entregue'
        )

        # Acesso negado para não autenticado
        url_ok = reverse('alterar_status_execucao', kwargs={'pk': ctrl.id, 'novo_status': 'ok'})
        res_no_auth = self.client.get(url_ok)
        self.assertEqual(res_no_auth.status_code, 302)

        # Aprovação pelo Auditor
        self.client.login(username="auditor1", password="password123")
        res_ok = self.client.get(url_ok)
        self.assertEqual(res_ok.status_code, 302)
        ctrl.refresh_from_db()
        self.assertEqual(ctrl.status, 'ok')

        # Solicitação de correção com justificativa
        url_corr = reverse('alterar_status_execucao', kwargs={'pk': ctrl.id, 'novo_status': 'correcao'})
        res_corr = self.client.post(url_corr, {'justificativa': 'Corrigir valor da fatura.'})
        self.assertEqual(res_corr.status_code, 302)
        ctrl.refresh_from_db()
        self.assertEqual(ctrl.status, 'correcao')
        self.assertEqual(ctrl.apontamentos.count(), 1)
        self.assertEqual(ctrl.apontamentos.first().descricao, 'Corrigir valor da fatura.')

    def test_salvar_calendario_execucao_deadline(self):
        """Testa atualização da data limite de entrega do Livro do Fiscal via AJAX."""
        self.client.login(username="auditor1", password="password123")
        url = reverse('salvar_calendario_prestacao')
        
        payload = json.dumps({
            'ano': 2026,
            'mes': 5,
            'data_entrega': '2026-05-15',
            'data_entrega_execucao': '2026-05-20',
            'data_apresentacao_fiscais': '2026-05-25',
            'data_apresentacao_gestores': '2026-05-28'
        })
        
        res = self.client.post(url, data=payload, content_type='application/json')
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.json()['success'])

        cal = CalendarioPrestacao.objects.get(ano=2026, mes=5)
        self.assertEqual(str(cal.data_entrega_execucao), '2026-05-20')

    def test_exportar_execucao_csv(self):
        """Testa exportação em CSV do relatório de controle de execução."""
        ControleExecucao.objects.create(
            contrato=self.contrato,
            agente=self.agente,
            mes_referencia=5,
            ano_referencia=2026,
            status='ok'
        )

        self.client.login(username="auditor1", password="password123")
        url = reverse('exportar_execucao_csv')
        res = self.client.get(url, {'mes': 5, 'ano': 2026})
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res['Content-Type'], 'text/csv; charset=utf-8')
        content = res.content.decode('utf-8-sig')
        self.assertIn("55/2026", content)
        self.assertIn("Conformidade (OK!)", content)

    def test_status_correcao_e_observacao_aci_na_lista_e_formulario(self):
        """Verifica se o status 'correção' e o texto de observação da ACI são exibidos na lista e no formulário."""
        from contratos.models import ApontamentoCorrecaoExecucao
        
        hoje = date.today()
        primeiro_dia_mes_atual = hoje.replace(day=1)
        ultimo_dia_mes_anterior = primeiro_dia_mes_atual - timedelta(days=1)

        ctrl = ControleExecucao.objects.create(
            contrato=self.contrato,
            agente=self.agente,
            mes_referencia=ultimo_dia_mes_anterior.month,
            ano_referencia=ultimo_dia_mes_anterior.year,
            status='correcao'
        )
        ApontamentoCorrecaoExecucao.objects.create(
            controle=ctrl,
            autor=self.user_auditor,
            descricao="Inconsistência nos valores das faturas apresentadas."
        )

        # 1. Verificar na página de seleção de contratos (fiscais.html)
        res_fiscais = self.client.get(reverse('portal_execucao_fiscais'))
        self.assertEqual(res_fiscais.status_code, 200)
        self.assertContains(res_fiscais, "correção")
        self.assertContains(res_fiscais, "Inconsistência nos valores das faturas apresentadas.")

        # 2. Verificar no formulário do fiscal (formulario.html)
        url_form = reverse('formulario_execucao', kwargs={'contrato_id': self.contrato.id})
        res_form = self.client.get(url_form)
        self.assertEqual(res_form.status_code, 200)
        self.assertContains(res_form, "Observação / Apontamentos da ACI após Análise")
        self.assertContains(res_form, "Inconsistência nos valores das faturas apresentadas.")

