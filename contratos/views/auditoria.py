import csv
import json
import urllib.parse
import io
from datetime import date, timedelta
from django.http import HttpResponse, HttpResponseBadRequest
from django.shortcuts import render
from django.db.models import Count, Q
from django.contrib.auth.decorators import login_required
from django.utils.dateparse import parse_date
from django.utils.safestring import mark_safe
from django.utils.text import slugify
from contratos.models import Contrato, Agente, Comissao, Integrante, DIAS_VALIDADE_QUALIFICACAO
from contratos.utils import get_filtro_ativos, export_csv_or_xlsx, is_auditor
from contratos.services import indicadores


def get_classificacao_vencimento(dias):
    """
    Função auxiliar para centralizar a regra de negócio de vencimentos.
    Facilita a manutenção caso os prazos mudem novamente.
    """
    if dias <= 7:
        return 'table-danger', 'CRÍTICO'
    elif 8 <= dias <= 15:
        return 'table-warning', 'ALERTA'
    else:
        return 'table-success', 'NORMAL'


@login_required
def painel_controle(request):
    hoje = date.today()

    # 1. MONITORAMENTO DE VENCIMENTOS DAS COMISSÕES
    # Serializado como JSON para evitar que o locale pt-BR formate números no template.
    venc = indicadores.contar('vencimento-comissoes', hoje)
    total_vencimentos_count = sum(venc.values())

    # 2. RADAR DE PERMANÊNCIA (top 10)
    top_10_permanencia = indicadores.radar_permanencia(hoje)[:10]
    permanencia_labels = [f"{i['agente'].posto.sigla} {i['agente'].nome_de_guerra}" for i in top_10_permanencia]
    permanencia_dias = [i['dias_totais'] for i in top_10_permanencia]
    permanencia_ids = [i['agente'].id for i in top_10_permanencia]

    # 3. QUALIFICAÇÃO
    dados_qualificacao = indicadores.contar('qualificacao', hoje)
    dados_qualificacao['total'] = sum(dados_qualificacao.values())

    # 4. VENCIMENTO DOS CONTRATOS (velocímetro 90/120 dias)
    venc_contratos = indicadores.contar('vencimento-contratos', hoje)
    total_contratos_ativos = sum(venc_contratos.values())
    venc_contratos['total'] = total_contratos_ativos

    # 5. SOBRECARGA DE FISCAIS (top 10)
    fiscais_sobrecarregados = list(indicadores.sobrecarga_fiscais(limite=10))
    sobrecarga_labels = [f"{ag.posto.sigla} {ag.nome_de_guerra}" for ag in fiscais_sobrecarregados]
    sobrecarga_valores = [ag.total_atuacoes for ag in fiscais_sobrecarregados]
    sobrecarga_ids = [ag.id for ag in fiscais_sobrecarregados]

    contratos_risco = indicadores.contratos_risco_qs(hoje)
    total_agentes_atuando = indicadores.agentes_ativos_qs().count()

    def _json(valor):
        return mark_safe(json.dumps(valor, ensure_ascii=False))

    context = {
        'total_vencimentos_count': total_vencimentos_count,
        'vencimentos_critico': venc['critico'],
        'vencimentos_json': _json(venc),
        'tem_permanencia': bool(top_10_permanencia),
        'permanencia_labels': _json(permanencia_labels),
        'permanencia_dias': _json(permanencia_dias),
        'permanencia_ids': _json(permanencia_ids),
        'tem_sobrecarga': bool(fiscais_sobrecarregados),
        'sobrecarga_labels': _json(sobrecarga_labels),
        'sobrecarga_valores': _json(sobrecarga_valores),
        'sobrecarga_ids': _json(sobrecarga_ids),
        'media_limite_fiscais': indicadores.media_limite_fiscais(hoje),
        'venc_data_json': _json(venc_contratos),
        'contratos_risco': contratos_risco,
        'total_contratos_ativos': total_contratos_ativos,
        'total_agentes_atuando': total_agentes_atuando,
        'dados_qualificacao_json': _json(dados_qualificacao),
        'detalhe_inicial': request.GET.get('detalhe', ''),
    }

    return render(request, 'contratos/painel_controle.html', context)


