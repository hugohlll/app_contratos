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
- Visualização exclusiva de comissões ativas (Fiscalização e Recebimento)
- Lista filtrada de integrantes vigentes e ativos com suas funções
- Histórico completo omitido na visão pública para focar na equipe atual

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
  - Curso de gestão válido por **5 anos (1.825 dias)**

- **📅 Monitoramento de Vencimentos de Comissões**
  - Distribuição por status (Crítico ≤7 dias / Alerta 8-15 dias / Normal >15 dias)
  - Top 5 comissões com prazo mais próximo de expirar
  - Usa `data_fim` da comissão ou, se ausente, `vigencia_fim` do contrato
  - Alertas visuais por criticidade

- **⏱️ Radar de Permanência**
  - Top 10 designações mais antigas
  - Cálculo de tempo contínuo (incluindo renovações)
  - Alertas para necessidade de rodízio (>1 ano)

- **📆 Velocímetro de Vigência de Contratos**
  - Distribuição de contratos por prazo de vencimento (≤90 dias / 90-120 dias / >120 dias)
  - Tabela completa de contratos com dias restantes e classificação de risco

- **⚖️ Sobrecarga de Fiscais**
  - Identificação de Fiscais com múltiplos contratos simultâneos
  - Gráfico com o top 10 fiscais mais sobrecarregados
  - Cálculo de média de contratos por fiscal como referência

- **🚨 Contratos em Risco**
  - Lista de contratos sem equipe de fiscalização ativa
  - Alertas visuais para ação imediata

#### 2. **Relatórios e Exportações**

- **Auditoria Completa (CSV)**
  - Todos os contratos vigentes
  - Equipes ativas completas
  - Dados de designações e documentos (portaria, boletim)

- **Monitoramento de Vencimentos de Comissões (CSV)**
  - Lista completa de comissões ativas com prazo de término
  - Classificação por status (Crítico / Alerta / Normal)
  - Dias restantes até vencimento da comissão

- **Vencimento de Contratos (CSV)**
  - Lista de contratos vigentes com prazo de vencimento
  - Classificação em Crítico (≤90 dias) / Alerta (91-120 dias) / Normal (>120 dias)

- **Radar de Permanência (CSV)**
  - Lista de designações ativas ordenadas por tempo de permanência
  - Calcula tempo contínuo (inclusive renovações)

- **Sobrecarga de Fiscais (CSV)**
  - Lista de Fiscais com o número de contratos que fiscalizam

- **Relatório de Qualificação (CSV)**
  - Status de curso de gestão de cada agente ativo
  - Datas de realização e validade (5 anos)
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
- Python 3.12+
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
docker compose up -d
```

3. **Execute as migrações:**
```bash
docker compose exec web python manage.py migrate
```

4. **Crie um superusuário (para acessar o admin):**
```bash
docker compose exec web python manage.py createsuperuser
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
   - **PAG**: Número do Processo Administrativo de Gestão (opcional)
   - **Tipo**: "Despesa" (padrão) ou "Receita"
   - **Objeto do Contrato**: Descrição do objeto
   - **Empresa Contratada**: Selecione a empresa
   - **Início da Vigência**: Data de início
   - **Fim da Vigência**: Data de término
   - **Valor Total**: Valor do contrato

### **4. Crie as Comissões**

Ao criar um contrato, uma comissão de Fiscalização é criada automaticamente. Para adicionar uma comissão de Recebimento:

1. Vá em **Contratos > Comissões**
2. Clique em **Adicionar Comissão**
3. Preencha:
   - **Contrato**: Selecione o contrato
   - **Tipo**: 
     - **Fiscalização**: Para equipe de fiscalização e gestão
     - **Recebimento**: Para comissão de recebimento de serviços
   - **Ativa?**: Marque se a comissão está ativa
   - **Nº Portaria da Comissão**: Número da portaria que institui a comissão (opcional)
   - **Data da Portaria**: Data da portaria da comissão (opcional)
   - **Nº Boletim**: Número do boletim de publicação (opcional)
   - **Data do Boletim**: Data do boletim (opcional)
   - **Início da Comissão**: Data de início da vigência da comissão (opcional; se omitido, usa vigência do contrato)
   - **Fim da Comissão**: Data de fim da vigência da comissão (opcional; se omitido, usa fim do contrato)

**Nota**: Comissões expiram automaticamente (status inativo) via script diário quando sua data fim é ultrapassada. Além disso, não podem possuir data final anterior à data inicial de qualquer de seus membros designados. Ao encurtar o prazo de uma comissão, todas as designações associadas têm seu prazo reduzido automaticamente.

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

