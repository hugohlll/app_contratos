"""Catálogo do Contratos.gov.br e classificação da OM beneficiada (#51).

Usa um cliente falso: nenhum acesso à internet.
"""
from datetime import date
from decimal import Decimal
from io import StringIO
from unittest import mock

from django.contrib.auth.models import Group, User
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase
from django.urls import reverse

from contratos.models import (
    Contrato, ContratoCatalogo, EmailPendente, Empresa, OrganizacaoMilitar, RegistroClassificacao,
)
from contratos.services.contratosgov import ContratosGovErro
from contratos.services.om_beneficiada import (
    ClassificacaoErro, IndiceOMs, classificar, decidir_sugestao, indicios_da_lista, indicios_do_detalhe,
    normalizar_numero, numero_local, sincronizar_catalogo, valor_br,
)

HOJE = date(2026, 11, 19)


def item(id_, numero='00013/2024', tipo='Contrato', cnpj='13.798.155/0001-67', fim='2027-07-17',
         objeto='SERVIÇOS DE LIMPEZA', requisitante=None, receita='Despesa'):
    return {
        'id': id_, 'numero': numero, 'tipo': tipo, 'receita_despesa': receita, 'categoria': 'Serviços',
        'fornecedor': {'cnpj_cpf_idgener': cnpj, 'nome': f'EMPRESA {id_} LTDA'},
        'objeto': objeto, 'vigencia_inicio': '2024-08-20', 'vigencia_fim': fim,
        'valor_global': '4.464.512,73', 'situacao': 'Ativo', 'unidades_requisitantes': requisitante,
        'processo': '67284.005168/2023-48',
    }


class ClienteFalso:
    def __init__(self, lista, arquivos=None, historico=None, empenhos=None, falha_detalhe=False):
        self.lista, self.falha_detalhe = lista, falha_detalhe
        self._arquivos, self._historico, self._empenhos = arquivos or {}, historico or {}, empenhos or {}
        self.chamadas = []

    def contratos_ativos(self, ug=None):
        if isinstance(self.lista, Exception):
            raise self.lista
        return self.lista

    def _detalhe(self, tabela, nome, id_):
        self.chamadas.append((nome, id_))
        if self.falha_detalhe:
            raise ContratosGovErro('falhou')
        return tabela.get(id_, [])

    def arquivos(self, id_):
        return self._detalhe(self._arquivos, 'arquivos', id_)

    def historico(self, id_):
        return self._detalhe(self._historico, 'historico', id_)

    def empenhos(self, id_):
        return self._detalhe(self._empenhos, 'empenhos', id_)


class ConversoesTests(TestCase):
    def test_numero(self):
        self.assertEqual(normalizar_numero('00013/2024'), (13, 2024))
        self.assertEqual(normalizar_numero('013/2024'), (13, 2024))
        self.assertIsNone(normalizar_numero('2025NE002363'))
        self.assertEqual(numero_local('00013/2024'), '013/2024')

    def test_valor(self):
        self.assertEqual(valor_br('4.464.512,73'), Decimal('4464512.73'))
        self.assertIsNone(valor_br(None))


