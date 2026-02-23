# Manual de Instalação e Atualização (Equipe de TI)

Este documento descreve os procedimentos para instalar, configurar e atualizar a aplicação **SISCONT** no servidor de produção da Organização Militar.

## Requisitos do Servidor

- Sistema Operacional: Linux (Debian/Ubuntu recomendado)
- Docker Engine (v20+) e Docker Compose v2 instalados
- Acesso à Internet (para baixar imagens base e atualizações) ou repositório local configurado
- Portas **80** (HTTP) disponível no servidor

## 1. Instalação Inicial

### 1.1 Clonar o Repositório
Baixe o código-fonte para o diretório `/opt/app_contratos` (ou outro de sua preferência):
```bash
git clone https://github.com/seu-usuario/app_contratos.git /opt/app_contratos
cd /opt/app_contratos
```

### 1.2 Configurar Variáveis de Ambiente
Copie o modelo de configuração e edite com os dados reais da OM:
```bash
cp .env.prod.example .env.prod
nano .env.prod
```
**Atenção — preencha todos os campos obrigatórios:**

| Variável | Descrição | Exemplo |
|---|---|---|
| `SECRET_KEY` | Chave criptográfica do Django — use uma string longa e aleatória | `a3f8k2...` (mín. 50 caracteres) |
| `POSTGRES_PASSWORD` | Senha do banco de dados PostgreSQL | `SenhaF0rte!2026` |
| `POSTGRES_USER` | Usuário do banco de dados | `admin_siscont` |
| `POSTGRES_DB` | Nome do banco de dados | `siscont_db` |
| `DATABASE_URL` | URL de conexão (deve refletir os valores acima) | `postgres://admin_siscont:SenhaF0rte!2026@db:5432/siscont_db` |
| `DJANGO_ALLOWED_HOSTS` | IP ou domínio do servidor (sem `http://`) | `10.0.0.5,portal.om.eb.mil.br` |

> **⚠️ IMPORTANTE:** O `DATABASE_URL` deve conter exatamente o mesmo usuário, senha e nome de banco definidos em `POSTGRES_USER`, `POSTGRES_PASSWORD` e `POSTGRES_DB`.

### 1.3 Habilitar Inicialização Automática do Docker
Para que a aplicação inicie automaticamente quando o servidor for ligado ou reiniciado:
```bash
sudo systemctl enable docker
```
Combinado com a diretiva `restart: always` nos serviços do `docker-compose.prod.yml`, isso garante:
- **Servidor liga** → Docker inicia → containers sobem automaticamente → aplicação online.

### 1.4 Iniciar a Aplicação
```bash
cd /opt/app_contratos
docker compose -f docker-compose.prod.yml up -d --build
```

### 1.5 Verificar se os Containers Estão Saudáveis
```bash
docker compose -f docker-compose.prod.yml ps
```
Todos os 3 serviços devem estar com status `Up`:

| Serviço | Função | Porta |
|---|---|---|
| `db` | Banco de dados PostgreSQL | 5432 (interna) |
| `web` | Aplicação Django via Gunicorn | 8000 (interna) |
| `nginx` | Proxy reverso e arquivos estáticos | **80** (externa) |

### 1.6 Inicializar o Banco de Dados
```bash
docker compose -f docker-compose.prod.yml exec web python manage.py migrate
```

### 1.7 Criar o Primeiro Administrador
```bash
docker compose -f docker-compose.prod.yml exec web python manage.py createsuperuser
```
Informe nome de usuário, e-mail e senha quando solicitado.

---

## 2. Modos de Operação

### A. Homologação / Treinamento (Dados Fictícios)
Para ambientes de teste com uma massa de dados realistas:

```bash
docker compose -f docker-compose.prod.yml exec web python manage.py populate_db
```

Este comando cria automaticamente:

| Recurso | Quantidade |
|---|---|
| Agentes militares | 200 |
| Empresas | 50 |
| Contratos (diversos status) | 200 |
| Comissões com integrantes | ~300 |

Usuários criados pelo `populate_db`:

