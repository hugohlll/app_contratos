
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User, Group
from contratos.models import PostoGraduacao, Agente, Empresa, Contrato, Comissao, Integrante, Funcao
from datetime import date, timedelta
import random

class Command(BaseCommand):
    help = 'Popula o banco de dados com dados de teste MASSIVOS'

    def handle(self, *args, **kwargs):
        self.stdout.write(self.style.WARNING('Iniciando carga de dados MASSIVA...'))

        # 1. CRIAR GRUPOS
        group_admin, _ = Group.objects.get_or_create(name='Administradores')
        group_auditor, _ = Group.objects.get_or_create(name='Auditores')
        self.stdout.write('Grupos criados.')

        # 2. CRIAR USUÁRIOS
        if not User.objects.filter(username='admin').exists():
            User.objects.create_superuser('admin', 'admin@example.com', 'admin')
            self.stdout.write('Superuser admin/admin criado.')

        user_gestor, created = User.objects.get_or_create(username='gestor')
        if created:
            user_gestor.set_password('senha123')
            user_gestor.save()
            user_gestor.groups.add(group_admin)
            self.stdout.write('Usuário gestor/senha123 criado.')

        user_auditor, created = User.objects.get_or_create(username='auditor')
        if created:
            user_auditor.set_password('senha123')
            user_auditor.save()
            user_auditor.groups.add(group_auditor)
            self.stdout.write('Usuário auditor/senha123 criado.')

        # 3. CRIAR POSTOS
        postos = [
            ('Cel', 'Coronel', 1), ('Ten Cel', 'Tenente-Coronel', 2), ('Maj', 'Major', 3),
            ('Cap', 'Capitão', 4), ('1º Ten', 'Primeiro Tenente', 5), ('2º Ten', 'Segundo Tenente', 6),
            ('Asp', 'Aspirante', 7), ('SO', 'Suboficial', 8), ('1S', 'Primeiro Sargento', 9),
            ('2S', 'Segundo Sargento', 10), ('3S', 'Terceiro Sargento', 11), ('Cb', 'Cabo', 12),
            ('S1', 'Soldado de 1ª Classe', 13), ('S2', 'Soldado de 2ª Classe', 14),
        ]
        for sigla, desc, ordem in postos:
            PostoGraduacao.objects.get_or_create(sigla=sigla, defaults={'descricao': desc, 'senioridade': ordem})
        self.stdout.write('Postos criados.')

        # 4. CRIAR AGENTES (200 agentes)
        nomes = ['Silva', 'Santos', 'Oliveira', 'Souza', 'Lima', 'Pereira', 'Ferreira', 'Costa', 'Almeida', 'Nascimento', 'Alves', 'Carvalho', 'Rodrigues', 'Ribeiro', 'Mendes', 'Barbosa']
        nomes_meio = ['Carlos', 'Marcos', 'Ricardo', 'Ana', 'Pedro', 'João', 'Lucas', 'Mariana', 'Fernanda', 'Gabriel', 'Larissa', 'Rafael', 'Amanda', 'Patricia', 'Bruno', 'Juliana']
        
        postos_objs = list(PostoGraduacao.objects.all())
        
        count_agentes = 0
        for i in range(200):
            saram = f"{random.randint(1000000, 9999999)}"
            if not Agente.objects.filter(saram=saram).exists():
                posto = random.choice(postos_objs)
                sobrenome = random.choice(nomes)
                nome_completo = f"{random.choice(nomes_meio)} {sobrenome}"
                
                # Variar data do curso para ter alguns vencidos
                dias_curso = random.randint(10, 800) # Se > 365, está vencido
                
                Agente.objects.create(
                    nome_completo=nome_completo,
                    nome_de_guerra=sobrenome,
                    posto=posto,
                    cpf=f"{random.randint(100,999)}.{random.randint(100,999)}.{random.randint(100,999)}-{random.randint(10,99)}",
                    data_ultimo_curso=date.today() - timedelta(days=dias_curso),
                    saram=saram
                )
                count_agentes += 1
        self.stdout.write(f'{count_agentes} Agentes gerados.')

        # 5. CRIAR FUNÇÕES
        funcoes = ['Presidente', 'Membro', 'Secretário', 'Gestor', 'Fiscal Administrativo', 'Fiscal Técnico', 'Fiscal Setorial']
        for func in funcoes:
            Funcao.objects.get_or_create(titulo=func, defaults={'sigla': func[:3].upper()})
        self.stdout.write('Funções criadas.')

        # 6. CRIAR EMPRESAS (50 empresas)
        tipos_empresa = ['Tech', 'Soluções', 'Construtora', 'Serviços', 'Comércio', 'Indústria', 'Logística', 'Consultoria', 'Engenharia', 'Alimentos']
        sufixos = ['Ltda', 'SA', 'Eireli', 'ME', 'EPP']
        
        count_emp = 0
        for i in range(50):
            cnpj = f"{random.randint(10,99)}.{random.randint(100,999)}.{random.randint(100,999)}/0001-{random.randint(10,99)}"
            if not Empresa.objects.filter(cnpj=cnpj).exists():
                razao = f"{random.choice(tipos_empresa)} {random.choice(nomes)} {random.choice(sufixos)}"
                Empresa.objects.create(razao_social=razao, cnpj=cnpj)
                count_emp += 1
        self.stdout.write(f'{count_emp} Empresas geradas.')

        # 7. CRIAR CONTRATOS (200 contratos)
        empresas = list(Empresa.objects.all())
        objetos = [
            'Serviços de Tecnologia da Informação', 'Aquisição de Material de Escritório', 
            'Reforma de Instalações Prediais', 'Manutenção de Viaturas', 'Fornecimento de Alimentação', 
            'Serviços de Limpeza e Conservação', 'Segurança Patrimonial Armada', 'Locação de Equipamentos', 
            'Consultoria Especializada em Engenharia', 'Aquisição de Licenças de Software',
            'Serviços de Jardinagem', 'Manutenção de Ar Condicionado', 'Fornecimento de Combustível'
        ]
        
        count_contr = 0
        for i in range(1, 201):
            num = f"{str(i).zfill(3)}/{date.today().year}"
            
            # 80% Despesa, 20% Receita
            tipo_contrato = 'DESPESA' if random.random() < 0.8 else 'RECEITA'

            if not Contrato.objects.filter(numero=num).exists():
                emp = random.choice(empresas)
                val = random.uniform(5000.0, 10000000.0)
                
                # Alguns contratos já encerrados, outros vigentes, outros futuros
                cenario = random.choice(['passado', 'vigente', 'vigente', 'vigente', 'futuro'])
                
                duracao = random.randint(180, 1460) # 6 meses a 4 anos
                
                if cenario == 'passado':
                    inicio = date.today() - timedelta(days=duracao + random.randint(50, 300))
                elif cenario == 'futuro':
                    inicio = date.today() + timedelta(days=random.randint(10, 60))
                else: # vigente
                    inicio = date.today() - timedelta(days=random.randint(10, duracao-10))
                
                fim = inicio + timedelta(days=duracao)

                Contrato.objects.create(
                    numero=num,
                    tipo=tipo_contrato,
                    empresa=emp,
                    objeto=random.choice(objetos),
                    vigencia_inicio=inicio,
                    vigencia_fim=fim,
                    valor_total=val
                )
                count_contr += 1
        self.stdout.write(f'{count_contr} Contratos gerados.')

        # 8. CRIAR COMISSÕES
        agentes = list(Agente.objects.all())
        funcao_gestor = Funcao.objects.get(titulo='Gestor')
        funcao_fiscal = Funcao.objects.get(titulo='Fiscal Técnico')
        funcao_presidente = Funcao.objects.get(titulo='Presidente')
        funcao_membro = Funcao.objects.get(titulo='Membro')
        
        count_comiss = 0
        for contrato in Contrato.objects.all():
            # Fiscalização (Padrão para todos)
            comissao_fisc = contrato.comissoes.filter(tipo='FISCALIZACAO').first()
            if comissao_fisc:
                portaria = f"{random.randint(100, 999)}/GC"
                dt_port = contrato.vigencia_inicio
                boletim = f"{random.randint(1, 52)}/{dt_port.year}"
                
                comissao_fisc.portaria_numero = portaria
                comissao_fisc.portaria_data = dt_port
                comissao_fisc.boletim_numero = boletim
                comissao_fisc.boletim_data = dt_port + timedelta(days=2)
                comissao_fisc.data_inicio = dt_port
                comissao_fisc.data_fim = contrato.vigencia_fim
                comissao_fisc.ativa = True
                comissao_fisc.save()

                # Adicionar membros aleatórios
                # Tentar não repetir o mesmo agente na comissão
                possiveis = random.sample(agentes, k=2)
                
                if not comissao_fisc.integrantes.exists():
                    Integrante.objects.create(comissao=comissao_fisc, agente=possiveis[0], funcao=funcao_gestor, data_inicio=dt_port, portaria_numero=portaria, portaria_data=dt_port)
                    Integrante.objects.create(comissao=comissao_fisc, agente=possiveis[1], funcao=funcao_fiscal, data_inicio=dt_port, portaria_numero=portaria, portaria_data=dt_port)
                    count_comiss += 1

            # Recebimento (Apenas se TIPO != RECEITA) e com 60% de chance
            if contrato.tipo != 'RECEITA' and random.random() > 0.4:
                comissao_rec, created = Comissao.objects.get_or_create(
                    contrato=contrato, tipo='RECEBIMENTO',
                    defaults={
                        'ativa': True,
                        'data_inicio': contrato.vigencia_inicio,
                        'data_fim': contrato.vigencia_fim
                    }
                )
                if created:
                    portaria = f"{random.randint(100, 999)}/GC"
                    dt_port = contrato.vigencia_inicio
                    
                    comissao_rec.portaria_numero = portaria
                    comissao_rec.portaria_data = dt_port
                    comissao_rec.boletim_numero = f"{random.randint(1,52)}/{dt_port.year}"
                    comissao_rec.boletim_data = dt_port + timedelta(days=2)
                    comissao_rec.save()

                    possiveis = random.sample(agentes, k=3)
                    Integrante.objects.create(comissao=comissao_rec, agente=possiveis[0], funcao=funcao_presidente, data_inicio=dt_port, portaria_numero=portaria, portaria_data=dt_port)
                    Integrante.objects.create(comissao=comissao_rec, agente=possiveis[1], funcao=funcao_membro, data_inicio=dt_port, portaria_numero=portaria, portaria_data=dt_port)
                    Integrante.objects.create(comissao=comissao_rec, agente=possiveis[2], funcao=funcao_membro, data_inicio=dt_port, portaria_numero=portaria, portaria_data=dt_port)
                    count_comiss += 1
        
        self.stdout.write(self.style.SUCCESS('Base de testes MASSIVA criada com sucesso!'))
