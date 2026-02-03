from django.core.management.base import BaseCommand
from django.contrib.auth.models import User, Group
from contratos.models import PostoGraduacao, Agente, Empresa, Contrato, Comissao, Integrante, Funcao
from datetime import date, timedelta

class Command(BaseCommand):
    help = 'Popula o banco de dados com dados de teste'

    def handle(self, *args, **kwargs):
        self.stdout.write(self.style.WARNING('Iniciando carga de dados...'))

        # 1. CRIAR GRUPOS
        group_admin, _ = Group.objects.get_or_create(name='Administradores')
        group_auditor, _ = Group.objects.get_or_create(name='Auditores')
        self.stdout.write('Grupos criados.')

        # 2. CRIAR USUÁRIOS
        # Superuser
        if not User.objects.filter(username='admin').exists():
            User.objects.create_superuser('admin', 'admin@example.com', 'admin')
            self.stdout.write('Superuser admin/admin criado.')

        # Gestor (Admin)
        user_gestor, created = User.objects.get_or_create(username='gestor')
        if created:
            user_gestor.set_password('senha123')
            user_gestor.save()
            user_gestor.groups.add(group_admin)
            self.stdout.write('Usuário gestor/senha123 criado (Grupo Administradores).')

        # Auditor
        user_auditor, created = User.objects.get_or_create(username='auditor')
        if created:
            user_auditor.set_password('senha123')
            user_auditor.save()
            user_auditor.groups.add(group_auditor)
            self.stdout.write('Usuário auditor/senha123 criado (Grupo Auditores).')

        # 3. CRIAR POSTOS/GRADUAÇÕES
        postos = [
            ('Cel', 'Coronel', 1),
            ('Ten Cel', 'Tenente-Coronel', 2),
            ('Maj', 'Major', 3),
            ('Cap', 'Capitão', 4),
            ('1º Ten', 'Primeiro Tenente', 5),
            ('2º Ten', 'Segundo Tenente', 6),
            ('Asp', 'Aspirante', 7),
            ('SO', 'Suboficial', 8),
            ('1S', 'Primeiro Sargento', 9),
            ('2S', 'Segundo Sargento', 10),
            ('3S', 'Terceiro Sargento', 11),
            ('Cb', 'Cabo', 12),
            ('S1', 'Soldado de Primeira Classe', 13),
            ('S2', 'Soldado de Segunda Classe', 14),
        ]
        
        for sigla, desc, ordem in postos:
            PostoGraduacao.objects.get_or_create(sigla=sigla, defaults={'descricao': desc, 'senioridade': ordem})
        self.stdout.write('Postos e Graduações criados.')

        # 4. CRIAR AGENTES (MILITARES)
        import random
        
        nomes = ['Silva', 'Santos', 'Oliveira', 'Souza', 'Lima', 'Pereira', 'Ferreira', 'Costa', 'Almeida', 'Nascimento', 'Alves', 'Carvalho', 'Rodrigues', 'Ribeiro']
        nomes_meio = ['Carlos', 'Marcos', 'Ricardo', 'Ana', 'Pedro', 'João', 'Lucas', 'Mariana', 'Fernanda', 'Gabriel', 'Larissa', 'Rafael', 'Amanda', 'Patricia']
        
        postos_objs = list(PostoGraduacao.objects.all())
        
        # Gerar 50 agentes
        for i in range(50):
            posto = random.choice(postos_objs)
            sobrenome = random.choice(nomes)
            nome_guerra = sobrenome
            nome_completo = f"{random.choice(nomes_meio)} {sobrenome}"
            saram = f"{random.randint(1000000, 9999999)}"
            
            if not Agente.objects.filter(saram=saram).exists():
                Agente.objects.create(
                    nome_completo=nome_completo,
                    nome_de_guerra=nome_guerra,
                    posto=posto,
                    cpf=f"{random.randint(100,999)}.{random.randint(100,999)}.{random.randint(100,999)}-{random.randint(10,99)}",
                    data_ultimo_curso=date.today() - timedelta(days=random.randint(10, 500)),
                    saram=saram
                )
        self.stdout.write('Agentes gerados.')

        # 5. CRIAR FUNÇÕES
        funcoes = ['Presidente', 'Membro', 'Secretário', 'Gestor', 'Fiscal Administrativo', 'Fiscal Técnico', 'Fiscal Setorial']
        for func in funcoes:
            Funcao.objects.get_or_create(titulo=func, defaults={'sigla': func[:3].upper()})
        self.stdout.write('Funções criadas.')

        # 6. CRIAR EMPRESAS
        tipos_empresa = ['Tech', 'Soluções', 'Construtora', 'Serviços', 'Comércio', 'Indústria', 'Logística', 'Consultoria']
        sufixos = ['Ltda', 'SA', 'Eireli', 'ME', 'EPP']
        
        # Gerar 20 empresas
        for i in range(20):
            razao = f"{random.choice(tipos_empresa)} {random.choice(nomes)} {random.choice(sufixos)}"
            cnpj = f"{random.randint(10,99)}.{random.randint(100,999)}.{random.randint(100,999)}/0001-{random.randint(10,99)}"
            
            if not Empresa.objects.filter(cnpj=cnpj).exists():
                Empresa.objects.create(razao_social=razao, cnpj=cnpj)
        
        self.stdout.write('Empresas geradas.')

        # 7. CRIAR CONTRATOS
        empresas = list(Empresa.objects.all())
        objetos = [
            'Serviços de Tecnologia da Informação', 'Aquisição de Material de Escritório', 
            'Reforma do Pavilhão A', 'Manutenção de Viaturas', 'Fornecimento de Alimentação', 
            'Serviços de Limpeza', 'Segurança Patrimonial', 'Locação de Equipamentos', 
            'Consultoria em Engenharia', 'Aquisição de Licenças de Software'
        ]
        
        # Gerar 50 contratos
        for i in range(1, 51):
            num = f"{str(i).zfill(3)}/{date.today().year}"
            emp = random.choice(empresas)
            obj = random.choice(objetos)
            val = random.uniform(10000.0, 5000000.0)
            
            days_duration = random.randint(90, 720) # 3 months to 2 years
            days_offset_end = random.randint(-100, 400) # Ends between 100 days ago and 400 days in future
            
            dt_fim = date.today() + timedelta(days=days_offset_end)
            dt_inicio = dt_fim - timedelta(days=days_duration)

            if not Contrato.objects.filter(numero=num).exists():
                Contrato.objects.create(
                    numero=num,
                    empresa=emp,
                    objeto=obj,
                    vigencia_inicio=dt_inicio,
                    vigencia_fim=dt_fim,
                    valor_total=val
                )
        self.stdout.write('Contratos gerados.')

        # 8. CRIAR COMISSÕES E DESIGNAÇÕES
        agentes = list(Agente.objects.all())
        funcao_gestor = Funcao.objects.get(titulo='Gestor')
        funcao_fiscal = Funcao.objects.get(titulo='Fiscal Técnico')
        funcao_presidente = Funcao.objects.get(titulo='Presidente')
        funcao_membro = Funcao.objects.get(titulo='Membro')
        
        for contrato in Contrato.objects.all():
            # Fiscalização
            comissao_fisc = contrato.comissoes.filter(tipo='FISCALIZACAO').first()
            if comissao_fisc:
                portaria = f"{random.randint(100, 999)}/GC"
                dt_port = contrato.vigencia_inicio + timedelta(days=5) # Portaria 5 days after contract start
                
                # Boletim info
                boletim = f"{random.randint(1, 52)}/{dt_port.year}"
                dt_bol = dt_port + timedelta(days=random.randint(1, 5)) # Published 1-5 days after portaria

                comissao_fisc.portaria_numero = portaria
                comissao_fisc.portaria_data = dt_port
                comissao_fisc.boletim_numero = boletim
                comissao_fisc.boletim_data = dt_bol
                comissao_fisc.data_inicio = dt_port
                comissao_fisc.data_fim = contrato.vigencia_fim
                comissao_fisc.ativa = True
                comissao_fisc.save()

                # Gestor e Fiscal
                for func in [funcao_gestor, funcao_fiscal]:
                    if not comissao_fisc.integrantes.filter(funcao=func).exists():
                        Integrante.objects.create(
                            comissao=comissao_fisc,
                            agente=random.choice(agentes),
                            funcao=func,
                            data_inicio=dt_port,
                            data_fim=contrato.vigencia_fim, # Set member end date too
                            portaria_numero=portaria,
                            portaria_data=dt_port,
                            boletim_numero=boletim,
                            boletim_data=dt_bol
                        )

            # Recebimento (Criar aleatoriamente para 50% dos contratos)
            if random.random() > 0.5:
                dt_port_rec = contrato.vigencia_inicio + timedelta(days=10)
                portaria_rec = f"{random.randint(100, 999)}/GC"
                boletim_rec = f"{random.randint(1, 52)}/{dt_port_rec.year}"
                dt_bol_rec = dt_port_rec + timedelta(days=random.randint(1, 5))

                # Check if model allows multiple or how it works. Assuming we can create one.
                comissao_rec, created = Comissao.objects.get_or_create(
                    contrato=contrato, 
                    tipo='RECEBIMENTO',
                    defaults={
                        'data_inicio': dt_port_rec,
                        'data_fim': contrato.vigencia_fim,
                        'ativa': True,
                        'portaria_numero': portaria_rec,
                        'portaria_data': dt_port_rec,
                        'boletim_numero': boletim_rec,
                        'boletim_data': dt_bol_rec
                    }
                )
                
                if not created:
                   comissao_rec.portaria_numero = portaria_rec
                   comissao_rec.portaria_data = dt_port_rec
                   comissao_rec.boletim_numero = boletim_rec
                   comissao_rec.boletim_data = dt_bol_rec
                   comissao_rec.data_inicio = dt_port_rec
                   comissao_rec.data_fim = contrato.vigencia_fim
                   comissao_rec.save()

                # Presidente e 2 Membros
                for func in [funcao_presidente, funcao_membro, funcao_membro]:
                     Integrante.objects.create(
                        comissao=comissao_rec, 
                        agente=random.choice(agentes), 
                        funcao=func, 
                        data_inicio=dt_port_rec, 
                        data_fim=contrato.vigencia_fim,
                        portaria_numero=portaria_rec, 
                        portaria_data=dt_port_rec,
                        boletim_numero=boletim_rec,
                        boletim_data=dt_bol_rec
                    )

        self.stdout.write(self.style.SUCCESS('Carga de dados MASSIVA concluída com sucesso!'))
