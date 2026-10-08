"""
Módulo de Notificações de Ocorrências Contratuais (NPA 009 / SCON / Nova Lei de Licitações).

Este serviço modulariza a geração de documentos de Notificação Oficial de Ocorrências,
permitindo a fácil substituição, revisão e acoplamento de novos modelos padronizados
sem impactar o fluxo do Livro do Fiscal.
"""

from abc import ABC, abstractmethod
import io
import os
from datetime import date
from django.conf import settings
from django.utils.text import slugify

from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import cm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, KeepTogether, Image
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle


class BaseNotificacaoGenerator(ABC):
    """
    Interface base para geradores de notificação.
    Qualquer novo modelo deve herdar desta classe e implementar `gerar_pdf`.
    """
    versao: str = "base"
    nome_modelo: str = "Modelo Base"

    @abstractmethod
    def gerar_pdf(self, ocorrencia) -> io.BytesIO:
        """Gera o arquivo PDF da notificação em memória e retorna o buffer BytesIO."""
        pass

    def obter_nome_arquivo(self, ocorrencia) -> str:
        """Gera o nome de arquivo padronizado para download."""
        raw_num = (ocorrencia.notificacao_numero or f"notificacao-{ocorrencia.id}").replace('/', '-')
        slug_notif = slugify(raw_num)
        return f"notificacao_{self.versao}_{slug_notif}.pdf"


