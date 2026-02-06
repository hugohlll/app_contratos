# 📂 Estrutura do Projeto SISCONT

Este documento detalha a organização de pastas e arquivos do sistema SISCONT, facilitando a navegação e o entendimento da arquitetura do projeto.

---

## 🏗️ Estrutura Principal

A raiz do projeto contém os arquivos de configuração de infraestrutura, dependências e o ponto de entrada da aplicação.

```
app_contratos/
│
├── core/                  # ⚙️ Configurações Globais do Projeto
├── contratos/             # 📦 Aplicação Principal (Lógica de Negócio)
├── docker-compose.yml     # Orquestração de containers (App + DB)
├── Dockerfile             # Definição da imagem Docker da aplicação
├── manage.py              # Utilitário de linha de comando do Django
├── requirements.txt       # Lista de dependências Python
└── README.md              # Documentação geral do projeto
```

---

## ⚙️ Core (Configurações)

A pasta `core/` armazena as configurações que afetam todo o projeto Django.

- **`settings.py`**: Configurações gerais (Banco de dados, Apps instalados, Middleware, Internacionalização, Variáveis de ambiente).
- **`urls.py`**: Roteamento principal URLs (mapeia rotas para os apps).
- **`wsgi.py`** e **`asgi.py`**: Pontos de entrada para servidores web (WSGI para deploy padrão, ASGI para assíncrono).

---

## 📦 Contratos (Aplicação Principal)

Esta é a "app" onde reside toda a lógica de negócio do SISCONT.

### 🧠 Lógica e Dados
- **`models.py`**: Definição do esquema de banco de dados (Tabelas: Contrato, Comissão, Agente, etc.).
- **`forms.py`**: Definição de formulários para validação de entrada de dados.
- **`admin.py`**: Configuração da interface administrativa do Django.
- **`apps.py`**: Metadados da aplicação.
- **`urls.py`**: Rotas específicas da aplicação `contratos`.
- **`utils.py`**: Funções utilitárias e auxiliares.

### 👁️ Views (Controladores)
As views estão organizadas em um pacote `views/` para melhor modularização:
- **`public.py`**: Views da área pública (Pesquisa, Detalhe do Contrato).
- **`portal.py`**: Views do portal operacional e gerenciamento de contratos.
- **`auditoria.py`**: Painel de auditoria, gráficos e relatórios gerenciais.
- **`militar.py`**: Área de consulta individual do militar.
- **`auth.py`**: Lógica de login e autenticação customizada.

### 🎨 Templates (Frontend)
Localizados em `contratos/templates/contratos/`:
- **`portal/`**: Templates do portal (dashboard, detalhes, edição).
    - `detalhe_contrato.html`, `base_portal.html`, etc.
- **`relatorio_periodo.html`**, **`relatorio_transparencia.html`**: Páginas de relatórios.
- **`home.html`**, **`pesquisa.html`**: Páginas públicas iniciais.

### 🏷️ Template Tags
Localizados em `contratos/templatetags/`:
- **`portal_tags.py`**: Filtros e tags customizadas para uso nos templates (ex: verificação de grupos de usuário).

### 🧪 Testes
Localizados em `contratos/tests/`:
- **`test_models.py`**: Testes unitários dos modelos.
- **`test_views.py`**: Testes de integração das views e URLs.
- **`test_forms.py`**: Validação de formulários.
- **`test_regression_*.py`**: Testes específicos para bugs corrigidos (regressão).

### 💾 Migrations
Pasta `contratos/migrations/`: Contém o histórico de alterações no esquema do banco de dados (versionamento do DB).

---

## 🐳 Infraestrutura (Docker)

- **`docker-compose.yml`**: Define dois serviços:
    - `web`: A aplicação Django rodando em Gunicorn/Dev Server.
    - `db`: Banco de dados PostgreSQL 15.
- **`Dockerfile`**: Constrói a imagem Linux com Python 3.11 e dependências instaladas.

---
**Desenvolvido por SO QSS SEL HUGO**
