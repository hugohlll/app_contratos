import csv
import json
import urllib.parse
import io
import math
from datetime import date, timedelta
from django.http import HttpResponse
from django.shortcuts import render
from django.db.models import Count, Q, Prefetch
from django.contrib.auth.decorators import login_required
from django.utils.dateparse import parse_date
from django.utils.safestring import mark_safe
from contratos.models import Contrato, Agente, Comissao, Integrante, DIAS_VALIDADE_QUALIFICACAO
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
    data_limite_curso = hoje - timedelta(days=DIAS_VALIDADE_QUALIFICACAO)
    filtro_ativos = get_filtro_ativos()

    # 1. MONITORAMENTO DE VENCIMENTOS (Lógica Refatorada)
    comissoes_com_prazo = Comissao.objects.filter(
        ativa=True,
        data_fim__isnull=False,
        data_fim__gte=hoje
    ).select_related('contrato')

    lista_completa = []
    for comissao in comissoes_com_prazo:
        dias_restantes = (comissao.data_fim - hoje).days

        # Aplicação dos critérios: <=7 Crítico | 8-15 Alerta | >15 Normal
        classe_cor, status_texto = get_classificacao_vencimento(dias_restantes)

        comissao.dias_restantes = dias_restantes
        comissao.classe_cor = classe_cor
        comissao.status_texto = status_texto
        lista_completa.append(comissao)

    # Ordena pelos mais próximos de vencer
    lista_completa.sort(key=lambda x: x.dias_restantes)
    top_5_vencimentos = lista_completa[:5]
    total_vencimentos_count = len(lista_completa)
    
    # Dados agregados para gráfico de vencimentos (serializado como JSON para evitar
    # que o locale pt-BR formate números com separador de milhar no template)
    vencimentos_critico = sum(1 for i in lista_completa if i.dias_restantes <= 7)
    vencimentos_alerta = sum(1 for i in lista_completa if 8 <= i.dias_restantes <= 15)
    vencimentos_normal = sum(1 for i in lista_completa if i.dias_restantes > 15)
    vencimentos_json = mark_safe(json.dumps({
        'critico': vencimentos_critico,
        'alerta': vencimentos_alerta,
        'normal': vencimentos_normal,
    }))

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
    
    # Dados para gráfico de permanência (top 10) - serializado como JSON
    permanencia_labels = [f"{item['agente'].posto.sigla} {item['agente'].nome_de_guerra}" for item in top_10_permanencia]
    permanencia_dias = [item['dias_totais'] for item in top_10_permanencia]
    permanencia_labels_json = mark_safe(json.dumps(permanencia_labels, ensure_ascii=False))
    permanencia_dias_json = mark_safe(json.dumps(permanencia_dias))
    tem_permanencia = len(top_10_permanencia) > 0

    # 3. ESTATÍSTICAS DE QUALIFICAÇÃO
    agentes_ativos_ids = Integrante.objects.filter(filtro_ativos).values_list('agente', flat=True).distinct()
    agentes_ativos_qs = Agente.objects.filter(id__in=agentes_ativos_ids)
    
    total_ativos = agentes_ativos_qs.count()
    qtd_sem_curso = agentes_ativos_qs.filter(data_ultimo_curso__isnull=True).count()
    qtd_vencidos = agentes_ativos_qs.filter(data_ultimo_curso__lt=data_limite_curso).count()
    qtd_em_dia = total_ativos - qtd_sem_curso - qtd_vencidos

    dados_qualificacao = {
        'sem_curso': qtd_sem_curso,
        'vencidos': qtd_vencidos,
        'em_dia': qtd_em_dia,
        'total': total_ativos
    }

    # CÁLCULO PARA O VELOCÍMETRO (Segmentado: 90 e 120 dias)
    limite_90 = hoje + timedelta(days=90)
    limite_120 = hoje + timedelta(days=120)

    count_venc_90 = Contrato.objects.filter(vigencia_fim__gte=hoje, vigencia_fim__lte=limite_90).count()
    count_venc_120 = Contrato.objects.filter(vigencia_fim__gt=limite_90, vigencia_fim__lte=limite_120).count()
    count_venc_maior_120 = Contrato.objects.filter(vigencia_fim__gt=limite_120).count()

    # Listagem completa de contratos ativos com cálculo de dias restantes
    # (Usada para a nova tabela de monitoramento de prazos)
    contratos_ativos_lista = Contrato.objects.filter(vigencia_fim__gte=hoje).select_related('empresa').order_by('vigencia_fim')
    for c in contratos_ativos_lista:
        c.dias_restantes = (c.vigencia_fim - hoje).days
        if c.dias_restantes <= 90:
            c.classe_vencimento = 'text-danger fw-bold'
        elif c.dias_restantes <= 120:
            c.classe_vencimento = 'text-warning fw-bold'
        else:
            c.classe_vencimento = 'text-success'

    # 4. SOBRECARGA DE FISCAIS E RISCOS
    # Filtra apenas as designações ativas onde o título da função é exatamente "Fiscal"
    integrantes_fiscais = Integrante.objects.filter(filtro_ativos, funcao__titulo='Fiscal')
    
    # Agrupa os agentes e conta as suas atuações exclusivas como Fiscais
    fiscais_sobrecarregados = Agente.objects.filter(
        integrante__in=integrantes_fiscais
    ).annotate(
        total_atuacoes=Count('integrante', filter=Q(integrante__in=integrantes_fiscais))
    ).filter(total_atuacoes__gt=0).order_by('-total_atuacoes')[:10]
    
    total_contratos_ativos = Contrato.objects.filter(vigencia_fim__gte=hoje).count()
    
    # Conta a quantidade de Fiscais ÚNICOS (agentes distintos) atuando no momento
    total_fiscais_unicos = integrantes_fiscais.values('agente').distinct().count()
    
    # NOVO CÁLCULO DO LIMITE: (Nº Total de Contratos) / (Total de Fiscais Únicos)
    media_limite_fiscais = math.ceil(total_contratos_ativos / total_fiscais_unicos) if total_fiscais_unicos > 0 else 0
    
    # Dados para gráfico de sobrecarga - serializado como JSON
    sobrecarga_labels = [f"{ag.posto.sigla} {ag.nome_de_guerra}" for ag in fiscais_sobrecarregados]
    sobrecarga_valores = [ag.total_atuacoes for ag in fiscais_sobrecarregados]
    sobrecarga_labels_json = mark_safe(json.dumps(sobrecarga_labels, ensure_ascii=False))
    sobrecarga_valores_json = mark_safe(json.dumps(sobrecarga_valores))
    tem_sobrecarga = len(sobrecarga_labels) > 0

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

    context = {
        'lista_vencimentos': top_5_vencimentos,
        'total_vencimentos_count': total_vencimentos_count,
        'vencimentos_critico': vencimentos_critico,
        'vencimentos_alerta': vencimentos_alerta,
        'vencimentos_normal': vencimentos_normal,
        'vencimentos_json': vencimentos_json,
        'top_permanencia': top_10_permanencia,
        'permanencia_labels': permanencia_labels_json,
        'permanencia_dias': permanencia_dias_json,
        'tem_permanencia': tem_permanencia,
        'agentes_sobrecarregados': fiscais_sobrecarregados,
        'sobrecarga_labels': sobrecarga_labels_json,
        'sobrecarga_valores': sobrecarga_valores_json,
        'tem_sobrecarga': tem_sobrecarga,
        'media_limite_fiscais': media_limite_fiscais,
        'venc_data_json': mark_safe(json.dumps({
            'ate_90': count_venc_90,
            'entre_90_120': count_venc_120,
            'apos_120': count_venc_maior_120,
            'total': total_contratos_ativos
        })),
        'contratos_ativos_lista': contratos_ativos_lista,
        'contratos_risco': contratos_risco,
        'total_contratos_ativos': total_contratos_ativos,
        'total_agentes_atuando': total_agentes_atuando,
        'tabela_contratos': tabela_contratos,
        'dados_qualificacao_json': mark_safe(json.dumps(dados_qualificacao)),
    }

    return render(request, 'contratos/painel_controle.html', context)


