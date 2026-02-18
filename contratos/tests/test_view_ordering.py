from django.test import TestCase, Client
from django.urls import reverse
from datetime import date
from contratos.models import Contrato, Empresa, Comissao, Integrante, Agente, Funcao, PostoGraduacao

class ContractDetailOrderingTest(TestCase):
    def setUp(self):
        self.client = Client()
        
        # Setup basic data
        self.empresa = Empresa.objects.create(razao_social="Empresa Teste", cnpj="00.000.000/0000-00")
        self.contrato = Contrato.objects.create(
            numero="001/2024",
            tipo="DESPESA",
            empresa=self.empresa,
            objeto="Teste",
            vigencia_inicio=date(2024, 1, 1),
            vigencia_fim=date(2024, 12, 31),
            valor_total=1000.00
        )
        # Contrato.save() creates a default FISCALIZACAO commission. Use it.
        self.comissao_fisc = self.contrato.comissoes.filter(tipo='FISCALIZACAO').first()
        self.comissao_fisc.data_inicio = date(2024, 1, 1)
        self.comissao_fisc.data_fim = date(2024, 12, 31)
        self.comissao_fisc.save()

        self.comissao_rec = Comissao.objects.create(
            contrato=self.contrato,
            tipo='RECEBIMENTO',
            ativa=True,
            data_inicio=date(2024, 1, 1),
            data_fim=date(2024, 12, 31)
        )
        
        self.posto = PostoGraduacao.objects.create(sigla="Cb", descricao="Cabo", senioridade=1)
        self.agente = Agente.objects.create(
            nome_completo="Agente Teste",
            nome_de_guerra="Teste",
            posto=self.posto,
            saram="1234567"
        )
        
        # Define Functions
        self.f_fiscal = Funcao.objects.create(titulo="Fiscal", ordem=0)
        self.f_fiscal_sub = Funcao.objects.create(titulo="Fiscal Substituto", ordem=0)
        self.f_fiscal_adm = Funcao.objects.create(titulo="Fiscal Administrativo", ordem=0)
        self.f_fiscal_tec = Funcao.objects.create(titulo="Fiscal Técnico", ordem=0)
        self.f_membro = Funcao.objects.create(titulo="Membro", ordem=0)
        
        self.f_presidente = Funcao.objects.create(titulo="Presidente", ordem=0)
        self.f_pres_sub = Funcao.objects.create(titulo="Presidente Substituto", ordem=0)

    def create_integrante(self, comissao, funcao, **kwargs):
        defaults = {
            'comissao': comissao,
            'funcao': funcao,
            'agente': self.agente,
            'data_inicio': date(2024, 1, 1),
            'portaria_numero': '123/2024',
            'portaria_data': date(2024, 1, 1)
        }
        defaults.update(kwargs)
        return Integrante.objects.create(**defaults)

    def test_fiscalizacao_ordering(self):
        # Define local variables for clarity, mapping to self.agente and self.f_... objects
        a1 = self.agente
        a2 = self.agente
        a3 = self.agente
        a4 = self.agente
        a5 = self.agente

        funcao_fiscal = self.f_fiscal
        funcao_substituto = self.f_fiscal_sub
        funcao_admin = self.f_fiscal_adm
        funcao_tecnico = self.f_fiscal_tec
        funcao_membro = self.f_membro

        # Insert in random/reverse order to test sorting
        self.comissao_fisc.integrantes.create(agente=a1, funcao=funcao_fiscal, data_inicio=date(2024, 1, 1), ordem=2, portaria_data=date(2024, 1, 1), portaria_numero='1')
        self.comissao_fisc.integrantes.create(agente=a2, funcao=funcao_substituto, data_inicio=date(2024, 1, 1), ordem=1, portaria_data=date(2024, 1, 1), portaria_numero='1')
        self.comissao_fisc.integrantes.create(agente=a3, funcao=funcao_admin, data_inicio=date(2024, 1, 1), ordem=3, portaria_data=date(2024, 1, 1), portaria_numero='1')
        self.comissao_fisc.integrantes.create(agente=a4, funcao=funcao_tecnico, data_inicio=date(2024, 1, 1), ordem=5, portaria_data=date(2024, 1, 1), portaria_numero='1')
        self.comissao_fisc.integrantes.create(agente=a5, funcao=funcao_membro, data_inicio=date(2024, 1, 1), ordem=4, portaria_data=date(2024, 1, 1), portaria_numero='1')

        url = reverse('detalhe_contrato', args=[self.contrato.id])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        
        # Check Fiscalização List - Deve respeitar a ordem manual
        comissao = response.context['comissoes_fiscalizacao'][0]
        integrantes = comissao.integrantes_lista
        
        titulos = [i.funcao.titulo for i in integrantes]
        # Ordem esperada baseada nos campos .ordem setados acima (1, 2, 3, 4, 5)
        esperado = [
            "Fiscal Substituto",   # ordem=1
            "Fiscal",              # ordem=2
            "Fiscal Administrativo", # ordem=3
            "Membro",              # ordem=4
            "Fiscal Técnico"       # ordem=5
        ]
        
        self.assertEqual(titulos, esperado)

    def test_recebimento_ordering(self):
        # Insert in reverse order
        self.create_integrante(self.comissao_rec, self.f_membro) # 3
        self.create_integrante(self.comissao_rec, self.f_pres_sub) # 2
        self.create_integrante(self.comissao_rec, self.f_presidente) # 1
        
        url = reverse('detalhe_contrato', args=[self.contrato.id])
        response = self.client.get(url)
        
        comissao = response.context['comissoes_recebimento'][0]
        integrantes = comissao.integrantes_lista
        
        titulos = [i.funcao.titulo for i in integrantes]
        # Ordem de inserção (auto-incremento): Membro(1), Pres Sub(2), Presidente(3)
        esperado = [
            "Membro",
            "Presidente Substituto",
            "Presidente"
        ]
        
        self.assertEqual(titulos, esperado)