class NotificacaoAnexoDLegadoGenerator(BaseNotificacaoGenerator):
    """
    Gerador do modelo clássico Anexo D da NPA 009/SCON/2025.
    Contém a notificação formal com prazo regulamentar de 5 dias úteis,
    recibo de ciência do notificado e certidão de recusa com 2 testemunhas.
    """
    versao = "anexo_d_npa009"
    nome_modelo = "Anexo D - NPA 009/SCON/2025 (Legado)"

    def gerar_pdf(self, oc) -> io.BytesIO:
        controle = oc.controle
        contrato = controle.contrato
        empresa = contrato.empresa

        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            leftMargin=1.5 * cm,
            rightMargin=1.5 * cm,
            topMargin=1.5 * cm,
            bottomMargin=1.5 * cm
        )

        styles = getSampleStyleSheet()
        printable_width = 18.0 * cm

        style_title = ParagraphStyle(
            'DocTitle', fontName='Helvetica-Bold', fontSize=11, leading=13,
            textColor=colors.HexColor('#0F172A'), alignment=1
        )
        style_sub = ParagraphStyle(
            'DocSub', fontName='Helvetica-Bold', fontSize=10, leading=12,
            textColor=colors.HexColor('#B91C1C'), alignment=1
        )
        style_body = ParagraphStyle(
            'DocBody', fontName='Helvetica', fontSize=8.5, leading=12,
            textColor=colors.HexColor('#0F172A')
        )
        style_label = ParagraphStyle(
            'Label', fontName='Helvetica-Bold', fontSize=8, leading=10,
            textColor=colors.HexColor('#475569')
        )
        style_val = ParagraphStyle(
            'Val', fontName='Helvetica', fontSize=8, leading=10,
            textColor=colors.HexColor('#0F172A')
        )

        story = []

        # Cabeçalho Oficial
        logo_path = os.path.join(settings.BASE_DIR, 'contratos', 'static', 'contratos', 'img', 'gap_logo.png')
        logo_img = None
        if os.path.exists(logo_path):
            try:
                logo_img = Image(logo_path, width=1.5 * cm, height=1.9 * cm)
            except Exception:
                logo_img = None

        hdr_text = [
            Paragraph("MINISTÉRIO DA DEFESA | COMANDO DA AERONÁUTICA", style_title),
            Paragraph(f"{controle.omap} — GRUPAMENTO DE APOIO DE BRASÍLIA", style_title),
            Spacer(1, 3),
            Paragraph(f"<b>NOTIFICAÇÃO DE OCORRÊNCIA Nº {oc.notificacao_numero or f'{oc.id}/{controle.ano_referencia}'}</b>", style_sub),
            Paragraph("<i>Modelo Padronizado conforme Anexo D da NPA 009/SCON/2025 e Lei nº 14.133/2021</i>", ParagraphStyle('sub2', parent=styles['Normal'], fontSize=7.5, alignment=1, textColor=colors.HexColor('#64748B'))),
        ]

        if logo_img:
            t_hdr = Table([[logo_img, hdr_text]], colWidths=[2.0 * cm, 16.0 * cm])
            t_hdr.setStyle(TableStyle([
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('ALIGN', (0, 0), (0, 0), 'CENTER'),
            ]))
            story.append(t_hdr)
        else:
            story.extend(hdr_text)

        story.append(Spacer(1, 8))
        story.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor('#DC2626'), spaceAfter=10))

        # Dados do Notificado
        notif_data = [
            [Paragraph("Ao(À) Notificado(a):", style_label), Paragraph(f"<b>{empresa.razao_social}</b>", style_val)],
            [Paragraph("CNPJ / Cadastro:", style_label), Paragraph(f"{empresa.cnpj} | Cadastro SICAF ativo", style_val)],
            [Paragraph("Representante / Preposto:", style_label), Paragraph(f"{controle.preposto_nome or 'Preposto Credenciado'} ({controle.preposto_cargo or 'Representante'}) — Tel: {controle.preposto_telefone or '-'} | E-mail: {controle.preposto_email or '-'}", style_val)],
            [Paragraph("Contrato Vinculado:", style_label), Paragraph(f"Contrato nº <b>{contrato.numero}</b> | e-PAG nº <b>{getattr(contrato, 'pag', None) or '—'}</b>", style_val)],
        ]
        t_notif = Table(notif_data, colWidths=[4.2 * cm, 13.8 * cm])
        t_notif.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#F8FAFC')),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#E2E8F0')),
            ('TOPPADDING', (0, 0), (-1, -1), 3),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
            ('LEFTPADDING', (0, 0), (-1, -1), 5),
            ('RIGHTPADDING', (0, 0), (-1, -1), 5),
        ]))
        story.append(t_notif)
        story.append(Spacer(1, 10))

        # Texto Intimatório da NPA
        p1 = Paragraph(
            f"<b>1.</b> Em cumprimento ao disposto no <b>Contrato nº {contrato.numero}</b> e nas diretrizes da <b>NPA 009/SCON/2025</b>, "
            f"fica V. Sa. formalmente notificado(a) a <b>CORRIGIR AS FALHAS/DISCREPÂNCIAS/OCORRÊNCIAS</b> indicadas neste instrumento, "
            f"no prazo regulamentar de <b>{oc.prazo_dias_uteis} (CINCO) DIAS ÚTEIS</b>, contados do recebimento desta, "
            "sob pena de aplicação de sanções administrativas com base na Lei nº 14.133/2021 e abertura de PAAI junto à Assessoria de Riscos Contratuais (ARC).",
            style_body
        )
        story.append(p1)
        story.append(Spacer(1, 8))

        p2 = Paragraph(
            "<b>2.</b> A presente Notificação decorre de descumprimento apurado no e-PAG correspondente, especificamente quanto ao seguinte fato:",
            style_body
        )
        story.append(p2)
        story.append(Spacer(1, 6))

        # Tabela de Detalhes da Ocorrência
        dt_f = oc.data_hora.strftime('%d/%m/%Y às %H:%M') if oc.data_hora else "Data não informada"
        oc_detalhes = [
            [Paragraph("Data e Horário do Fato:", style_label), Paragraph(dt_f, style_val)],
            [Paragraph("Local da Ocorrência:", style_label), Paragraph(oc.local or "Instalações da OM", style_val)],
            [Paragraph("Classificação da Ocorrência:", style_label), Paragraph(oc.get_tipo_display(), style_val)],
            [Paragraph("Descrição Detalhada do Fato:", style_label), Paragraph(oc.descricao, style_val)],
            [Paragraph("Cláusula / Dispositivo Violado:", style_label), Paragraph(f"<b>{oc.dispositivo_violado or 'Disposições do Contrato e Termo de Referência'}</b>", style_val)],
            [Paragraph("Evidências / Documentos:", style_label), Paragraph(oc.evidencias or "Relatório fotográfico / Parecer técnico anexo", style_val)],
            [Paragraph("Determinação / Providência Exigida:", style_label), Paragraph(oc.acao_fiscal or "Cessação imediata do desvio e saneamento completo no prazo concedido.", style_val)],
        ]
        t_oc_det = Table(oc_detalhes, colWidths=[4.8 * cm, 13.2 * cm])
        t_oc_det.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#FEF2F2')),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#FECACA')),
            ('TOPPADDING', (0, 0), (-1, -1), 3),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
            ('LEFTPADDING', (0, 0), (-1, -1), 5),
            ('RIGHTPADDING', (0, 0), (-1, -1), 5),
        ]))
        story.append(t_oc_det)
        story.append(Spacer(1, 10))

        # Local, Data e Assinatura do Fiscal
        MESES_PT = ['', 'janeiro', 'fevereiro', 'março', 'abril', 'maio', 'junho',
                    'julho', 'agosto', 'setembro', 'outubro', 'novembro', 'dezembro']
        hoje_d = date.today()
        dt_ext = f"Brasília-DF, {hoje_d.day:02d} de {MESES_PT[hoje_d.month]} de {hoje_d.year}."

        p_sigla = controle.agente.posto.sigla if (controle.agente and controle.agente.posto) else ""
        n_guerra = controle.agente.nome_de_guerra.upper() if controle.agente else "FISCAL"
        fiscal_str = f"{p_sigla} {n_guerra}".strip()

        sig_fiscal = [
            Paragraph(dt_ext, ParagraphStyle('DtF', parent=styles['Normal'], alignment=2, fontSize=8, textColor=colors.HexColor('#0F172A'))),
            Spacer(1, 14),
            Paragraph("____________________________________________________________", ParagraphStyle('Line', parent=styles['Normal'], alignment=1, fontSize=8, textColor=colors.HexColor('#94A3B8'))),
            Spacer(1, 2),
            Paragraph(f"<b>{fiscal_str}</b>", ParagraphStyle('Name', parent=styles['Normal'], alignment=1, fontSize=8.5, leading=10)),
            Paragraph("Fiscal do Contrato / Comissão de Fiscalização — GAP-BR", ParagraphStyle('Func', parent=styles['Normal'], alignment=1, fontSize=7.5, leading=9.5, textColor=colors.HexColor('#64748B'))),
        ]
        t_sf = Table([[sig_fiscal]], colWidths=[printable_width])
        t_sf.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('TOPPADDING', (0, 0), (-1, -1), 2),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ]))
        story.append(t_sf)
        story.append(Spacer(1, 8))

        story.append(HRFlowable(width="100%", thickness=0.8, color=colors.HexColor('#94A3B8'), spaceAfter=8))

        # Recibo e Ciência do Notificado
        recibo_content = [
            Paragraph("<b>RECIBO E CIÊNCIA DO NOTIFICADO:</b>", style_label),
            Spacer(1, 3),
            Paragraph("Recebi a 1ª via desta Notificação em: _____/_____/_________ às _____:_____ hs.", style_val),
            Spacer(1, 8),
            Table([[
                Paragraph("___________________________________________________<br/><b>Assinatura do Preposto / Representante</b>", ParagraphStyle('RecSig', parent=styles['Normal'], alignment=1, fontSize=7.5, leading=10, textColor=colors.HexColor('#334155')))
            ]], colWidths=[printable_width]),
        ]
        t_rec = Table([[recibo_content]], colWidths=[printable_width])
        t_rec.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#F8FAFC')),
            ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor('#CBD5E1')),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('LEFTPADDING', (0, 0), (-1, -1), 6),
            ('RIGHTPADDING', (0, 0), (-1, -1), 6),
        ]))
        story.append(t_rec)
        story.append(Spacer(1, 8))

        story.append(HRFlowable(width="100%", thickness=0.8, color=colors.HexColor('#94A3B8'), spaceAfter=8))

        # Termo de Declaração e Certidão de Recusa com 2 Testemunhas
        testemunhas_block = [
            Paragraph("<b>TERMO DE DECLARAÇÃO E CERTIDÃO DE RECUSA DE ASSINATURA (COM TESTEMUNHAS):</b>", style_label),
            Spacer(1, 2),
            Paragraph(
                f"<i>Certificamos que a Notificação de Ocorrência nº {oc.notificacao_numero or oc.id} foi lida em seu inteiro teor na presença do(a) "
                "Notificado(a) / Preposto acima qualificado, o(a) qual <b>RECUSOU-SE</b> a assinar/receber o comprovante na data e horário indicados.</i>",
                style_val
            ),
            Spacer(1, 6),
            Table([
                [
                    Paragraph("<b>1ª TESTEMUNHA:</b><br/>Nome: __________________________________________<br/>Posto/Grad./Cargo: _______________________________<br/>Identidade / Órgão Exp.: ___________________________<br/>Hora da Leitura: _____:_____ hs.<br/>Assinatura: ____________________________________", style_val),
                    Paragraph("<b>2ª TESTEMUNHA:</b><br/>Nome: __________________________________________<br/>Posto/Grad./Cargo: _______________________________<br/>Identidade / Órgão Exp.: ___________________________<br/>Hora da Leitura: _____:_____ hs.<br/>Assinatura: ____________________________________", style_val)
                ]
            ], colWidths=[9.0 * cm, 9.0 * cm])
        ]
        t_test = Table([[testemunhas_block]], colWidths=[printable_width])
        t_test.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#FFFBEB')),
            ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor('#FCD34D')),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('LEFTPADDING', (0, 0), (-1, -1), 6),
            ('RIGHTPADDING', (0, 0), (-1, -1), 6),
        ]))
        story.append(KeepTogether(t_test))

        doc.build(story)
        buffer.seek(0)
        return buffer


