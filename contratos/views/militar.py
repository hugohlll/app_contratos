import csv
from datetime import date
from django.http import HttpResponse
from django.shortcuts import render
from django.db.models import Q
from contratos.models import Integrante
from contratos.utils import get_filtro_ativos


def consulta_militar(request):
    query = request.GET.get('q')
    integrantes_ativos = []
    hoje = date.today()

    if query:
        base_qs = Integrante.objects.filter(
            Q(agente__saram=query) |
            Q(agente__nome_de_guerra__icontains=query) |
            Q(agente__nome_completo__icontains=query)
        )
        filtro_ativo = get_filtro_ativos()

        integrantes_ativos = base_qs.filter(filtro_ativo).select_related(
            'comissao__contrato',
            'comissao__contrato__empresa',
            'funcao',
            'agente',
            'posto'
        ).order_by('comissao__contrato__vigencia_fim')

    return render(request, 'contratos/militar.html', {
        'integrantes': integrantes_ativos,
        'query': query,
        'hoje': hoje
    })


def exportar_historico_militar_csv(request):
    query = request.GET.get('q')
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="historico_comissoes.csv"'

    writer = csv.writer(response, delimiter=';')
    writer.writerow([
        'Militar', 'SARAM', 'Status', 'Contrato', 'Objeto',
        'Função', 'Início', 'Fim Previsto', 'Fim Efetivo (Desligamento)', 'Motivo Saída', 'Portaria'
    ])

    if query:
        hoje = date.today()
        historico_completo = Integrante.objects.filter(
            Q(agente__saram=query) |
            Q(agente__nome_de_guerra__icontains=query) |
            Q(agente__nome_completo__icontains=query)
        ).select_related('agente', 'funcao', 'comissao__contrato').order_by('-data_inicio')

        for item in historico_completo:
            status = "ATIVO" if item.is_ativo else "ENCERRADO"

            inicio = item.data_inicio.strftime('%d/%m/%Y') if item.data_inicio else "-"
            fim_prev = item.data_fim.strftime('%d/%m/%Y') if item.data_fim else "Indefinido"
            fim_real = item.data_desligamento.strftime('%d/%m/%Y') if item.data_desligamento else "-"
            motivo = item.motivo_desligamento if item.motivo_desligamento else "-"

            writer.writerow([
                item.agente.nome_de_guerra,
                item.agente.saram,
                status,
                item.comissao.contrato.numero,
                item.comissao.contrato.objeto[:50],
                item.funcao.titulo,
                inicio,
                fim_prev,
                fim_real,
                motivo,
                item.portaria_numero
            ])

    return response