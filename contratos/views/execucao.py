import json
from datetime import date, timedelta
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse, HttpResponse, FileResponse
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.urls import reverse
from django.utils import timezone
from django.utils.dateparse import parse_datetime, parse_date
from django.utils.text import slugify
from django.conf import settings
import csv
import io
import os

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
    ControleExecucao, RegistroFatura, OcorrenciaContratual, ApontamentoCorrecaoExecucao,
    HistoricoObservacaoExecucao
)
from contratos.forms import ControleExecucaoForm, OcorrenciaContratualForm
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
    """
    Formulário para preenchimento e envio do Livro do Fiscal (NPA 009/SCON/2025).
    Suporta Lançamento Tempestivo Contínuo (Salvar Rascunho) e Ateste Final (Finalizar e Atestar).
    """
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

    if request.method == 'POST':
        form = ControleExecucaoForm(request.POST, contrato=contrato, instance=controle_existente)
        acao = request.POST.get('acao', 'finalizar')

        if form.is_valid():
            controle = form.save(commit=False)
            controle.contrato = contrato
            controle.mes_referencia = filtro_mes
            controle.ano_referencia = filtro_ano

            if acao == 'rascunho':
                controle.status = 'rascunho'
            else:
                controle.status = 'entregue'

            controle.data_envio = timezone.now()
            controle.save()

            if controle.observacao and controle.observacao.strip():
                HistoricoObservacaoExecucao.objects.create(
                    controle=controle,
                    agente=controle.agente,
                    observacao=controle.observacao.strip()
                )

            # Processar Ocorrências (JSON enviado pelo frontend com 10 campos da NPA 009)
            ocorrencias_json_str = request.POST.get('ocorrencias_json', '[]')
            relatorio_text_lines = []

            if not controle.sem_ocorrencias_periodo:
                try:
                    ocorrencias_data = json.loads(ocorrencias_json_str)
                    controle.ocorrencias.all().delete()
                    for idx, oc in enumerate(ocorrencias_data, 1):
                        dt_raw = oc.get('data_hora') or oc.get('data')
                        dt_parsed = parse_datetime(dt_raw) if dt_raw else None
                        if not dt_parsed and dt_raw:
                            d_only = parse_date(dt_raw[:10])
                            if d_only:
                                dt_parsed = timezone.make_aware(timezone.datetime.combine(d_only, timezone.datetime.min.time()))
                        if not dt_parsed:
                            dt_parsed = timezone.now()
                        elif timezone.is_naive(dt_parsed):
                            dt_parsed = timezone.make_aware(dt_parsed)

                        tp = oc.get('tipo', 'TECNICA')
                        desc = oc.get('descricao', '').strip()
                        local = oc.get('local', '').strip()
                        disp = oc.get('dispositivo_violado', '').strip()
                        evid = oc.get('evidencias', '').strip()
                        notif_emit = bool(oc.get('notificacao_emitida'))
                        notif_num = oc.get('notificacao_numero', '').strip()
                        prazo = int(oc.get('prazo_dias_uteis') or 5)
                        ciencia = oc.get('ciencia_preposto', 'na')
                        tramite = bool(oc.get('tramite_arc'))
                        status_oc = oc.get('status_ocorrencia', 'aberto')
                        acao_fiscal = oc.get('acao_fiscal', '').strip()

                        if desc:
                            OcorrenciaContratual.objects.create(
                                controle=controle,
                                data_hora=dt_parsed,
                                local=local,
                                tipo=tp,
                                descricao=desc,
                                dispositivo_violado=disp,
                                evidencias=evid,
                                notificacao_emitida=notif_emit,
                                notificacao_numero=notif_num,
                                prazo_dias_uteis=prazo,
                                ciencia_preposto=ciencia,
                                tramite_arc=tramite,
                                status_ocorrencia=status_oc,
                                acao_fiscal=acao_fiscal,
                            )
                            relatorio_text_lines.append(
                                f"[{idx}] {dt_parsed.strftime('%d/%m/%Y %H:%M')} | {tp} | Local: {local or 'N/A'}\n"
                                f"    Descrição: {desc}\n"
                                f"    Dispositivo: {disp or 'N/A'} | Notificação: {'Sim (' + notif_num + ')' if notif_emit else 'Não'}\n"
                                f"    Situação: {status_oc.upper()} | Providência: {acao_fiscal or 'N/A'}"
                            )
                except Exception:
                    pass
            else:
                # Marcado como sem ocorrências
                controle.ocorrencias.all().delete()
                controle.relatorio_ocorrencias = "Em conformidade: Não houve ocorrências ou desvios registrados no período."

            if relatorio_text_lines and not controle.sem_ocorrencias_periodo:
                controle.relatorio_ocorrencias = "\n\n".join(relatorio_text_lines)
            elif not controle.relatorio_ocorrencias:
                controle.relatorio_ocorrencias = "Em conformidade: Não houve ocorrências no período."

            controle.save()

            if acao == 'rascunho':
                messages.success(request, f"Rascunho do Livro {controle.numero_livro} salvo com sucesso! O livro permanece em andamento para lançamentos tempestivos.")
                return redirect('formulario_execucao', contrato_id=contrato.id)
            else:
                messages.success(request, f"Livro do Fiscal {controle.numero_livro} finalizado e atestado com sucesso!")
                return redirect('upload_prestacao', contrato_id=contrato.id)
        else:
            messages.error(request, "Por favor, corrija os erros apontados no formulário.")
    else:
        form = ControleExecucaoForm(contrato=contrato, instance=controle_existente)

    ocorrencias_existentes = []
    apontamentos = []
    if controle_existente:
        for oc in controle_existente.ocorrencias.all():
            ocorrencias_existentes.append({
                'id': oc.id,
                'data_hora': oc.data_hora.strftime('%Y-%m-%dT%H:%M') if oc.data_hora else '',
                'data_hora_fmt': oc.data_hora.strftime('%d/%m/%Y %H:%M') if oc.data_hora else '',
                'local': oc.local,
                'tipo': oc.tipo,
                'tipo_display': oc.get_tipo_display(),
                'descricao': oc.descricao,
                'dispositivo_violado': oc.dispositivo_violado,
                'evidencias': oc.evidencias,
                'notificacao_emitida': oc.notificacao_emitida,
                'notificacao_numero': oc.notificacao_numero,
                'prazo_dias_uteis': oc.prazo_dias_uteis,
                'ciencia_preposto': oc.ciencia_preposto,
                'ciencia_preposto_display': oc.get_ciencia_preposto_display(),
                'tramite_arc': oc.tramite_arc,
                'status_ocorrencia': oc.status_ocorrencia,
                'status_ocorrencia_display': oc.get_status_ocorrencia_display(),
                'acao_fiscal': oc.acao_fiscal,
                'notificacao_pdf_url': reverse('download_notificacao_anexo_d_pdf', args=[oc.id]) if oc.id else ''
            })
        apontamentos = controle_existente.apontamentos.select_related('autor').all()

    return render(request, 'contratos/execucao/formulario.html', {
        'contrato': contrato,
        'comissao': comissao_ativa,
        'integrantes': integrantes,
        'form': form,
        'controle_existente': controle_existente,
        'apontamentos': apontamentos,
        'ocorrencias_json': json.dumps(ocorrencias_existentes, default=str),
        'mes_referencia': filtro_mes,
        'ano_referencia': filtro_ano,
    })


