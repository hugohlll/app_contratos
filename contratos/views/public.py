import csv
from datetime import date
from django.http import HttpResponse
from django.shortcuts import render
from django.db.models import Q, Prefetch, Case, When, Value, IntegerField
from contratos.models import Contrato, Comissao, Integrante
from contratos.utils import get_filtro_ativos


def pesquisa_publica(request):
    return render(request, 'contratos/pesquisa.html')


def buscar_contratos(request):
    query = request.GET.get('q')
    contratos = []
    
    if query:
        filtro_integrante_ativo = get_filtro_ativos()
        
        contratos = Contrato.objects.filter(
            Q(numero__icontains=query) |
            Q(objeto__icontains=query) |
            Q(empresa__razao_social__icontains=query)
        ).prefetch_related(
            Prefetch(
                'comissoes',
                queryset=Comissao.objects.filter(ativa=True).prefetch_related(
                    Prefetch('integrantes',
                             queryset=Integrante.objects.filter(filtro_integrante_ativo).select_related('agente', 'funcao').annotate(
                                 prioridade=Case(
                                     When(funcao__titulo__icontains='Gestor', then=Value(1)),
                                     When(funcao__titulo__icontains='Presidente', then=Value(1)),
                                     When(funcao__titulo__icontains='Fiscal', then=Value(2)),
                                     When(funcao__titulo__icontains='Membro', then=Value(2)),
                                     default=Value(3),
                                     output_field=IntegerField(),
                                 )
                             ).order_by('prioridade', 'funcao__titulo'))
                ),
                to_attr='comissoes_vigentes'
            )
        ).distinct().order_by('vigencia_fim')

    return render(request, 'contratos/resultado_busca.html', {'contratos': contratos, 'query': query})


def detalhe_contrato(request, contrato_id):
    contrato = Contrato.objects.get(id=contrato_id)
    filtro_integrante_ativo = get_filtro_ativos()

    comissoes_ativas = contrato.comissoes.filter(ativa=True).prefetch_related(
        Prefetch(
            'integrantes',
            queryset=Integrante.objects.filter(filtro_integrante_ativo).select_related('agente', 'funcao'),
            to_attr='integrantes_ativos_lista'
        )
    )

    comissoes_fiscalizacao = [c for c in comissoes_ativas if c.tipo == 'FISCALIZACAO']
    comissoes_recebimento = [c for c in comissoes_ativas if c.tipo == 'RECEBIMENTO']

    return render(request, 'contratos/detalhe.html', {
        'contrato': contrato,
        'comissoes_fiscalizacao': comissoes_fiscalizacao,
        'comissoes_recebimento': comissoes_recebimento
    })


def relatorio_transparencia(request):
    hoje = date.today()
    filtro_integrante_ativo = get_filtro_ativos()

    contratos = Contrato.objects.filter(vigencia_fim__gte=hoje).prefetch_related(
        Prefetch(
            'comissoes',
            queryset=Comissao.objects.filter(ativa=True).prefetch_related(
                Prefetch('integrantes',
                         queryset=Integrante.objects.filter(filtro_integrante_ativo).select_related('agente', 'funcao').annotate(
                             prioridade=Case(
                                 When(funcao__titulo__icontains='Gestor', then=Value(1)),
                                 When(funcao__titulo__icontains='Presidente', then=Value(1)),
                                 When(funcao__titulo__icontains='Fiscal', then=Value(2)),
                                 When(funcao__titulo__icontains='Membro', then=Value(2)),
                                 default=Value(3),
                                 output_field=IntegerField(),
                             )
                         ).order_by('prioridade', 'funcao__titulo'))
            ),
            to_attr='comissoes_vigentes'
        )
    ).order_by('vigencia_fim')

    return render(request, 'contratos/relatorio_transparencia.html', {'contratos': contratos})


def exportar_transparencia_csv(request):
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="contratos_gap_br.csv"'

    writer = csv.writer(response, delimiter=';')
    writer.writerow([
        'Contrato', 'Empresa', 'Vigência Contrato',
        'Comissão', 'Função', 'Posto/Grad', 'Nome',
        'Início Designação', 'Término Previsto',
        'Nº Portaria', 'Data Portaria',
        'Nº Boletim', 'Data Boletim'
    ])

    hoje = date.today()
    filtro_integrante_ativo = get_filtro_ativos()
    contratos = Contrato.objects.filter(vigencia_fim__gte=hoje)

    for contrato in contratos:
        comissoes = contrato.comissoes.filter(ativa=True)
        if comissoes.exists():
            for com in comissoes:
                for integrante in com.integrantes.filter(filtro_integrante_ativo):
                    inicio = integrante.data_inicio.strftime('%d/%m/%Y') if integrante.data_inicio else "-"
                    fim = integrante.data_fim.strftime('%d/%m/%Y') if integrante.data_fim else "Indeterminado"
                    data_port = integrante.portaria_data.strftime('%d/%m/%Y') if integrante.portaria_data else "-"
                    data_bol = integrante.boletim_data.strftime('%d/%m/%Y') if integrante.boletim_data else "-"
                    posto = integrante.posto_graduacao.sigla if integrante.posto_graduacao else integrante.agente.posto.sigla

                    writer.writerow([
                        contrato.numero,
                        contrato.empresa.razao_social,
                        contrato.vigencia_fim.strftime('%d/%m/%Y'),
                        com.get_tipo_display(),
                        integrante.funcao.titulo,
                        posto,
                        integrante.agente.nome_de_guerra,
                        inicio,
                        fim,
                        integrante.portaria_numero,
                        data_port,
                        integrante.boletim_numero if integrante.boletim_numero else "-",
                        data_bol
                    ])
        else:
            writer.writerow([contrato.numero, contrato.empresa.razao_social, contrato.vigencia_fim.strftime('%d/%m/%Y'),
                             "SEM COMISSÃO"] + ["-"] * 9)

    return response