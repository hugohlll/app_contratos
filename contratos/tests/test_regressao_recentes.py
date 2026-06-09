"""
Testes de regressão para as alterações mais recentes do sistema.

Cobertura:
- Envio de arquivo inválido: erro exibido na mesma tela (sem redirect)
- Mês de referência permanece visível após erro de validação
- Contratos com comissão INATIVA marcados como "Em Risco" no painel
- Registros 'pendente' (fantasma) nunca aparecem na exportação CSV mensal
"""

import os
from datetime import date, timedelta

from django.contrib.auth.models import Group, User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase
from django.urls import reverse

from contratos.models import (
    Agente,
    Comissao,
    Contrato,
    Empresa,
    Funcao,
    Integrante,
    PostoGraduacao,
    PrestacaoContas,
)


# ─────────────────────────────────────────────
# Fixture base compartilhada
# ─────────────────────────────────────────────
class _BaseFixture(TestCase):
    """Cria os objetos mínimos necessários em todos os grupos de teste."""

    def setUp(self):
        self.posto = PostoGraduacao.objects.create(
            sigla="TEN", descricao="Tenente", senioridade=3
        )
        self.empresa = Empresa.objects.create(
            razao_social="Empresa Regressão Ltda", cnpj="00.000.000/0001-00"
        )
        self.contrato = Contrato.objects.create(
            numero="REG/2026",
            tipo="DESPESA",
            empresa=self.empresa,
            objeto="Objeto Regressão",
            vigencia_inicio=date.today(),
            vigencia_fim=date.today() + timedelta(days=365),
            valor_total=50000.00,
        )
        self.agente = Agente.objects.create(
            nome_completo="Fiscal Teste",
            nome_de_guerra="Teste",
            posto=self.posto,
            saram="7654321",
        )
        self.funcao = Funcao.objects.create(titulo="Fiscal", ordem=1)
        self.client = Client()

    def _criar_auditor(self, username="auditor_reg"):
        grupo, _ = Group.objects.get_or_create(name="Auditores")
        user = User.objects.create_user(username=username, password="senha123")
        user.groups.add(grupo)
        return user

    def _criar_comissao_ativa_com_fiscal(self):
        comissao = Comissao.objects.create(
            contrato=self.contrato,
            tipo="FISCALIZACAO",
            ativa=True,
            data_inicio=date.today(),
        )
        Integrante.objects.create(
            comissao=comissao,
            agente=self.agente,
            funcao=self.funcao,
            data_inicio=date.today(),
            portaria_numero="000",
            portaria_data=date.today(),
        )
        return comissao