@require_POST
def salvar_ocorrencia_tempestiva(request):
    """
    Endpoint AJAX para registrar uma ocorrência tempestiva avulsa durante o mês.
    Cria ou recupera o ControleExecucao em rascunho e retorna os dados da ocorrência salva.
    """
    try:
        data = json.loads(request.body)
        contrato_id = data.get('contrato_id')
        mes = int(data.get('mes_referencia'))
        ano = int(data.get('ano_referencia'))
        contrato = get_object_or_404(Contrato, pk=contrato_id)

        controle, _ = ControleExecucao.objects.get_or_create(
            contrato=contrato,
            mes_referencia=mes,
            ano_referencia=ano,
            defaults={'status': 'rascunho', 'omap': 'GAP-BR', 'unidade_gestora': '120006 - GAP-BR'}
        )

        oc_id = data.get('id')
        dt_raw = data.get('data_hora')
        dt_parsed = parse_datetime(dt_raw) if dt_raw else timezone.now()
        if not dt_parsed:
            dt_parsed = timezone.now()
        elif timezone.is_naive(dt_parsed):
            dt_parsed = timezone.make_aware(dt_parsed)

        if oc_id:
            oc = get_object_or_404(OcorrenciaContratual, pk=oc_id, controle=controle)
        else:
            oc = OcorrenciaContratual(controle=controle)

        oc.data_hora = dt_parsed
        oc.local = data.get('local', '').strip()
        oc.tipo = data.get('tipo', 'TECNICA')
        oc.descricao = data.get('descricao', '').strip()
        oc.dispositivo_violado = data.get('dispositivo_violado', '').strip()
        oc.evidencias = data.get('evidencias', '').strip()
        oc.notificacao_emitida = bool(data.get('notificacao_emitida'))
        oc.notificacao_numero = data.get('notificacao_numero', '').strip()
        oc.prazo_dias_uteis = int(data.get('prazo_dias_uteis') or 5)
        oc.ciencia_preposto = data.get('ciencia_preposto', 'na')
        oc.tramite_arc = bool(data.get('tramite_arc'))
        oc.status_ocorrencia = data.get('status_ocorrencia', 'aberto')
        oc.acao_fiscal = data.get('acao_fiscal', '').strip()
        oc.save()

        # Desmarca 'sem_ocorrencias_periodo' se houver ocorrência
        controle.sem_ocorrencias_periodo = False
        controle.save()

        notif_url = reverse('download_notificacao_anexo_d_pdf', args=[oc.id]) if oc.notificacao_emitida else ""

        return JsonResponse({
            'success': True,
            'ocorrencia': {
                'id': oc.id,
                'data_hora': oc.data_hora.strftime('%Y-%m-%dT%H:%M'),
                'data_hora_fmt': oc.data_hora.strftime('%d/%m/%Y %H:%M'),
                'local': oc.local,
                'tipo': oc.tipo,
                'tipo_display': oc.get_tipo_display(),
                'descricao': oc.descricao,
                'dispositivo_violado': oc.dispositivo_violado,
                'evidencias': oc.evidencias,
                'notificacao_emitida': oc.notificacao_emitida,
                'notificacao_numero': oc.notificacao_numero,
                'prazo_dias_uteis': oc.prazo_dias_uteis,
                'ciencia_preposto': oc.ciencia_preposto,
                'ciencia_preposto_display': oc.get_ciencia_preposto_display(),
                'tramite_arc': oc.tramite_arc,
                'status_ocorrencia': oc.status_ocorrencia,
                'status_ocorrencia_display': oc.get_status_ocorrencia_display(),
                'acao_fiscal': oc.acao_fiscal,
                'notificacao_pdf_url': notif_url,
            }
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)


@require_POST
def excluir_ocorrencia(request, pk):
    """Exclui uma ocorrência pontual via AJAX."""
    oc = get_object_or_404(OcorrenciaContratual, pk=pk)
    controle = oc.controle
    oc.delete()
    if not controle.ocorrencias.exists():
        controle.sem_ocorrencias_periodo = True
        controle.save()
    return JsonResponse({'success': True})


@login_required
def visualizar_controle_execucao(request, pk):
    """Visualização em formato somente leitura do Livro do Fiscal (ACI / Admin / Gestor)."""
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
    historico_observacoes = controle.historico_observacoes.select_related('agente', 'agente__posto').all()

    return render(request, 'contratos/execucao/visualizar.html', {
        'controle': controle,
        'comissao': comissao,
        'integrantes': integrantes,
        'apontamentos': apontamentos,
        'ocorrencias_estruturadas': ocorrencias_estruturadas,
        'historico_observacoes': historico_observacoes,
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

    if novo_status not in ['rascunho', 'entregue', 'correcao', 'ok']:
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
    """Exporta planilha de acompanhamento da Execução Contratual (Livro do Fiscal NPA 009)."""
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
        'Número do Livro', 'Contrato', 'Objeto', 'UG', 'OMAP', 'Fiscal Responsável',
        'Mês Ref.', 'Ano Ref.', 'Data Envio', 'Status', 'Preposto Nome', 'Preposto Tel.',
        'Sem Ocorrências?', 'Qtd Ocorrências', 'Obra Engenharia?', 'Relatório Resumido'
    ])

    controles = ControleExecucao.objects.filter(
        mes_referencia=filtro_mes, ano_referencia=filtro_ano
    ).select_related('contrato', 'agente', 'agente__posto').prefetch_related('ocorrencias')

    for c in controles:
        fiscal_nome = f"{c.agente.posto.sigla} {c.agente.nome_de_guerra}" if c.agente else "Não informado"
        writer.writerow([
            c.numero_livro,
            c.contrato.numero,
            c.contrato.objeto[:50],
            c.unidade_gestora,
            c.omap,
            fiscal_nome,
            c.mes_referencia,
            c.ano_referencia,
            c.data_envio.strftime('%d/%m/%Y %H:%M'),
            c.get_status_display(),
            c.preposto_nome or '-',
            c.preposto_telefone or '-',
            'Sim' if c.sem_ocorrencias_periodo else 'Não',
            c.ocorrencias.count(),
            'Sim' if c.eh_obra_engenharia else 'Não',
            c.relatorio_ocorrencias[:150]
        ])

    return response


# =========================================================================
# Canvas Customizado para o Livro do Fiscal (Rodapé Oficial COMAER / GAP-BR)
# =========================================================================
class LivroFiscalCanvas(canvas.Canvas):
    def __init__(self, *args, numero_livro="", empresa_nome="", **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []
        self.numero_livro = numero_livro
        self.empresa_nome = empresa_nome

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
                emp_str = f" ({self.empresa_nome})" if self.empresa_nome else ""
                footer_text = f"Livro do Fiscal nº {self.numero_livro}{emp_str} — pág. {self._pageNumber}/{num_pages}"

                self.setStrokeColor(colors.HexColor('#CBD5E1'))
                self.setLineWidth(0.5)
                self.line(1.5 * cm, 1.2 * cm, 19.5 * cm, 1.2 * cm)
                self.drawRightString(19.5 * cm, 0.8 * cm, footer_text)
                self.restoreState()
            super().showPage()
        super().save()


# =========================================================================
# Geração de PDF do Livro do Fiscal (NPA 009/SCON/2025)
# =========================================================================
def gerar_livro_fiscal_pdf(request, pk):
    """Gera o PDF oficial do Livro de Registro de Ocorrências do Fiscal de Contrato."""
    controle = get_object_or_404(
        ControleExecucao.objects.select_related(
            'contrato', 'contrato__empresa', 'agente', 'agente__posto'
        ).prefetch_related('ocorrencias'),
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
    printable_width = 18.0 * cm

    style_header_title = ParagraphStyle(
        'H1', fontName='Helvetica-Bold', fontSize=11, leading=13,
        textColor=colors.HexColor('#0F172A'), alignment=1
    )
    style_header_sub = ParagraphStyle(
        'H2', fontName='Helvetica-Bold', fontSize=10, leading=12,
        textColor=colors.HexColor('#0D6EFD'), alignment=1
    )
    style_header_meta = ParagraphStyle(
        'H3', fontName='Helvetica-Oblique', fontSize=8, leading=10,
        textColor=colors.HexColor('#64748B'), alignment=1
    )
    style_section_title = ParagraphStyle(
        'SecTitle', fontName='Helvetica-Bold', fontSize=9, leading=11,
        textColor=colors.white
    )
    style_label = ParagraphStyle(
        'Label', fontName='Helvetica-Bold', fontSize=7.5, leading=9.5,
        textColor=colors.HexColor('#334155')
    )
    style_value = ParagraphStyle(
        'Value', fontName='Helvetica', fontSize=8, leading=10,
        textColor=colors.HexColor('#0F172A')
    )
    style_value_bold = ParagraphStyle(
        'ValB', fontName='Helvetica-Bold', fontSize=8, leading=10,
        textColor=colors.HexColor('#0F172A')
    )
    style_table_head = ParagraphStyle(
        'THead', fontName='Helvetica-Bold', fontSize=7.5, leading=9.5,
        textColor=colors.HexColor('#1E293B'), alignment=0
    )

    story = []

    # Cabeçalho Oficial
    logo_path = os.path.join(settings.BASE_DIR, 'contratos', 'static', 'contratos', 'img', 'gap_logo.png')
    logo_img = None
    if os.path.exists(logo_path):
        try:
            logo_img = Image(logo_path, width=1.6 * cm, height=2.0 * cm)
        except Exception:
            logo_img = None

    header_nodes = [
        Paragraph("MINISTÉRIO DA DEFESA | COMANDO DA AERONÁUTICA", style_header_title),
        Paragraph("GRUPAMENTO DE APOIO DE BRASÍLIA (GAP-BR)", style_header_title),
        Spacer(1, 2),
        Paragraph(f"LIVRO DE REGISTRO DE OCORRÊNCIAS DO FISCAL DE CONTRATO", style_header_sub),
        Paragraph(f"Livro nº {controle.numero_livro} — Período: {controle.mes_referencia:02d}/{controle.ano_referencia}", style_header_meta),
        Paragraph("<i>Conforme NPA 009/SCON/2025 e Lei nº 14.133/2021, art. 117, § 1º</i>", style_header_meta),
    ]

    if logo_img:
        ht = Table([[logo_img, header_nodes]], colWidths=[2.2 * cm, 15.8 * cm])
        ht.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('ALIGN', (0, 0), (0, 0), 'CENTER'),
            ('TOPPADDING', (0, 0), (-1, -1), 0),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
        ]))
        story.append(ht)
    else:
        story.extend(header_nodes)

    story.append(Spacer(1, 8))
    story.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor('#0D6EFD'), spaceAfter=8))

    def make_sec_header(title):
        p = Paragraph(f"<b>{title}</b>", style_section_title)
        t = Table([[p]], colWidths=[printable_width])
        t.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#0D6EFD')),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            ('LEFTPADDING', (0, 0), (-1, -1), 6),
            ('RIGHTPADDING', (0, 0), (-1, -1), 6),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ]))
        return t

    def make_kv(rows, widths=None):
        if not widths:
            widths = [4.8 * cm, 13.2 * cm]
        formatted = []
        for r in rows:
            formatted.append([Paragraph(r[0], style_label), Paragraph(str(r[1]), style_value)])
        t = Table(formatted, colWidths=widths)
        t.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#F8FAFC')),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#E2E8F0')),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('TOPPADDING', (0, 0), (-1, -1), 3),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
            ('LEFTPADDING', (0, 0), (-1, -1), 5),
            ('RIGHTPADDING', (0, 0), (-1, -1), 5),
        ]))
        return t

    # 1. Termo de Abertura e Identificação
    contrato = controle.contrato
    empresa = contrato.empresa if contrato else None
    empresa_str = f"{empresa.razao_social} (CNPJ: {empresa.cnpj})" if empresa else "Não informada"
    vig_str = f"{contrato.vigencia_inicio.strftime('%d/%m/%Y')} a {contrato.vigencia_fim.strftime('%d/%m/%Y')}" if (contrato and contrato.vigencia_inicio and contrato.vigencia_fim) else "Não informada"
    fiscal_resp = f"{controle.agente.posto.sigla} {controle.agente.nome_de_guerra}" if (controle.agente and controle.agente.posto) else (controle.agente.nome_de_guerra if controle.agente else "Não informado")

    comissao = Comissao.objects.filter(contrato=contrato, ativa=True, tipo='FISCALIZACAO').first()
    if not comissao:
        comissao = Comissao.objects.filter(contrato=contrato, tipo='FISCALIZACAO').order_by('-data_inicio').first()

    desig_str = "Conforme Portaria de Designação"
    if comissao and comissao.boletim_numero:
        desig_str = f"BInt nº {comissao.boletim_numero}"
        if comissao.boletim_data:
            desig_str += f" de {comissao.boletim_data.strftime('%d/%m/%Y')}"
        if comissao.portaria_numero:
            desig_str += f" / Portaria nº {comissao.portaria_numero}"

    prep_dados = f"{controle.preposto_nome or 'Não informado'} | Cargo: {controle.preposto_cargo or '-'} | CPF/RG: {controle.preposto_cpf or '-'} | Tel: {controle.preposto_telefone or '-'} | E-mail: {controle.preposto_email or '-'}"

    abertura_data = [
        ["Número do Livro / Ano:", f"<b>{controle.numero_livro}</b>"],
        ["Processo Adm. de Gestão (PAG / e-PAG):", getattr(contrato, 'pag', None) or "e-PAG"],
        ["Organização Militar Apoiada (OMAP):", controle.omap],
        ["Unidade Gestora (UG / Gestão):", controle.unidade_gestora],
        ["Número e Objeto do Contrato:", f"Contrato nº {contrato.numero} — {contrato.objeto}"],
        ["Contratada / CNPJ:", empresa_str],
        ["Período de Vigência Contratual:", vig_str],
        ["Ato de Designação da Fiscalização:", desig_str],
        ["Fiscal Responsável (Registro):", fiscal_resp],
        ["Preposto Aceito da Contratada:", prep_dados],
        ["Fundamentação Normativa:", "NPA 009/SCON/2025, Manual de Contratações do COMAER (13/12/2024), Lei nº 14.133/2021 (art. 117, § 1º)"],
    ]

    story.append(KeepTogether([
        make_sec_header("1. TERMO DE ABERTURA E IDENTIFICAÇÃO DO CONTRATO"),
        Spacer(1, 3),
        make_kv(abertura_data)
    ]))
    story.append(Spacer(1, 8))

    # 2. Diário de Obra e Engenharia (Anexo B) - se aplicável
    if controle.eh_obra_engenharia:
        obras_data = [
            ["Condições Climáticas e Paralisações:", controle.condicoes_climaticas or "Sem registro de paralisações por intempéries."],
            ["Efetivo de Pessoal no Canteiro:", controle.efetivo_trabalhadores or "Conforme equipe padrão informada pela contratada."],
            ["Equipamentos e Maquinário:", controle.maquinario_equipamentos or "Equipamentos em condições operacionais normais."],
            ["Anotação de Resp. Técnica (ART/RRT):", controle.art_rrt or "ART/RRT quitada e arquivada no e-PAG."],
            ["Matrícula CEI / CNO no INSS:", controle.matricula_cei_cno or "Matrícula regularizada no e-PAG."],
            ["Segurança do Trabalho e CAT:", controle.seguranca_trabalho_cat or "EPIs em uso regular. Sem registro de acidentes no período."],
        ]
        story.append(KeepTogether([
            make_sec_header("2. REQUISITOS ESPECÍFICOS PARA DIÁRIO DE OBRA E ENGENHARIA (ANEXO B DA NPA 009)"),
            Spacer(1, 3),
            make_kv(obras_data)
        ]))
        story.append(Spacer(1, 8))

    # 3. Registro de Ocorrências Contratuais (10 Campos)
    story.append(make_sec_header("3. REGISTRO DE OCORRÊNCIAS DA FISCALIZAÇÃO"))
    story.append(Spacer(1, 3))

    ocorrencias = list(controle.ocorrencias.all())
    if controle.sem_ocorrencias_periodo or not ocorrencias:
        conf_table = Table([[
            Paragraph(
                "<b>DECLARAÇÃO DE CONFORMIDADE NO PERÍODO:</b><br/>"
                f"Atesto que durante o período de apuração de <b>{controle.mes_referencia:02d}/{controle.ano_referencia}</b> "
                "a execução do objeto contratual transcorreu em estrita conformidade com as cláusulas avençadas e os instrumentos convocatórios, "
                "não tendo sido constatadas irregularidades, falhas, descumprimentos ou desvios passíveis de notificação ou glosa.",
                style_value
            )
        ]], colWidths=[printable_width])
        conf_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#F0FDF4')),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#86EFAC')),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('LEFTPADDING', (0, 0), (-1, -1), 8),
            ('RIGHTPADDING', (0, 0), (-1, -1), 8),
        ]))
        story.append(conf_table)
    else:
        for idx, oc in enumerate(ocorrencias, 1):
            dt_s = oc.data_hora.strftime('%d/%m/%Y às %H:%M') if oc.data_hora else "S/D"
            notif_s = f"Sim (Nº {oc.notificacao_numero}) — Prazo: {oc.prazo_dias_uteis} dias úteis" if oc.notificacao_emitida else "Não emitida"
            tramite_s = "Sim (Encaminhado à ARC para PAAI)" if oc.tramite_arc else "Não (Trâmite ordinário)"

            oc_data = [
                ["Item / Data e Horário:", f"<b>Ocorrência #{idx}</b> — {dt_s}"],
                ["Local da Ocorrência:", oc.local or "Dependências da OM"],
                ["Tipo de Ocorrência:", oc.get_tipo_display()],
                ["Descrição Detalhada e Factual:", oc.descricao],
                ["Dispositivo Contratual Violado:", oc.dispositivo_violado or "Cláusulas gerais do Termo de Referência"],
                ["Evidências Anexadas:", oc.evidencias or "Registros fotográficos / e-PAG"],
                ["Notificação e Prazo (Anexo D):", notif_s],
                ["Ciência / Recusa do Preposto:", oc.get_ciencia_preposto_display()],
                ["Trâmite à ARC / SCON:", tramite_s],
                ["Situação Atual:", f"<b>{oc.get_status_ocorrencia_display().upper()}</b>"],
                ["Determinação do Fiscal:", oc.acao_fiscal or "Determinado o saneamento tempestivo."],
            ]
            story.append(KeepTogether([
                make_kv(oc_data, widths=[4.5 * cm, 13.5 * cm]),
                Spacer(1, 4)
            ]))

    story.append(Spacer(1, 6))

    # Observações Complementares
    if controle.observacao:
        obs_table = make_kv([["Observações Gerais / Justificativas:", controle.observacao]])
        story.append(KeepTogether([
            make_sec_header("4. OBSERVAÇÕES E APONTAMENTOS COMPLEMENTARES"),
            Spacer(1, 3),
            obs_table,
            Spacer(1, 6)
        ]))

    # Declaração Oficial de Conformidade da NPA 009
    decl_p = Paragraph(
        "<i>\"Declaro, sob as penas da lei e regulamentos militares aplicáveis, que todas as ocorrências, apontamentos e orientações registradas neste Livro foram anotadas de forma fidedigna, objetiva, imparcial e tempestiva. Atesto o cumprimento integral das obrigações fixadas no art. 117, § 1º da Lei nº 14.133/2021, na NPA 009/SCON/2025 do GAP-BR e no Manual de Contratações Públicas do COMAER.\"</i>",
        style_value
    )
    decl_t = Table([[decl_p]], colWidths=[printable_width])
    decl_t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#F8FAFC')),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#CBD5E1')),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('RIGHTPADDING', (0, 0), (-1, -1), 8),
    ]))

    # Bloco de Assinatura
    p_sigla = controle.agente.posto.sigla if (controle.agente and controle.agente.posto) else ""
    n_guerra = controle.agente.nome_de_guerra.upper() if controle.agente else "FISCAL"
    nome_assinante = f"{p_sigla} {n_guerra}".strip()

    sig_content = [
        Paragraph("____________________________________________________________", ParagraphStyle('Line', parent=styles['Normal'], alignment=1, fontSize=8, textColor=colors.HexColor('#94A3B8'))),
        Spacer(1, 2),
        Paragraph(f"<b>{nome_assinante}</b>", ParagraphStyle('Name', parent=styles['Normal'], alignment=1, fontSize=8.5, leading=10, textColor=colors.HexColor('#0F172A'))),
        Paragraph("Fiscal Responsável pelo Contrato — GAP-BR", ParagraphStyle('Func', parent=styles['Normal'], alignment=1, fontSize=7.5, leading=9.5, textColor=colors.HexColor('#64748B'))),
        Paragraph("(datado e assinado eletronicamente)", ParagraphStyle('Meta', parent=styles['Normal'], alignment=1, fontSize=7.5, leading=9.5, textColor=colors.HexColor('#64748B')))
    ]

    sig_t = Table([[sig_content]], colWidths=[printable_width])
    sig_t.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('TOPPADDING', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
    ]))

    story.append(KeepTogether([
        make_sec_header("DECLARAÇÃO DE CONFORMIDADE E FECHAMENTO"),
        Spacer(1, 4),
        decl_t,
        Spacer(1, 6),
        sig_t
    ]))

    def make_canvas(*args, **kwargs):
        emp_nome = controle.contrato.empresa.nome_exibicao if (controle.contrato and controle.contrato.empresa) else ""
        return LivroFiscalCanvas(
            *args,
            numero_livro=controle.numero_livro,
            empresa_nome=emp_nome,
            **kwargs
        )

    doc.build(story, canvasmaker=make_canvas)
    buffer.seek(0)

    slug_ct = slugify(contrato.numero.replace('/', '-'))
    filename = f"livro_fiscal_{slug_ct}_{controle.ano_referencia}_{controle.mes_referencia:02d}.pdf"
    response = FileResponse(buffer, as_attachment=True, filename=filename, content_type='application/pdf')
    response['Cache-Control'] = 'no-cache, no-store, must-revalidate, max-age=0'
    return response


