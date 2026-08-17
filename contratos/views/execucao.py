import json
from datetime import date, timedelta
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse, HttpResponse
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.urls import reverse
import csv

import io
import os
from django.conf import settings
from django.utils.text import slugify

from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.pdfgen import canvas
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, HRFlowable, KeepTogether
)

from contratos.models import (
    Contrato, Agente, Integrante, Comissao, CalendarioPrestacao,
    ControleExecucao, RegistroFatura, OcorrenciaContratual, ApontamentoCorrecaoExecucao
)
from contratos.forms import ControleExecucaoForm
from contratos.utils import is_admin, is_auditor, admin_required, auditor_required


def portal_execucao_index(request):
    """Redireciona para o Portal de Prestação de Contas público."""
    return redirect('portal_prestacao_index')


def portal_execucao_fiscais(request):
    """Redireciona para a Seleção de Contratos no Portal de Prestação de Contas."""
    return redirect('portal_prestacao_fiscais')


def excluir_controle_execucao_publico(request, contrato_id):
    """Permite ao fiscal excluir o registro do Livro do Fiscal do contrato no mês de referência atual."""
    contrato = get_object_or_404(Contrato, pk=contrato_id)
    hoje = date.today()
    primeiro_dia_mes_atual = hoje.replace(day=1)
    ultimo_dia_mes_anterior = primeiro_dia_mes_atual - timedelta(days=1)
    filtro_mes = ultimo_dia_mes_anterior.month
    filtro_ano = ultimo_dia_mes_anterior.year

    controle = ControleExecucao.objects.filter(
        contrato=contrato, mes_referencia=filtro_mes, ano_referencia=filtro_ano
    ).first()

    if controle:
        controle.delete()
        messages.success(request, f"Registro do Livro do Fiscal do Contrato {contrato.numero} excluído com sucesso.")
    else:
        messages.info(request, "Nenhum registro encontrado para este contrato no período atual.")

    return redirect('upload_prestacao', contrato_id=contrato.id)


def formulario_execucao(request, contrato_id):
    """Formulário público para preenchimento/envio do Livro do Fiscal."""
    contrato = get_object_or_404(Contrato, pk=contrato_id)

    hoje = date.today()
    primeiro_dia_mes_atual = hoje.replace(day=1)
    ultimo_dia_mes_anterior = primeiro_dia_mes_atual - timedelta(days=1)
    filtro_mes = ultimo_dia_mes_anterior.month
    filtro_ano = ultimo_dia_mes_anterior.year

    # Buscar comissão de fiscalização ativa
    comissao_ativa = Comissao.objects.filter(
        contrato=contrato, ativa=True, tipo='FISCALIZACAO'
    ).first()

    integrantes = []
    if comissao_ativa:
        integrantes = Integrante.objects.filter(
            comissao=comissao_ativa, data_desligamento__isnull=True
        ).select_related('agente', 'agente__posto').order_by('funcao', 'agente__nome_de_guerra')

    # Verificar se já existe um envio para este mês
    controle_existente = ControleExecucao.objects.filter(
        contrato=contrato, mes_referencia=filtro_mes, ano_referencia=filtro_ano
    ).order_by('-id').first()

    if controle_existente and controle_existente.status == 'ok':
        return redirect('visualizar_controle_execucao', pk=controle_existente.pk)

    # Verificar se a data atual está a 120 dias ou menos do fim da vigência
    dentro_prazo_aditivo = False
    if contrato.data_recomendada_aditivo:
        dentro_prazo_aditivo = (hoje >= contrato.data_recomendada_aditivo)

    if request.method == 'POST':
        form = ControleExecucaoForm(request.POST, contrato=contrato, instance=controle_existente, dentro_prazo_aditivo=dentro_prazo_aditivo)
        if form.is_valid():
            controle = form.save(commit=False)
            controle.contrato = contrato
            controle.mes_referencia = filtro_mes
            controle.ano_referencia = filtro_ano
            controle.status = 'entregue'
            controle.save()

            # Processar Faturas (JSON enviado pelo frontend)
            faturas_json_str = request.POST.get('faturas_json', '[]')
            try:
                faturas_data = json.loads(faturas_json_str)
                controle.faturas.all().delete()
                for fat in faturas_data:
                    num_nf = fat.get('numero_nf', '').strip()
                    val = fat.get('valor', 0)
                    num_ob = fat.get('numero_ob', '').strip()
                    if num_nf:
                        RegistroFatura.objects.create(
                            controle=controle,
                            numero_nf=num_nf,
                            valor=val,
                            numero_ob=num_ob
                        )
            except Exception:
                pass

            # Processar Ocorrências (JSON enviado pelo frontend assistente)
            ocorrencias_json_str = request.POST.get('ocorrencias_json', '[]')
            relatorio_text_lines = []
            try:
                ocorrencias_data = json.loads(ocorrencias_json_str)
                controle.ocorrencias.all().delete()
                for idx, oc in enumerate(ocorrencias_data, 1):
                    dt = oc.get('data')
                    tp = oc.get('tipo', 'outro')
                    desc = oc.get('descricao', '').strip()
                    acao = oc.get('acao_fiscal', '').strip()
                    prazo = oc.get('prazo', '').strip()

                    if dt and desc:
                        OcorrenciaContratual.objects.create(
                            controle=controle,
                            data=dt,
                            tipo=tp,
                            descricao=desc,
                            acao_fiscal=acao,
                            prazo=prazo
                        )
                        relatorio_text_lines.append(
                            f"[{idx}] Data: {dt} | Tipo: {tp.upper()}\n"
                            f"    Ocorrência: {desc}\n"
                            f"    Ação do Fiscal: {acao}\n"
                            f"    Prazo: {prazo if prazo else 'N/A'}\n"
                        )
            except Exception:
                pass

            if relatorio_text_lines:
                controle.relatorio_ocorrencias = "\n".join(relatorio_text_lines)
            elif not controle.relatorio_ocorrencias:
                controle.relatorio_ocorrencias = "Sem ocorrências registradas no período."
            controle.save()

            messages.success(request, "Livro do Fiscal enviado com sucesso! Agora você pode enviar a prestação de contas mensal.")
            return redirect('upload_prestacao', contrato_id=contrato.id)
        else:
            messages.error(request, "Por favor, corrija os erros apontados no formulário.")
    else:
        form = ControleExecucaoForm(contrato=contrato, instance=controle_existente, dentro_prazo_aditivo=dentro_prazo_aditivo)

    faturas_existentes = []
    ocorrencias_existentes = []
    apontamentos = []
    if controle_existente:
        faturas_existentes = list(controle_existente.faturas.values('numero_nf', 'valor', 'numero_ob'))
        ocorrencias_existentes = list(controle_existente.ocorrencias.values('data', 'tipo', 'descricao', 'acao_fiscal', 'prazo'))
        apontamentos = controle_existente.apontamentos.select_related('autor').all()

    return render(request, 'contratos/execucao/formulario.html', {
        'contrato': contrato,
        'comissao': comissao_ativa,
        'integrantes': integrantes,
        'form': form,
        'controle_existente': controle_existente,
        'apontamentos': apontamentos,
        'faturas_json': json.dumps(faturas_existentes, default=str),
        'ocorrencias_json': json.dumps(ocorrencias_existentes, default=str),
        'mes_referencia': filtro_mes,
        'ano_referencia': filtro_ano,
        'dentro_prazo_aditivo': dentro_prazo_aditivo,
    })


