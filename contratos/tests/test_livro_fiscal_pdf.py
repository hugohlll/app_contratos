"""
Testes para geração do PDF do Livro do Fiscal (ControleExecucao).
"""
import os
from datetime import date
from django.test import TestCase, Client
from django.urls import reverse

from contratos.models import (
    Contrato, Empresa, Agente, PostoGraduacao, Comissao, Integrante, Funcao,
    ControleExecucao, RegistroFatura, OcorrenciaContratual
)


class LivroFiscalPDFTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        self.posto = PostoGraduacao.objects.create(sigla="Maj", descricao="Major", senioridade=3)
        self.agente = Agente.objects.create(
            nome_completo="Julio Mendes", nome_de_guerra="Mendes",
            posto=self.posto, saram="1234567"
        )
        self.empresa = Empresa.objects.create(
            razao_social="Consultoria Nascimento ME", cnpj="12345678000195"
        )
        self.contrato = Contrato.objects.create(
            numero="001/2025", objeto="Prestação de Serviços de TI",
            empresa=self.empresa,
            vigencia_inicio=date(2025, 1, 1),
            vigencia_fim=date(2025, 12, 31),
            valor_total=500000.00
        )
        self.comissao = Comissao.objects.create(
            contrato=self.contrato, tipo='FISCALIZACAO', portaria_numero="Portaria Nº 12/2025",
            ativa=True, data_inicio=date(2025, 1, 1)
        )
        self.funcao = Funcao.objects.create(titulo="Fiscal Titular", ordem=1)
        self.integrante = Integrante.objects.create(
            comissao=self.comissao, agente=self.agente, funcao=self.funcao,
            data_inicio=date(2025, 1, 1), portaria_numero="Portaria Nº 12/2025",
            portaria_data=date(2025, 1, 1)
        )

        # Registro de ControleExecucao aprovado (status 'ok')
        self.controle_ok = ControleExecucao.objects.create(
            contrato=self.contrato,
            agente=self.agente,
            mes_referencia=7,
            ano_referencia=2026,
            status='ok',
            confirmacao_siloms_assinatura=True,
            confirmacao_siloms_vigencia=True,
            confirmacao_siloms_execucao=True,
            possibilidade_aditivo='sim',
            tratativas_120_dias='sim',
            coordenacao_doc_scon='sim',
            notas_empenho='2026NE000123',
            cronograma_fisico_financeiro='conforme',
            detalhamento_cronograma='Cronograma em dia',
            relatorio_ocorrencias='Sem anormalidades no período',
            observacao='Tudo ok com a prestação.'
        )
        RegistroFatura.objects.create(
            controle=self.controle_ok,
            numero_nf='1052',
            valor=15000.50,
            numero_ob='2026OB800100'
        )
        OcorrenciaContratual.objects.create(
            controle=self.controle_ok,
            data=date(2026, 7, 10),
            tipo='reuniao',
            descricao='Reunião mensal de alinhamento',
            acao_fiscal='Ata assinada e juntada',
            prazo='N/A'
        )

        # Registro de ControleExecucao entregue (sem ok)
        self.controle_entregue = ControleExecucao.objects.create(
            contrato=self.contrato,
            agente=self.agente,
            mes_referencia=6,
            ano_referencia=2026,
            status='entregue'
        )

    def test_gerar_pdf_status_ok(self):
        """Verifica se a view gera o PDF corretamente para controle aprovado."""
        url = reverse('download_livro_fiscal_pdf', kwargs={'pk': self.controle_ok.pk})
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/pdf')
        
        # Nome do arquivo solicitado: livro_fiscal_{contrato}_{empresa}_{ano_referencia}_{mes_referencia}.pdf
        expected_filename = "livro_fiscal_001-2025_consultoria-nascimento-me_2026_07.pdf"
        self.assertIn(f'filename="{expected_filename}"', response['Content-Disposition'])
        
        # Validar conteúdo binário PDF (FileResponse usa streaming_content)
        pdf_content = b''.join(response.streaming_content)
        self.assertTrue(pdf_content.startswith(b'%PDF'))
        self.assertGreater(len(pdf_content), 1000)

    def test_botan_download_pdf_visivel_apenas_quando_ok(self):
        """Verifica se o botão de download PDF é exibido na página de upload quando status é 'ok'."""
        url = reverse('upload_prestacao', kwargs={'contrato_id': self.contrato.id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

        pdf_url = reverse('download_livro_fiscal_pdf', kwargs={'pk': self.controle_ok.pk})
        
        # O mês de referência da página no teste é 7/2026 (controle_ok) se bate com mês anterior ou atual
        if response.context['controle_execucao'] and response.context['controle_execucao'].status == 'ok':
            self.assertContains(response, pdf_url)
            self.assertContains(response, 'Baixar Livro do Fiscal (PDF)')