# ─────────────────────────────────────────────
# 1. Erros de validação no upload de arquivo
# ─────────────────────────────────────────────
class UploadArquivoInvalidoTests(_BaseFixture):
    """Cobre o comportamento após a refatoração que eliminou o redirect em caso de erro."""

    def setUp(self):
        super().setUp()
        self._criar_comissao_ativa_com_fiscal()
        self.url = reverse("upload_prestacao", kwargs={"contrato_id": self.contrato.id})

    def test_arquivo_invalido_renderiza_mesma_pagina(self):
        """Ao enviar arquivo não-PDF, a view deve renderizar 200 (não 302 redirect)."""
        arquivo_invalido = SimpleUploadedFile(
            "imagem.jpg", b"conteudo_falso", content_type="image/jpeg"
        )
        data = {
            "agente": self.agente.id,
            "mes_referencia": 5,
            "ano_referencia": 2026,
            "arquivo": arquivo_invalido,
        }
        response = self.client.post(self.url, data)

        # Não deve redirecionar — deve renderizar a própria tela com o formulário
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "contratos/prestacao/upload_contrato.html")

    def test_arquivo_invalido_exibe_mensagem_de_erro(self):
        """A mensagem de validação deve estar presente no conteúdo da resposta."""
        arquivo_invalido = SimpleUploadedFile(
            "planilha.xlsx", b"conteudo_falso", content_type="application/vnd.ms-excel"
        )
        data = {
            "agente": self.agente.id,
            "mes_referencia": 5,
            "ano_referencia": 2026,
            "arquivo": arquivo_invalido,
        }
        response = self.client.post(self.url, data)

        self.assertEqual(response.status_code, 200)
        # A mensagem de erro específica do formulário deve aparecer
        self.assertContains(response, "Apenas arquivos PDF são aceitos.")

    def test_arquivo_invalido_nao_cria_registro_no_banco(self):
        """Um envio inválido não deve criar nenhuma PrestacaoContas."""
        arquivo_invalido = SimpleUploadedFile(
            "documento.docx", b"conteudo_falso", content_type="application/msword"
        )
        data = {
            "agente": self.agente.id,
            "mes_referencia": 5,
            "ano_referencia": 2026,
            "arquivo": arquivo_invalido,
        }
        self.client.post(self.url, data)

        self.assertEqual(PrestacaoContas.objects.count(), 0)

    def test_arquivo_invalido_mantem_campos_preenchidos(self):
        """O formulário deve manter o agente selecionado e campos preenchidos após o erro."""
        arquivo_invalido = SimpleUploadedFile(
            "foto.png", b"conteudo_falso", content_type="image/png"
        )
        data = {
            "agente": self.agente.id,
            "mes_referencia": 5,
            "ano_referencia": 2026,
            "arquivo": arquivo_invalido,
            "observacao": "Observação de teste",
        }
        response = self.client.post(self.url, data)

        self.assertEqual(response.status_code, 200)
        # O formulário no contexto deve conter os dados do POST
        form = response.context["form"]
        self.assertEqual(int(form["mes_referencia"].value()), 5)
        self.assertEqual(int(form["ano_referencia"].value()), 2026)

    def test_mes_referencia_presente_no_html_apos_erro(self):
        """O mês de referência (ex: '05/2026') deve aparecer no HTML após um erro de validação."""
        arquivo_invalido = SimpleUploadedFile(
            "imagem.jpg", b"conteudo_falso", content_type="image/jpeg"
        )
        # Usando um mês específico para facilitar a verificação
        data = {
            "agente": self.agente.id,
            "mes_referencia": 5,
            "ano_referencia": 2026,
            "arquivo": arquivo_invalido,
        }
        response = self.client.post(self.url, data)

        self.assertEqual(response.status_code, 200)
        content = response.content.decode("utf-8")
        # O input de referência com "05/2026" deve estar visível no HTML
        self.assertIn("05/2026", content)