class NovoModeloNotificacaoGenerator(BaseNotificacaoGenerator):
    """
    Estrutura modular para o Novo Modelo de Notificação que será definido e revisado.
    Permite acoplar a nova padronização assim que os requisitos forem homologados.
    """
    versao = "novo_modelo"
    nome_modelo = "Novo Modelo Padronizado (Em Revisão)"

    def gerar_pdf(self, ocorrencia) -> io.BytesIO:
        # Quando o novo modelo for homologado, sua implementação ReportLab/HTML será adicionada aqui.
        raise NotImplementedError(
            "O novo modelo de notificação está em fase de revisão e adaptação técnica."
        )


class NotificacaoService:
    """
    Serviço centralizador de Notificações de Ocorrências Contratuais.
    Gerencia a ativação/desativação da geração automática e despacha a emissão
    para o gerador apropriado.
    """
    CONFIG_FLAG = 'NOTIFICACAO_AUTOMATICA_HABILITADA'

    _GENERATORS = {
        'legado': NotificacaoAnexoDLegadoGenerator,
        'anexo_d': NotificacaoAnexoDLegadoGenerator,
        'novo': NovoModeloNotificacaoGenerator,
    }

    _DEFAULT_TYPE = 'legado'

    @classmethod
    def is_habilitada(cls) -> bool:
        """
        Retorna se a geração automática de notificações está habilitada no sistema.
        Por padrão, retorna False conforme diretriz de revisão do modelo.
        """
        return bool(getattr(settings, cls.CONFIG_FLAG, False))

    @classmethod
    def get_generator(cls, tipo: str = None) -> BaseNotificacaoGenerator:
        """Retorna a instância do gerador de documento para o tipo especificado."""
        key = tipo or cls._DEFAULT_TYPE
        generator_class = cls._GENERATORS.get(key, NotificacaoAnexoDLegadoGenerator)
        return generator_class()

    @classmethod
    def registrar_generator(cls, key: str, generator_class):
        """Permite registrar dinamicamente novos geradores de notificação."""
        cls._GENERATORS[key] = generator_class

    @classmethod
    def gerar_documento(cls, ocorrencia, tipo: str = None, permitir_desabilitado: bool = False):
        """
        Gera o documento de notificação.
        :param ocorrencia: Objeto OcorrenciaContratual.
        :param tipo: Identificador do modelo ('legado', 'novo', etc.).
        :param permitir_desabilitado: Se True, permite gerar mesmo quando a geração automática estiver desabilitada.
        :return: Tupla (buffer: BytesIO, filename: str)
        """
        if not cls.is_habilitada() and not permitir_desabilitado:
            raise PermissionError(
                "A emissão automática da notificação está temporariamente desabilitada para revisão do modelo."
            )

        generator = cls.get_generator(tipo)
        buffer = generator.gerar_pdf(ocorrencia)
        filename = generator.obter_nome_arquivo(ocorrencia)
        return buffer, filename
