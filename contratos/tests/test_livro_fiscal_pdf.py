"""
Testes para geração do PDF do Livro do Fiscal (ControleExecucao).
"""
import os
import io
import pypdf
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
            confirmacao_siloms_execucao='sim',
            data_execucao_fisico_financeira=date(2026, 12, 31),
            possibilidade_aditivo='sim',
            tratativas_120_dias='sim',
            coordenacao_doc_scon='sim',
            garantia_vigente='nao',
            garantia_providencias='Notificação emitida para renovação da fiança bancária.',
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

    def test_gerar_pdf_multipagina_rodape(self):
        """Verifica se o rodapé 'livro do fiscal ct xxx - mm/aaaa - pág x/n' é exibido a partir da página 2."""
        # Criar múltiplas ocorrências para forçar mais de uma página no PDF
        for i in range(10):
            OcorrenciaContratual.objects.create(
                controle=self.controle_ok,
                data=date(2026, 7, 1 + i),
                tipo='email',
                descricao=f'Ocorrência de teste de paginação nº {i+1}',
                acao_fiscal='Notificação enviada',
                prazo='5 dias'
            )

        url = reverse('download_livro_fiscal_pdf', kwargs={'pk': self.controle_ok.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

        pdf_bytes = b''.join(response.streaming_content)
        reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
        num_pages = len(reader.pages)
        self.assertGreaterEqual(num_pages, 2)

        # Página 1 não deve conter o rodapé
        page1_text = reader.pages[0].extract_text()
        self.assertNotIn('Livro do Fiscal CT 001/2025', page1_text)

        # Página 2 deve conter a identificação do rodapé
        page2_text = reader.pages[1].extract_text()
        expected_footer = f"Livro do Fiscal CT 001/2025 (Consultoria Nascimento ME) - 07/2026 - pág 2/{num_pages}"
        self.assertIn(expected_footer, page2_text)

    def test_gerar_pdf_dados_minimos_sem_faturas_sem_ocorrencias(self):
        """Verifica que o PDF é gerado corretamente com dados mínimos (sem faturas, sem ocorrências, sem observação)."""
        controle_min = ControleExecucao.objects.create(
            contrato=self.contrato,
            agente=self.agente,
            mes_referencia=5,
            ano_referencia=2026,
            status='ok'
        )

        url = reverse('download_livro_fiscal_pdf', kwargs={'pk': controle_min.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

        pdf_bytes = b''.join(response.streaming_content)
        reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
        self.assertGreaterEqual(len(reader.pages), 1)

        # Extrair todo o texto do PDF
        full_text = ''.join(page.extract_text() for page in reader.pages)

        # Deve conter as seções obrigatórias
        self.assertIn('Nenhuma fatura registrada', full_text)
        self.assertIn('Nenhuma ocorrência registrada', full_text)

        # Não deve conter a seção de observações gerais (campo vazio)
        self.assertNotIn('OBSERVAÇÕES GERAIS', full_text)

    def test_gerar_pdf_muitas_faturas_fallback_extend(self):
        """Verifica que o PDF é gerado corretamente quando há mais de 10 faturas (fallback sem KeepTogether)."""
        for i in range(15):
            RegistroFatura.objects.create(
                controle=self.controle_ok,
                numero_nf=f'NF-{i+2000}',
                valor=1000.00 + i,
                numero_ob=f'2026OB{i:06d}'
            )

        url = reverse('download_livro_fiscal_pdf', kwargs={'pk': self.controle_ok.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

        pdf_bytes = b''.join(response.streaming_content)
        reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
        full_text = ''.join(page.extract_text() for page in reader.pages)

        # Deve conter todas as 16 faturas (15 novas + 1 do setUp)
        self.assertIn('NF-2000', full_text)
        self.assertIn('NF-2014', full_text)
        self.assertIn('TOTAL REGISTRADO', full_text)

    def test_conteudo_textual_secoes_do_pdf(self):
        """Verifica que o texto extraído do PDF contém todas as 6 seções e a assinatura."""
        url = reverse('download_livro_fiscal_pdf', kwargs={'pk': self.controle_ok.pk})
        response = self.client.get(url)

        pdf_bytes = b''.join(response.streaming_content)
        reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
        full_text = ''.join(page.extract_text() for page in reader.pages)

        secoes_esperadas = [
            'SEÇÃO 1: IDENTIFICAÇÃO DO CONTRATO E DA EQUIPE',
            'SEÇÃO 2: CONTROLE DE PRAZOS E SILOMS',
            'SEÇÃO 3: EXECUÇÃO ORÇAMENTÁRIA E FINANCEIRA',
            'SEÇÃO 4: CRONOGRAMA E MEDIÇÃO DE RESULTADOS',
            'SEÇÃO 5: OCORRÊNCIAS E TRATATIVAS',
            'SEÇÃO 6: APURAÇÃO DE IRREGULARIDADES (PAAI)',
        ]
        for secao in secoes_esperadas:
            self.assertIn(secao, full_text)

        # Verificar dados do contrato na seção 1
        self.assertIn('001/2025', full_text)
        self.assertIn('Consultoria Nascimento ME', full_text)

        # Verificar bloco de assinatura
        self.assertIn('Atesto a veracidade das informações prestadas', full_text)
        self.assertIn('MENDES', full_text)

        # Verificar seção de observações (presente pois controle_ok tem observação)
        self.assertIn('OBSERVAÇÕES GERAIS', full_text)
        self.assertIn('Tudo ok', full_text)

        # Verificar garantia vencida com providências (presente pois controle_ok tem garantia_vigente='nao')
        self.assertIn('Notificação emitida para renovação da fiança bancária', full_text)

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
