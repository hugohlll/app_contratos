"""
Testes para geração do PDF do Livro do Fiscal (NPA 009/SCON/2025) e Notificação Anexo D.
"""
import io
import pypdf
from datetime import date
from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone

from contratos.models import (
    Contrato, Empresa, Agente, PostoGraduacao, Comissao, Integrante, Funcao,
    ControleExecucao, OcorrenciaContratual
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
            tipo="DESPESA",
            vigencia_inicio=date(2025, 1, 1),
            vigencia_fim=date(2025, 12, 31),
            valor_total=500000.00
        )
        self.comissao = Comissao.objects.create(
            contrato=self.contrato, tipo='FISCALIZACAO', portaria_numero="Portaria Nº 12/2025",
            boletim_numero="BInt 45/2025", boletim_data=date(2025, 1, 5),
            ativa=True, data_inicio=date(2025, 1, 1)
        )
        self.funcao = Funcao.objects.create(titulo="Fiscal Titular", ordem=1)
        self.integrante = Integrante.objects.create(
            comissao=self.comissao, agente=self.agente, funcao=self.funcao,
            data_inicio=date(2025, 1, 1), portaria_numero="Portaria Nº 12/2025",
            portaria_data=date(2025, 1, 1)
        )

        # Registro de ControleExecucao aprovado (status 'ok') conforme NPA 009
        self.controle_ok = ControleExecucao.objects.create(
            contrato=self.contrato,
            agente=self.agente,
            mes_referencia=7,
            ano_referencia=2026,
            status='ok',
            omap='GAP-BR',
            unidade_gestora='120006 - GAP-BR',
            preposto_nome='Carlos Eduardo Preposto',
            preposto_cargo='Gerente de Operações',
            preposto_cpf='123.456.789-00',
            preposto_telefone='(61) 98765-4321',
            preposto_email='preposto@empresa.com.br',
            sem_ocorrencias_periodo=False,
            observacao='Execução transcorrendo sob acompanhamento contínuo.'
        )

        self.ocorrencia1 = OcorrenciaContratual.objects.create(
            controle=self.controle_ok,
            data_hora=timezone.now(),
            local='Prédio do Comando',
            tipo='TECNICA',
            descricao='Atraso injustificado na entrega do relatório mensal.',
            dispositivo_violado='Cláusula 8.2 do Contrato',
            evidencias='Comunicação eletrônica e-PAG 67100.001/2026',
            notificacao_emitida=True,
            notificacao_numero='001/GAP-BR/2026',
            prazo_dias_uteis=5,
            ciencia_preposto='assinado',
            tramite_arc=False,
            status_ocorrencia='saneamento',
            acao_fiscal='Notificada a empresa para saneamento em 5 dias úteis.'
        )

    def test_gerar_pdf_status_ok(self):
        """Verifica se a view gera o PDF corretamente para controle aprovado."""
        url = reverse('download_livro_fiscal_pdf', kwargs={'pk': self.controle_ok.pk})
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/pdf')

        # Nomenclatura gerada
        self.assertIn('livro_fiscal_001-2025_2026_07.pdf', response['Content-Disposition'])

        pdf_content = b''.join(response.streaming_content)
        self.assertTrue(pdf_content.startswith(b'%PDF'))
        self.assertGreater(len(pdf_content), 1000)

    def test_conteudo_textual_secoes_npa009(self):
        """Verifica que o texto extraído do PDF contém os termos da NPA 009, UG 120006 e declaração oficial."""
        url = reverse('download_livro_fiscal_pdf', kwargs={'pk': self.controle_ok.pk})
        response = self.client.get(url)

        pdf_bytes = b''.join(response.streaming_content)
        reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
        full_text = ''.join(page.extract_text() for page in reader.pages)

        # Cabeçalho e Identificação
        self.assertIn('GRUPAMENTO DE APOIO DE BRASÍLIA', full_text)
        self.assertIn('LIVRO DE REGISTRO DE OCORRÊNCIAS', full_text)
        self.assertIn('07/2026/D/001/2025', full_text)
        self.assertIn('Consultoria Nascimento ME', full_text)
        self.assertIn('Carlos Eduardo Preposto', full_text)
        self.assertNotIn('Unidade Gestora (UG / Gestão):', full_text)
        self.assertNotIn('Processo Adm. de Gestão (PAG / e-PAG):', full_text)
        self.assertNotIn('Fundamentação Normativa:', full_text)

        # Ocorrência registrada
        self.assertIn('Atraso injustificado na entrega do relatório mensal', full_text)
        self.assertIn('001/GAP-BR/2026', full_text)

        # Declaração Oficial NPA 009
        clean_text = ' '.join(full_text.split())
        self.assertIn('Declaro, sob as penas da lei e regulamentos militares aplicáveis', clean_text)
        self.assertIn('art. 117, § 1º da Lei nº 14.133/2021', clean_text)
        self.assertIn('NPA 009/SCON/2025 do GAP-BR', clean_text)
        self.assertIn('MENDES', clean_text)
        self.assertIn('(datado e assinado eletronicamente)', clean_text)

    def test_gerar_pdf_declaracao_conformidade_sem_ocorrencias(self):
        """Verifica que o PDF exibe a declaração de conformidade quando não houver ocorrências."""
        controle_sem_oc = ControleExecucao.objects.create(
            contrato=self.contrato,
            agente=self.agente,
            mes_referencia=5,
            ano_referencia=2026,
            status='ok',
            sem_ocorrencias_periodo=True
        )

        url = reverse('download_livro_fiscal_pdf', kwargs={'pk': controle_sem_oc.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

        pdf_bytes = b''.join(response.streaming_content)
        reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
        full_text = ''.join(page.extract_text() for page in reader.pages)

        self.assertIn('DECLARAÇÃO DE CONFORMIDADE NO PERÍODO', full_text)
        self.assertIn('estrita conformidade', full_text)

    def test_gerar_pdf_multipagina_rodape(self):
        """Verifica se o rodapé com numeração sequencial é exibido a partir da página 2."""
        for i in range(12):
            OcorrenciaContratual.objects.create(
                controle=self.controle_ok,
                data_hora=timezone.now(),
                local=f'Setor Operacional {i+1}',
                tipo='TECNICA',
                descricao=f'Ocorrência de paginação nº {i+1} com descrição detalhada de serviço.',
                dispositivo_violado=f'Item {i+1} do Termo de Referência',
                status_ocorrencia='aberto'
            )

        url = reverse('download_livro_fiscal_pdf', kwargs={'pk': self.controle_ok.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

        pdf_bytes = b''.join(response.streaming_content)
        reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
        num_pages = len(reader.pages)
        self.assertGreaterEqual(num_pages, 2)

        page2_text = reader.pages[1].extract_text()
        self.assertIn('Livro do Fiscal nº 07/2026/D/001/2025', page2_text)

    def test_gerar_notificacao_anexo_d_pdf(self):
        """Verifica a geração do PDF da Notificação Oficial (Anexo D da NPA 009) com 2 testemunhas."""
        url = reverse('download_notificacao_anexo_d_pdf', kwargs={'pk': self.ocorrencia1.pk})
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/pdf')

        pdf_bytes = b''.join(response.streaming_content)
        reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
        full_text = ''.join(page.extract_text() for page in reader.pages)
        clean_text = ' '.join(full_text.split())

        # Elementos obrigatórios do Anexo D
        self.assertIn('NOTIFICAÇÃO DE OCORRÊNCIA', clean_text)
        self.assertIn('001/GAP-BR/2026', clean_text)
        self.assertIn('(CINCO) DIAS ÚTEIS', clean_text)
        self.assertIn('RECEIBO E CIÊNCIA DO NOTIFICADO', clean_text)
        self.assertIn('TERMO DE DECLARAÇÃO E CERTIDÃO DE RECUSA DE ASSINATURA', clean_text)
        self.assertIn('1ª TESTEMUNHA', clean_text)
        self.assertIn('2ª TESTEMUNHA', clean_text)

    def test_pdf_contem_auditoria_tempestividade(self):
        """Verifica se o PDF do Livro do Fiscal inclui a linha de auditoria de tempestividade."""
        url = reverse('download_livro_fiscal_pdf', kwargs={'pk': self.controle_ok.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

        pdf_bytes = b''.join(response.streaming_content)
        reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
        full_text = ''.join(page.extract_text() for page in reader.pages)

        self.assertIn('Tempestividade do Registro:', full_text)
        self.assertIn('lançado no sistema em', full_text)