# ─────────────────────────────────────────────
# 2. Contratos em risco — comissão inativa
# ─────────────────────────────────────────────
class ContratosEmRiscoTests(_BaseFixture):
    """
    Cobre a correção na query de 'contratos_risco':
    - Comissão com data futura mas inativa → contrato deve entrar no painel de risco.
    - Contrato sem nenhuma comissão → também deve entrar no painel de risco.
    - Contrato com comissão ATIVA e fiscal ativo → NÃO deve entrar no painel de risco.
    """

    def setUp(self):
        super().setUp()
        auditor = self._criar_auditor("auditor_risco")
        self.client.login(username="auditor_risco", password="senha123")
        self.url = reverse("painel_controle")

    def test_contrato_sem_comissao_aparece_em_risco(self):
        """Contrato vigente sem nenhuma comissão deve aparecer na lista de contratos em risco."""
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)

        contratos_risco = response.context["contratos_risco"]
        ids_em_risco = [c.id for c in contratos_risco]
        self.assertIn(self.contrato.id, ids_em_risco)

    def test_contrato_com_comissao_inativa_aparece_em_risco(self):
        """
        Contrato com comissão de fiscalização INATIVA (mesmo com data de fim futura
        e integrante vinculado) deve aparecer como em risco, pois não possui cobertura ativa.
        """
        comissao_inativa = Comissao.objects.create(
            contrato=self.contrato,
            tipo="FISCALIZACAO",
            ativa=False,  # ← inativa!
            data_inicio=date.today() - timedelta(days=30),
            data_fim=date.today() + timedelta(days=180),  # data futura — era o bug
        )
        Integrante.objects.create(
            comissao=comissao_inativa,
            agente=self.agente,
            funcao=self.funcao,
            data_inicio=date.today() - timedelta(days=30),
            portaria_numero="001",
            portaria_data=date.today() - timedelta(days=30),
        )

        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)

        contratos_risco = response.context["contratos_risco"]
        ids_em_risco = [c.id for c in contratos_risco]
        self.assertIn(
            self.contrato.id,
            ids_em_risco,
            "Contrato com comissão INATIVA deveria aparecer em risco.",
        )

    def test_contrato_com_comissao_ativa_nao_aparece_em_risco(self):
        """Contrato com comissão ativa e fiscal ativo NÃO deve aparecer em risco."""
        self._criar_comissao_ativa_com_fiscal()

        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)

        contratos_risco = response.context["contratos_risco"]
        ids_em_risco = [c.id for c in contratos_risco]
        self.assertNotIn(
            self.contrato.id,
            ids_em_risco,
            "Contrato com comissão ATIVA não deveria aparecer em risco.",
        )

    def test_contrato_expirado_nunca_aparece_em_risco(self):
        """Contratos encerrados (vigência passada) não devem figurar no painel de risco."""
        contrato_expirado = Contrato.objects.create(
            numero="EXP/2024",
            tipo="DESPESA",
            empresa=self.empresa,
            objeto="Contrato Expirado",
            vigencia_inicio=date.today() - timedelta(days=365),
            vigencia_fim=date.today() - timedelta(days=1),
            valor_total=10000.00,
        )

        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)

        contratos_risco = response.context["contratos_risco"]
        ids_em_risco = [c.id for c in contratos_risco]
        self.assertNotIn(
            contrato_expirado.id,
            ids_em_risco,
            "Contrato expirado não deve aparecer em risco.",
        )


