# 🛡️ SISCONT - Sistema de Gestão de Contratos Administrativos

Sistema web desenvolvido em Django para gerenciamento completo de contratos administrativos em organizações militares, com foco em transparência, controle e conformidade.

---

## 📋 Índice

- [Sobre o Projeto](#sobre-o-projeto)
- [Objetivo](#objetivo)
- [Funcionalidades](#funcionalidades)
- [Requisitos](#requisitos)
- [Instalação](#instalação)
- [Configuração Inicial](#configuração-inicial)
- [Manual do Usuário](#manual-do-usuário)
- [Estrutura do Projeto](#estrutura-do-projeto)
- [Tecnologias Utilizadas](#tecnologias-utilizadas)
- [Desenvolvimento](#desenvolvimento)
- [Suporte](#suporte)

---

## 🎯 Sobre o Projeto

O **SISCONT** é uma aplicação web desenvolvida especificamente para organizações militares gerenciarem seus contratos administrativos de forma eficiente, transparente e em conformidade com as regulamentações. O sistema permite o controle completo de:

- Contratos administrativos e suas vigências
- Comissões de fiscalização e recebimento
- Designações de militares para comissões
- Qualificação e treinamento dos agentes
- Histórico completo de atuações
- Monitoramento de vencimentos e riscos

---

## 🎯 Objetivo

Garantir **transparência**, **controle** e **conformidade** no gerenciamento de contratos administrativos, oferecendo:

✅ **Transparência Pública**: Acesso público a informações sobre contratos vigentes e equipes designadas  
✅ **Controle Interno**: Painel de auditoria com monitoramento de riscos e conformidade  
✅ **Gestão Eficiente**: Rastreamento completo de designações, qualificações e histórico  
✅ **Conformidade Regulatória**: Alertas automáticos para vencimentos, qualificações e rodízios  

---

## 🚀 Funcionalidades

### 🌐 **Área Pública** (Acesso Livre)

#### 1. **Pesquisa de Contratos**
- Busca por número do contrato, objeto ou empresa contratada
- Resultados instantâneos com informações essenciais
- Link direto para detalhes completos

#### 2. **Detalhes do Contrato**
- Informações completas do contrato (número, objeto, empresa, vigência, valor)
- Visualização de todas as comissões ativas (Fiscalização e Recebimento)
- Lista de integrantes ativos com suas funções
- Histórico de designações

#### 3. **Relatório de Transparência**
- Lista todos os contratos vigentes
- Exibe equipes de fiscalização e recebimento ativas
- Informações sobre designações e prazos
- Exportação em CSV para análise externa

---

### 👤 **Área do Militar** (Acesso Livre)

#### 1. **Consulta de Histórico Individual**
- Busca por SARAM, nome de guerra ou nome completo
- Visualização de todas as designações ativas do militar
- Informações sobre contratos, funções e prazos
- Status de cada designação

#### 2. **Exportação de Histórico**
- Geração de CSV com histórico completo de comissões
- Inclui todas as designações (ativas e encerradas)
- Dados sobre contratos, funções, datas e motivos de saída

---

### 🔐 **Área Restrita - Auditoria** (Requer Login)

#### 1. **Painel de Controle Visual**
Dashboard interativo com gráficos e indicadores:

- **📊 Métricas Principais**
  - Total de contratos vigentes
  - Militares designados ativos
  - Designações com prazo definido
  - Contratos em risco

- **🎓 Status de Qualificação**
  - Gráfico de distribuição (Em Dia / Vencido / Sem Curso)
  - Estatísticas detalhadas
  - Curso de gestão válido por 365 dias

- **📅 Monitoramento de Vencimentos**
  - Distribuição por status (Crítico ≤7 dias / Alerta 8-15 dias / Normal >15 dias)
  - Top 5 designações mais urgentes
  - Alertas visuais por criticidade

- **⏱️ Radar de Permanência**
  - Top 10 designações mais antigas
  - Cálculo de tempo contínuo (incluindo renovações)
  - Alertas para necessidade de rodízio (>1 ano)

- **⚖️ Sobrecarga de Agentes**
  - Identificação de militares com múltiplas designações simultâneas
  - Gráfico de distribuição de carga de trabalho

- **🚨 Contratos em Risco**
  - Lista de contratos sem equipe de fiscalização ativa
  - Alertas visuais para ação imediata

#### 2. **Relatórios e Exportações**

- **Auditoria Completa (CSV)**
  - Todos os contratos vigentes
  - Equipes ativas completas
  - Dados de designações e documentos

- **Monitoramento de Vencimentos (CSV)**
  - Lista completa de designações com prazo
  - Classificação por status
  - Dias restantes até vencimento

- **Relatório de Qualificação (CSV)**
  - Status de curso de gestão de cada agente
  - Datas de realização e validade
  - Situação (Em Dia / Vencido / Sem Curso)

- **Relatório por Período**
  - Consulta de designações em intervalo específico
  - Filtro por data inicial e final
  - Exportação em CSV

---

## 📦 Requisitos

### **Opção 1: Docker (Recomendado)**
- Docker 20.10+
- Docker Compose 2.0+

### **Opção 2: Instalação Manual**
- Python 3.11+
- PostgreSQL 15+
- pip (gerenciador de pacotes Python)

---

## 🛠️ Instalação

### **Método 1: Docker (Ambiente de Desenvolvimento)**

1. **Clone o repositório:**
```bash
git clone <url-do-repositorio>
cd app_contratos
```

2. **Inicie os containers:**
```bash
docker-compose up -d
```

3. **Execute as migrações:**
```bash
docker-compose exec web python manage.py migrate
```

4. **Crie um superusuário (para acessar o admin):**
```bash
docker-compose exec web python manage.py createsuperuser
```

5. **Acesse a aplicação:**
   - Aplicação: http://localhost:8000
   - Admin Django: http://localhost:8000/admin

---

### **🚀 Instalação em Produção**

Para implantar o sistema em um servidor real (Linux/Docker/Nginx), consulte os manuais dedicados:

- **[Manual de Instalação (TI)](MANUAL_INSTALACAO_TI.md)**: Guia completo para instalação no servidor da OM.
- **[Manual de Teste Local](MANUAL_TESTE_LOCAL.md)**: Guia para simular o ambiente de produção na sua máquina.

---

### **Método 2: Instalação Manual**

1. **Clone o repositório:**
```bash
git clone <url-do-repositorio>
cd app_contratos
```

2. **Crie um ambiente virtual:**
```bash
python3 -m venv venv
source venv/bin/activate  # Linux/Mac
# ou
venv\Scripts\activate  # Windows
```

3. **Instale as dependências:**
```bash
pip install -r requirements.txt
```

4. **Configure o banco de dados PostgreSQL:**
   - Crie um banco de dados
   - Configure as credenciais em `core/settings.py`

5. **Execute as migrações:**
```bash
python manage.py migrate
```

6. **Crie um superusuário:**
```bash
python manage.py createsuperuser
```

7. **Inicie o servidor:**
```bash
python manage.py runserver
```

8. **Acesse a aplicação:**
   - Aplicação: http://localhost:8000
   - Admin Django: http://localhost:8000/admin

---

## ⚙️ Configuração Inicial

### **1. Acesse o Admin Django**

Acesse http://localhost:8000/admin e faça login com o superusuário criado.

### **2. Cadastre os Dados Básicos**

#### **a) Postos e Graduações**
1. Vá em **Contratos > Postos e Graduações**
2. Clique em **Adicionar Posto/Graduação**
3. Preencha:
   - **Sigla**: Ex: "Cel", "Maj", "Cap"
   - **Descrição Completa**: Ex: "Coronel", "Major", "Capitão"
   - **Ordem de Antiguidade**: Número para ordenação (menor = mais antigo)

#### **b) Tipos de Função**
1. Vá em **Contratos > Tipos de Função**
2. Clique em **Adicionar Tipo de Função**
3. Preencha:
   - **Título da Função**: Ex: "Gestor do Contrato", "Fiscal", "Presidente da Comissão"
   - **Sigla**: Ex: "GEST", "FISC", "PRES"
   - **Ativa?**: Marque se a função está em uso

#### **c) Empresas**
1. Vá em **Contratos > Empresas**
2. Clique em **Adicionar Empresa**
3. Preencha:
   - **Razão Social**: Nome completo da empresa
   - **CNPJ**: Com formatação (XX.XXX.XXX/XXXX-XX)
   - **Contato/Email**: Opcional

#### **d) Agentes (Militares)**
1. Vá em **Contratos > Agentes**
2. Clique em **Adicionar Agente**
3. Preencha:
   - **Nome Completo**: Nome completo do militar
   - **Nome de Guerra**: Nome de guerra
   - **Posto Atual**: Selecione o posto
   - **SARAM/Matrícula**: Número único de identificação
   - **CPF**: Opcional
   - **Data do Último Curso de Gestão**: Data do último curso realizado (válido por 365 dias)

### **3. Cadastre os Contratos**

1. Vá em **Contratos > Contratos**
2. Clique em **Adicionar Contrato**
3. Preencha:
   - **Número do Contrato**: Ex: "CT 001/2024"
   - **Objeto do Contrato**: Descrição do objeto
   - **Empresa Contratada**: Selecione a empresa
   - **Início da Vigência**: Data de início
   - **Fim da Vigência**: Data de término
   - **Valor Total**: Valor do contrato

### **4. Crie as Comissões**

1. Vá em **Contratos > Comissões**
2. Clique em **Adicionar Comissão**
3. Preencha:
   - **Contrato**: Selecione o contrato
   - **Tipo**: 
     - **Fiscalização (Gestor/Fiscal)**: Para equipe de fiscalização
     - **Recebimento (Pres/Membros)**: Para comissão de recebimento
   - **Ativa?**: Marque se a comissão está ativa

### **5. Designe os Integrantes**

Ao criar ou editar uma Comissão, você pode adicionar integrantes diretamente na página da comissão:

1. Na seção **Integrantes**, clique em **Adicionar outro Integrante**
2. Preencha:
   - **Função**: Selecione a função do militar
   - **Militar**: Selecione o agente
   - **Início (Designação)**: Data de início da designação
   - **Término Previsto**: Data prevista de término (opcional)
   - **Nº Portaria**: Número da portaria de designação
   - **Data da Portaria**: Data da portaria
   - **Nº Boletim**: Número do boletim (opcional)
   - **Data do Boletim**: Data do boletim (opcional)
   - **Obs**: Observações (opcional)

**Nota**: O sistema automaticamente salva o posto do militar na época da designação, preservando o histórico mesmo se o militar for promovido.

### **6. Encerrar Designações**

Para encerrar uma designação antes do prazo:

1. Vá em **Contratos > Histórico de Integrantes**
2. Encontre o integrante e clique para editar
3. Na seção **Encerramento / Dispensa**, preencha:
   - **Data Efetiva de Saída**: Data real de saída
   - **Motivo da Saída**: Ex: "Término de prazo", "Dispensa", "Transferência"
   - **Doc. de Desligamento**: Número do documento (opcional)
   - **Obs**: Observações adicionais

---

## 📖 Manual do Usuário

### **🌐 Área Pública**

#### **Pesquisar Contratos**

1. Acesse a página inicial (http://localhost:8000)
2. Digite no campo de busca:
   - Número do contrato (ex: "001/2024")
   - Objeto do contrato (ex: "manutenção")
   - Nome da empresa (ex: "Empresa XYZ")
3. Clique em **Buscar** ou pressione Enter
4. Clique em um resultado para ver os detalhes

#### **Ver Detalhes do Contrato**

1. Na página de detalhes, você verá:
   - Informações do contrato (número, objeto, empresa, vigência, valor)
   - Comissões ativas (Fiscalização e Recebimento)
   - Integrantes ativos de cada comissão com suas funções

#### **Relatório de Transparência**

1. Acesse **Transparência** no menu
2. Visualize todos os contratos vigentes
3. Veja as equipes ativas de cada contrato
4. Clique em **Baixar CSV** para exportar os dados

---

### **👤 Área do Militar**

#### **Consultar Histórico Individual**

1. Acesse **Consulta Militar** no menu
2. Digite:
   - SARAM/Matrícula
   - Nome de guerra
   - Nome completo
3. Clique em **Buscar**
4. Visualize todas as designações ativas
5. Clique em **Exportar Histórico Completo** para baixar CSV

---

### **🔐 Área de Auditoria (Requer Login)**

#### **Acessar o Painel de Controle**

1. Acesse **Auditoria** no menu (ou http://localhost:8000/auditoria)
2. Se não estiver logado, será redirecionado para login
3. Após login, visualize o dashboard completo

#### **Interpretar os Gráficos**

**📊 Métricas Principais:**
- Cards no topo mostram números-chave do sistema
- Badges vermelhos indicam alertas (ex: designações críticas)

**🎓 Qualificação:**
- **Verde (Em Dia)**: Curso válido (menos de 1 ano)
- **Vermelho (Vencido)**: Curso realizado há mais de 1 ano
- **Cinza (Sem Curso)**: Nenhuma data cadastrada

**📅 Vencimentos:**
- **Vermelho (Crítico)**: ≤ 7 dias para vencer
- **Amarelo (Alerta)**: 8-15 dias para vencer
- **Verde (Normal)**: > 15 dias para vencer

**⏱️ Permanência:**
- **Verde**: Menos de 1 ano (normal)
- **Amarelo**: 1-2 anos (atenção para rodízio)
- **Vermelho**: Mais de 2 anos (rodízio necessário)

**⚖️ Sobrecarga:**
- Mostra militares com múltiplas designações simultâneas
- Quanto maior a barra, mais designações o militar possui

#### **Exportar Relatórios**

1. No painel, encontre a seção **📥 Relatórios e Exportações**
2. Escolha o tipo de relatório:
   - **Auditoria Completa**: Todos os dados
   - **Relatório por Período**: Filtrado por datas
   - **Vencimentos**: Apenas designações com prazo
   - **Qualificação**: Status de cursos dos agentes
3. Clique no botão de download
4. O arquivo CSV será baixado automaticamente

#### **Gerar Relatório por Período**

1. Acesse **Relatório por Período** no painel
2. Selecione:
   - **Data Inicial**: Início do período
   - **Data Final**: Fim do período
3. Clique em **Consultar**
4. Visualize os resultados
5. Clique em **Exportar CSV** para baixar

---

## 📁 Estrutura do Projeto

```
app_contratos/
│
├── contratos/              # Aplicação principal
│   ├── migrations/        # Migrações do banco de dados
│   ├── templates/         # Templates HTML
│   │   └── contratos/
│   │       ├── detalhe.html
│   │       ├── militar.html
│   │       ├── painel_controle.html
│   │       ├── pesquisa.html
│   │       ├── relatorio_periodo.html
│   │       └── relatorio_transparencia.html
│   ├── views/             # Views organizadas por módulo
│   │   ├── auditoria.py  # Painel de controle e relatórios
│   │   ├── auth.py       # Autenticação
│   │   ├── militar.py    # Consulta individual
│   │   └── public.py     # Área pública
│   ├── admin.py          # Configuração do admin Django
│   ├── models.py         # Modelos de dados
│   ├── urls.py           # Rotas da aplicação
│   └── utils.py          # Funções auxiliares
│
├── core/                  # Configurações do projeto
│   ├── settings.py       # Configurações Django
│   ├── urls.py           # URLs principais
│   ├── wsgi.py           # WSGI config
│   └── asgi.py           # ASGI config
│
├── docker-compose.yml     # Configuração Docker Compose
├── Dockerfile            # Imagem Docker
├── manage.py             # Script de gerenciamento Django
└── README.md             # Este arquivo
```

---

## 🛠️ Tecnologias Utilizadas

- **Backend:**
  - Django 5.2.10
  - Python 3.11
  - PostgreSQL 15

- **Frontend:**
  - Bootstrap 5.3.0
  - Chart.js 4.4.0
  - HTML5/CSS3/JavaScript

- **Infraestrutura:**
  - Docker & Docker Compose
  - PostgreSQL

---

## 💻 Desenvolvimento

### **Estrutura de Branches**

- `master`: Versão estável em produção
- `feature/*`: Novas funcionalidades em desenvolvimento

### **Executar em Modo Desenvolvimento**

```bash
# Com Docker
docker-compose up

# Manual
python manage.py runserver
```

### **Criar Migrações**

```bash
python manage.py makemigrations
python manage.py migrate
```

### **Acessar o Shell do Django**

```bash
docker-compose exec web python manage.py shell
# ou
python manage.py shell
```

### **Criar Dados de Teste**

Use o admin Django para criar dados de exemplo ou crie fixtures:

```bash
python manage.py dumpdata contratos > fixtures/initial_data.json
python manage.py loaddata fixtures/initial_data.json
```

---

## 🔒 Segurança

### **Configurações Importantes para Produção**

1. **Altere o SECRET_KEY** em `core/settings.py`
2. **Desative DEBUG**: `DEBUG = False`
3. **Configure ALLOWED_HOSTS**: Adicione seu domínio
4. **Use variáveis de ambiente** para credenciais sensíveis
5. **Configure HTTPS** no servidor web (Nginx/Apache)
6. **Use um banco de dados seguro** com senhas fortes

### **Exemplo de Configuração com Variáveis de Ambiente**

```python
# core/settings.py
import os

SECRET_KEY = os.environ.get('SECRET_KEY', 'sua-chave-secreta')
DEBUG = os.environ.get('DEBUG', 'False') == 'True'
ALLOWED_HOSTS = os.environ.get('ALLOWED_HOSTS', '').split(',')

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.environ.get('DB_NAME'),
        'USER': os.environ.get('DB_USER'),
        'PASSWORD': os.environ.get('DB_PASSWORD'),
        'HOST': os.environ.get('DB_HOST', 'localhost'),
        'PORT': os.environ.get('DB_PORT', '5432'),
    }
}
```

---

## 📊 Modelos de Dados

### **Principais Entidades**

1. **PostoGraduacao**: Hierarquia militar
2. **Agente**: Militares cadastrados
3. **Empresa**: Empresas contratadas
4. **Contrato**: Contratos administrativos
5. **Comissao**: Comissões de fiscalização/recebimento
6. **Funcao**: Tipos de função nas comissões
7. **Integrante**: Histórico de designações

### **Relacionamentos**

- Um **Contrato** pode ter várias **Comissões**
- Uma **Comissão** pode ter vários **Integrantes**
- Um **Integrante** pertence a um **Agente**, uma **Função** e uma **Comissão**
- Um **Agente** tem um **Posto** atual e histórico de **Postos** nas designações

---

## 🐛 Solução de Problemas

### **Erro de Conexão com Banco de Dados**

```bash
# Verifique se o PostgreSQL está rodando
docker-compose ps

# Verifique os logs
docker-compose logs db

# Recrie o banco
docker-compose down -v
docker-compose up -d
```

### **Erro de Migrações**

```bash
# Resete as migrações (CUIDADO: apaga dados)
python manage.py migrate --run-syncdb

# Ou recrie do zero
python manage.py makemigrations
python manage.py migrate
```

### **Problemas com Static Files**

```bash
# Colete arquivos estáticos
python manage.py collectstatic
```

---

## 📞 Suporte

Para dúvidas, problemas ou sugestões:

1. **Documentação Django**: https://docs.djangoproject.com/
2. **Issues no GitHub**: Abra uma issue descrevendo o problema
3. **Logs da Aplicação**: Verifique `docker-compose logs web`

---

## 📝 Licença

[Especifique a licença do projeto aqui]

---

## 👥 Contribuindo

Contribuições são bem-vindas! Para contribuir:

1. Faça um fork do projeto
2. Crie uma branch para sua feature (`git checkout -b feature/MinhaFeature`)
3. Commit suas mudanças (`git commit -m 'Adiciona MinhaFeature'`)
4. Push para a branch (`git push origin feature/MinhaFeature`)
5. Abra um Pull Request

---

## 📅 Changelog

### **Versão 1.0.0**
- ✅ Área pública de pesquisa e transparência
- ✅ Área do militar para consulta individual
- ✅ Painel de auditoria com gráficos interativos
- ✅ Exportações em CSV
- ✅ Sistema completo de gestão de contratos

### **Versão 1.1.0 (Beta)**
- ✨ **UX/UI Aprimorado**:
    - Ordenação hierárquica de membros (Gestor > Fiscal, Presidente > Membro)
    - Simplificação visual de tipos de comissão
    - Formatação de valores monetários (R$) e datas (pt-br)
- 🛡️ **Validação Robusta**:
    - Sincronização visual de erros cliente/servidor
    - Validação estrita de datas de comissão (impedir datas passadas para ativos)
- 🔧 **Correções e Estabilidade**:
    - Varredura e correção de erros de renderização (tags quebradas)
    - Testes automatizados padronizados (20/20 passing)

---

**Desenvolvido por SO QSS SEL HUGO**
