import json
from datetime import date
from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User, Group
from django.core.files.uploadedfile import SimpleUploadedFile

from contratos.models import Contrato, Empresa, PrestacaoContas, Agente, PostoGraduacao, Comissao, ApontamentoCorrecao

class ApontamentoCorrecaoTests(TestCase):
    """Suíte de testes automatizados para a funcionalidade de Apontamentos de Correção."""

    def setUp(self):
        self.posto = PostoGraduacao.objects.create(sigla="CB", descricao="Cabo", senioridade=8)
        self.empresa = Empresa.objects.create(razao_social="Alpha Serviços SA", cnpj="11222333000181")
        self.agente = Agente.objects.create(
            nome_completo="Carlos Pereira", nome_de_guerra="Pereira",
            posto=self.posto, saram="7654321"
        )
        self.contrato = Contrato.objects.create(
            numero="20/2026", objeto="Manutenção Predial",
            empresa=self.empresa,
            vigencia_inicio=date(2026, 1, 1),
            vigencia_fim=date(2026, 12, 31),
            valor_total=50000.00
        )
        self.comissao = Comissao.objects.create(
            contrato=self.contrato, tipo='FISCALIZACAO',
            ativa=True, data_inicio=date(2026, 1, 1)
        )
        
        pdf_content = b"%PDF-1.4 test content"
        pdf = SimpleUploadedFile("pc.pdf", pdf_content, content_type="application/pdf")
        
        self.prestacao = PrestacaoContas.objects.create(
            contrato=self.contrato, agente=self.agente,
            mes_referencia=5, ano_referencia=2026, arquivo=pdf,
            status='entregue'
        )

        # Configurar grupo e usuários
        self.grupo_auditores, _ = Group.objects.get_or_create(name='Auditores')
        self.user_auditor = User.objects.create_user(username="auditor_test", password="pass123")
        self.user_auditor.groups.add(self.grupo_auditores)
        self.client = Client()

    def test_model_apontamento_creation(self):
        """Verifica se a criação direta do model ApontamentoCorrecao funciona com todos os campos."""
        apontamento = ApontamentoCorrecao.objects.create(
            prestacao=self.prestacao,
            autor=self.user_auditor,
            descricao="Falta assinatura no relatório."
        )
        self.assertEqual(ApontamentoCorrecao.objects.count(), 1)
        self.assertEqual(apontamento.prestacao, self.prestacao)
        self.assertEqual(apontamento.autor, self.user_auditor)
        self.assertEqual(apontamento.descricao, "Falta assinatura no relatório.")
        self.assertIsNotNone(apontamento.data_registro)
        self.assertIn("PC 20/2026 - 05/2026", str(apontamento))

    def test_correcao_sem_justificativa_retorna_erro_ajax(self):
        """Mudar status para correção sem enviar justificativa deve retornar erro 400 via AJAX."""
        self.client.login(username="auditor_test", password="pass123")
        url = reverse('alterar_status_prestacao', kwargs={'pk': self.prestacao.id, 'novo_status': 'correcao'})
        
        # Envio AJAX sem justificativa no body JSON
        response = self.client.post(
            url,
            data=json.dumps({}),
            content_type='application/json',
            HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        )
        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertFalse(data['success'])
        self.assertIn("A justificativa de correção é obrigatória", data['error'])
        
        # O status da prestação de contas não deve ter mudado
        self.prestacao.refresh_from_db()
        self.assertEqual(self.prestacao.status, 'entregue')

    def test_correcao_sem_justificativa_retorna_erro_standard(self):
        """Mudar status para correção sem enviar justificativa via requisição tradicional deve retornar erro."""
        self.client.login(username="auditor_test", password="pass123")
        url = reverse('alterar_status_prestacao', kwargs={'pk': self.prestacao.id, 'novo_status': 'correcao'})
        
        response = self.client.post(url, {})
        self.assertEqual(response.status_code, 302) # Redireciona de volta
        
        # O status não deve ter mudado
        self.prestacao.refresh_from_db()
        self.assertEqual(self.prestacao.status, 'entregue')

    def test_correcao_com_justificativa_sucesso_ajax(self):
        """Mudar status para correção com justificativa válida via AJAX atualiza status e cria apontamento."""
        self.client.login(username="auditor_test", password="pass123")
        url = reverse('alterar_status_prestacao', kwargs={'pk': self.prestacao.id, 'novo_status': 'correcao'})
        
        response = self.client.post(
            url,
            data=json.dumps({'justificativa': 'Assinatura ilegível na pág. 3'}),
            content_type='application/json',
            HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])
        self.assertEqual(data['status'], 'correcao')
        
        # Verifica se o status mudou no banco
        self.prestacao.refresh_from_db()
        self.assertEqual(self.prestacao.status, 'correcao')
        
        # Verifica se o ApontamentoCorrecao foi registrado
        self.assertEqual(ApontamentoCorrecao.objects.count(), 1)
        apt = ApontamentoCorrecao.objects.first()
        self.assertEqual(apt.prestacao, self.prestacao)
        self.assertEqual(apt.descricao, 'Assinatura ilegível na pág. 3')
        self.assertEqual(apt.autor, self.user_auditor)

    def test_acumulo_historico_apontamentos(self):
        """Verifica se múltiplas solicitações de correção acumulam histórico persistente no banco."""
        self.client.login(username="auditor_test", password="pass123")
        url = reverse('alterar_status_prestacao', kwargs={'pk': self.prestacao.id, 'novo_status': 'correcao'})
        
        # Primeira correção
        self.client.post(
            url,
            data=json.dumps({'justificativa': 'Problema no layout'}),
            content_type='application/json',
            HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        )
        
        # Segunda correção (ex: fiscal reenviou e ainda tem problema)
        self.client.post(
            url,
            data=json.dumps({'justificativa': 'Ainda falta o anexo B'}),
            content_type='application/json',
            HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        )
        
        # Deve ter 2 apontamentos registrados
        self.assertEqual(ApontamentoCorrecao.objects.count(), 2)
        apontamentos = ApontamentoCorrecao.objects.all().order_by('data_registro')
        self.assertEqual(apontamentos[0].descricao, 'Problema no layout')
        self.assertEqual(apontamentos[1].descricao, 'Ainda falta o anexo B')



    def test_correcao_usuario_nao_auditor_retorna_403(self):
        """Usuário sem permissão de auditor deve receber 403 ao tentar solicitar correção via AJAX."""
        user_normal = User.objects.create_user(username="fiscal_comum", password="pass123")
        self.client.login(username="fiscal_comum", password="pass123")
        url = reverse('alterar_status_prestacao', kwargs={'pk': self.prestacao.id, 'novo_status': 'correcao'})

        response = self.client.post(
            url,
            data=json.dumps({'justificativa': 'Tentativa não autorizada'}),
            content_type='application/json',
            HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        )
        self.assertEqual(response.status_code, 403)
        data = response.json()
        self.assertFalse(data['success'])

        # Status não deve ter mudado
        self.prestacao.refresh_from_db()
        self.assertEqual(self.prestacao.status, 'entregue')

    def test_status_invalido_retorna_erro_ajax(self):
        """Enviar status inválido via AJAX deve retornar 400 com mensagem de erro."""
        self.client.login(username="auditor_test", password="pass123")
        url = reverse('alterar_status_prestacao', kwargs={'pk': self.prestacao.id, 'novo_status': 'invalido'})

        response = self.client.post(
            url,
            data=json.dumps({}),
            content_type='application/json',
            HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        )
        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertFalse(data['success'])
        self.assertIn("Status inválido", data['error'])

    def test_cascade_delete_apontamentos(self):
        """Ao excluir a PrestacaoContas, todos os ApontamentoCorrecao associados devem ser removidos."""
        ApontamentoCorrecao.objects.create(
            prestacao=self.prestacao,
            autor=self.user_auditor,
            descricao="Apontamento 1"
        )
        ApontamentoCorrecao.objects.create(
            prestacao=self.prestacao,
            autor=self.user_auditor,
            descricao="Apontamento 2"
        )
        self.assertEqual(ApontamentoCorrecao.objects.count(), 2)

        self.prestacao.delete()
        self.assertEqual(ApontamentoCorrecao.objects.count(), 0)

