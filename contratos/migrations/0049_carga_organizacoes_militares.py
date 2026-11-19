from django.db import migrations

# Carga inicial do cadastro de OMs (#51). Códigos UASG e prefixos de PI só onde confirmados;
# o Administrador completa o restante pela tela de OMs.
OMS = [
    ('GAP-BR', 'Grupamento de Apoio de Brasília', '120006', '', True),
    ('OABR', 'Odontoclínica de Aeronáutica de Brasília', '120112', '', False),
    ('COMGEP', 'Comando-Geral do Pessoal', '120131', 'CG', False),
    ('CCA-BR', 'Centro de Computação da Aeronáutica de Brasília', '', '', False),
    ('EMAER', 'Estado-Maior da Aeronáutica', '', 'EM', False),
    ('GABAER', 'Gabinete do Comandante da Aeronáutica', '', 'GB', False),
    ('CIAER', 'Centro de Inteligência da Aeronáutica', '', '', False),
    ('SEFA', 'Secretaria de Economia, Finanças e Administração da Aeronáutica', '', '', False),
    ('DIREF', 'Diretoria de Economia e Finanças da Aeronáutica', '', '', False),
    ('SECPROM', '', '', '', False),
    ('DECEA', 'Departamento de Controle do Espaço Aéreo', '', 'DC', False),
]


def carregar(apps, schema_editor):
    OM = apps.get_model('contratos', 'OrganizacaoMilitar')
    for sigla, nome, uasg, pi, gapbr in OMS:
        OM.objects.get_or_create(sigla=sigla, defaults=dict(nome=nome, codigo_uasg=uasg, prefixos_pi=pi, eh_gapbr=gapbr))


class Migration(migrations.Migration):
    dependencies = [('contratos', '0048_catalogo_om_beneficiada')]
    operations = [migrations.RunPython(carregar, migrations.RunPython.noop)]