**Nota**: O sistema salva automaticamente o posto do militar na época, preservando o histórico. Adicionalmente, o sistema garante que **a Data de Término de um integrante jamais ultrapasse a Data Fim da comissão**.

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
- **Verde (Em Dia)**: Curso válido (realizado há menos de 5 anos)
- **Vermelho (Vencido)**: Curso realizado há mais de 5 anos
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
├── .github/               # Workflows CI/CD
│   └── workflows/
│       └── ci.yml
├── contratos/              # Aplicação principal
│   ├── management/        # Comandos de gerenciamento
│   │   └── commands/
│   │       ├── populate_db.py
│   │       └── desativar_comissoes_expiradas.py
│   ├── migrations/        # Migrações do banco de dados
│   ├── templates/         # Templates HTML (incl. portal)
│   │   └── contratos/
│   │       ├── portal/    # Templates da área restrita
│   │       ├── detalhe.html
│   │       ├── militar.html
│   │       ├── painel_controle.html
│   │       └── ...
│   ├── templatetags/      # Custom template filters
│   ├── tests/             # Testes automatizados
│   ├── views/             # Views organizadas por módulo
│   │   ├── auditoria.py  # Painel de controle e relatórios
│   │   ├── auth.py       # Autenticação
│   │   ├── militar.py    # Consulta individual
│   │   ├── portal.py     # Portal administrativo
│   │   ├── public.py     # Área pública
│   │   └── users.py      # Gestão de usuários
│   ├── admin.py          # Configuração do admin Django
│   ├── apps.py           # Configuração do app
│   ├── forms.py          # Formulários Django
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
├── nginx/                 # Configuração do Nginx
│   └── nginx.conf
├── .env.prod.example      # Modelo de variáveis de ambiente
├── docker-compose.yml     # Configuração Docker (Dev/CI)
├── docker-compose.prod.yml# Configuração Docker Produção
├── Dockerfile            # Imagem Docker (Dev)
├── Dockerfile.prod       # Imagem Docker (Prod)
├── manage.py             # Script de gerenciamento Django
├── requirements.txt      # Dependências Python
├── ESTRUTURA_PROJETO.md  # Documentação da estrutura
├── MANUAL_INSTALACAO_TI.md # Manual de instalação (TI)
├── MANUAL_TESTE_LOCAL.md # Manual de teste local
└── README.md             # Este arquivo
```

---

## 🛠️ Tecnologias Utilizadas

- **Backend:**
  - Django 5.2.10
  - Python 3.12
  - PostgreSQL 15

- **Frontend:**
  - Bootstrap 5.3.0
  - Chart.js 4.4.0
  - HTML5/CSS3/JavaScript

- **Infraestrutura:**
  - Docker & Docker Compose
  - PostgreSQL
  - Nginx (Produção)
  - GitHub Actions (CI/CD)

---

## 💻 Desenvolvimento

### **Estrutura de Branches**

- `master`: Versão estável em produção
- `feature/*`: Novas funcionalidades em desenvolvimento

### **Executar em Modo Desenvolvimento**

```bash
# Com Docker
docker compose up

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
docker compose exec web python manage.py shell
# ou
python manage.py shell
```

### **Criar Dados de Teste**

O projeto inclui um comando personalizado para popular o banco de dados com dados de teste realistas:

```bash
# Via Docker
docker compose exec web python manage.py populate_db

# Manualmente
python manage.py populate_db
```

---

## 🔒 Segurança

### **Configurações Importantes para Produção**

1. **Configure o `.env.prod`** com variáveis de ambiente seguras (veja `.env.prod.example`)
2. **`SECRET_KEY`**: Use uma chave longa e aleatória (mín. 50 caracteres)
3. **`DEBUG=False`**: Nunca deixe `True` em produção
4. **`DJANGO_ALLOWED_HOSTS`**: Configure com o IP/domínio real do servidor
5. **Senhas do banco**: Use senhas fortes em `POSTGRES_PASSWORD`
6. **Configure HTTPS** no servidor web (Nginx/Apache)

> **Nota:** O `core/settings.py` já lê `SECRET_KEY` e `DEBUG` de variáveis de ambiente automaticamente. Não é necessário editar o código.

### **Exemplo de `.env.prod`**

```env
DEBUG=False
SECRET_KEY=sua-chave-muito-segura-e-longa-com-mais-de-50-caracteres
DJANGO_ALLOWED_HOSTS=10.0.0.5,portal.om.eb.mil.br

POSTGRES_USER=admin_siscont
POSTGRES_PASSWORD=SenhaF0rte!2026
POSTGRES_DB=siscont_db

DATABASE_URL=postgres://admin_siscont:SenhaF0rte!2026@db:5432/siscont_db
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
docker compose ps

# Verifique os logs
docker compose logs db

# Recrie o banco (CUIDADO: APAGA DADOS)
docker compose down -v
docker compose up -d
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
# Coletar arquivos estáticos
python manage.py collectstatic
```

> **⚠️ Em produção (Docker):** O volume `static_volume` persiste os arquivos entre builds. Se uma imagem ou CSS foi alterado e o site mostra a versão antiga, force a atualização:
> ```bash
> docker compose -f docker-compose.prod.yml exec web python manage.py collectstatic --noinput --clear
> ```

---

## 📞 Suporte

Para dúvidas, problemas ou sugestões:

1. **Documentação Django**: https://docs.djangoproject.com/
2. **Issues no GitHub**: Abra uma issue descrevendo o problema
3. **Logs da Aplicação**: Verifique `docker compose logs web`

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

### **Versão 1.3.1**
- ✅ **Regras de Comissão e Designação**: Validação rigorosa impede integrante de possuir data final superior à comissão. Encurtar prazo de comissão ajusta designações em cascata.
- ✅ **Portal Público Afunilado**: Consulta de contrato passou a exibir unicamente comissões ativas e integrantes ainda vigentes na atuação.

### **Versão 1.3.0**
- ✅ **Estabilidade de Produção**: Versão estável com pacotes da versão 1.2.0 consolidados.
- ✅ **Visualização de Versões (UI)**: Inclusão da exibição dinâmica e fixa da versão do sistema no rodapé público e na barra lateral do painel de auditoria.
- ✅ **Dashboard de Auditoria**: Correção do problema de inversão de porcentagens na contagem de dias do radar de permanência e correção na métrica de contratos sem data fim definida. Monitoramento de vencimentos agora usa a data da comissão (não da designação individual).
- ✅ **Exportação CSV**: Ordenação correta do radar de permanência por número de dias. Estabilização e melhorias variadas na formatação do Download via Google Chrome. Nova coluna de ordenação no CSV de comissões expiradas.
- ✅ **Identificação de Membros de Comissão**: Posto/graduação exibido junto ao nome de guerra na consulta pública.

### **Versão 1.2.0**
- ✅ **Upgrade Python 3.12**: Docker atualizado para Python 3.12 com `setuptools` para compatibilidade `distutils`.
- ✅ **Manuais Atualizados**: Manuais de TI e teste local reescritos com Docker Compose v2, backup/restauração, e troubleshooting.
- ✅ **Logo GAP-BR**: Escudo oficial atualizado.
- ✅ **Variáveis de Ambiente**: `SECRET_KEY` e `DEBUG` lidos do `.env.prod` (não mais hardcoded).
- ✅ **Correções de Templates**: Variáveis Django quebradas em múltiplas linhas nos templates de busca e transparência.
- ✅ **CI/CD**: Correção do teste `test_editar_comissao_rendering` para verificar path resolvido.

### **Versão 1.1.0**
- ✅ **Prazo de Qualificação**: Período de validade do curso de gestão atualizado para 5 anos (1.825 dias).
- ✅ **Velocímetro de Vigência**: Novo gráfico no painel de auditoria exibindo contratos por prazo de vencimento (≤90 / 90-120 / >120 dias).
- ✅ **Sobrecarga de Fiscais**: Dashboard e exportação CSV para acompanhar fiscais com múltiplos contratos simultâneos.
- ✅ **Vigência da Comissão**: Novos campos `data_inicio` e `data_fim` no modelo Comissão para controlar o prazo da comissão independentemente do contrato.
- ✅ **Campo PAG e Tipo no Contrato**: Campos Processo Administrativo de Gestão e Tipo (Despesa/Receita) adicionados ao cadastro de contratos.
- ✅ **Portaria e Boletim da Comissão**: Campos de portaria e boletim movidos para o nível da Comissão (além de já existirem no nível da Designação).
- ✅ **Radar de Permanência e Sobrecarga (CSV)**: Novos relatórios de exportação para radar de permanência e sobrecarga de fiscais.

### **Versão 1.0.0 (MVP)**
- ✅ **Gestão Completa de Contratos**: Cadastro, edição e visualização de contratos e comissões.
- ✅ **Área Pública**: Pesquisa de contratos e Portal de Transparência.
- ✅ **Área do Militar**: Consulta de histórico individual por SARAM/Nome.
- ✅ **Painel de Auditoria**: Dashboard com gráficos, métricas e alertas de risco.
- ✅ **Relatórios e Exportação**: Geração de CSVs para auditoria, vencimentos e histórico.
- ✅ **UX/UI Aprimorado**: Ordenação hierárquica, validações visuais e design responsivo.
- ✅ **Infraestrutura**: Configuração Docker completa (Dev/Prod), CI/CD pipeline e Nginx.
- ✅ **Testes**: Cobertura de testes automatizados e script de população de dados (`populate_db`).

**Desenvolvido por SO QSS SEL HUGO**