@login_required
def exportar_vencimentos_csv(request):
    response = HttpResponse(content_type='text/csv; charset=utf-8')
    filename = "monitoramento_vencimentos.csv"
    encoded_filename = urllib.parse.quote(filename)
    response['Content-Disposition'] = f'attachment; filename="{filename}"; filename*=UTF-8\'\'{encoded_filename}'
    response['Cache-Control'] = 'no-cache, no-store, must-revalidate, max-age=0'
    response['Pragma'] = 'no-cache'
    response['Expires'] = '0'
    response['X-Content-Type-Options'] = 'nosniff'
    response['Access-Control-Expose-Headers'] = 'Content-Disposition'
    response.write('\ufeff')  # BOM
    
    writer = csv.writer(response, delimiter=';')
    writer.writerow(['Status', 'Dias Restantes', 'Comissão', 'Contrato', 'Término Previsto'])

    hoje = date.today()
    comissoes = Comissao.objects.filter(
        ativa=True,
        data_fim__isnull=False
    ).select_related('contrato')

    lista_export = []
    for comissao in comissoes:
        dias = (comissao.data_fim - hoje).days
        _, status = get_classificacao_vencimento(dias)
        lista_export.append((dias, status, comissao))

    lista_export.sort(key=lambda x: x[0])
    for dias, status, comissao in lista_export:
        writer.writerow([
            status,
            dias,
            f"Comissão de {comissao.get_tipo_display()}",
            comissao.contrato.numero,
            comissao.data_fim.strftime('%d/%m/%Y')
        ])
    
    return response


