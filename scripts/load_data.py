import os
import sys
import django
import csv

# Configura o ambiente Django para permitir acesso aos models sem o comando runserver
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from contratos.models import Agente, Empresa, PostoGraduacao

def carregar_agentes(caminho_csv):
    """Lê o CSV de agentes e cadastra no banco de dados"""
    print(f"\n--- Iniciando carga de Agentes a partir de: {caminho_csv} ---")
    
    agentes_criados = 0
    agentes_atualizados = 0
    erros = 0
    
    with open(caminho_csv, mode='r', encoding='utf-8') as arquivo:
        leitor = csv.DictReader(arquivo)
        for linha in leitor:
            try:
                saram = linha.get('SARAM', '').strip()
                if not saram:
                    continue # Pula linhas vazias
                
                sigla_posto = linha.get('Posto/Graduação', '').strip()
                nome_completo = linha.get('Nome Completo', '').strip()
                cpf = linha.get('CPF', '').strip()
                
                # Regra de Negócio: Garantir que o Posto/Graduação exista.
                # Como a lista real tem senioridade definida, se faltar algum, criamos com senioridade alta (menor prioridade).
                posto, created_posto = PostoGraduacao.objects.get_or_create(
                    sigla=sigla_posto,
                    defaults={'descricao': sigla_posto, 'senioridade': 99}
                )
                if created_posto:
                    print(f"Novo Posto/Graduação cadastrado automaticamente: {sigla_posto}")
                
                # Regra de Negócio: Nome de Guerra (provisório usando o último nome)
                partes_nome = nome_completo.split()
                nome_de_guerra = partes_nome[-1] if partes_nome else "N/I"
                if len(nome_de_guerra) > 50:
                    nome_de_guerra = nome_de_guerra[:50]
                
                # Criar ou atualizar o Agente baseando-se no SARAM (matrícula) única
                agente, created = Agente.objects.get_or_create(
                    saram=saram,
                    defaults={
                        'nome_completo': nome_completo[:150],
                        'nome_de_guerra': nome_de_guerra,
                        'posto': posto,
                        'cpf': cpf[:14]
                    }
                )
                
                if created:
                    agentes_criados += 1
                else:
                    # Atualiza dados se o agente já existir
                    agente.nome_completo = nome_completo[:150]
                    agente.cpf = cpf[:14]
                    agente.posto = posto
                    agente.save()
                    agentes_atualizados += 1
            except Exception as e:
                print(f"Erro ao processar linha SARAM '{linha.get('SARAM')}': {e}")
                erros += 1
                
    print(f"--- Concluído: {agentes_criados} criados, {agentes_atualizados} atualizados, {erros} erros. ---")

def carregar_empresas(caminho_csv):
    """Lê o CSV de empresas e cadastra no banco de dados"""
    print(f"\n--- Iniciando carga de Empresas a partir de: {caminho_csv} ---")
    
    empresas_criadas = 0
    empresas_atualizadas = 0
    erros = 0
    
    with open(caminho_csv, mode='r', encoding='utf-8') as arquivo:
        leitor = csv.DictReader(arquivo)
        for linha in leitor:
            try:
                razao_social = linha.get('EMPRESA', '').strip()
                cnpj = linha.get('CNPJ', '').strip()
                
                if not cnpj and not razao_social:
                    continue # Pula linhas totalmente vazias
                
                # O CNPJ é único no banco
                empresa, created = Empresa.objects.get_or_create(
                    cnpj=cnpj,
                    defaults={'razao_social': razao_social[:200]}
                )
                
                if created:
                    empresas_criadas += 1
                else:
                    # Atualiza a razão social caso a empresa já exista
                    empresa.razao_social = razao_social[:200]
                    empresa.save()
                    empresas_atualizadas += 1
            except Exception as e:
                print(f"Erro ao processar linha CNPJ '{linha.get('CNPJ')}': {e}")
                erros += 1
                
    print(f"--- Concluído: {empresas_criadas} criadas, {empresas_atualizadas} atualizadas, {erros} erros. ---")

if __name__ == '__main__':
    if len(sys.argv) < 3:
        print("Uso correto:")
        print("python load_data.py <caminho_arquivo_agentes.csv> <caminho_arquivo_empresas.csv>")
        sys.exit(1)
        
    arquivo_agentes = sys.argv[1]
    arquivo_empresas = sys.argv[2]
    
    if not os.path.exists(arquivo_agentes):
        print(f"ERRO: Arquivo de agentes não encontrado: {arquivo_agentes}")
        sys.exit(1)
        
    if not os.path.exists(arquivo_empresas):
        print(f"ERRO: Arquivo de empresas não encontrado: {arquivo_empresas}")
        sys.exit(1)
        
    carregar_agentes(arquivo_agentes)
    carregar_empresas(arquivo_empresas)
    print("\nSCRIPT FINALIZADO COM SUCESSO.")