@login_required
def visualizar_controle_execucao(request, pk):
    """Visualização em formato somente leitura do Livro do Fiscal (ACI / Admin)."""
    controle = get_object_or_404(
        ControleExecucao.objects.select_related('contrato', 'contrato__empresa', 'agente', 'agente__posto'), pk=pk
    )

    comissao = Comissao.objects.filter(
        contrato=controle.contrato, ativa=True, tipo='FISCALIZACAO'
    ).first()
    if not comissao:
        comissao = Comissao.objects.filter(
            contrato=controle.contrato, tipo='FISCALIZACAO'
        ).order_by('-data_inicio').first()

    integrantes = []
    if comissao:
        integrantes = list(
            comissao.integrantes.filter(data_desligamento__isnull=True).select_related(
                'agente', 'agente__posto', 'posto_graduacao', 'funcao'
            ).order_by('ordem', 'funcao__ordem', 'id')
        )

    apontamentos = controle.apontamentos.select_related('autor').all()
    ocorrencias_estruturadas = controle.ocorrencias.all()

    return render(request, 'contratos/execucao/visualizar.html', {
        'controle': controle,
        'comissao': comissao,
        'integrantes': integrantes,
        'apontamentos': apontamentos,
        'ocorrencias_estruturadas': ocorrencias_estruturadas,
        'is_admin': is_admin(request.user),
        'is_auditor': is_auditor(request.user),
    })


@login_required
def alterar_status_execucao(request, pk, novo_status):
    """Altera o status do Livro do Fiscal (ACI Auditor / Admin)."""
    if not is_auditor(request.user):
        messages.error(request, "Acesso não autorizado.")
        return redirect('dashboard_prestacao')

    controle = get_object_or_404(ControleExecucao, pk=pk)

    if novo_status not in ['entregue', 'correcao', 'ok']:
        messages.error(request, "Status inválido.")
        return redirect('dashboard_prestacao')

    justificativa = ""
    if request.method == 'POST':
        if request.content_type == 'application/json':
            try:
                justificativa = json.loads(request.body).get('justificativa', '').strip()
            except json.JSONDecodeError:
                pass
        else:
            justificativa = request.POST.get('justificativa', '').strip()

    if novo_status == 'correcao' and not justificativa:
        messages.error(request, "A justificativa é obrigatória para solicitar correção.")
        return redirect(reverse('visualizar_controle_execucao', args=[pk]))

    controle.status = novo_status
    controle.save()

    if novo_status == 'correcao' and justificativa:
        ApontamentoCorrecaoExecucao.objects.create(
            controle=controle,
            autor=request.user,
            descricao=justificativa
        )

    messages.success(request, f"Status do Livro do Fiscal alterado para '{controle.get_status_display()}' com sucesso.")
    return redirect('dashboard_prestacao')