@login_required
def exportar_csv(request):
    """Exportação geral da auditoria"""
    buffer = io.StringIO()
    writer = csv.writer(buffer, delimiter=';')
    
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
    
    response = HttpResponse(buffer.getvalue().encode('utf-8-sig'), content_type='text/csv; charset=utf-8')
    filename = "auditoria_completa.csv"
    encoded_filename = urllib.parse.quote(filename)
    response['Content-Disposition'] = f'attachment; filename="{filename}"; filename*=UTF-8\'\'{encoded_filename}'
    response['Cache-Control'] = 'no-cache, no-store, must-revalidate, max-age=0'
    response['Pragma'] = 'no-cache'
    response['Expires'] = '0'
    response['X-Content-Type-Options'] = 'nosniff'
    response['Access-Control-Expose-Headers'] = 'Content-Disposition'
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
    buffer = io.StringIO()
    writer = csv.writer(buffer, delimiter=';')
    writer.writerow(['Militar', 'SARAM', 'Função', 'Contrato', 'Data Último Curso', 'Validade', 'Situação'])

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

        writer.writerow([
            nome_completo, item.agente.saram, item.funcao.titulo,
            item.comissao.contrato.numero, dt_fmt, validade_fmt, situacao
        ])
        
    response = HttpResponse(buffer.getvalue().encode('utf-8-sig'), content_type='text/csv; charset=utf-8')
    filename = "relatorio_qualificacao_agentes.csv"
    encoded_filename = urllib.parse.quote(filename)
    response['Content-Disposition'] = f'attachment; filename="{filename}"; filename*=UTF-8\'\'{encoded_filename}'
    response['Cache-Control'] = 'no-cache, no-store, must-revalidate, max-age=0'
    response['Pragma'] = 'no-cache'
    response['Expires'] = '0'
    response['X-Content-Type-Options'] = 'nosniff'
    response['Access-Control-Expose-Headers'] = 'Content-Disposition'
    return response


