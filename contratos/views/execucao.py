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

from django.core.exceptions import ValidationError

from contratos.models import (
    Contrato, Agente, Integrante, Comissao, CalendarioPrestacao,
    ControleExecucao, RegistroFatura, OcorrenciaContratual, ApontamentoCorrecaoExecucao,
    HistoricoObservacaoExecucao
)
from contratos.forms import ControleExecucaoForm, OcorrenciaContratualForm
from contratos.utils import is_admin, is_auditor, admin_required, auditor_required
from contratos.services.notificacao import NotificacaoService
from contratos.services.execucao_modulos import ModulosLivroFiscalService
from contratos.services.ocorrencias import OcorrenciasService


def portal_execucao_index(request):
    """Redireciona para o Portal de Prestação de Contas público."""
    return redirect('portal_prestacao_index')


def portal_execucao_fiscais(request):
    """Redireciona para a Seleção de Contratos no Portal de Prestação de Contas."""
    return redirect('portal_prestacao_fiscais')


def portal_registro_tempestivo(request):
    """
    Os lançamentos tempestivos devem ser realizados pelo Portal de Prestação de Contas.
    Redireciona o acesso de /tempestivo/ para o portal da prestação de contas.
    """
    return redirect('portal_prestacao_fiscais')


@require_POST
def excluir_controle_execucao_publico(request, contrato_id):
    """
    Permite ao fiscal excluir o registro do Livro do Fiscal do contrato no mês de referência atual.
    Livros já atestados ('entregue') ou homologados ('ok') não podem ser excluídos pelo fiscal.
    """
    contrato = get_object_or_404(Contrato, pk=contrato_id)
    hoje = date.today()
    primeiro_dia_mes_atual = hoje.replace(day=1)
    ultimo_dia_mes_anterior = primeiro_dia_mes_atual - timedelta(days=1)
    filtro_mes = ultimo_dia_mes_anterior.month
    filtro_ano = ultimo_dia_mes_anterior.year

    controle = ControleExecucao.objects.filter(
        contrato=contrato, mes_referencia=filtro_mes, ano_referencia=filtro_ano
    ).first()

    if controle and not OcorrenciasService.livro_editavel(controle):
        messages.error(
            request,
            f"O Livro do Fiscal {controle.numero_livro} já foi atestado e não pode ser excluído. "
            "Para alterações, solicite à ACI a devolução para correção."
        )
    elif controle:
        controle.delete()
        messages.success(request, f"Registro do Livro do Fiscal do Contrato {contrato.numero} excluído com sucesso.")
    else:
        messages.info(request, "Nenhum registro encontrado para este contrato no período atual.")

    return redirect('upload_prestacao', contrato_id=contrato.id)