@admin_required
def excluir_controle_execucao(request, pk):
    """Excluir registro do Livro do Fiscal (Apenas Admin)."""
    controle = get_object_or_404(ControleExecucao, pk=pk)
    controle.delete()
    messages.success(request, "Registro do Livro do Fiscal excluído com sucesso.")
    return redirect('dashboard_prestacao')


@auditor_required
def exportar_execucao_csv(request):
    """Exporta planilha de acompanhamento da Execução Contratual (Livro do Fiscal)."""
    hoje = date.today()
    try:
        filtro_mes = int(request.GET.get('mes', hoje.month))
        filtro_ano = int(request.GET.get('ano', hoje.year))
    except (ValueError, TypeError):
        filtro_mes = hoje.month
        filtro_ano = hoje.year

    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = f'attachment; filename="livros_do_fiscal_{filtro_mes:02d}_{filtro_ano}.csv"'
    response.write(b'\xef\xbb\xbf')

    writer = csv.writer(response, delimiter=';')
    writer.writerow([
        'Contrato', 'Objeto', 'Fiscal Responsável', 'Mês Ref.', 'Ano Ref.',
        'Data Envio', 'Status', 'Substituição Fiscal',
        'Garantia Vigente', 'Providências Garantia',
        'Glosa Realizada', 'Empresa Sancionada', 'Doc. Sanção SILOMS', 'Necessidade PAAI', 'Relatório Ocorrências'
    ])

    controles = ControleExecucao.objects.filter(
        mes_referencia=filtro_mes, ano_referencia=filtro_ano
    ).select_related('contrato', 'agente', 'agente__posto')

    for c in controles:
        fiscal_nome = f"{c.agente.posto.sigla} {c.agente.nome_de_guerra}" if c.agente else "Não informado"
        writer.writerow([
            c.contrato.numero,
            c.contrato.objeto[:50],
            fiscal_nome,
            c.mes_referencia,
            c.ano_referencia,
            c.data_envio.strftime('%d/%m/%Y %H:%M'),
            c.get_status_display(),
            'Sim' if c.houve_substituicao else 'Não',
            c.get_garantia_vigente_display(),
            c.garantia_providencias or '-',
            c.get_glosa_realizada_display(),
            c.get_empresa_sancionada_display() if c.empresa_sancionada else 'Não informado',
            c.get_doc_sancao_siloms_display() if c.doc_sancao_siloms else 'Não informado',
            c.get_necessidade_paai_display(),
            c.relatorio_ocorrencias[:100]
        ])

    return response


