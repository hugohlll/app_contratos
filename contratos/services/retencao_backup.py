"""
Regras de retenção dos arquivos de backup (quais apagar), sem acesso a disco ou rede.

Os arquivos seguem o padrão `<prefixo>AAAAMMDD.<ext>` (ex.: db_backup_20261111.sql).
Arquivos fora do padrão nunca são selecionados para apagar.
"""
import re

_DATA = re.compile(r'_(\d{8})\.[A-Za-z0-9]+$')


def data_do_nome(nome):
    m = _DATA.search(nome)
    return m.group(1) if m else None


def selecionar_para_apagar(nomes, prefixo, diarios, mensais=0):
    """
    Mantém os `diarios` arquivos mais recentes e, além deles, o primeiro arquivo de cada um
    dos `mensais` meses mais recentes. Retorna a lista dos nomes a apagar.
    """
    datados = sorted(
        ((data_do_nome(n), n) for n in nomes if n.startswith(prefixo) and data_do_nome(n)),
        reverse=True,
    )
    manter = {n for _, n in datados[:max(diarios, 0)]}

    if mensais > 0:
        primeiro_do_mes = {}
        for data, nome in datados:  # do mais novo para o mais antigo: o último visto é o 1º do mês
            primeiro_do_mes[data[:6]] = nome
        for mes in sorted(primeiro_do_mes, reverse=True)[:mensais]:
            manter.add(primeiro_do_mes[mes])

    return [n for _, n in datados if n not in manter]