class SugestaoTests(TestCase):
    def setUp(self):
        self.indice = IndiceOMs.carregar()  # carga inicial da migração 0049

    def test_requisitante_por_uasg_e_por_nome(self):
        ind = indicios_da_lista(item(1, requisitante='120112'), self.indice)
        self.assertEqual(ind[0]['om'], 'OABR')
        ind = indicios_da_lista(item(1, requisitante='Odontoclínica de Aeronáutica de Brasília'), self.indice)
        self.assertEqual(ind[0]['om'], 'OABR')

    def test_requisitante_desconhecido_vira_indicio_sem_om(self):
        ind = indicios_da_lista(item(1, requisitante='999999'), self.indice)
        self.assertEqual(ind[0]['om'], '')

    def test_sigla_no_objeto(self):
        ind = indicios_da_lista(item(1, objeto='ADEQUAÇÃO DAS INSTALAÇÕES DO COMGEP'), self.indice)
        self.assertEqual([i['om'] for i in ind], ['COMGEP'])

    def test_nome_completo_no_objeto(self):
        ind = indicios_da_lista(item(1, objeto='RESÍDUOS PROVENIENTES DA ODONTOCLÍNICA DE AERONÁUTICA DE BRASÍLIA'),
                                self.indice)
        self.assertEqual([i['om'] for i in ind], ['OABR'])

    def test_processo_na_requisitante_nao_e_quebrado(self):
        ind = indicios_da_lista(item(1, requisitante='67284.002659/2024-38'), self.indice)
        self.assertEqual([(i['valor'], i['om']) for i in ind], [('67284.002659/2024-38', '')])

    def test_sigla_dentro_de_palavra_nao_conta(self):
        self.assertEqual(indicios_da_lista(item(1, objeto='SERVIÇOS DE OABRASIL'), self.indice), [])

    def test_numero_formal_e_plano_interno(self):
        cliente = ClienteFalso([], arquivos={7: [{'descricao': 'TERMO DE CONTRATO Nº 013/GAP-BR-COMGEP/2024'}]},
                               empenhos={7: [{'planointerno': 'CG0622BAG03 - TRANSPORTE', 'empenhado': '10,00'},
                                             {'planointerno': 'SF063100600 - CONTRATOS', 'empenhado': '1,00'}]})
        ind = indicios_do_detalhe(cliente, 7, self.indice)
        self.assertEqual([(i['fonte'], i['om']) for i in ind], [('Número formal', 'COMGEP'), ('Plano interno', 'COMGEP')])

    def test_concordancia_gera_sugestao_e_divergencia_nao(self):
        concordam = [{'om': 'COMGEP'}, {'om': 'COMGEP'}, {'om': ''}]
        self.assertEqual(decidir_sugestao(concordam, self.indice).sigla, 'COMGEP')
        self.assertIsNone(decidir_sugestao([{'om': 'COMGEP'}, {'om': 'OABR'}], self.indice))
        self.assertIsNone(decidir_sugestao([], self.indice))


class SincronizacaoTests(TestCase):
    def setUp(self):
        self.empresa = Empresa.objects.create(razao_social='LOCAL LTDA', cnpj='11.111.111/0001-11')
        self.local = Contrato.objects.create(numero='005/2023', objeto='x', empresa=self.empresa,
                                             vigencia_inicio=date(2023, 1, 1), vigencia_fim=date(2027, 1, 1),
                                             valor_total=10)

    def test_filtra_tipo_e_vigencia_e_vincula_existente(self):
        lista = [
            item(1),                                           # novo, vigente → a classificar
            item(2, tipo='Empenho', numero='2025NE000001'),   # outro tipo → fora
            item(3, tipo='Outros', numero='00006/2026'),      # outro tipo → fora
            item(4, numero='00009/2020', fim='2021-01-01'),   # vencido → fora
            item(5, numero='00005/2023', cnpj='11.111.111/0001-11', fim='2020-01-01'),  # já no SISCONT
        ]
        r = sincronizar_catalogo(ClienteFalso(lista), hoje=HOJE)
        self.assertEqual(sorted(ContratoCatalogo.objects.values_list('id_contratosgov', flat=True)), [1, 5])
        self.assertEqual([c.id_contratosgov for c in r.novos], [1])
        vinculado = ContratoCatalogo.objects.get(id_contratosgov=5)
        self.assertEqual(vinculado.contrato, self.local)
        self.assertTrue(vinculado.vinculo_automatico)
        self.assertEqual(vinculado.om_beneficiada.sigla, 'GAP-BR')
        self.assertTrue(vinculado.registros.get().automatico)
        self.assertEqual(r.pendentes, 1)

    def test_mesmo_numero_com_outro_cnpj_nao_vincula(self):
        sincronizar_catalogo(ClienteFalso([item(5, numero='00005/2023', cnpj='22.222.222/0001-22')]), hoje=HOJE)
        self.assertEqual(ContratoCatalogo.objects.get().situacao, ContratoCatalogo.PENDENTE)

    def test_falha_na_lista_nao_grava_nada(self):
        with self.assertRaises(ContratosGovErro):
            sincronizar_catalogo(ClienteFalso(ContratosGovErro('fora do ar')), hoje=HOJE)
        self.assertFalse(ContratoCatalogo.objects.exists())

    def test_sugestao_so_para_pendentes_e_refeita(self):
        cliente = ClienteFalso([item(1, requisitante='120112'), item(5, numero='00005/2023', cnpj='11.111.111/0001-11')])
        sincronizar_catalogo(cliente, hoje=HOJE)
        self.assertEqual({id_ for _, id_ in cliente.chamadas}, {1})
        c = ContratoCatalogo.objects.get(id_contratosgov=1)
        self.assertEqual(c.sugestao_om.sigla, 'OABR')
        # No dia seguinte aparece o número formal de outra OM: os indícios divergem, a sugestão some.
        cliente._arquivos = {1: [{'descricao': 'CONTRATO 001/GAP-BR-COMGEP/2026'}]}
        sincronizar_catalogo(cliente, hoje=HOJE)
        c.refresh_from_db()
        self.assertIsNone(c.sugestao_om)
        self.assertEqual(len(c.sugestao_indicios), 2)

    def test_falha_no_detalhe_mantem_sugestao_anterior(self):
        sincronizar_catalogo(ClienteFalso([item(1, requisitante='120112')]), hoje=HOJE)
        r = sincronizar_catalogo(ClienteFalso([item(1, requisitante='120112')], falha_detalhe=True), hoje=HOJE)
        self.assertEqual(r.sugestoes_falhas, 1)
        self.assertEqual(ContratoCatalogo.objects.get().sugestao_om.sigla, 'OABR')

    def test_classificado_nao_e_mais_consultado(self):
        sincronizar_catalogo(ClienteFalso([item(1)]), hoje=HOJE)
        c = ContratoCatalogo.objects.get()
        classificar(c, None, om=OrganizacaoMilitar.objects.get(sigla='OABR'))
        cliente = ClienteFalso([item(1)])
        r = sincronizar_catalogo(cliente, hoje=HOJE)
        self.assertEqual(cliente.chamadas, [])
        self.assertEqual(r.novos, [])


