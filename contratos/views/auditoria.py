import csv
from datetime import date, timedelta
from django.http import HttpResponse
from django.shortcuts import render
from django.db.models import Count, Q, Prefetch
from django.contrib.auth.decorators import login_required
from django.utils.dateparse import parse_date
from contratos.models import Contrato, Agente, Comissao, Integrante
from contratos.utils import get_filtro_ativos


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
    data_limite_curso = hoje - timedelta(days=365)
    filtro_ativos = get_filtro_ativos()

    # 1. MONITORAMENTO DE VENCIMENTOS (Lógica Refatorada)
    integrantes_com_prazo = Integrante.objects.filter(filtro_ativos).filter(
        data_fim__isnull=False
    ).select_related('agente', 'funcao', 'comissao__contrato')

    lista_completa = []
    for integrante in integrantes_com_prazo:
        dias_restantes = (integrante.data_fim - hoje).days

        # Aplicação dos critérios: <=7 Crítico | 8-15 Alerta | >15 Normal
        classe_cor, status_texto = get_classificacao_vencimento(dias_restantes)

        integrante.dias_restantes = dias_restantes
        integrante.classe_cor = classe_cor
        integrante.status_texto = status_texto
        lista_completa.append(integrante)

    # Ordena pelos mais próximos de vencer
    lista_completa.sort(key=lambda x: x.dias_restantes)
    top_5_vencimentos = lista_completa[:5]
    total_vencimentos_count = len(lista_completa)

    # 2. RADAR DE PERMANÊNCIA (Cálculo de tempo de designação contínua)
    integrantes_ativos = Integrante.objects.filter(filtro_ativos).select_related(
        'agente', 'funcao', 'comissao__contrato'
    )
    radar_permanencia = []

    for atual in integrantes_ativos:
        data_inicio_real = atual.data_inicio
        # Busca recursiva simples para encontrar a data de início real da sequência de designações
        while True:
            dia_anterior = data_inicio_real - timedelta(days=1)
            designacao_anterior = Integrante.objects.filter(
                comissao=atual.comissao,
                agente=atual.agente,
                funcao=atual.funcao
            ).filter(Q(data_fim=dia_anterior) | Q(data_desligamento=dia_anterior)).first()

            if designacao_anterior:
                data_inicio_real = designacao_anterior.data_inicio
            else:
                break

        dias_totais = (hoje - data_inicio_real).days
        anos, meses = dias_totais // 365, (dias_totais % 365) // 30

        # Classificação de tempo para rodízio
        classe_tempo = 'bg-success'
        if dias_totais > 730:  # 2 anos
            classe_tempo = 'bg-danger'
        elif dias_totais > 365:  # 1 ano
            classe_tempo = 'bg-warning text-dark'

        radar_permanencia.append({
            'agente': atual.agente,
            'funcao': atual.funcao,
            'contrato': atual.comissao.contrato,
            'dias_totais': dias_totais,
            'tempo_formatado': f"{anos}a {meses}m ({dias_totais} dias)",
            'inicio_real': data_inicio_real,
            'classe_tempo': classe_tempo,
            'inicio_original': atual.data_inicio
        })

    radar_permanencia.sort(key=lambda x: x['dias_totais'], reverse=True)
    top_10_permanencia = radar_permanencia[:10]

    # 3. ESTATÍSTICAS DE QUALIFICAÇÃO
    equipe_ativa_qs = Integrante.objects.filter(filtro_ativos).select_related('agente')
    total_ativos = equipe_ativa_qs.count()
    qtd_sem_curso = equipe_ativa_qs.filter(agente__data_ultimo_curso__isnull=True).count()
    qtd_vencidos = equipe_ativa_qs.filter(agente__data_ultimo_curso__lt=data_limite_curso).count()
    qtd_em_dia = total_ativos - qtd_sem_curso - qtd_vencidos

    dados_qualificacao = {
        'sem_curso': qtd_sem_curso,
        'vencidos': qtd_vencidos,
        'em_dia': qtd_em_dia,
        'total': total_ativos
    }

    # 4. SOBRECARGA E RISCOS
    agentes_sobrecarregados = Agente.objects.annotate(
        total_atuacoes=Count('integrante', filter=Q(integrante__in=Integrante.objects.filter(filtro_ativos)))
    ).filter(total_atuacoes__gt=0).order_by('-total_atuacoes')[:10]

    contratos_risco = Contrato.objects.filter(vigencia_fim__gte=hoje).annotate(
        fiscais_ativos=Count('comissoes__integrantes', filter=Q(comissoes__tipo='FISCALIZACAO') & Q(
            comissoes__integrantes__in=Integrante.objects.filter(filtro_ativos)))
    ).filter(fiscais_ativos=0)

    total_contratos_ativos = Contrato.objects.filter(vigencia_fim__gte=hoje).count()
    total_agentes_atuando = Agente.objects.filter(
        integrante__in=Integrante.objects.filter(filtro_ativos)).distinct().count()

    tabela_contratos = Contrato.objects.filter(vigencia_fim__gte=hoje).prefetch_related(
        Prefetch('comissoes', queryset=Comissao.objects.filter(ativa=True).prefetch_related(
            Prefetch('integrantes',
                     queryset=Integrante.objects.filter(filtro_ativos).select_related('agente', 'funcao'),
                     to_attr='equipe_vigente')
        ), to_attr='comissoes_ativas')
    ).order_by('vigencia_fim')

    return render(request, 'contratos/painel_controle.html', {
        'lista_vencimentos': top_5_vencimentos,
        'total_vencimentos_count': total_vencimentos_count,
        'top_permanencia': top_10_permanencia,
        'agentes_sobrecarregados': agentes_sobrecarregados,
        'contratos_risco': contratos_risco,
        'total_contratos_ativos': total_contratos_ativos,
        'total_agentes_atuando': total_agentes_atuando,
        'tabela_contratos': tabela_contratos,
        'dados_qualificacao': dados_qualificacao,
    })