@login_required
def detalhe_indicador(request, indicador):
    """
    Lista os registros de um segmento de gráfico do painel.
    Sem `formato`, devolve o fragmento HTML exibido no painel lateral;
    com `formato=csv|xlsx`, exporta o mesmo recorte.
    """
    segmento = request.GET.get('segmento', indicadores.SEGMENTO_TODOS)
    try:
        ind, rotulo, linhas = indicadores.detalhar(indicador, segmento)
    except KeyError:
        return HttpResponseBadRequest('Indicador inválido.')
    except ValueError:
        return HttpResponseBadRequest('Segmento inválido.')

    if request.GET.get('formato') in ('csv', 'xlsx'):
        sufixo = '' if segmento == indicadores.SEGMENTO_TODOS else f"_{slugify(rotulo)}"
        return export_csv_or_xlsx(request, f"{ind.nome_arquivo}{sufixo}", ind.colunas, [l.celulas for l in linhas])

    return render(request, 'contratos/auditoria/_detalhe.html', {
        'indicador': ind,
        'segmento': segmento,
        'rotulo': rotulo,
        'linhas': linhas,
        'pode_abrir_contrato': is_auditor(request.user),
    })


@login_required
def exportar_vencimentos_csv(request):
    headers = ['Contrato', 'Empresa', 'Comissão', 'Término Previsto', 'Status', 'Dias Restantes']
    data = []

    hoje = date.today()
    comissoes = Comissao.objects.filter(
        ativa=True
    ).select_related('contrato')

    lista_export = []
    for comissao in comissoes:
        data_fim_efetiva = comissao.data_fim or (comissao.contrato.vigencia_fim if comissao.contrato else None)
        if not data_fim_efetiva:
            continue
            
        dias = (data_fim_efetiva - hoje).days
        _, status = get_classificacao_vencimento(dias)
        lista_export.append((dias, status, comissao, data_fim_efetiva))

    lista_export.sort(key=lambda x: x[0])
    for dias, status, comissao, data_fim_efetiva in lista_export:
        data.append([
            comissao.contrato.numero if comissao.contrato else comissao.get_tipo_display(),
            comissao.contrato.empresa.razao_social if comissao.contrato else (comissao.descricao_objeto or '-'),
            comissao.get_tipo_display(),
            data_fim_efetiva.strftime('%d/%m/%Y'),
            status,
            dias
        ])
    
    return export_csv_or_xlsx(request, 'monitoramento_vencimentos', headers, data)


@login_required
def exportar_csv(request):
    """Exportação geral da auditoria"""
    headers = [
        'Contrato', 'Empresa', 'Vigência Contrato', 'Comissão', 'Função',
        'Militar', 'SARAM', 'Início Designação', 'Término Previsto',
        'Nº Portaria', 'Data Portaria', 'Nº Boletim', 'Data Boletim'
    ]
    data = []

    hoje = date.today()
    contratos = Contrato.objects.filter(vigencia_fim__gte=hoje)
    filtro_ativo = get_filtro_ativos()

    for contrato in contratos:
        comissoes = contrato.comissoes.filter(ativa=True)
        if comissoes.exists():
            for com in comissoes:
                for integrante in com.integrantes.filter(filtro_ativo):
                    inicio = integrante.data_inicio.strftime('%d/%m/%Y') if integrante.data_inicio else "-"
                    fim = integrante.data_fim.strftime('%d/%m/%Y') if integrante.data_fim else "Ativa"
                    data_port = integrante.portaria_data.strftime('%d/%m/%Y') if integrante.portaria_data else "-"
                    data_bol = integrante.boletim_data.strftime('%d/%m/%Y') if integrante.boletim_data else "-"
                    data.append([
                        contrato.numero, contrato.empresa.razao_social, contrato.vigencia_fim.strftime('%d/%m/%Y'),
                        com.get_tipo_display(), integrante.funcao.titulo, integrante.agente.nome_de_guerra,
                        integrante.agente.saram, inicio, fim, integrante.portaria_numero, data_port,
                        integrante.boletim_numero, data_bol
                    ])
        else:
            data.append([
                                contrato.numero, contrato.empresa.razao_social,
                                contrato.vigencia_fim.strftime('%d/%m/%Y'),
                                "SEM COMISSÃO"
                            ] + ["-"] * 9)
    
    return export_csv_or_xlsx(request, 'auditoria_completa', headers, data)