# ─────────────────────────────────────────────
# 3. Exportação CSV — registros fantasma pendente
# ─────────────────────────────────────────────
class ExportacaoPendenteFanatmasmaTests(_BaseFixture):
    """
    Cobre a correção que excluiu registros 'pendente' da exportação mensal.
    Um registro pendente (sem arquivo, criado automaticamente pelo toggle de prioridade)
    não deve aparecer nas linhas de dados do CSV — o contrato deve aparecer como "Pendente"
    mas com os campos de responsável e data em branco ("-").
    """

    def setUp(self):
        super().setUp()
        self._criar_comissao_ativa_com_fiscal()
        auditor = self._criar_auditor("auditor_export")
        self.client.login(username="auditor_export", password="senha123")
        self.url_export = reverse("exportar_prestacao_csv")

    def test_registro_pendente_nao_gera_linha_de_dado_no_csv(self):
        """
        Um PrestacaoContas com status='pendente' não deve gerar uma linha de dado
        no CSV; o contrato deve aparecer como Pendente (placeholder gerado pela lógica
        de contratos sem envio).
        """
        # Cria um registro fantasma (sem arquivo, como faria o toggle de prioridade)
        PrestacaoContas.objects.create(
            contrato=self.contrato,
            agente=None,
            mes_referencia=5,
            ano_referencia=2026,
            status="pendente",
        )

        response = self.client.get(self.url_export, {"mes": 5, "ano": 2026, "formato": "csv"})
        self.assertEqual(response.status_code, 200)

        content = response.content.decode("utf-8-sig")
        lines = [l for l in content.split("\r\n") if l]

        # Pegar as linhas de dados referentes ao nosso contrato
        linhas_contrato = [l for l in lines[1:] if l.startswith("REG/2026")]

        # Deve haver exatamente UMA linha para este contrato (o pendente real, sem timestamp)
        self.assertEqual(
            len(linhas_contrato),
            1,
            f"Esperava 1 linha para REG/2026, obteve {len(linhas_contrato)}",
        )

        # Essa linha única deve mostrar "Pendente" com campos em branco
        cols = linhas_contrato[0].split(";")
        situacao_col = cols[9]  # coluna Situação
        responsavel_col = cols[10]  # coluna Responsável

        self.assertEqual(situacao_col, "Pendente")
        self.assertEqual(responsavel_col, "-")

    def test_registro_pendente_nao_exibe_data_de_envio_falsa(self):
        """
        O registro 'pendente' tem auto_now_add no campo data_envio, mas esse timestamp
        falso não deve aparecer no CSV exportado.
        """
        # Registro fantasma com data criada automaticamente pelo banco
        fantasma = PrestacaoContas.objects.create(
            contrato=self.contrato,
            agente=None,
            mes_referencia=5,
            ano_referencia=2026,
            status="pendente",
        )
        # Confirma que o fantasma tem data gerada (não é None)
        self.assertIsNotNone(fantasma.data_envio)

        response = self.client.get(self.url_export, {"mes": 5, "ano": 2026, "formato": "csv"})
        content = response.content.decode("utf-8-sig")
        lines = [l for l in content.split("\r\n") if l]
        linhas_contrato = [l for l in lines[1:] if l.startswith("REG/2026")]

        self.assertEqual(len(linhas_contrato), 1)
        cols = linhas_contrato[0].split(";")
        # Coluna de data/hora do envio (índice 11) deve estar vazia/traço
        data_hora_col = cols[11] if len(cols) > 11 else ""
        self.assertNotIn(
            str(fantasma.data_envio.year),
            data_hora_col,
            "Data de envio fantasma não deveria aparecer no CSV.",
        )

    def test_registro_entregue_aparece_normalmente_no_csv(self):
        """Um envio real ('entregue') deve aparecer normalmente no CSV com todos os campos."""
        pdf_file = SimpleUploadedFile("real.pdf", b"%PDF-1.4", content_type="application/pdf")
        prest = PrestacaoContas.objects.create(
            contrato=self.contrato,
            agente=self.agente,
            mes_referencia=5,
            ano_referencia=2026,
            arquivo=pdf_file,
            status="entregue",
        )

        response = self.client.get(self.url_export, {"mes": 5, "ano": 2026, "formato": "csv"})
        content = response.content.decode("utf-8-sig")
        lines = [l for l in content.split("\r\n") if l]
        linhas_contrato = [l for l in lines[1:] if l.startswith("REG/2026")]

        self.assertEqual(len(linhas_contrato), 1)
        cols = linhas_contrato[0].split(";")
        self.assertEqual(cols[9], "Entregue")
        self.assertIn("Teste", cols[10])  # nome_de_guerra do agente

        # Limpeza
        if prest.arquivo and os.path.isfile(prest.arquivo.path):
            os.remove(prest.arquivo.path)

    def test_pendente_fantasma_e_registro_real_no_mesmo_mes(self):
        """
        Se coexistirem um registro fantasma (pendente) e um real (entregue)
        para o mesmo contrato/mês, apenas o registro real deve aparecer no CSV.
        """
        # Cria o fantasma
        PrestacaoContas.objects.create(
            contrato=self.contrato,
            agente=None,
            mes_referencia=5,
            ano_referencia=2026,
            status="pendente",
        )
        # Cria o real
        pdf_file = SimpleUploadedFile("real2.pdf", b"%PDF-1.4", content_type="application/pdf")
        prest_real = PrestacaoContas.objects.create(
            contrato=self.contrato,
            agente=self.agente,
            mes_referencia=5,
            ano_referencia=2026,
            arquivo=pdf_file,
            status="entregue",
        )

        response = self.client.get(self.url_export, {"mes": 5, "ano": 2026, "formato": "csv"})
        content = response.content.decode("utf-8-sig")
        lines = [l for l in content.split("\r\n") if l]
        linhas_contrato = [l for l in lines[1:] if l.startswith("REG/2026")]

        # Somente o real (entregue) deve aparecer
        self.assertEqual(len(linhas_contrato), 1)
        cols = linhas_contrato[0].split(";")
        self.assertEqual(cols[9], "Entregue")

        # Limpeza
        if prest_real.arquivo and os.path.isfile(prest_real.arquivo.path):
            os.remove(prest_real.arquivo.path)
