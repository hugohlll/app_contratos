import json
from datetime import date, timedelta
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse, HttpResponse
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.urls import reverse
import csv

from contratos.models import (
    Contrato, Agente, Integrante, Comissao, CalendarioPrestacao,
    ControleExecucao, RegistroFatura, OcorrenciaContratual, ApontamentoCorrecaoExecucao
)
from contratos.forms import ControleExecucaoForm
from contratos.utils import is_admin, is_auditor, admin_required, auditor_required


def portal_execucao_index(request):
    """Landing page pública do Portal de Controle de Execução Contratual (Livro do Fiscal)."""
    hoje = date.today()
    primeiro_dia_mes_atual = hoje.replace(day=1)
    ultimo_dia_mes_anterior = primeiro_dia_mes_atual - timedelta(days=1)

    filtro_mes = ultimo_dia_mes_anterior.month
    filtro_ano = ultimo_dia_mes_anterior.year

    cal = CalendarioPrestacao.objects.filter(ano=filtro_ano, mes=filtro_mes).first()
    data_limite = cal.data_entrega_execucao if cal and cal.data_entrega_execucao else None

    meses_nomes = ["Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
                   "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"]
    nome_mes_referencia = meses_nomes[filtro_mes - 1]

    return render(request, 'contratos/execucao/index.html', {
        'mes_referencia': filtro_mes,
        'ano_referencia': filtro_ano,
        'nome_mes_referencia': nome_mes_referencia,
        'data_limite': data_limite,
    })


def portal_execucao_fiscais(request):
    """Lista de contratos vigentes para seleção do fiscal no preenchimento do Livro do Fiscal."""
    hoje = date.today()
    primeiro_dia_mes_atual = hoje.replace(day=1)
    ultimo_dia_mes_anterior = primeiro_dia_mes_atual - timedelta(days=1)

    filtro_mes = ultimo_dia_mes_anterior.month
    filtro_ano = ultimo_dia_mes_anterior.year

    contratos = Contrato.objects.filter(
        vigencia_inicio__lte=hoje,
        vigencia_fim__gte=hoje
    ).order_by('numero')

    controles = ControleExecucao.objects.filter(
        mes_referencia=filtro_mes, ano_referencia=filtro_ano
    ).prefetch_related('apontamentos')
    controles_map = {c.contrato_id: c for c in controles}

    contratos_info = []
    for c in contratos:
        ctrl = controles_map.get(c.id)
        is_enviado = bool(ctrl and ctrl.status in ['entregue', 'correcao', 'ok'])
        ultimo_apontamento = ctrl.apontamentos.first() if (ctrl and ctrl.apontamentos.exists()) else None

        contratos_info.append({
            'contrato': c,
            'controle': ctrl,
            'is_enviado': is_enviado,
            'ultimo_apontamento': ultimo_apontamento,
        })

    return render(request, 'contratos/execucao/fiscais.html', {
        'contratos_info': contratos_info,
        'mes_referencia': filtro_mes,
        'ano_referencia': filtro_ano,
    })


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

    return redirect('portal_execucao_fiscais')


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

    if request.method == 'POST':
        form = ControleExecucaoForm(request.POST, contrato=contrato, instance=controle_existente)
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
        form = ControleExecucaoForm(contrato=contrato, instance=controle_existente)

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
    })


@login_required
def visualizar_controle_execucao(request, pk):
    """Visualização em formato somente leitura do Livro do Fiscal (ACI / Admin)."""
    controle = get_object_or_404(
        ControleExecucao.objects.select_related('contrato', 'agente', 'agente__posto'), pk=pk
    )

    comissao = Comissao.objects.filter(
        contrato=controle.contrato, ativa=True, tipo='FISCALIZACAO'
    ).first()

    apontamentos = controle.apontamentos.select_related('autor').all()

    return render(request, 'contratos/execucao/visualizar.html', {
        'controle': controle,
        'comissao': comissao,
        'apontamentos': apontamentos,
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
        'Glosa Realizada', 'Necessidade PAAI', 'Relatório Ocorrências'
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
            'Sim' if c.glosa_realizada else 'Não',
            c.get_necessidade_paai_display(),
            c.relatorio_ocorrencias[:100]
        ])

    return response