@login_required
def relatorio_por_periodo(request):
    data_inicial = request.GET.get('data_inicial')
    data_final = request.GET.get('data_final')
    resultados = []
    if data_inicial and data_final:
        dt_ini = parse_date(data_inicial)
        dt_fim = parse_date(data_final)
        if dt_ini and dt_fim:
            resultados = Integrante.objects.filter(data_inicio__lte=dt_fim).filter(
                Q(data_fim__gte=dt_ini) | Q(data_fim__isnull=True)).filter(
                Q(data_desligamento__gte=dt_ini) | Q(data_desligamento__isnull=True)).select_related(
                'agente', 'funcao', 'comissao__contrato', 'comissao__contrato__empresa'
            ).order_by('comissao__contrato__numero', 'data_inicio')
    return render(request, 'contratos/relatorio_periodo.html', {
        'resultados': resultados,
        'data_inicial': data_inicial,
        'data_final': data_final
    })


@login_required
def exportar_qualificacao_csv(request):
    headers = ['Militar', 'SARAM', 'Função', 'Contrato', 'Data Último Curso', 'Validade', 'Situação']
    data = []

    hoje = date.today()
    data_limite_curso = hoje - timedelta(days=DIAS_VALIDADE_QUALIFICACAO)
    equipe_ativa = Integrante.objects.filter(get_filtro_ativos()).select_related(
        'agente', 'agente__posto', 'posto_graduacao', 'funcao', 'comissao__contrato'
    ).order_by('agente__nome_de_guerra')

    for item in equipe_ativa:
        dt_curso = item.agente.data_ultimo_curso
        situacao, validade_fmt = "EM DIA", "-"
        if not dt_curso:
            situacao, dt_fmt = "SEM CURSO (IRREGULAR)", "Não Realizado"
        elif dt_curso < data_limite_curso:
            situacao = "VENCIDO (IRREGULAR)"
            dt_fmt = dt_curso.strftime('%d/%m/%Y')
            validade_fmt = (dt_curso + timedelta(days=DIAS_VALIDADE_QUALIFICACAO)).strftime('%d/%m/%Y')
        else:
            dt_fmt = dt_curso.strftime('%d/%m/%Y')
            validade_fmt = (dt_curso + timedelta(days=DIAS_VALIDADE_QUALIFICACAO)).strftime('%d/%m/%Y')

        posto = item.posto_graduacao.sigla if item.posto_graduacao else item.agente.posto.sigla
        nome_completo = f"{posto} {item.agente.nome_de_guerra}"

        data.append([
            nome_completo, item.agente.saram, item.funcao.titulo,
            item.comissao.contrato.numero if item.comissao.contrato else item.comissao.get_tipo_display(),
            dt_fmt, validade_fmt, situacao
        ])
        
    return export_csv_or_xlsx(request, 'relatorio_qualificacao_agentes', headers, data)


