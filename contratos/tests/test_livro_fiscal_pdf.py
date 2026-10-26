"""
Testes para geração do PDF do Livro do Fiscal (NPA 009/SCON/2025) e Notificação Anexo D.
"""
import io
import pypdf
from datetime import date
from django.test import TestCase, Client, override_settings
from django.urls import reverse
from django.utils import timezone
from django.contrib.auth.models import User
from django.contrib.messages import get_messages
from contratos.services.notificacao import NotificacaoService, BaseNotificacaoGenerator

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
        self.assertIn('Número do Livro:', full_text)
        self.assertNotIn('Número do Livro / Ano:', full_text)
        # Cabeçalhos de seção sem numeração
        self.assertIn('TERMO DE ABERTURA E IDENTIFICAÇÃO DO CONTRATO', full_text)
        self.assertNotIn('1. TERMO DE ABERTURA', full_text)
        self.assertIn('REGISTRO DE OCORRÊNCIAS DA FISCALIZAÇÃO', full_text)
        self.assertNotIn('3. REGISTRO DE OCORRÊNCIAS', full_text)
        self.assertIn('OBSERVAÇÕES E APONTAMENTOS COMPLEMENTARES', full_text)
        # Dados do preposto retirados do PDF
        self.assertNotIn('Preposto Aceito da Contratada:', full_text)
        self.assertNotIn('Carlos Eduardo Preposto', full_text)
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
        self.assertIn('Maj JULIO MENDES', clean_text)
        self.assertIn('Fiscal Responsável pelo Contrato — GAP-BR', clean_text)
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

    def test_gerar_notificacao_anexo_d_pdf_suspensa_por_padrao(self):
        """Verifica que a emissão automática de Notificação Oficial está desabilitada por padrão."""
        url = reverse('download_notificacao_anexo_d_pdf', kwargs={'pk': self.ocorrencia1.pk})
        response = self.client.get(url)

        # Redireciona com aviso informativo quando suspensa
        self.assertEqual(response.status_code, 302)
        self.assertIn(f"/execucao/{self.controle_ok.pk}/", response.url)

    @override_settings(NOTIFICACAO_AUTOMATICA_HABILITADA=True)
    def test_gerar_notificacao_anexo_d_pdf_habilitada(self):
        """Verifica a geração do PDF da Notificação Oficial quando habilitada no sistema."""
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
        self.assertIn('RECIBO E CIÊNCIA DO NOTIFICADO', clean_text)
        self.assertIn('TERMO DE DECLARAÇÃO E CERTIDÃO DE RECUSA DE ASSINATURA', clean_text)
        self.assertIn('1ª TESTEMUNHA', clean_text)
        self.assertIn('2ª TESTEMUNHA', clean_text)

    def test_notificacao_service_modularidade_e_extensibilidade(self):
        """Testa o serviço desacoplado de notificações e capacidade de plugar novo modelo."""
        # 1. Por padrão desabilitado
        self.assertFalse(NotificacaoService.is_habilitada())

        # 2. Obtenção do gerador legado
        gen_legado = NotificacaoService.get_generator('legado')
        self.assertEqual(gen_legado.versao, 'anexo_d_npa009')

        # 3. Geração direta permitindo desabilitado
        buffer, filename = NotificacaoService.gerar_documento(self.ocorrencia1, permitir_desabilitado=True)
        self.assertTrue(filename.startswith('notificacao_anexo_d_npa009_'))
        self.assertGreater(buffer.getbuffer().nbytes, 1000)

        # 4. Bloqueio caso tente gerar com serviço desabilitado e sem override
        with self.assertRaises(PermissionError):
            NotificacaoService.gerar_documento(self.ocorrencia1, permitir_desabilitado=False)

        # 5. Extensibilidade: plugar um novo modelo de notificação customizado
        class MockNovoModeloGenerator(BaseNotificacaoGenerator):
            versao = "novo_modelo_2026"
            nome_modelo = "Novo Modelo 2026"

            def gerar_pdf(self, oc):
                buf = io.BytesIO()
                buf.write(b"%PDF-1.4 Mock Novo Modelo")
                buf.seek(0)
                return buf

        NotificacaoService.registrar_generator('novo_modelo_teste', MockNovoModeloGenerator)
        gen_novo = NotificacaoService.get_generator('novo_modelo_teste')
        self.assertEqual(gen_novo.versao, 'novo_modelo_2026')
        buf_novo, fn_novo = NotificacaoService.gerar_documento(self.ocorrencia1, tipo='novo_modelo_teste', permitir_desabilitado=True)
        self.assertEqual(fn_novo, f"notificacao_novo_modelo_2026_001-gap-br-2026.pdf")
        self.assertEqual(buf_novo.read(), b"%PDF-1.4 Mock Novo Modelo")

    def test_pdf_sem_rotulo_tempestividade(self):
        """Verifica se o PDF do Livro do Fiscal não expõe a classificação de tempestividade."""
        url = reverse('download_livro_fiscal_pdf', kwargs={'pk': self.controle_ok.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

        pdf_bytes = b''.join(response.streaming_content)
        reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
        full_text = ''.join(page.extract_text() for page in reader.pages)

        self.assertNotIn('Tempestividade do Registro:', full_text)

    def test_pdf_modular_preposto(self):
        """Verifica se os dados do preposto não aparecem no PDF por padrão, mas aparecem se o módulo for ativado."""
        from contratos.services.execucao_modulos import ModulosLivroFiscalService

        # 1. Por padrão: desabilitado, preposto não aparece
        url = reverse('download_livro_fiscal_pdf', kwargs={'pk': self.controle_ok.pk})
        response = self.client.get(url)
        pdf_bytes = b''.join(response.streaming_content)
        reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
        full_text = ''.join(page.extract_text() for page in reader.pages)
        self.assertNotIn('Preposto Aceito da Contratada:', full_text)
        self.assertNotIn('Carlos Eduardo Preposto', full_text)

        # 2. Se reativado modularmente: preposto aparece
        try:
            ModulosLivroFiscalService.BLOCO_PREPOSTO_HABILITADO = True
            res_ativado = self.client.get(url)
            pdf_bytes_ativado = b''.join(res_ativado.streaming_content)
            reader_ativado = pypdf.PdfReader(io.BytesIO(pdf_bytes_ativado))
            full_text_ativado = ''.join(page.extract_text() for page in reader_ativado.pages)
            self.assertIn('Preposto Aceito da Contratada:', full_text_ativado)
            self.assertIn('Carlos Eduardo Preposto', full_text_ativado)
        finally:
            ModulosLivroFiscalService.BLOCO_PREPOSTO_HABILITADO = False

    def test_download_nao_logado_bloqueado_quando_nao_ok(self):
        """Usuário não logado não pode baixar PDF de Livro em rascunho, entregue ou correção."""
        for st in ['rascunho', 'entregue', 'correcao']:
            ctrl = ControleExecucao.objects.create(
                contrato=self.contrato,
                agente=self.agente,
                mes_referencia=8,
                ano_referencia=2026,
                status=st
            )
            url = reverse('download_livro_fiscal_pdf', kwargs={'pk': ctrl.pk})
            response = self.client.get(url, follow=False)

            self.assertEqual(response.status_code, 302, f"Deveria redirecionar para status '{st}'")
            expected_redirect = reverse('formulario_execucao', kwargs={'contrato_id': self.contrato.id})
            self.assertIn(expected_redirect, response.url)

            # Verifica mensagem de aviso
            response_followed = self.client.get(url, follow=True)
            msgs = list(get_messages(response_followed.wsgi_request))
            self.assertTrue(
                any("O download do Livro do Fiscal só está disponível após a validação e conformidade pela ACI." in str(m) for m in msgs),
                f"Mensagem de aviso ausente para status '{st}'"
            )

    def test_download_logado_aci_permitido_em_qualquer_status(self):
        """Usuário autenticado (ACI / Admin) pode baixar PDF em qualquer status."""
        user = User.objects.create_user(username='auditor_aci_teste', password='pwd')
        self.client.force_login(user)

        for st in ['rascunho', 'entregue', 'correcao', 'ok']:
            ctrl = ControleExecucao.objects.create(
                contrato=self.contrato,
                agente=self.agente,
                mes_referencia=9,
                ano_referencia=2026,
                status=st
            )
            url = reverse('download_livro_fiscal_pdf', kwargs={'pk': ctrl.pk})
            response = self.client.get(url)

            self.assertEqual(response.status_code, 200, f"Deveria permitir download logado para status '{st}'")
            self.assertEqual(response['Content-Type'], 'application/pdf')

    def test_formulario_exibicao_botao_download_condicional(self):
        """Formulário exibe botão desabilitado com tooltip para fiscal e habilitado para ACI ou status 'ok'."""
        ctrl_entregue = ControleExecucao.objects.create(
            contrato=self.contrato,
            agente=self.agente,
            mes_referencia=10,
            ano_referencia=2026,
            status='entregue'
        )
        url_form = reverse('formulario_execucao', kwargs={'contrato_id': self.contrato.id}) + f"?mes=10&ano=2026"

        # 1. Não logado com status entregue: botão desabilitado com tooltip informativo
        self.client.logout()
        res_anonimo = self.client.get(url_form)
        self.assertEqual(res_anonimo.status_code, 200)
        self.assertContains(res_anonimo, 'Download disponível apenas após conformidade da ACI')
        self.assertContains(res_anonimo, '<button type="button" class="btn btn-sm btn-outline-secondary fw-bold" disabled')
        # Não deve haver link <a> para download
        download_url = reverse('download_livro_fiscal_pdf', kwargs={'pk': ctrl_entregue.pk})
        self.assertNotContains(res_anonimo, f'href="{download_url}')

        # 2. Não logado na tela de prestação com status 'ok': botão de download liberado
        ctrl_entregue.status = 'ok'
        ctrl_entregue.save()
        url_prestacao_ok = reverse('upload_prestacao', kwargs={'contrato_id': self.contrato.id}) + f"?mes=10&ano=2026"
        res_anonimo_ok = self.client.get(url_prestacao_ok)
        self.assertEqual(res_anonimo_ok.status_code, 200)
        self.assertContains(res_anonimo_ok, f'href="{download_url}')

        # 3. Logado na ACI com status não-ok no formulário: botão ativo com link para download
        ctrl_entregue.status = 'entregue'
        ctrl_entregue.save()
        user = User.objects.create_user(username='auditor_form_teste', password='pwd')
        self.client.force_login(user)
        res_logado = self.client.get(url_form)
        self.assertEqual(res_logado.status_code, 200)
        self.assertContains(res_logado, f'href="{download_url}')

    def test_upload_contrato_aviso_aguardando_conformidade(self):
        """Tela de envio de prestação exibe aviso de conformidade pendente quando status é 'entregue'."""
        ControleExecucao.objects.create(
            contrato=self.contrato,
            agente=self.agente,
            mes_referencia=11,
            ano_referencia=2026,
            status='entregue'
        )
        url_prestacao = reverse('upload_prestacao', kwargs={'contrato_id': self.contrato.id}) + f"?mes=11&ano=2026"
        res = self.client.get(url_prestacao)
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, 'Aguardando ateste de conformidade da ACI para liberação do documento oficial do SILOMS.')