class ClassificacaoTests(TestCase):
    def setUp(self):
        sincronizar_catalogo(ClienteFalso([item(1, receita='Receita')]), hoje=HOJE)
        self.c = ContratoCatalogo.objects.get()
        self.admin = User.objects.create_user('adm', is_superuser=True)
        self.gapbr = OrganizacaoMilitar.objects.get(sigla='GAP-BR')
        self.oabr = OrganizacaoMilitar.objects.get(sigla='OABR')

    def test_gapbr_vira_contrato(self):
        classificar(self.c, self.admin, om=self.gapbr)
        contrato = self.c.contrato
        self.assertEqual(contrato.numero, '013/2024')
        self.assertEqual(contrato.tipo, 'RECEITA')
        self.assertEqual(contrato.valor_total, Decimal('4464512.73'))
        self.assertEqual(contrato.empresa.cnpj, '13.798.155/0001-67')
        self.assertEqual(self.c.registros.get().usuario, self.admin)

    def test_om_apoiada_nao_vira_contrato(self):
        classificar(self.c, self.admin, om=self.oabr)
        self.assertIsNone(self.c.contrato)
        self.assertFalse(Contrato.objects.exists())

    def test_desconsiderar_exige_justificativa(self):
        with self.assertRaises(ClassificacaoErro):
            classificar(self.c, self.admin, desconsiderar=True)
        classificar(self.c, self.admin, desconsiderar=True, justificativa='Registro duplicado')
        self.assertEqual(self.c.situacao, ContratoCatalogo.DESCONSIDERADO)

    def test_correcao_exige_justificativa_e_nao_exclui_contrato(self):
        classificar(self.c, self.admin, om=self.gapbr)
        contrato = self.c.contrato
        with self.assertRaises(ClassificacaoErro):
            classificar(self.c, self.admin, om=self.oabr)
        avisos = classificar(self.c, self.admin, om=self.oabr, justificativa='Era da OABR')
        self.assertTrue(avisos)
        self.assertIsNone(self.c.contrato)
        self.assertTrue(Contrato.objects.filter(pk=contrato.pk).exists())
        self.assertEqual(RegistroClassificacao.objects.filter(catalogo=self.c).count(), 2)

    def test_numero_ja_usado_por_outra_empresa_bloqueia(self):
        outra = Empresa.objects.create(razao_social='OUTRA', cnpj='99.999.999/0001-99')
        Contrato.objects.create(numero='013/2024', objeto='x', empresa=outra, vigencia_inicio=HOJE,
                                vigencia_fim=HOJE, valor_total=1)
        with self.assertRaises(ClassificacaoErro):
            classificar(self.c, self.admin, om=self.gapbr)
        self.c.refresh_from_db()
        self.assertEqual(self.c.situacao, ContratoCatalogo.PENDENTE)  # transação desfeita