@login_required
def exportar_vencimentos_csv(request):
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="monitoramento_vencimentos.csv"'
    writer = csv.writer(response, delimiter=';')
    writer.writerow(['Status', 'Dias Restantes', 'Militar', 'Função', 'Contrato', 'Término Previsto'])

    hoje = date.today()
    integrantes = Integrante.objects.filter(get_filtro_ativos()).filter(
        data_fim__isnull=False
    ).select_related('agente', 'funcao', 'comissao__contrato')

    lista_export = []
    for integrante in integrantes:
        dias = (integrante.data_fim - hoje).days
        _, status = get_classificacao_vencimento(dias)  # Usa a mesma função auxiliar
        lista_export.append((dias, status, integrante))

    lista_export.sort(key=lambda x: x[0])
    for dias, status, integrante in lista_export:
        writer.writerow([
            status,
            dias,
            integrante.agente.nome_de_guerra,
            integrante.funcao.titulo,
            integrante.comissao.contrato.numero,
            integrante.data_fim.strftime('%d/%m/%Y')
        ])
    return response


@login_required
def exportar_csv(request):
    """Exportação geral da auditoria"""
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="auditoria_completa.csv"'
    writer = csv.writer(response, delimiter=';')
    writer.writerow([
        'Contrato', 'Empresa', 'Vigência Contrato', 'Comissão', 'Função',
        'Militar', 'SARAM', 'Início Designação', 'Término Previsto',
        'Nº Portaria', 'Data Portaria', 'Nº Boletim', 'Data Boletim'
    ])

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
                    writer.writerow([
                        contrato.numero, contrato.empresa.razao_social, contrato.vigencia_fim.strftime('%d/%m/%Y'),
                        com.get_tipo_display(), integrante.funcao.titulo, integrante.agente.nome_de_guerra,
                        integrante.agente.saram, inicio, fim, integrante.portaria_numero, data_port,
                        integrante.boletim_numero, data_bol
                    ])
        else:
            writer.writerow([
                                contrato.numero, contrato.empresa.razao_social,
                                contrato.vigencia_fim.strftime('%d/%m/%Y'),
                                "SEM COMISSÃO"
                            ] + ["-"] * 9)
    return response


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
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="relatorio_qualificacao_agentes.csv"'
    writer = csv.writer(response, delimiter=';')
    writer.writerow(['Militar', 'SARAM', 'Função', 'Contrato', 'Data Último Curso', 'Validade', 'Situação'])

    hoje = date.today()
    data_limite_curso = hoje - timedelta(days=365)
    equipe_ativa = Integrante.objects.filter(get_filtro_ativos()).select_related(
        'agente', 'funcao', 'comissao__contrato'
    ).order_by('agente__nome_de_guerra')

    for item in equipe_ativa:
        dt_curso = item.agente.data_ultimo_curso
        situacao, validade_fmt = "EM DIA", "-"
        if not dt_curso:
            situacao, dt_fmt = "SEM CURSO (IRREGULAR)", "Não Realizado"
        elif dt_curso < data_limite_curso:
            situacao = "VENCIDO (IRREGULAR)"
            dt_fmt = dt_curso.strftime('%d/%m/%Y')
            validade_fmt = (dt_curso + timedelta(days=365)).strftime('%d/%m/%Y')
        else:
            dt_fmt = dt_curso.strftime('%d/%m/%Y')
            validade_fmt = (dt_curso + timedelta(days=365)).strftime('%d/%m/%Y')

        writer.writerow([
            item.agente.nome_de_guerra, item.agente.saram, item.funcao.titulo,
            item.comissao.contrato.numero, dt_fmt, validade_fmt, situacao
        ])
    return response


@login_required
def exportar_relatorio_periodo_csv(request):
    data_inicial = request.GET.get('data_inicial')
    data_final = request.GET.get('data_final')
    response = HttpResponse(content_type='text/csv')
    nome_arquivo = f"relatorio_agentes_{data_inicial}_a_{data_final}.csv"
    response['Content-Disposition'] = f'attachment; filename="{nome_arquivo}"'
    writer = csv.writer(response, delimiter=';')
    writer.writerow([
        'Contrato', 'Empresa', 'Militar', 'SARAM', 'Função',
        'Início Designação', 'Fim Designação', 'Portaria', 'Boletim'
    ])
    if data_inicial and data_final:
        dt_ini = parse_date(data_inicial)
        dt_fim = parse_date(data_final)
        resultados = Integrante.objects.filter(data_inicio__lte=dt_fim).filter(
            Q(data_fim__gte=dt_ini) | Q(data_fim__isnull=True)).filter(
            Q(data_desligamento__gte=dt_ini) | Q(data_desligamento__isnull=True)).select_related(
            'agente', 'funcao', 'comissao__contrato'
        )
        for r in resultados:
            fim_fmt = r.data_fim.strftime('%d/%m/%Y') if r.data_fim else "Ativa (Indefinido)"
            bol_fmt = f"{r.boletim_numero} ({r.boletim_data.strftime('%d/%m/%Y')})" if r.boletim_numero else "-"
            writer.writerow([
                r.comissao.contrato.numero, r.comissao.contrato.empresa.razao_social,
                r.agente.nome_de_guerra, r.agente.saram, r.funcao.titulo,
                r.data_inicio.strftime('%d/%m/%Y'), fim_fmt, r.portaria_numero, bol_fmt
            ])
    return response