# =========================================================================
# Geração de PDF do Anexo D da NPA 009 (Notificação Oficial com Testemunhas)
# =========================================================================
def gerar_notificacao_anexo_d_pdf(request, pk):
    """
    Gera a Notificação Oficial de Ocorrência com prazo de 5 dias úteis e
    Certidão de Recusa de Assinatura com 2 testemunhas (Anexo D da NPA 009/SCON/2025).
    """
    oc = get_object_or_404(
        OcorrenciaContratual.objects.select_related(
            'controle', 'controle__contrato', 'controle__contrato__empresa',
            'controle__agente', 'controle__agente__posto'
        ),
        pk=pk
    )
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
    style_body_bold = ParagraphStyle(
        'DocBodyB', fontName='Helvetica-Bold', fontSize=8.5, leading=12,
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
        f"<b>2.</b> A presente Notificação decorre de descumprimento apurado no e-PAG correspondente, especificamente quanto ao seguinte fato:",
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

    # Linha divisória pontilhada
    story.append(HRFlowable(width="100%", thickness=0.8, color=colors.HexColor('#94A3B8'), spaceAfter=8))

    # Recibo e Ciência do Notificado
    recibo_content = [
        Paragraph("<b>RECEIBO E CIÊNCIA DO NOTIFICADO:</b>", style_label),
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

    slug_notif = slugify(oc.notificacao_numero or f"notificacao-{oc.id}")
    filename = f"notificacao_anexo_d_{slug_notif}.pdf"
    response = FileResponse(buffer, as_attachment=True, filename=filename, content_type='application/pdf')
    response['Cache-Control'] = 'no-cache, no-store, must-revalidate, max-age=0'
    return response