def ocorrencias_contrato(request, contrato_id):
    """
    Página enxuta e unificada para registro e edição de ocorrências contratuais.
    Exibe os dois meses abertos (mês anterior X e mês corrente X+1) agrupados em cards.
    """
    contrato = get_object_or_404(Contrato, pk=contrato_id)
    comissao_ativa = Comissao.objects.filter(
        contrato=contrato, ativa=True, tipo='FISCALIZACAO'
    ).first()

    hoje = timezone.localdate()
    meses_visiveis = OcorrenciasService.get_meses_visiveis(hoje)
    (mes_x, ano_x), (mes_x1, ano_x1) = meses_visiveis

    controles = {
        (c.mes_referencia, c.ano_referencia): c
        for c in ControleExecucao.objects.filter(
            contrato=contrato,
            mes_referencia__in=[mes_x, mes_x1],
            ano_referencia__in=[ano_x, ano_x1]
        ).prefetch_related('ocorrencias')
    }

    grupos_mes = []
    total_ocorrencias_abertas = 0

    for m, a in [(mes_x1, ano_x1), (mes_x, ano_x)]:
        is_corrente = (m == mes_x1 and a == ano_x1)
        ctrl = controles.get((m, a))
        editavel = OcorrenciasService.livro_editavel(ctrl)

        cal = CalendarioPrestacao.objects.filter(mes=m, ano=a).first()
        data_limite = cal.data_entrega_execucao if (cal and cal.data_entrega_execucao) else None
        fora_do_prazo = bool(data_limite and hoje > data_limite)

        if is_corrente:
            status_rotulo = "Mês em Andamento"
            status_badge_class = "bg-primary text-white"
        elif ctrl and not editavel:
            status_rotulo = f"Livro Atestado ({ctrl.get_status_display()}) — Somente Leitura"
            status_badge_class = "bg-success text-white" if ctrl.status == 'ok' else "bg-secondary text-white"
        elif ctrl and ctrl.status == 'correcao':
            status_rotulo = "Aguardando Correção"
            status_badge_class = "bg-warning text-dark"
        else:
            if data_limite:
                if fora_do_prazo:
                    status_rotulo = f"Aguardando Ateste (Fora do prazo - limite {data_limite.strftime('%d/%m/%Y')})"
                    status_badge_class = "bg-danger text-white"
                else:
                    status_rotulo = f"Aguardando Ateste até {data_limite.strftime('%d/%m/%Y')}"
                    status_badge_class = "bg-info text-dark"
            else:
                status_rotulo = "Pendente de Ateste"
                status_badge_class = "bg-warning text-dark"

        ocs = list(ctrl.ocorrencias.all().order_by('-data_hora')) if ctrl else []
        if editavel:
            total_ocorrencias_abertas += len(ocs)

        grupos_mes.append({
            'mes': m,
            'ano': a,
            'is_corrente': is_corrente,
            'controle': ctrl,
            'editavel': editavel,
            'status_rotulo': status_rotulo,
            'status_badge_class': status_badge_class,
            'data_limite': data_limite,
            'fora_do_prazo': fora_do_prazo,
            'ocorrencias': ocs,
        })

    abrir_modal_auto = (total_ocorrencias_abertas == 0)

    primeiro_dia_x = date(ano_x, mes_x, 1)
    min_datetime = f"{primeiro_dia_x.strftime('%Y-%m-%d')}T00:00"
    max_datetime = timezone.localtime().strftime('%Y-%m-%dT%H:%M')

    return render(request, 'contratos/execucao/ocorrencias.html', {
        'contrato': contrato,
        'comissao': comissao_ativa,
        'grupos_mes': grupos_mes,
        'abrir_modal_auto': abrir_modal_auto,
        'min_datetime': min_datetime,
        'max_datetime': max_datetime,
        'notificacao_automatica_habilitada': NotificacaoService.is_habilitada(),
    })


