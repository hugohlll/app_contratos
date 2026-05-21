import os
from datetime import date
from django.test import TestCase, Client
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from django.contrib.auth.models import User

from contratos.models import Contrato, Empresa, PrestacaoContas, Agente, PostoGraduacao, Comissao, Integrante, Funcao

class PrestacaoContasTests(TestCase):
    def setUp(self):
        # Configurar ambiente de teste
        self.posto = PostoGraduacao.objects.create(sigla="SGT", descricao="Sargento", senioridade=5)
        self.empresa = Empresa.objects.create(razao_social="Empresa Teste Ltda", cnpj="12345678000199")
        self.agente = Agente.objects.create(
            nome_completo="Joao Silva", 
            nome_de_guerra="Silva", 
            posto=self.posto, 
            saram="1234567"
        )
        self.contrato = Contrato.objects.create(
            numero="10/2026",
            objeto="Serviços de Teste",
            empresa=self.empresa,
            vigencia_inicio=date(2026, 1, 1),
            vigencia_fim=date(2026, 12, 31),
            valor_total=1000.00
        )
        
        # Adicionar o agente a uma comissão ativa
        self.comissao = Comissao.objects.create(
            contrato=self.contrato,
            tipo='FISCALIZACAO',
            ativa=True,
            data_inicio=date(2026, 1, 1)
        )
        self.funcao = Funcao.objects.create(titulo="Fiscal", ordem=1)
        self.integrante = Integrante.objects.create(
            comissao=self.comissao,
            agente=self.agente,
            funcao=self.funcao,
            data_inicio=date(2026, 1, 1),
            portaria_numero="123",
            portaria_data=date(2026, 1, 1)
        )
        
        self.user = User.objects.create_user(username="admin", password="password123")
        self.client = Client()

    def test_upload_prestacao_sem_login(self):
        """O Fical deve conseguir enviar o PDF via formulário público sem estar logado"""
        url = reverse('upload_prestacao', kwargs={'contrato_id': self.contrato.id})
        
        # Simula arquivo PDF válido
        pdf_file = SimpleUploadedFile(
            "teste.pdf",
            b"%PDF-1.4...",
            content_type="application/pdf"
        )
        
        data = {
            'agente': self.agente.id,
            'mes_referencia': 5,
            'ano_referencia': 2026,
            'arquivo': pdf_file,
            'observacao': 'Teste envio'
        }
        
        response = self.client.post(url, data)
        
        # Após salvar deve redirecionar para detalhe_contrato com param ?enviado=1
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.url.endswith("?enviado=1"))
        
        # Verificar se salvou no BD
        self.assertEqual(PrestacaoContas.objects.count(), 1)
        prestacao = PrestacaoContas.objects.first()
        self.assertEqual(prestacao.mes_referencia, 5)
        self.assertEqual(prestacao.ano_referencia, 2026)
        
        # Verificar renomeação do arquivo
        self.assertTrue(prestacao.arquivo.name.startswith("prestacoes/sgt_silva_empresa-teste-ltda_10-2026_05-2026"))
        self.assertTrue(prestacao.arquivo.name.endswith(".pdf"))
        
        # Limpar arquivo gerado no teste
        if prestacao.arquivo and os.path.isfile(prestacao.arquivo.path):
            os.remove(prestacao.arquivo.path)

    def test_upload_substituicao_mesmo_mes(self):
        """O reenvio para o mesmo contrato, ano e mês deve substituir o anterior"""
        # Upload 1
        pdf_file1 = SimpleUploadedFile("arq1.pdf", b"conteudo1", content_type="application/pdf")
        PrestacaoContas.objects.create(
            contrato=self.contrato,
            agente=self.agente,
            mes_referencia=6,
            ano_referencia=2026,
            arquivo=pdf_file1
        )
        self.assertEqual(PrestacaoContas.objects.count(), 1)
        
        # Upload 2 (POST request para simular substituição da view)
        url = reverse('upload_prestacao', kwargs={'contrato_id': self.contrato.id})
        pdf_file2 = SimpleUploadedFile("arq2.pdf", b"conteudo2", content_type="application/pdf")
        
        data = {
            'agente': self.agente.id,
            'mes_referencia': 6,
            'ano_referencia': 2026,
            'arquivo': pdf_file2,
            'observacao': 'Nova versao'
        }
        
        self.client.post(url, data)
        
        # Deve continuar tendo apenas 1 registro no banco
        self.assertEqual(PrestacaoContas.objects.count(), 1)
        prestacao = PrestacaoContas.objects.first()
        self.assertEqual(prestacao.observacao, 'Nova versao')

    def test_dashboard_requer_login(self):
        """Dashboard gerencial deve estar protegido"""
        url = reverse('dashboard_prestacao')
        response = self.client.get(url)
        # Redireciona para login
        self.assertEqual(response.status_code, 302)
        
        # Login
        self.client.login(username="admin", password="password123")
        response2 = self.client.get(url)
        # Sucesso
        self.assertEqual(response2.status_code, 200)