@login_required
def exportar_relatorio_periodo_csv(request):
    data_inicial = request.GET.get('data_inicial')
    data_final = request.GET.get('data_final')
    
    headers = [
        'Contrato', 'Tipo Comissão', 'Empresa', 'Militar', 'SARAM', 'CPF', 'Função',
        'Início', 'Término (Previsão)', 'Nº Portaria', 'Data Portaria', 'Nº Boletim', 'Data Boletim'
    ]
    data = []
    
    if data_inicial and data_final:
        dt_ini = parse_date(data_inicial)
        dt_fim = parse_date(data_final)
        resultados = Integrante.objects.filter(data_inicio__lte=dt_fim).filter(
            Q(data_fim__gte=dt_ini) | Q(data_fim__isnull=True)).filter(
            Q(data_desligamento__gte=dt_ini) | Q(data_desligamento__isnull=True)).select_related(
            'agente', 'funcao', 'comissao__contrato'
        )
        for r in resultados:
            fim_fmt = r.data_fim.strftime('%d/%m/%Y') if r.data_fim else "-"
            data_port = r.portaria_data.strftime('%d/%m/%Y') if r.portaria_data else "-"
            bol_num = r.boletim_numero if r.boletim_numero else "-"
            bol_data = r.boletim_data.strftime('%d/%m/%Y') if r.boletim_data else "-"
            
            posto = r.posto_graduacao.sigla if r.posto_graduacao else r.agente.posto.sigla
            nome_completo = f"{posto} {r.agente.nome_de_guerra}"
            
            tipo_label = r.comissao.get_tipo_display()
            
            if r.comissao.contrato:
                contrato_numero = r.comissao.contrato.numero
                empresa_nome = r.comissao.contrato.empresa.razao_social
            else:
                contrato_numero = tipo_label
                empresa_nome = (r.comissao.descricao_objeto or '-')[:50]

            data.append([
                contrato_numero, tipo_label, empresa_nome,
                nome_completo, r.agente.saram, r.agente.cpf or '-', r.funcao.titulo,
                r.data_inicio.strftime('%d/%m/%Y'), fim_fmt, 
                r.portaria_numero, data_port, bol_num, bol_data
            ])
            
    nome_arquivo = f"relatorio_agentes_{data_inicial}_a_{data_final}"
    return export_csv_or_xlsx(request, nome_arquivo, headers, data)
    
    
@login_required
def exportar_radar_permanencia_csv(request):
    headers = ['Militar', 'Função', 'Contrato', 'Dias Totais', 'Tempo Formatado', 'Início Real']
    data = []
    
    radar_permanencia = indicadores.radar_permanencia(date.today())

    for item in radar_permanencia:
        data.append([
            f"{item['agente'].posto.sigla} {item['agente'].nome_de_guerra}",
            item['funcao'].titulo,
            item['contrato'].numero if item['contrato'] else '-',
            item['dias_totais'],
            item['tempo_formatado'],
            item['inicio_real'].strftime('%d/%m/%Y')
        ])
        
    return export_csv_or_xlsx(request, 'radar_permanencia', headers, data)


@login_required
def exportar_sobrecarga_fiscais_csv(request):
    headers = ['Militar (Fiscal)', 'SARAM', 'Quantidade de Contratos Fiscalizados']
    data = []
    
    filtro_ativos = get_filtro_ativos()
    integrantes_fiscais = Integrante.objects.filter(filtro_ativos, funcao__titulo='Fiscal')
    
    fiscais_sobrecarregados = Agente.objects.filter(
        integrante__in=integrantes_fiscais
    ).annotate(
        total_atuacoes=Count('integrante', filter=Q(integrante__in=integrantes_fiscais))
    ).filter(total_atuacoes__gt=0).order_by('-total_atuacoes', 'posto__senioridade', 'nome_de_guerra')
    
    for agente in fiscais_sobrecarregados:
        data.append([
            f"{agente.posto.sigla} {agente.nome_de_guerra}",
            agente.saram,
            agente.total_atuacoes
        ])
        
    return export_csv_or_xlsx(request, 'sobrecarga_fiscais', headers, data)
@login_required
def exportar_contratos_vencimento_csv(request):
    headers = ['Contrato', 'Empresa', 'Vencimento', 'Dias Restantes', 'Situação']
    data = []
    
    hoje = date.today()
    contratos = Contrato.objects.filter(vigencia_fim__gte=hoje).select_related('empresa').order_by('vigencia_fim')
    
    for c in contratos:
        dias = (c.vigencia_fim - hoje).days
        situacao = "NORMAL"
        if dias <= 90:
            situacao = "CRÍTICO"
        elif dias <= 120:
            situacao = "ALERTA"
            
        data.append([
            c.numero,
            c.empresa.razao_social,
            c.vigencia_fim.strftime('%d/%m/%Y'),
            dias,
            situacao
        ])
        
    return export_csv_or_xlsx(request, 'vencimento_contratos', headers, data)
