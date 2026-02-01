import csv
from datetime import date
from django.http import HttpResponse
from django.shortcuts import render
from django.db.models import Q, Prefetch
from contratos.models import Contrato, Comissao, Integrante
from contratos.utils import get_filtro_ativos


def pesquisa_publica(request):
    query = request.GET.get('q')
    resultados = []
    if query:
        resultados = Contrato.objects.filter(
            Q(numero__icontains=query) |
            Q(objeto__icontains=query) |
            Q(empresa__razao_social__icontains=query)
        ).distinct()
    return render(request, 'contratos/pesquisa.html', {'resultados': resultados, 'query': query})


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

    return render(request, 'contratos/detalhe.html', {
        'contrato': contrato,
        'comissoes': comissoes_ativas
    })


def relatorio_transparencia(request):
    hoje = date.today()
    filtro_integrante_ativo = get_filtro_ativos()

    contratos = Contrato.objects.filter(vigencia_fim__gte=hoje).prefetch_related(
        Prefetch(
            'comissoes',
            queryset=Comissao.objects.filter(ativa=True).prefetch_related(
                Prefetch('integrantes',
                         queryset=Integrante.objects.filter(filtro_integrante_ativo).select_related('agente', 'funcao'))
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
        'Comissão', 'Função', 'Militar',
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

                    writer.writerow([
                        contrato.numero,
                        contrato.empresa.razao_social,
                        contrato.vigencia_fim.strftime('%d/%m/%Y'),
                        com.get_tipo_display(),
                        integrante.funcao.titulo,
                        integrante.agente.nome_de_guerra,
                        inicio,
                        fim,
                        integrante.portaria_numero,
                        data_port,
                        integrante.boletim_numero,
                        data_bol
                    ])
        else:
            writer.writerow([contrato.numero, contrato.empresa.razao_social, contrato.vigencia_fim.strftime('%d/%m/%Y'),
                             "SEM COMISSÃO"] + ["-"] * 8)

    return response