def formulario_execucao(request, contrato_id):
    """
    Formulário para preenchimento e envio do Livro do Fiscal (NPA 009/SCON/2025).
    """
    contrato = get_object_or_404(Contrato, pk=contrato_id)

    modo = request.GET.get('modo') or request.POST.get('modo')
    if modo == 'tempestivo':
        return redirect('ocorrencias_contrato', contrato_id=contrato.id)

    hoje = date.today()
    primeiro_dia_mes_atual = hoje.replace(day=1)
    ultimo_dia_mes_anterior = primeiro_dia_mes_atual - timedelta(days=1)

    param_mes = request.GET.get('mes') or request.POST.get('mes_referencia')
    param_ano = request.GET.get('ano') or request.POST.get('ano_referencia')
    if param_mes and param_ano:
        try:
            filtro_mes = int(param_mes)
            filtro_ano = int(param_ano)
        except (ValueError, TypeError):
            filtro_mes = ultimo_dia_mes_anterior.month
            filtro_ano = ultimo_dia_mes_anterior.year
    else:
        filtro_mes = ultimo_dia_mes_anterior.month
        filtro_ano = ultimo_dia_mes_anterior.year

    is_mes_corrente = (filtro_mes == hoje.month and filtro_ano == hoje.year)

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

    # Edição permitida apenas no mês anterior (X) e no mês corrente (X+1), ou em Livro devolvido pela ACI.
    # Livro já atestado ('entregue') só volta a ser editável após devolução para correção.
    periodo_permitido = (
        (filtro_mes, filtro_ano) in OcorrenciasService.get_meses_visiveis()
        or bool(controle_existente and controle_existente.status == 'correcao')
    )
    if not controle_existente and not periodo_permitido:
        messages.error(
            request,
            f"O período {filtro_mes:02d}/{filtro_ano} não está aberto para preenchimento do Livro do Fiscal."
        )
        return redirect('upload_prestacao', contrato_id=contrato.id)

    somente_leitura = not periodo_permitido or not OcorrenciasService.livro_editavel(controle_existente)
    if not OcorrenciasService.livro_editavel(controle_existente):
        motivo_somente_leitura = "Este Livro já foi atestado e aguarda a análise da ACI."
    else:
        motivo_somente_leitura = f"O período {filtro_mes:02d}/{filtro_ano} não está mais aberto para edição."

    if request.method == 'POST' and somente_leitura:
        messages.error(
            request,
            f"{motivo_somente_leitura} Para alterações, solicite à ACI a devolução para correção."
        )
        return redirect(
            reverse('formulario_execucao', kwargs={'contrato_id': contrato.id}) + f"?mes={filtro_mes}&ano={filtro_ano}"
        )

    if request.method == 'POST':
        form = ControleExecucaoForm(request.POST, contrato=contrato, instance=controle_existente)
        acao = request.POST.get('acao', 'finalizar')

        if is_mes_corrente and acao == 'finalizar':
            acao = 'rascunho'
            messages.warning(
                request,
                "O mês de referência ainda está em andamento. O Livro do Fiscal foi salvo como rascunho com sucesso. "
                "O ateste oficial estará disponível na Prestação de Contas a partir do 1º dia do mês subsequente."
            )

        if form.is_valid() and form.cleaned_data.get('sem_ocorrencias_periodo') and controle_existente:
            qtd_ocorrencias = controle_existente.ocorrencias.count()
            if qtd_ocorrencias:
                form.add_error(
                    'sem_ocorrencias_periodo',
                    f"Existem {qtd_ocorrencias} ocorrência(s) registrada(s) neste mês. "
                    "Exclua-as na tela de ocorrências antes de declarar o período sem ocorrências."
                )

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

            observacao_tramite = request.POST.get('observacao_tramite', '').strip()
            if acao != 'rascunho' and observacao_tramite:
                HistoricoObservacaoExecucao.objects.create(
                    controle=controle,
                    agente=controle.agente,
                    observacao=observacao_tramite
                )

            # Se fornecido ocorrencias_json (compatibilidade com envios legados e testes):
            ocorrencias_json_raw = request.POST.get('ocorrencias_json')
            if ocorrencias_json_raw and not controle.sem_ocorrencias_periodo:
                try:
                    oc_list = json.loads(ocorrencias_json_raw)
                    if isinstance(oc_list, list) and oc_list:
                        for oc_item in oc_list:
                            dt_raw = oc_item.get('data_hora') or oc_item.get('data_hora_fmt') or oc_item.get('data')
                            dt_parsed = parse_datetime(dt_raw) if dt_raw else None
                            if not dt_parsed and dt_raw and '/' in str(dt_raw):
                                try:
                                    parts = str(dt_raw).strip().split(' ')
                                    d_parts = parts[0].split('/')
                                    if len(d_parts) == 3:
                                        d_obj = date(int(d_parts[2]), int(d_parts[1]), int(d_parts[0]))
                                        t_obj = timezone.datetime.min.time()
                                        if len(parts) > 1 and ':' in parts[1]:
                                            t_parts = parts[1].split(':')
                                            t_obj = timezone.datetime.min.time().replace(hour=int(t_parts[0]), minute=int(t_parts[1]))
                                        dt_parsed = timezone.make_aware(timezone.datetime.combine(d_obj, t_obj))
                                except Exception:
                                    pass
                            if not dt_parsed and dt_raw:
                                d_only = parse_date(str(dt_raw)[:10])
                                if d_only:
                                    dt_parsed = timezone.make_aware(timezone.datetime.combine(d_only, timezone.datetime.min.time()))
                            if not dt_parsed:
                                dt_parsed = timezone.now()
                            elif timezone.is_naive(dt_parsed):
                                dt_parsed = timezone.make_aware(dt_parsed)

                            oc_id = oc_item.get('id')
                            if oc_id:
                                oc_obj = OcorrenciaContratual.objects.filter(pk=oc_id, controle=controle).first()
                                if not oc_obj:
                                    oc_obj = OcorrenciaContratual(controle=controle)
                            else:
                                oc_obj = OcorrenciaContratual(controle=controle)

                            oc_obj.data_hora = dt_parsed
                            oc_obj.local = oc_item.get('local', '').strip()
                            oc_obj.tipo = oc_item.get('tipo', 'TECNICA')
                            oc_obj.descricao = oc_item.get('descricao', '').strip()
                            oc_obj.dispositivo_violado = oc_item.get('dispositivo_violado', '').strip()
                            oc_obj.evidencias = oc_item.get('evidencias', '').strip()
                            oc_obj.notificacao_emitida = bool(oc_item.get('notificacao_emitida'))
                            oc_obj.notificacao_numero = oc_item.get('notificacao_numero', '').strip() if oc_obj.notificacao_emitida else ''
                            oc_obj.prazo_dias_uteis = int(oc_item.get('prazo_dias_uteis') or 5)
                            oc_obj.ciencia_preposto = oc_item.get('ciencia_preposto', 'na')
                            oc_obj.tramite_arc = bool(oc_item.get('tramite_arc'))
                            oc_obj.status_ocorrencia = oc_item.get('status_ocorrencia', 'aberto')
                            oc_obj.acao_fiscal = oc_item.get('acao_fiscal', '').strip()
                            oc_obj.save()
                except Exception:
                    pass

            # Consolidar Ocorrências a partir dos registros gravados no banco
            if controle.sem_ocorrencias_periodo:
                controle.relatorio_ocorrencias = "Em conformidade: Não houve ocorrências ou desvios registrados no período."
            else:
                relatorio_text_lines = []
                for idx, oc in enumerate(controle.ocorrencias.all().order_by('data_hora'), 1):
                    dt_s = oc.data_hora.strftime('%d/%m/%Y %H:%M') if oc.data_hora else 'S/D'
                    notif_s = f"Sim ({oc.notificacao_numero})" if oc.notificacao_emitida else "Não"
                    relatorio_text_lines.append(
                        f"[{idx}] {dt_s} | {oc.get_tipo_display()} | Local: {oc.local or 'N/A'}\n"
                        f"    Descrição: {oc.descricao}\n"
                        f"    Dispositivo: {oc.dispositivo_violado or 'N/A'} | Notificação: {notif_s}\n"
                        f"    Situação: {oc.get_status_ocorrencia_display().upper()}\n"
                        f"    Providência: {oc.acao_fiscal or 'N/A'}"
                    )
                if relatorio_text_lines:
                    controle.relatorio_ocorrencias = "\n\n".join(relatorio_text_lines)
                else:
                    controle.relatorio_ocorrencias = "Em conformidade: Não houve ocorrências no período."

            controle.save()

            if acao == 'rascunho':
                messages.success(request, f"Rascunho do Livro {controle.numero_livro} salvo com sucesso!")
                return redirect('formulario_execucao', contrato_id=contrato.id)
            else:
                messages.success(request, f"Livro do Fiscal {controle.numero_livro} finalizado e atestado com sucesso!")
                return redirect('upload_prestacao', contrato_id=contrato.id)
        else:
            erros_sem_ocorrencias = form.errors.get('sem_ocorrencias_periodo')
            messages.error(
                request,
                erros_sem_ocorrencias[0] if erros_sem_ocorrencias else "Por favor, corrija os erros apontados no formulário."
            )
    else:
        form = ControleExecucaoForm(contrato=contrato, instance=controle_existente)

    ocorrencias_existentes = []
    apontamentos = []
    if controle_existente:
        for oc in controle_existente.ocorrencias.all().order_by('-data_hora'):
            ocorrencias_existentes.append({
                'id': oc.id,
                'data_hora': oc.data_hora.strftime('%Y-%m-%dT%H:%M') if oc.data_hora else '',
                'data_hora_fmt': oc.data_hora.strftime('%d/%m/%Y %H:%M') if oc.data_hora else '',
                'data_registro': oc.data_registro.strftime('%d/%m/%Y %H:%M') if oc.data_registro else '',
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
                'notificacao_pdf_url': reverse('download_notificacao_anexo_d_pdf', args=[oc.id]) if (oc.id and NotificacaoService.is_habilitada()) else ''
            })
        apontamentos = controle_existente.apontamentos.select_related('autor').all()

    cal = CalendarioPrestacao.objects.filter(mes=filtro_mes, ano=filtro_ano).first()
    data_limite_execucao = cal.data_entrega_execucao if (cal and cal.data_entrega_execucao) else None
    fora_do_prazo = bool(data_limite_execucao and date.today() > data_limite_execucao)

    return render(request, 'contratos/execucao/formulario.html', {
        'contrato': contrato,
        'comissao': comissao_ativa,
        'integrantes': integrantes,
        'form': form,
        'controle_existente': controle_existente,
        'controle': controle_existente,
        'apontamentos': apontamentos,
        'ocorrencias': ocorrencias_existentes,
        'ocorrencias_json': json.dumps(ocorrencias_existentes, default=str),
        'mes_referencia': filtro_mes,
        'ano_referencia': filtro_ano,
        'is_mes_corrente': is_mes_corrente,
        'bloquear_ateste_mes_corrente': is_mes_corrente,
        'somente_leitura': somente_leitura,
        'motivo_somente_leitura': motivo_somente_leitura,
        'data_limite_execucao': data_limite_execucao,
        'fora_do_prazo': fora_do_prazo,
        'notificacao_automatica_habilitada': NotificacaoService.is_habilitada(),
        'exibir_bloco_preposto': ModulosLivroFiscalService.is_preposto_habilitado(),
        'exibir_bloco_obras': ModulosLivroFiscalService.is_obras_habilitado(),
    })