| Usuário | Senha | Perfil |
|---|---|---|
| `admin` | `admin` | Superusuário |
| `gestor` | `senha123` | Administrador |
| `auditor` | `senha123` | Auditor |

> **⚠️ ATENÇÃO:** Se for usar este modo em ambiente acessível pela rede, **troque as senhas** dos usuários de teste imediatamente.

### B. Produção Estrita (Uso Real)
Para o ambiente final de produção:
1. **NÃO EXECUTE** o `populate_db`.
2. Crie apenas o superusuário (Passo 1.7).
3. Cadastre os usuários e dados reais manualmente via sistema.

### Persistência dos Dados
Os dados do banco de dados são salvos no volume Docker `postgres_data`.
- **Segurança:** Se você parar os containers (`docker compose stop`) ou reiniciar a máquina, os dados **PERMANECEM SALVOS**.
- **⚠️ Perigo:** Os dados só serão apagados se você rodar `docker compose down -v` (com a flag `-v` de volumes). **NUNCA use essa flag em produção.**

---

## 3. Procedimento de Atualização

Sempre que houver uma nova versão do sistema (commit no Git), siga estes passos:

### 3.1 Baixar Atualizações
```bash
cd /opt/app_contratos
git pull origin master
```

### 3.2 Reconstruir e Reiniciar Containers
Isso garante que novas dependências e alterações de código sejam aplicadas:
```bash
docker compose -f docker-compose.prod.yml up -d --build
```

### 3.3 Aplicar Migrações (Se Houver)
Caso a atualização envolva mudanças no banco de dados:
```bash
docker compose -f docker-compose.prod.yml exec web python manage.py migrate
```

> **Nota:** O `collectstatic` já é executado automaticamente durante o build da imagem Docker (passo 3.2).

---

## 4. Backup e Restauração

### 4.1 Criar Backup
```bash
docker compose -f docker-compose.prod.yml exec db pg_dump -U admin_siscont siscont_db > backup_$(date +%F).sql
```
> **Substitua** `admin_siscont` e `siscont_db` pelos valores configurados no seu `.env.prod`.

### 4.2 Restaurar Backup
```bash
# 1. Copiar o arquivo de backup para dentro do container
docker cp backup_2026-02-22.sql $(docker compose -f docker-compose.prod.yml ps -q db):/tmp/backup.sql

# 2. Restaurar o banco (apaga os dados atuais e substitui pelo backup)
docker compose -f docker-compose.prod.yml exec db bash -c "psql -U admin_siscont -d siscont_db < /tmp/backup.sql"
```

> **Recomenda-se** manter backups diários em local seguro (pendrive, servidor de rede, etc.).

---

## 5. Comandos Úteis de Manutenção

| Ação | Comando |
|---|---|
| Ver logs em tempo real | `docker compose -f docker-compose.prod.yml logs -f --tail=50` |
| Ver logs de um serviço | `docker compose -f docker-compose.prod.yml logs -f web` |
| Reiniciar todos os serviços | `docker compose -f docker-compose.prod.yml restart` |
| Parar sem perder dados | `docker compose -f docker-compose.prod.yml stop` |
| Verificar status | `docker compose -f docker-compose.prod.yml ps` |
| Acessar shell do container | `docker compose -f docker-compose.prod.yml exec web bash` |

---

## 6. Solução de Problemas Comuns

### Container `web` reiniciando em loop
Verifique os logs:
```bash
docker compose -f docker-compose.prod.yml logs web --tail=30
```
Causas comuns:
- Variáveis de ambiente incorretas no `.env.prod`
- `DATABASE_URL` não corresponde às credenciais do Postgres

### Página retorna erro 502 Bad Gateway
O Nginx está funcionando mas não consegue se comunicar com o Gunicorn:
```bash
docker compose -f docker-compose.prod.yml restart web
```

### Erro `ModuleNotFoundError: No module named 'distutils'`
Em versões recentes do Ubuntu (24.04+) e Python (3.12+), o módulo `distutils` foi removido. Para ambientes sem Docker:
```bash
sudo apt install python3-setuptools
```
No ambiente Docker deste projeto, isso já é tratado automaticamente.