@login_required
def exportar_relatorio_periodo_csv(request):
    data_inicial = request.GET.get('data_inicial')
    data_final = request.GET.get('data_final')
    
    buffer = io.StringIO()
    writer = csv.writer(buffer, delimiter=';')
    writer.writerow([
        'Contrato', 'Tipo Comissão', 'Empresa', 'Militar', 'SARAM', 'CPF', 'Função',
        'Início', 'Término (Previsão)', 'Nº Portaria', 'Data Portaria', 'Nº Boletim', 'Data Boletim'
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
            fim_fmt = r.data_fim.strftime('%d/%m/%Y') if r.data_fim else "-"
            data_port = r.portaria_data.strftime('%d/%m/%Y') if r.portaria_data else "-"
            bol_num = r.boletim_numero if r.boletim_numero else "-"
            bol_data = r.boletim_data.strftime('%d/%m/%Y') if r.boletim_data else "-"
            
            posto = r.posto_graduacao.sigla if r.posto_graduacao else r.agente.posto.sigla
            nome_completo = f"{posto} {r.agente.nome_de_guerra}"
            
            tipo_label = "Fiscalização" if r.comissao.tipo == 'FISCALIZACAO' else "Recebimento"
            
            writer.writerow([
                r.comissao.contrato.numero, tipo_label, r.comissao.contrato.empresa.razao_social,
                nome_completo, r.agente.saram, r.agente.cpf or '-', r.funcao.titulo,
                r.data_inicio.strftime('%d/%m/%Y'), fim_fmt, 
                r.portaria_numero, data_port, bol_num, bol_data
            ])
            
    nome_arquivo = f"relatorio_agentes_{data_inicial}_a_{data_final}.csv"
    encoded_filename = urllib.parse.quote(nome_arquivo)
    response = HttpResponse(buffer.getvalue().encode('utf-8-sig'), content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = f'attachment; filename="{nome_arquivo}"; filename*=UTF-8\'\'{encoded_filename}'
    response['Cache-Control'] = 'no-cache, no-store, must-revalidate, max-age=0'
    response['Pragma'] = 'no-cache'
    response['Expires'] = '0'
    response['X-Content-Type-Options'] = 'nosniff'
    response['Access-Control-Expose-Headers'] = 'Content-Disposition'
    return response
    
    
@login_required
def exportar_radar_permanencia_csv(request):
    response = HttpResponse(content_type='text/csv; charset=utf-8-sig')
    response = HttpResponse(content_type='text/csv; charset=utf-8')
    filename = "radar_permanencia.csv"
    encoded_filename = urllib.parse.quote(filename)
    response['Content-Disposition'] = f'attachment; filename="{filename}"; filename*=UTF-8\'\'{encoded_filename}'
    response['Cache-Control'] = 'no-cache, no-store, must-revalidate, max-age=0'
    response['Pragma'] = 'no-cache'
    response['Expires'] = '0'
    response['X-Content-Type-Options'] = 'nosniff'
    response['Access-Control-Expose-Headers'] = 'Content-Disposition'
    response.write('\ufeff')
    
    writer = csv.writer(response, delimiter=';')
    writer.writerow(['Militar', 'Função', 'Contrato', 'Dias Totais', 'Tempo Formatado', 'Início Real'])
    
    hoje = date.today()
    filtro_ativos = get_filtro_ativos()
    
    integrantes_ativos = Integrante.objects.filter(filtro_ativos).select_related(
        'agente', 'funcao', 'comissao__contrato'
    )
    
    radar_permanencia = []
    
    for atual in integrantes_ativos:
        data_inicio_real = atual.data_inicio
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
        
        radar_permanencia.append({
            'agente': atual.agente,
            'funcao': atual.funcao,
            'contrato': atual.comissao.contrato,
            'dias_totais': dias_totais,
            'tempo_formatado': f"{anos}a {meses}m ({dias_totais} dias)",
            'inicio_real': data_inicio_real,
        })
        
    radar_permanencia.sort(key=lambda x: x['dias_totais'], reverse=True)
    
    for item in radar_permanencia:
        writer.writerow([
            f"{item['agente'].posto.sigla} {item['agente'].nome_de_guerra}",
            item['funcao'].titulo,
            item['contrato'].numero,
            item['dias_totais'],
            item['tempo_formatado'],
            item['inicio_real'].strftime('%d/%m/%Y')
        ])
        
    return response


@login_required
def exportar_sobrecarga_fiscais_csv(request):
    response = HttpResponse(content_type='text/csv; charset=utf-8')
    filename = "sobrecarga_fiscais.csv"
    encoded_filename = urllib.parse.quote(filename)
    # Adicionando RFC 5987 para Chrome
    response['Content-Disposition'] = f'attachment; filename="{filename}"; filename*=UTF-8\'\'{encoded_filename}'
    response['Cache-Control'] = 'no-cache, no-store, must-revalidate, max-age=0'
    response['Pragma'] = 'no-cache'
    response['Expires'] = '0'
    response['X-Content-Type-Options'] = 'nosniff'
    response['Access-Control-Expose-Headers'] = 'Content-Disposition'
    response.write('\ufeff')
    
    writer = csv.writer(response, delimiter=';')
    writer.writerow(['Militar (Fiscal)', 'SARAM', 'Quantidade de Contratos Fiscalizados'])
    
    filtro_ativos = get_filtro_ativos()
    integrantes_fiscais = Integrante.objects.filter(filtro_ativos, funcao__titulo='Fiscal')
    
    fiscais_sobrecarregados = Agente.objects.filter(
        integrante__in=integrantes_fiscais
    ).annotate(
        total_atuacoes=Count('integrante', filter=Q(integrante__in=integrantes_fiscais))
    ).filter(total_atuacoes__gt=0).order_by('-total_atuacoes')
    
    for agente in fiscais_sobrecarregados:
        writer.writerow([
            f"{agente.posto.sigla} {agente.nome_de_guerra}",
            agente.saram,
            agente.total_atuacoes
        ])
        
    return response
@login_required
def exportar_contratos_vencimento_csv(request):
    response = HttpResponse(content_type='text/csv; charset=utf-8')
    filename = "vencimento_contratos.csv"
    encoded_filename = urllib.parse.quote(filename)
    response['Content-Disposition'] = f'attachment; filename="{filename}"; filename*=UTF-8\'\'{encoded_filename}'
    response['Cache-Control'] = 'no-cache, no-store, must-revalidate, max-age=0'
    response['Pragma'] = 'no-cache'
    response['Expires'] = '0'
    response['X-Content-Type-Options'] = 'nosniff'
    response['Access-Control-Expose-Headers'] = 'Content-Disposition'
    response.write('\ufeff')
    
    writer = csv.writer(response, delimiter=';')
    writer.writerow(['Contrato', 'Empresa', 'Vencimento', 'Dias Restantes', 'Situação'])
    
    hoje = date.today()
    contratos = Contrato.objects.filter(vigencia_fim__gte=hoje).select_related('empresa').order_by('vigencia_fim')
    
    for c in contratos:
        dias = (c.vigencia_fim - hoje).days
        situacao = "NORMAL"
        if dias <= 90:
            situacao = "CRÍTICO"
        elif dias <= 120:
            situacao = "ALERTA"
            
        writer.writerow([
            c.numero,
            c.empresa.razao_social,
            c.vigencia_fim.strftime('%d/%m/%Y'),
            dias,
            situacao
        ])
        
    return response