@require_POST
def salvar_ocorrencia(request):
    """
    Endpoint AJAX para registrar ou editar uma ocorrência contratual.
    Roteia automaticamente a ocorrência para o ControleExecucao correspondente à data_hora.
    """
    try:
        data = json.loads(request.body)
        contrato_id = data.get('contrato_id')
        contrato = get_object_or_404(Contrato, pk=contrato_id)

        oc_id = data.get('id')
        dt_raw = data.get('data_hora') or data.get('data_hora_fmt')
        if not dt_raw:
            return JsonResponse({'success': False, 'error': 'A data e horário da constatação são obrigatórios.'}, status=400)

        dt_parsed = parse_datetime(dt_raw) if dt_raw else None
        if not dt_parsed and dt_raw and '/' in str(dt_raw):
            try:
                parts = str(dt_raw).strip().split(' ')
                d_parts = parts[0].split('/')
                if len(d_parts) == 3:
                    d_obj = date(int(d_parts[2]), int(d_parts[1]), int(d_parts[0]))
                    t_obj = timezone.datetime.min.time()
                    if len(parts) > 1 and ':' in parts[1]:
                        t_parts = parts[1].split(':')
                        t_obj = timezone.datetime.min.time().replace(hour=int(t_parts[0]), minute=int(t_parts[1]))
                    dt_parsed = timezone.make_aware(timezone.datetime.combine(d_obj, t_obj))
            except Exception:
                pass
        if not dt_parsed and dt_raw:
            d_only = parse_date(str(dt_raw)[:10])
            if d_only:
                dt_parsed = timezone.make_aware(timezone.datetime.combine(d_only, timezone.datetime.min.time()))
        if not dt_parsed:
            dt_parsed = timezone.now()
        elif timezone.is_naive(dt_parsed):
            dt_parsed = timezone.make_aware(dt_parsed)

        desc = data.get('descricao', '').strip()
        if not desc:
            return JsonResponse({'success': False, 'error': 'A descrição detalhada da ocorrência é obrigatória.'}, status=400)

        try:
            controle_destino = OcorrenciasService.resolver_livro_para_data(contrato, dt_parsed)
        except ValidationError as val_err:
            msg = val_err.messages[0] if hasattr(val_err, 'messages') else str(val_err)
            return JsonResponse({'success': False, 'error': msg}, status=400)

        if oc_id:
            oc = get_object_or_404(OcorrenciaContratual, pk=oc_id, controle__contrato=contrato)
            if not OcorrenciasService.livro_editavel(oc.controle):
                return JsonResponse({
                    'success': False,
                    'error': f'O Livro original ({oc.controle.mes_referencia:02d}/{oc.controle.ano_referencia}) já foi atestado e não permite alterações.'
                }, status=403)
            oc.controle = controle_destino
        else:
            oc = OcorrenciaContratual(controle=controle_destino)

        oc.data_hora = dt_parsed
        oc.local = data.get('local', '').strip()
        oc.tipo = data.get('tipo', 'TECNICA')
        oc.descricao = desc
        oc.dispositivo_violado = data.get('dispositivo_violado', '').strip()
        oc.evidencias = data.get('evidencias', '').strip()
        oc.notificacao_emitida = bool(data.get('notificacao_emitida'))
        oc.notificacao_numero = data.get('notificacao_numero', '').strip() if oc.notificacao_emitida else ''
        oc.prazo_dias_uteis = int(data.get('prazo_dias_uteis') or 5)
        oc.ciencia_preposto = data.get('ciencia_preposto', 'na')
        oc.tramite_arc = bool(data.get('tramite_arc'))
        oc.status_ocorrencia = data.get('status_ocorrencia', 'aberto')
        oc.acao_fiscal = data.get('acao_fiscal', '').strip()
        oc.save()

        controle_destino.sem_ocorrencias_periodo = False
        controle_destino.save()

        notif_url = reverse('download_notificacao_anexo_d_pdf', args=[oc.id]) if (oc.notificacao_emitida and NotificacaoService.is_habilitada()) else ""

        return JsonResponse({
            'success': True,
            'mes_referencia': controle_destino.mes_referencia,
            'ano_referencia': controle_destino.ano_referencia,
            'numero_livro': controle_destino.numero_livro,
            'ocorrencia': {
                'id': oc.id,
                'data_hora': oc.data_hora.strftime('%Y-%m-%dT%H:%M'),
                'data_hora_fmt': oc.data_hora.strftime('%d/%m/%Y %H:%M'),
                'data_registro': oc.data_registro.strftime('%d/%m/%Y %H:%M') if oc.data_registro else '',
                'eh_tempestiva': oc.eh_tempestiva,
                'classificacao_tempestividade': 'Tempestivo' if oc.eh_tempestiva else 'Agrupado (Extemporâneo)',
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


salvar_ocorrencia_tempestiva = salvar_ocorrencia


@require_POST
def excluir_ocorrencia(request, pk):
    """Exclui uma ocorrência pontual via AJAX, garantindo que o livro esteja em estado editável."""
    oc = get_object_or_404(OcorrenciaContratual, pk=pk)
    controle = oc.controle
    if not OcorrenciasService.livro_editavel(controle):
        return JsonResponse({
            'success': False,
            'error': f'O Livro do Fiscal de {controle.mes_referencia:02d}/{controle.ano_referencia} já foi atestado e não permite exclusão de ocorrências.'
        }, status=403)

    oc.delete()
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
        'notificacao_automatica_habilitada': NotificacaoService.is_habilitada(),
    })


@login_required
@require_POST
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
@require_POST
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
        'Sem Ocorrências?', 'Qtd Ocorrências', 'Qtd Ocorrências Fora do Mês', 'Obra Engenharia?', 'Relatório Resumido'
    ])

    controles = ControleExecucao.objects.filter(
        mes_referencia=filtro_mes, ano_referencia=filtro_ano
    ).select_related('contrato', 'agente', 'agente__posto').prefetch_related('ocorrencias')

    for c in controles:
        fiscal_nome = f"{c.agente.posto.sigla} {c.agente.nome_de_guerra}" if c.agente else "Não informado"
        ocs_fora = sum(1 for oc in c.ocorrencias.all() if not oc.eh_tempestiva)
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
            ocs_fora,
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

    # Acesso não autenticado (fiscal) só pode baixar após conformidade da ACI (status 'ok')
    if not request.user.is_authenticated and controle.status != 'ok':
        messages.warning(
            request,
            "O download do Livro do Fiscal só está disponível após a validação e conformidade pela ACI."
        )
        return redirect('formulario_execucao', contrato_id=controle.contrato.id)

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

    abertura_data = [
        ["Número do Livro:", f"<b>{controle.numero_livro}</b>"],
        ["Número e Objeto do Contrato:", f"Contrato nº {contrato.numero} — {contrato.objeto}"],
        ["Contratada / CNPJ:", empresa_str],
        ["Período de Vigência Contratual:", vig_str],
        ["Ato de Designação da Fiscalização:", desig_str],
        ["Fiscal Responsável (Registro):", fiscal_resp],
    ]

    if ModulosLivroFiscalService.is_preposto_habilitado():
        prep_dados = f"{controle.preposto_nome or 'Não informado'} | Cargo: {controle.preposto_cargo or '-'} | Tel: {controle.preposto_telefone or '-'} | E-mail: {controle.preposto_email or '-'}"
        abertura_data.append(["Preposto Aceito da Contratada:", prep_dados])

    story.append(KeepTogether([
        make_sec_header("TERMO DE ABERTURA E IDENTIFICAÇÃO DO CONTRATO"),
        Spacer(1, 3),
        make_kv(abertura_data)
    ]))
    story.append(Spacer(1, 8))

    # Diário de Obra e Engenharia (Anexo B) - se aplicável e modularmente habilitado
    if controle.eh_obra_engenharia and ModulosLivroFiscalService.is_obras_habilitado():
        obras_data = [
            ["Condições Climáticas e Paralisações:", controle.condicoes_climaticas or "Sem registro de paralisações por intempéries."],
            ["Efetivo de Pessoal no Canteiro:", controle.efetivo_trabalhadores or "Conforme equipe padrão informada pela contratada."],
            ["Equipamentos e Maquinário:", controle.maquinario_equipamentos or "Equipamentos em condições operacionais normais."],
            ["Anotação de Resp. Técnica (ART/RRT):", controle.art_rrt or "ART/RRT quitada e arquivada no e-PAG."],
            ["Matrícula CEI / CNO no INSS:", controle.matricula_cei_cno or "Matrícula regularizada no e-PAG."],
            ["Segurança do Trabalho e CAT:", controle.seguranca_trabalho_cat or "EPIs em uso regular. Sem registro de acidentes no período."],
        ]
        story.append(KeepTogether([
            make_sec_header("REQUISITOS ESPECÍFICOS PARA DIÁRIO DE OBRA E ENGENHARIA (ANEXO B DA NPA 009)"),
            Spacer(1, 3),
            make_kv(obras_data)
        ]))
        story.append(Spacer(1, 8))

    # Registro de Ocorrências Contratuais (10 Campos)
    story.append(make_sec_header("REGISTRO DE OCORRÊNCIAS DA FISCALIZAÇÃO"))
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
            reg_s = oc.data_registro.strftime('%d/%m/%Y às %H:%M') if oc.data_registro else dt_s
            selo_temp = "Tempestivo (em tempo real)" if oc.eh_tempestiva else "Agrupado (Extemporâneo na Prestação)"
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
                ["Determinação do Fiscal:", oc.acao_fiscal or "Determinado o saneamento."],
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
            make_sec_header("OBSERVAÇÕES E APONTAMENTOS COMPLEMENTARES"),
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
    n_completo = (controle.agente.nome_completo or controle.agente.nome_de_guerra).upper() if controle.agente else "FISCAL"
    nome_assinante = f"{p_sigla} {n_completo}".strip()

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
# Geração de Notificação Oficial de Ocorrência (Modularizada via NotificacaoService)
# =========================================================================
def gerar_notificacao_anexo_d_pdf(request, pk):
    """
    Gera a Notificação Oficial de Ocorrência delegando a lógica ao NotificacaoService.
    A geração automática padrão está suspensa para revisão de modelo, sendo permitida
    apenas quando habilitada ou forçada por usuário da ACI (force=1 para testes/auditoria).
    """
    oc = get_object_or_404(
        OcorrenciaContratual.objects.select_related(
            'controle', 'controle__contrato', 'controle__contrato__empresa',
            'controle__agente', 'controle__agente__posto'
        ),
        pk=pk
    )

    permitir = (
        NotificacaoService.is_habilitada()
        or (bool(request.GET.get('force')) and is_auditor(request.user))
        or (request.user.is_authenticated and request.user.is_superuser)
    )

    if not permitir:
        messages.info(
            request,
            "A emissão automática da Notificação Oficial (Anexo D) está temporariamente suspensa "
            "aguardando revisão e adaptação do novo modelo padronizado."
        )
        return redirect('visualizar_controle_execucao', pk=oc.controle.pk)

    try:
        tipo = request.GET.get('tipo', 'legado')
        buffer, filename = NotificacaoService.gerar_documento(oc, tipo=tipo, permitir_desabilitado=True)
        response = FileResponse(buffer, as_attachment=True, filename=filename, content_type='application/pdf')
        response['Cache-Control'] = 'no-cache, no-store, must-revalidate, max-age=0'
        return response
    except Exception as e:
        messages.error(request, f"Erro ao gerar documento de notificação: {e}")
        return redirect('visualizar_controle_execucao', pk=oc.controle.pk)