class LivroFiscalCanvas(canvas.Canvas):
    """Canvas customizado de 2 passos para adicionar rodapé a partir da página 2 com totalização de páginas."""
    def __init__(self, *args, contrato_numero="", empresa_nome="", mes_referencia=0, ano_referencia=0, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []
        self.contrato_numero = contrato_numero
        self.empresa_nome = empresa_nome
        self.mes_referencia = mes_referencia
        self.ano_referencia = ano_referencia

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            if self._pageNumber > 1:
                self.saveState()
                self.setFont("Helvetica", 8)
                self.setFillColor(colors.HexColor('#64748B'))
                
                # Identificação solicitada: "Livro do Fiscal CT xxx (Empresa) - mm/aaaa - pág x/n"
                emp_str = f" ({self.empresa_nome})" if self.empresa_nome else ""
                footer_text = f"Livro do Fiscal CT {self.contrato_numero}{emp_str} - {self.mes_referencia:02d}/{self.ano_referencia} - pág {self._pageNumber}/{num_pages}"
                
                self.setStrokeColor(colors.HexColor('#CBD5E1'))
                self.setLineWidth(0.5)
                self.line(1.5 * cm, 1.2 * cm, 19.5 * cm, 1.2 * cm)
                
                self.drawRightString(19.5 * cm, 0.8 * cm, footer_text)
                self.restoreState()
            super().showPage()
        super().save()


def gerar_livro_fiscal_pdf(request, pk):
    """Gera o relatório em PDF do Livro do Fiscal (Controle de Execução Contratual)."""
    controle = get_object_or_404(
        ControleExecucao.objects.select_related(
            'contrato', 'contrato__empresa', 'agente', 'agente__posto'
        ),
        pk=pk
    )

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

    # Custom Styles
    style_header_title = ParagraphStyle(
        'HeaderTitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=12,
        leading=14,
        textColor=colors.HexColor('#0F172A'),
        alignment=1
    )
    style_header_sub = ParagraphStyle(
        'HeaderSub',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=11,
        leading=13,
        textColor=colors.HexColor('#0D6EFD'),
        alignment=1
    )
    style_header_meta = ParagraphStyle(
        'HeaderMeta',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8,
        leading=10,
        textColor=colors.HexColor('#64748B'),
        alignment=1
    )

    style_section_title = ParagraphStyle(
        'SectionTitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=10,
        leading=12,
        textColor=colors.white
    )

    style_label = ParagraphStyle(
        'CellLabel',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=8,
        leading=10,
        textColor=colors.HexColor('#475569')
    )
    style_value = ParagraphStyle(
        'CellValue',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8.5,
        leading=11,
        textColor=colors.HexColor('#0F172A')
    )
    style_value_bold = ParagraphStyle(
        'CellValueBold',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=8.5,
        leading=11,
        textColor=colors.HexColor('#0F172A')
    )
    style_table_head = ParagraphStyle(
        'TableHead',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=8,
        leading=10,
        textColor=colors.HexColor('#1E293B'),
        alignment=0
    )

    story = []
    printable_width = 18.0 * cm

    # --- CABEÇALHO DO DOCUMENTO ---
    logo_path = os.path.join(settings.BASE_DIR, 'contratos', 'static', 'contratos', 'img', 'gap_logo.png')
    logo_img = None
    if os.path.exists(logo_path):
        try:
            logo_img = Image(logo_path, width=1.7 * cm, height=2.1 * cm)
        except Exception:
            logo_img = None

    header_text_nodes = [
        Paragraph("GRUPAMENTO DE APOIO DE BRASÍLIA", style_header_title),
        Spacer(1, 2),
        Paragraph(
            f"LIVRO DO FISCAL — CT Nº {controle.contrato.numero} — {controle.mes_referencia:02d}/{controle.ano_referencia}",
            style_header_sub
        ),
        Spacer(1, 2),
        Paragraph(
            f"Relatório Mensal de Controle de Execução Contratual | Registrado em {controle.data_envio.strftime('%d/%m/%Y às %H:%M')}",
            style_header_meta
        )
    ]

    if logo_img:
        header_table = Table([[logo_img, header_text_nodes]], colWidths=[2.2 * cm, 15.8 * cm])
        header_table.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('ALIGN', (0, 0), (0, 0), 'CENTER'),
            ('LEFTPADDING', (0, 0), (-1, -1), 0),
            ('RIGHTPADDING', (0, 0), (-1, -1), 0),
            ('TOPPADDING', (0, 0), (-1, -1), 0),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
        ]))
        story.append(header_table)
    else:
        story.extend(header_text_nodes)

    story.append(Spacer(1, 10))
    story.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor('#0D6EFD'), spaceAfter=12))

    def make_section_header(title):
        p = Paragraph(f"<b>{title}</b>", style_section_title)
        t = Table([[p]], colWidths=[printable_width])
        t.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#0D6EFD')),
            ('TOPPADDING', (0, 0), (-1, -1), 5),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
            ('LEFTPADDING', (0, 0), (-1, -1), 8),
            ('RIGHTPADDING', (0, 0), (-1, -1), 8),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ]))
        return t

    def make_kv_table(data_rows, col_widths=None):
        if not col_widths:
            col_widths = [4.5 * cm, 13.5 * cm]
        formatted_rows = []
        for r in data_rows:
            label_p = Paragraph(r[0], style_label)
            val_p = Paragraph(str(r[1]), style_value)
            formatted_rows.append([label_p, val_p])
        t = Table(formatted_rows, colWidths=col_widths)
        t.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#F8FAFC')),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#E2E8F0')),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            ('LEFTPADDING', (0, 0), (-1, -1), 6),
            ('RIGHTPADDING', (0, 0), (-1, -1), 6),
        ]))
        return t

    # --- SEÇÃO 1: IDENTIFICAÇÃO DO CONTRATO E DA EQUIPE ---
    empresa_str = f"{controle.contrato.empresa.razao_social} (CNPJ: {controle.contrato.empresa.cnpj})" if (controle.contrato and controle.contrato.empresa) else "Não informada"
    vigencia_str = f"{controle.contrato.vigencia_inicio.strftime('%d/%m/%Y')} a {controle.contrato.vigencia_fim.strftime('%d/%m/%Y')}" if (controle.contrato and controle.contrato.vigencia_inicio and controle.contrato.vigencia_fim) else "Não informada"
    fiscal_resp = f"{controle.agente.posto.sigla} {controle.agente.nome_de_guerra}" if (controle.agente and controle.agente.posto) else (controle.agente.nome_de_guerra if controle.agente else "Não informado")

    # Comissão Ativa
    comissao = Comissao.objects.filter(contrato=controle.contrato, ativa=True, tipo='FISCALIZACAO').first()
    if not comissao:
        comissao = Comissao.objects.filter(contrato=controle.contrato, tipo='FISCALIZACAO').order_by('-data_inicio').first()

    portaria_str = "Não informada"
    if comissao and comissao.portaria_numero:
        portaria_str = comissao.portaria_numero
        if comissao.portaria_data:
            portaria_str += f", de {comissao.portaria_data.strftime('%d/%m/%Y')}"

    boletim_str = "Não informado"
    if comissao and comissao.boletim_numero:
        boletim_str = comissao.boletim_numero
        if comissao.boletim_data:
            boletim_str += f", de {comissao.boletim_data.strftime('%d/%m/%Y')}"
    
    sec1_data = [
        ["Contrato Nº:", controle.contrato.numero],
        ["Empresa Contratada:", empresa_str],
        ["Objeto:", controle.contrato.objeto],
        ["Período de Vigência:", vigencia_str],
        ["Fiscal Responsável (Registro):", fiscal_resp],
        ["Portaria da Comissão:", portaria_str],
        ["Boletim de Publicação:", boletim_str],
    ]

    sec1_flowables = [
        make_section_header("SEÇÃO 1: IDENTIFICAÇÃO DO CONTRATO E DA EQUIPE"),
        Spacer(1, 4),
        make_kv_table(sec1_data)
    ]

    # Tabela de Integrantes da Comissão
    integrantes = []
    if comissao:
        integrantes = list(
            comissao.integrantes.filter(data_desligamento__isnull=True).select_related(
                'agente', 'agente__posto', 'posto_graduacao', 'funcao'
            ).order_by('ordem', 'funcao__ordem', 'id')
        )

    if integrantes:
        ing_rows = [[
            Paragraph("Posto/Graduação", style_table_head),
            Paragraph("Nome de Guerra / Completo", style_table_head),
            Paragraph("Função na Comissão", style_table_head)
        ]]
        for ing in integrantes:
            p_sigla = ing.posto_graduacao.sigla if ing.posto_graduacao else (ing.agente.posto.sigla if (ing.agente and ing.agente.posto) else "")
            n_guerra = f"{ing.agente.nome_de_guerra} ({ing.agente.nome_completo})" if ing.agente else "-"
            f_nome = ing.funcao.titulo if ing.funcao else "Integrante"
            ing_rows.append([
                Paragraph(p_sigla, style_value_bold),
                Paragraph(n_guerra, style_value),
                Paragraph(f_nome, style_value)
            ])

        t_ing = Table(ing_rows, colWidths=[3.5 * cm, 9.5 * cm, 5.0 * cm], repeatRows=1)
        t_ing.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#F1F5F9')),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#CBD5E1')),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('TOPPADDING', (0, 0), (-1, -1), 3),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
            ('LEFTPADDING', (0, 0), (-1, -1), 5),
            ('RIGHTPADDING', (0, 0), (-1, -1), 5),
        ]))
        sec1_flowables.extend([
            Spacer(1, 6),
            Paragraph("<b>Integrantes da Comissão de Fiscalização:</b>", style_label),
            Spacer(1, 3),
            t_ing
        ])

    # Controle de Substituição na Fiscalização
    houve_sub_str = "Sim" if controle.houve_substituicao else "Não"
    entrega_formal_str = controle.get_substituicao_entrega_formal_display()

    sub_desc = f"<b>Substituição no Período:</b> {houve_sub_str} &nbsp;|&nbsp; <b>Entrega Formal dos Registros pelo Substituto:</b> {entrega_formal_str}"
    if controle.houve_substituicao and controle.substituicao_obs:
        sub_desc += f"<br/><b>Obs. Transição:</b> {controle.substituicao_obs}"

    sec1_flowables.extend([
        Spacer(1, 6),
        make_kv_table([["Controle de Substituição:", sub_desc]])
    ])

    story.append(KeepTogether(sec1_flowables))
    story.append(Spacer(1, 10))

    # --- SEÇÃO 2: CONTROLE DE PRAZOS E MARCOS ---
    dt_rec = controle.contrato.data_recomendada_aditivo.strftime('%d/%m/%Y') if (controle.contrato and controle.contrato.data_recomendada_aditivo) else "—"
    dt_lim = controle.contrato.data_limite_aditivo.strftime('%d/%m/%Y') if (controle.contrato and controle.contrato.data_limite_aditivo) else "—"

    garantia_desc = controle.get_garantia_vigente_display()
    if controle.garantia_vigente == 'nao' and controle.garantia_providencias:
        garantia_desc += f"<br/><b>Providências Adotadas:</b> {controle.garantia_providencias}"

    if controle.confirmacao_siloms_execucao == 'sim':
        dt_exec_str = controle.data_execucao_fisico_financeira.strftime('%d/%m/%Y') if controle.data_execucao_fisico_financeira else "Data não informada"
        exec_info_pdf = f"✓ Conferido no SILOMS ({dt_exec_str})"
    else:
        exec_info_pdf = "N/A"

    sec2_data = [
        ["SILOMS — Assinatura/Início:", "✓ Conferido e atualizado" if controle.confirmacao_siloms_assinatura else "✗ Pendente / Não conferido"],
        ["SILOMS — Vigência/Aditivos:", "✓ Conferido e atualizado" if controle.confirmacao_siloms_vigencia else "✗ Pendente / Não conferido"],
        ["Término Exec. Físico-Financeira:", exec_info_pdf],
        ["Admite Termo Aditivo?", controle.get_possibilidade_aditivo_display()],
        ["Tratativas 120 dias antes:", controle.get_tratativas_120_dias_display()],
        ["Coordenação DOC/SCON:", controle.get_coordenacao_doc_scon_display()],
        ["Garantia Contratual Vigente:", garantia_desc],
        ["Data Recomendada (120d):", dt_rec],
        ["Data Limite para Aditivo (90d):", dt_lim],
    ]
    sec2_flowables = [
        make_section_header("SEÇÃO 2: CONTROLE DE PRAZOS E SILOMS"),
        Spacer(1, 4),
        make_kv_table(sec2_data)
    ]
    story.append(KeepTogether(sec2_flowables))
    story.append(Spacer(1, 10))

    # --- SEÇÃO 3: EXECUÇÃO ORÇAMENTÁRIA E FINANCEIRA ---
    sec3_data = [
        ["Notas de Empenho (com saldo):", controle.notas_empenho or "Nenhuma nota de empenho informada"],
        ["Obs. caso sem empenho:", controle.obs_sem_empenho or "N/A"],
        ["Cronograma Físico-Financeiro:", controle.get_cronograma_fisico_financeiro_display()],
    ]

    sec3_flowables = [
        make_section_header("SEÇÃO 3: EXECUÇÃO ORÇAMENTÁRIA E FINANCEIRA"),
        Spacer(1, 4),
        make_kv_table(sec3_data)
    ]

    faturas = list(controle.faturas.all())
    sec3_flowables.extend([
        Spacer(1, 6),
        Paragraph("<b>Faturas Registradas no Mês de Referência:</b>", style_label),
        Spacer(1, 3)
    ])

    if faturas:
        fat_rows = [[
            Paragraph("Nº Nota Fiscal / Fatura", style_table_head),
            Paragraph("Valor (R$)", style_table_head),
            Paragraph("Nº Ordem Bancária (OB)", style_table_head)
        ]]
        total_val = 0
        for f in faturas:
            total_val += f.valor
            val_str = f"R$ {f.valor:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
            fat_rows.append([
                Paragraph(f.numero_nf, style_value),
                Paragraph(val_str, style_value_bold),
                Paragraph(f.numero_ob or "-", style_value)
            ])
        total_str = f"R$ {total_val:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
        fat_rows.append([
            Paragraph("<b>TOTAL REGISTRADO:</b>", style_label),
            Paragraph(f"<b>{total_str}</b>", style_value_bold),
            Paragraph("", style_value)
        ])

        t_fat = Table(fat_rows, colWidths=[6.0 * cm, 6.0 * cm, 6.0 * cm], repeatRows=1)
        t_fat.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#F1F5F9')),
            ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#E2E8F0')),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#CBD5E1')),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            ('LEFTPADDING', (0, 0), (-1, -1), 6),
            ('RIGHTPADDING', (0, 0), (-1, -1), 6),
        ]))
        sec3_flowables.append(t_fat)
    else:
        sec3_flowables.append(make_kv_table([["Faturas do Mês:", "Nenhuma fatura registrada no período."]]))

    if len(faturas) <= 10:
        story.append(KeepTogether(sec3_flowables))
    else:
        story.extend(sec3_flowables)
    story.append(Spacer(1, 10))

    # --- SEÇÃO 4: CRONOGRAMA E MEDIÇÃO DE RESULTADOS ---
    alt_desc = f"Sim — {controle.alteracao_cronograma_desc}" if (controle.alteracao_cronograma == 'sim' and controle.alteracao_cronograma_desc) else controle.get_alteracao_cronograma_display()
    atr_desc = f"Sim — {controle.atraso_entrega_desc}" if (controle.atraso_entrega == 'sim' and controle.atraso_entrega_desc) else controle.get_atraso_entrega_display()
    imp_desc = f"Sim — {controle.impossibilidade_recebimento_desc}" if (controle.impossibilidade_recebimento == 'sim' and controle.impossibilidade_recebimento_desc) else controle.get_impossibilidade_recebimento_display()
    dil_desc = f"Sim — {controle.diligencia_visita_desc}" if (controle.diligencia_visita == 'sim' and controle.diligencia_visita_desc) else controle.get_diligencia_visita_display()
    glo_desc = f"Sim — {controle.glosa_desc}" if (controle.glosa_realizada == 'sim' and controle.glosa_desc) else controle.get_glosa_realizada_display()

    sec4_data = [
        ["Status do Cronograma:", controle.detalhamento_cronograma or "Sem observações específicas"],
        ["Alteração no Cronograma?", alt_desc],
        ["Atraso na Entrega?", atr_desc],
        ["Impossibilidade de Recebimento?", imp_desc],
        ["Diligência / Visita Técnica?", dil_desc],
        ["IMR Aplicado?", controle.get_imr_aplicado_display()],
        ["Glosa Realizada?", glo_desc],
    ]
    sec4_flowables = [
        make_section_header("SEÇÃO 4: CRONOGRAMA E MEDIÇÃO DE RESULTADOS"),
        Spacer(1, 4),
        make_kv_table(sec4_data)
    ]
    story.append(KeepTogether(sec4_flowables))
    story.append(Spacer(1, 10))

    # --- SEÇÃO 5: OCORRÊNCIAS E TRATATIVAS ---
    sec5_flowables = [
        make_section_header("SEÇÃO 5: OCORRÊNCIAS E TRATATIVAS"),
        Spacer(1, 4)
    ]

    ocorrencias = list(controle.ocorrencias.all())
    if ocorrencias:
        oc_rows = [[
            Paragraph("Data", style_table_head),
            Paragraph("Tipo", style_table_head),
            Paragraph("Descrição da Ocorrência", style_table_head),
            Paragraph("Ação do Fiscal / Providência", style_table_head),
            Paragraph("Prazo", style_table_head)
        ]]
        tipo_dict = {
            'reuniao': 'Reunião', 'email': 'E-mail/Ofício', 'visita': 'Visita Técnica',
            'falha': 'Falha/Descumprimento', 'notificacao': 'Notificação', 'outro': 'Outro'
        }
        for o in ocorrencias:
            t_lbl = tipo_dict.get(o.tipo, o.tipo).upper()
            dt_str = o.data.strftime('%d/%m/%Y') if o.data else "-"
            oc_rows.append([
                Paragraph(dt_str, style_value),
                Paragraph(t_lbl, style_value_bold),
                Paragraph(o.descricao or "-", style_value),
                Paragraph(o.acao_fiscal or "-", style_value),
                Paragraph(o.prazo or "-", style_value)
            ])
        t_oc = Table(oc_rows, colWidths=[2.2 * cm, 2.8 * cm, 5.5 * cm, 5.5 * cm, 2.0 * cm], repeatRows=1)
        t_oc.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#F1F5F9')),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#CBD5E1')),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('TOPPADDING', (0, 0), (-1, -1), 3),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
            ('LEFTPADDING', (0, 0), (-1, -1), 4),
            ('RIGHTPADDING', (0, 0), (-1, -1), 4),
        ]))
        sec5_flowables.append(t_oc)
    else:
        sec5_flowables.append(make_kv_table([["Ocorrências Registradas:", "Nenhuma ocorrência registrada no período."]]))

    if len(ocorrencias) <= 8:
        story.append(KeepTogether(sec5_flowables))
    else:
        story.extend(sec5_flowables)
    story.append(Spacer(1, 10))

    # --- SEÇÃO 6: SANÇÕES E PAAI ---
    sec6_data = [
        ["Empresa Sancionada (Impedimento/Inidoneidade):", controle.get_empresa_sancionada_display() if controle.empresa_sancionada else "Não informado"],
    ]
    if controle.empresa_sancionada == 'sim':
        sec6_data.append(["Doc. Comprobatória no SILOMS:", controle.get_doc_sancao_siloms_display() if controle.doc_sancao_siloms else "Não informado"])
        if controle.sancao_observacao:
            sec6_data.append(["Obs. Sanção:", controle.sancao_observacao])

    sec6_data.extend([
        ["Ocorrências Ativas/Reincidentes:", controle.get_ocorrencias_ativas_empresa_display()],
        ["Necessidade de PAAI?", controle.get_necessidade_paai_display()],
    ])
    if controle.paai_justificativa:
        sec6_data.append(["Justificativa PAAI:", controle.paai_justificativa])

    sec6_flowables = [
        make_section_header("SEÇÃO 6: SANÇÕES E PAAI"),
        Spacer(1, 4),
        make_kv_table(sec6_data)
    ]
    story.append(KeepTogether(sec6_flowables))
    story.append(Spacer(1, 10))

    if controle.observacao:
        obs_flowables = [
            make_section_header("OBSERVAÇÕES GERAIS"),
            Spacer(1, 4),
            make_kv_table([["Observações:", controle.observacao]])
        ]
        story.append(KeepTogether(obs_flowables))
        story.append(Spacer(1, 10))

    # --- ASSINATURAS DA COMISSÃO DE FISCALIZAÇÃO ---
    MESES_PT = [
        '', 'janeiro', 'fevereiro', 'março', 'abril', 'maio', 'junho',
        'julho', 'agosto', 'setembro', 'outubro', 'novembro', 'dezembro'
    ]
    dt_envio = controle.data_envio
    data_str_pt = f"Brasília-DF, {dt_envio.day:02d} de {MESES_PT[dt_envio.month]} de {dt_envio.year}."

    style_date_right = ParagraphStyle(
        'DateRight',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9,
        leading=11,
        textColor=colors.HexColor('#0F172A'),
        alignment=2
    )

    sig_block = [
        Spacer(1, 10),
        Paragraph(
            "Atesto a veracidade das informações prestadas no presente Livro do Fiscal relativo ao acompanhamento e fiscalização deste contrato.",
            style_value
        ),
        Spacer(1, 10),
        Paragraph(data_str_pt, style_date_right),
        Spacer(1, 25)
    ]

    # Determinar a assinatura do responsável pelo envio
    assinantes = []
    if controle.agente:
        p_sigla = controle.agente.posto.sigla if (controle.agente and controle.agente.posto) else ""
        n_guerra = controle.agente.nome_de_guerra.upper()
        funcao_titulo = "Fiscal Responsável"
        if comissao:
            ing_resp = comissao.integrantes.filter(agente=controle.agente, data_desligamento__isnull=True).first()
            if ing_resp:
                if ing_resp.posto_graduacao:
                    p_sigla = ing_resp.posto_graduacao.sigla
                if ing_resp.funcao:
                    funcao_titulo = ing_resp.funcao.titulo
        assinantes.append((f"{p_sigla} {n_guerra}".strip(), funcao_titulo))
    elif integrantes:
        ing = integrantes[0]
        p_sigla = ing.posto_graduacao.sigla if ing.posto_graduacao else (ing.agente.posto.sigla if (ing.agente and ing.agente.posto) else "")
        n_guerra = ing.agente.nome_de_guerra.upper() if ing.agente else "FISCAL"
        f_nome = ing.funcao.titulo if ing.funcao else "Fiscal Responsável"
        assinantes.append((f"{p_sigla} {n_guerra}".strip(), f_nome))

    sig_cells = []
    for nome_sig, func_sig in assinantes:
        cell_content = [
            Paragraph("____________________________________________", ParagraphStyle('Line', parent=styles['Normal'], alignment=1, fontSize=9, textColor=colors.HexColor('#94A3B8'))),
            Spacer(1, 2),
            Paragraph(f"<b>{nome_sig}</b>", ParagraphStyle('Name', parent=styles['Normal'], alignment=1, fontSize=8.5, leading=10, textColor=colors.HexColor('#0F172A'))),
            Paragraph(func_sig, ParagraphStyle('Func', parent=styles['Normal'], alignment=1, fontSize=8, leading=10, textColor=colors.HexColor('#64748B')))
        ]
        sig_cells.append(cell_content)

    if sig_cells:
        t_sig = Table([[sig_cells[0]]], colWidths=[printable_width])
        t_sig.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 15),
        ]))
        sig_block.append(t_sig)

    story.append(KeepTogether(sig_block))

    # Construir PDF com o canvas customizado de rodapé
    def make_canvas(*args, **kwargs):
        emp_nome = controle.contrato.empresa.nome_exibicao if (controle.contrato and controle.contrato.empresa) else ""
        return LivroFiscalCanvas(
            *args,
            contrato_numero=controle.contrato.numero if controle.contrato else "",
            empresa_nome=emp_nome,
            mes_referencia=controle.mes_referencia,
            ano_referencia=controle.ano_referencia,
            **kwargs
        )

    doc.build(story, canvasmaker=make_canvas)
    buffer.seek(0)

    # Nomenclatura solicitada: livro_fiscal_{contrato}_{empresa}_{ano_referencia}_{mes_referencia}.pdf
    contrato_slug = slugify(controle.contrato.numero.replace('/', '-')) if (controle.contrato and controle.contrato.numero) else f"contrato-{controle.contrato.id}"
    empresa_slug = slugify(controle.contrato.empresa.razao_social) if (controle.contrato and controle.contrato.empresa and controle.contrato.empresa.razao_social) else "empresa"
    filename = f"livro_fiscal_{contrato_slug}_{empresa_slug}_{controle.ano_referencia}_{controle.mes_referencia:02d}.pdf"

    from django.http import FileResponse
    response = FileResponse(buffer, as_attachment=True, filename=filename, content_type='application/pdf')
    response['Cache-Control'] = 'no-cache, no-store, must-revalidate, max-age=0'
    response['Pragma'] = 'no-cache'
    response['Expires'] = '0'
    return response