class TelasTests(TestCase):
    def setUp(self):
        sincronizar_catalogo(ClienteFalso([item(1), item(2, numero='00014/2024')]), hoje=HOJE)
        self.admin = User.objects.create_user('adm', password='x')
        self.admin.groups.add(Group.objects.get_or_create(name='Administradores')[0])
        self.auditor = User.objects.create_user('aud', password='x')
        self.auditor.groups.add(Group.objects.get_or_create(name='Auditores')[0])

    def test_so_administrador_acessa(self):
        self.client.force_login(self.auditor)
        self.assertEqual(self.client.get(reverse('catalogo_contratosgov')).status_code, 302)
        resp = self.client.get(reverse('portal_home'))
        self.assertNotContains(resp, 'Contratos a classificar')
        self.client.force_login(self.admin)
        resp = self.client.get(reverse('catalogo_contratosgov'))
        self.assertContains(resp, '00013/2024')

    def test_contador_no_menu(self):
        self.client.force_login(self.admin)
        resp = self.client.get(reverse('portal_home'))
        self.assertContains(resp, 'Contratos a classificar')
        ContratoCatalogo.objects.update(situacao=ContratoCatalogo.DESCONSIDERADO)
        resp = self.client.get(reverse('portal_home'))
        self.assertNotContains(resp, '📥 Contratos a classificar')

    def test_classificar_e_lote(self):
        self.client.force_login(self.admin)
        oabr = OrganizacaoMilitar.objects.get(sigla='OABR')
        c1, c2 = ContratoCatalogo.objects.order_by('id_contratosgov')
        resp = self.client.post(reverse('classificar_catalogo', args=[c1.pk]), {'om': oabr.pk})
        self.assertRedirects(resp, reverse('catalogo_contratosgov'))
        resp = self.client.post(reverse('classificar_catalogo_lote'), {'selecionados': [c2.pk], 'om': oabr.pk})
        self.assertEqual(ContratoCatalogo.objects.filter(om_beneficiada=oabr).count(), 2)

    def test_tela_de_classificacao_mostra_indicios(self):
        c = ContratoCatalogo.objects.first()
        c.sugestao_indicios = [{'fonte': 'Número formal', 'valor': 'GAP-BR-COMGEP', 'om': 'COMGEP', 'observacao': ''}]
        c.save()
        self.client.force_login(self.admin)
        resp = self.client.get(reverse('classificar_catalogo', args=[c.pk]))
        self.assertContains(resp, 'GAP-BR-COMGEP')

    def test_cadastro_de_om_so_um_gapbr(self):
        self.client.force_login(self.admin)
        resp = self.client.post(reverse('nova_om'), {'sigla': 'babr', 'nome': 'Base', 'codigo_uasg': '',
                                                     'prefixos_pi': '', 'eh_gapbr': 'on', 'ativa': 'on'})
        self.assertContains(resp, 'Só uma OM pode ser marcada como GAP-BR')
        self.client.post(reverse('nova_om'), {'sigla': 'babr', 'nome': 'Base', 'ativa': 'on'})
        self.assertTrue(OrganizacaoMilitar.objects.filter(sigla='BABR').exists())


class ComandoTests(TestCase):
    def test_comando_avisa_administradores(self):
        adm = User.objects.create_user('adm', email='adm@exemplo.invalid', is_superuser=True)
        with mock.patch('contratos.management.commands.sincronizar_catalogo_contratosgov.ClienteContratosGov',
                        return_value=ClienteFalso([item(1)])):
            out = StringIO()
            call_command('sincronizar_catalogo_contratosgov', stdout=out)
        self.assertIn('Novos a classificar: 1', out.getvalue())
        email = EmailPendente.objects.get()
        self.assertIn(adm.email, email.destinatarios)
        self.assertIn('00013/2024', email.corpo_texto)

    def test_comando_falha_sem_gravar(self):
        with mock.patch('contratos.management.commands.sincronizar_catalogo_contratosgov.ClienteContratosGov',
                        return_value=ClienteFalso(ContratosGovErro('fora do ar'))):
            with self.assertRaisesRegex(CommandError, 'fora do ar'):
                call_command('sincronizar_catalogo_contratosgov', stdout=StringIO())
        self.assertFalse(ContratoCatalogo.objects.exists())
