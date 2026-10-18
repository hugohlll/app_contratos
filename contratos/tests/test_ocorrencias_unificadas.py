import json
from datetime import date, timedelta
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from django.contrib.auth.models import User, Group

from contratos.models import (
    Contrato, Agente, PostoGraduacao, Comissao, Integrante, Empresa, Funcao,
    ControleExecucao, OcorrenciaContratual
)


class OcorrenciasUnificadasTests(TestCase):
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

        # 2. Dados Básicos
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
            numero='99/2026',
            tipo='DESPESA',
            pag='67100.0099/2026-10',
            objeto='Prestação de serviço de manutenção predial',
            empresa=self.empresa,
            vigencia_inicio=date.today() - timedelta(days=180),
            vigencia_fim=date.today() + timedelta(days=365),
            valor_total=100000.00
        )

        self.comissao = Comissao.objects.create(
            contrato=self.contrato,
            portaria_numero='Portaria 100/2026',
            boletim_numero='BInt 10/2026',
            tipo='FISCALIZACAO',
            ativa=True
        )
        Integrante.objects.create(
            comissao=self.comissao,
            agente=self.agente,
            funcao=self.funcao,
            data_inicio=date(2026, 1, 1),
            portaria_data=date(2026, 1, 1)
        )

        hoje = timezone.localtime(timezone.now()).date()
        primeiro_dia_mes = hoje.replace(day=1)
        ultimo_dia_mes_anterior = primeiro_dia_mes - timedelta(days=1)
        self.mes_x = ultimo_dia_mes_anterior.month
        self.ano_x = ultimo_dia_mes_anterior.year
        self.mes_x_plus_1 = hoje.month
        self.ano_x_plus_1 = hoje.year

    def test_tela_ocorrencias_contrato_rendering(self):
        """Verifica se a tela de ocorrências do contrato é exibida com os cards dos meses visíveis."""
        url = reverse('ocorrencias_contrato', kwargs={'contrato_id': self.contrato.id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Registro e Edição de Ocorrências')
        self.assertContains(response, f"{self.mes_x:02d}")
        self.assertContains(response, f"{self.mes_x_plus_1:02d}")
        self.assertContains(response, 'Adicionar Ocorrência')

    def test_salvar_ocorrencia_mes_x_plus_1_cria_rascunho(self):
        """Ocorrência com data no mês corrente (X+1) é roteada para rascunho do mês corrente."""
        hoje = timezone.localtime(timezone.now())
        data_hora_str = hoje.strftime('%Y-%m-%dT%H:%M')

        url = reverse('salvar_ocorrencia')
        payload = {
            'contrato_id': self.contrato.id,
            'data_hora': data_hora_str,
            'local': 'Hangar 01',
            'tipo': 'TECNICA',
            'descricao': 'Falha na execução do serviço técnico no mês corrente.',
            'status_ocorrencia': 'aberto'
        }
        response = self.client.post(
            url,
            data=json.dumps(payload),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])

        # Livro X+1 deve existir com status rascunho
        livro = ControleExecucao.objects.filter(
            contrato=self.contrato,
            mes_referencia=self.mes_x_plus_1,
            ano_referencia=self.ano_x_plus_1
        ).first()
        self.assertIsNotNone(livro)
        self.assertEqual(livro.status, 'rascunho')

        oc = OcorrenciaContratual.objects.get(id=data['ocorrencia']['id'])
        self.assertEqual(oc.controle, livro)
        self.assertEqual(oc.descricao, 'Falha na execução do serviço técnico no mês corrente.')
        self.assertTrue(oc.eh_tempestiva)

    def test_salvar_ocorrencia_mes_x_cria_ou_vincula_a_rascunho(self):
        """Ocorrência com data no mês de referência (X) é roteada para o livro do mês X."""
        data_oc = date(self.ano_x, self.mes_x, 15)
        data_hora_str = f"{data_oc.strftime('%Y-%m-%d')}T10:30"

        url = reverse('salvar_ocorrencia')
        payload = {
            'contrato_id': self.contrato.id,
            'data_hora': data_hora_str,
            'local': 'Portaria Principal',
            'tipo': 'ADMINISTRATIVA',
            'descricao': 'Atraso na entrega de documentos do mês X.',
            'status_ocorrencia': 'saneamento',
            'notificacao_emitida': True,
            'notificacao_numero': '001/2026',
            'prazo_dias_uteis': 5
        }
        response = self.client.post(
            url,
            data=json.dumps(payload),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])

        livro = ControleExecucao.objects.filter(
            contrato=self.contrato,
            mes_referencia=self.mes_x,
            ano_referencia=self.ano_x
        ).first()
        self.assertIsNotNone(livro)
        self.assertEqual(livro.status, 'rascunho')

        oc = OcorrenciaContratual.objects.get(id=data['ocorrencia']['id'])
        self.assertEqual(oc.controle, livro)
        self.assertEqual(oc.notificacao_numero, '001/2026')
        self.assertFalse(oc.eh_tempestiva)  # Registrada no mês X+1 para o mês X

    def test_bloqueio_ocorrencia_mes_x_quando_atestado(self):
        """Se o livro do mês X já foi atestado ('entregue' ou 'ok'), novas ocorrências no mês X são rejeitadas."""
        ControleExecucao.objects.create(
            contrato=self.contrato,
            mes_referencia=self.mes_x,
            ano_referencia=self.ano_x,
            agente=self.agente,
            status='entregue'
        )

        data_oc = date(self.ano_x, self.mes_x, 10)
        data_hora_str = f"{data_oc.strftime('%Y-%m-%d')}T14:00"

        url = reverse('salvar_ocorrencia')
        payload = {
            'contrato_id': self.contrato.id,
            'data_hora': data_hora_str,
            'local': 'Subestação',
            'tipo': 'TECNICA',
            'descricao': 'Tentativa de lançamento em mês já atestado.',
            'status_ocorrencia': 'aberto'
        }
        response = self.client.post(
            url,
            data=json.dumps(payload),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertFalse(data['success'])
        self.assertIn('já foi atestado', data['error'])

    def test_ocorrencia_mes_x_permitida_em_correcao(self):
        """Se o livro do mês X estiver em status 'correcao', é permitido cadastrar/editar ocorrências."""
        livro = ControleExecucao.objects.create(
            contrato=self.contrato,
            mes_referencia=self.mes_x,
            ano_referencia=self.ano_x,
            agente=self.agente,
            status='correcao'
        )

        data_oc = date(self.ano_x, self.mes_x, 12)
        data_hora_str = f"{data_oc.strftime('%Y-%m-%d')}T09:00"

        url = reverse('salvar_ocorrencia')
        payload = {
            'contrato_id': self.contrato.id,
            'data_hora': data_hora_str,
            'local': 'Refeitório',
            'tipo': 'SETORIAL',
            'descricao': 'Ocorrência lançada durante período de correção.',
            'status_ocorrencia': 'aberto'
        }
        response = self.client.post(
            url,
            data=json.dumps(payload),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])
        self.assertEqual(livro.ocorrencias.count(), 1)

    def test_bloqueio_data_anterior_ao_mes_x(self):
        """Data de constatação anterior ao mês X é rejeitada."""
        data_passada = date(self.ano_x, self.mes_x, 1) - timedelta(days=40)
        data_hora_str = f"{data_passada.strftime('%Y-%m-%d')}T10:00"

        url = reverse('salvar_ocorrencia')
        payload = {
            'contrato_id': self.contrato.id,
            'data_hora': data_hora_str,
            'tipo': 'TECNICA',
            'descricao': 'Data muito antiga.',
            'status_ocorrencia': 'aberto'
        }
        response = self.client.post(
            url,
            data=json.dumps(payload),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertFalse(data['success'])
        self.assertIn('já foi atestado', data['error'])

    def test_bloqueio_data_futura(self):
        """Data de constatação no futuro é rejeitada."""
        amanha = timezone.localtime(timezone.now()) + timedelta(days=2)
        data_hora_str = amanha.strftime('%Y-%m-%dT%H:%M')

        url = reverse('salvar_ocorrencia')
        payload = {
            'contrato_id': self.contrato.id,
            'data_hora': data_hora_str,
            'tipo': 'TECNICA',
            'descricao': 'Data futura.',
            'status_ocorrencia': 'aberto'
        }
        response = self.client.post(
            url,
            data=json.dumps(payload),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertFalse(data['success'])
        self.assertIn('não podem estar no futuro', data['error'])

    def test_edicao_ocorrencia_move_entre_livros(self):
        """Editar a data de uma ocorrência move-a automaticamente para o livro correspondente."""
        hoje = timezone.localtime(timezone.now())
        dt_x_plus_1 = hoje.strftime('%Y-%m-%dT%H:%M')
        url = reverse('salvar_ocorrencia')
        res = self.client.post(
            url,
            data=json.dumps({
                'contrato_id': self.contrato.id,
                'data_hora': dt_x_plus_1,
                'tipo': 'TECNICA',
                'descricao': 'Ocorrência inicial.',
                'status_ocorrencia': 'aberto'
            }),
            content_type='application/json'
        )
        oc_id = res.json()['ocorrencia']['id']
        oc = OcorrenciaContratual.objects.get(id=oc_id)
        self.assertEqual(oc.controle.mes_referencia, self.mes_x_plus_1)

        # Edita para o mês X
        data_x = date(self.ano_x, self.mes_x, 18)
        dt_x = f"{data_x.strftime('%Y-%m-%d')}T15:00"
        res_edit = self.client.post(
            url,
            data=json.dumps({
                'contrato_id': self.contrato.id,
                'id': oc_id,
                'data_hora': dt_x,
                'tipo': 'TECNICA',
                'descricao': 'Ocorrência movida para o mês anterior.',
                'status_ocorrencia': 'aberto'
            }),
            content_type='application/json'
        )
        self.assertEqual(res_edit.status_code, 200)
        oc.refresh_from_db()
        self.assertEqual(oc.controle.mes_referencia, self.mes_x)
        self.assertEqual(oc.descricao, 'Ocorrência movida para o mês anterior.')
        self.assertFalse(oc.eh_tempestiva)

    def test_excluir_ocorrencia_livro_editavel_nao_marca_conformidade_automatica(self):
        """Ao excluir a última ocorrência de um livro editável, sem_ocorrencias_periodo não deve ser ativado automaticamente."""
        livro = ControleExecucao.objects.create(
            contrato=self.contrato,
            mes_referencia=self.mes_x,
            ano_referencia=self.ano_x,
            agente=self.agente,
            status='rascunho',
            sem_ocorrencias_periodo=False
        )
        oc = OcorrenciaContratual.objects.create(
            controle=livro,
            data_hora=timezone.now() - timedelta(days=35),
            tipo='TECNICA',
            descricao='Única ocorrência do mês.'
        )

        url_del = reverse('excluir_ocorrencia', kwargs={'pk': oc.id})
        res = self.client.post(url_del)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(livro.ocorrencias.count(), 0)

        livro.refresh_from_db()
        self.assertFalse(livro.sem_ocorrencias_periodo, "Conformidade não pode ser marcada automaticamente.")

    def test_excluir_ocorrencia_livro_atestado_bloqueado(self):
        """Excluir ocorrência de um livro atestado ('entregue' ou 'ok') é bloqueado."""
        livro = ControleExecucao.objects.create(
            contrato=self.contrato,
            mes_referencia=self.mes_x,
            ano_referencia=self.ano_x,
            agente=self.agente,
            status='entregue'
        )
        oc = OcorrenciaContratual.objects.create(
            controle=livro,
            data_hora=timezone.now() - timedelta(days=35),
            tipo='TECNICA',
            descricao='Ocorrência de livro atestado.'
        )

        url_del = reverse('excluir_ocorrencia', kwargs={'pk': oc.id})
        res = self.client.post(url_del)
        self.assertEqual(res.status_code, 403)
        self.assertTrue(OcorrenciaContratual.objects.filter(id=oc.id).exists())

    def test_submissao_livro_preserva_ocorrencias_e_relatorio_sem_rotulo_tempestivo(self):
        """Ao salvar/finalizar o livro em formulario_execucao, ocorrências são preservadas e o relatório não usa 'Tempestivo'."""
        livro = ControleExecucao.objects.create(
            contrato=self.contrato,
            mes_referencia=self.mes_x,
            ano_referencia=self.ano_x,
            agente=self.agente,
            status='rascunho'
        )
        oc = OcorrenciaContratual.objects.create(
            controle=livro,
            data_hora=timezone.now() - timedelta(days=35),
            tipo='ADMINISTRATIVA',
            descricao='Irregularidade mantida no fechamento.'
        )

        url = reverse('formulario_execucao', kwargs={'contrato_id': self.contrato.id})
        payload = {
            'mes_referencia': self.mes_x,
            'ano_referencia': self.ano_x,
            'agente': self.agente.id,
            'omap': 'GAP-BR',
            'unidade_gestora': '120006 - GAP-BR',
            'observacao': 'Tudo verificado.',
            'acao': 'rascunho'
        }
        res = self.client.post(url, payload)
        self.assertEqual(res.status_code, 302)

        livro.refresh_from_db()
        self.assertEqual(livro.ocorrencias.count(), 1)
        self.assertEqual(livro.ocorrencias.first().id, oc.id)
        self.assertIn('Irregularidade mantida no fechamento', livro.relatorio_ocorrencias)
        self.assertNotIn('Tempestivo', livro.relatorio_ocorrencias)
        self.assertNotIn('Extemporâneo', livro.relatorio_ocorrencias)

    def test_pdf_livro_fiscal_sem_campo_tempestividade(self):
        """Geração do PDF do Livro do Fiscal não contém 'Tempestividade do Registro'."""
        livro = ControleExecucao.objects.create(
            contrato=self.contrato,
            mes_referencia=self.mes_x,
            ano_referencia=self.ano_x,
            agente=self.agente,
            status='entregue'
        )
        OcorrenciaContratual.objects.create(
            controle=livro,
            data_hora=timezone.now() - timedelta(days=35),
            tipo='TECNICA',
            descricao='Ocorrência para testar PDF.'
        )

        url = reverse('download_livro_fiscal_pdf', kwargs={'pk': livro.id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/pdf')

        conteudo = b"".join(response.streaming_content).decode('latin1', errors='ignore')
        self.assertNotIn('Tempestividade do Registro', conteudo)

    def test_exportar_csv_inclui_coluna_auditoria_ocorrencias_fora_do_mes(self):
        """Exportação CSV do controle de execução inclui a coluna de auditoria 'Qtd Ocorrências Fora do Mês'."""
        self.client.login(username='auditor1', password='password123')
        livro = ControleExecucao.objects.create(
            contrato=self.contrato,
            mes_referencia=self.mes_x,
            ano_referencia=self.ano_x,
            agente=self.agente,
            status='ok'
        )
        # Ocorrência registrada no mês corrente mas vinculada ao mês anterior (fora do mês)
        OcorrenciaContratual.objects.create(
            controle=livro,
            data_hora=timezone.now() - timedelta(days=35),
            data_registro=timezone.now(),  # mês corrente, diferente de mes_x
            tipo='TECNICA',
            descricao='Ocorrência auditável.'
        )

        url = f"{reverse('exportar_execucao_csv')}?mes={self.mes_x}&ano={self.ano_x}"
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        csv_text = response.content.decode('utf-8-sig')
        self.assertIn('Qtd Ocorrências Fora do Mês', csv_text)
        self.assertIn(';1;', csv_text)
