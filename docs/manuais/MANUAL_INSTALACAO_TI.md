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
| `cron` | Serviço para rodar scripts automatizados (rotinas diárias) | - |
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

### 1.8 Configurar Envio Automático de E-mails (Gmail API)
O sistema suporta o envio automático de alertas (ex: vencimento de comissões e contratos) via Gmail API. Para habilitar essa funcionalidade:

1. Acesse o guia completo na documentação da aplicação: **[Roteiro de Implementação: Gmail API](../roteiros/ROTEIRO_PRODUCAO_GMAIL_API.md)**.
2. O guia explicará como criar as credenciais OAuth 2.0 no Google Cloud.
3. Ao gerar as credenciais, você baixará um arquivo chamado `credentials.json` e, após a autenticação inicial simulada no script, também será gerado o arquivo `token.json`.
4. Crie uma pasta `secrets/` na raiz do projeto (onde fica o `docker-compose.prod.yml`) e mova ambos os arquivos JSON para dentro dela:
   ```bash
   mkdir -p /opt/app_contratos/secrets
   mv credentials.json /opt/app_contratos/secrets/
   mv token.json /opt/app_contratos/secrets/
   ```
5. O `docker-compose.prod.yml` já está configurado de fábrica para ler as credenciais automaticamente desta pasta nos serviços `.web` e `.cron`. Reinicie a arquitetura para carregar os novos arquivos:
   ```bash
   docker compose -f docker-compose.prod.yml up -d
   ```

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
Os dados do banco de dados são salvos no volume Docker nomeado `siscont_pg_data_prod`.
- **Segurança:** Se você parar os containers (`docker compose stop`) ou reiniciar a máquina, os dados **PERMANECEM SALVOS**.
- **⚠️ Perigo:** Os dados só serão apagados se você rodar `docker compose -f docker-compose.prod.yml down -v` (com a flag `-v` de volumes). **NUNCA use essa flag em produção.**

> **Nota:** Os volumes de produção possuem nomes explícitos para evitar conflitos:
> | Volume | Conteúdo |
> |---|---|
> | `siscont_pg_data_prod` | Banco de dados PostgreSQL |
> | `siscont_static_prod` | Arquivos estáticos (CSS, JS, imagens) |
> | `siscont_media_prod` | Uploads de mídia (prestações de contas, etc.) |

---

## 2.1 Segregação de Ambientes (Desenvolvimento vs Produção)

O SISCONT utiliza dois ambientes Docker completamente isolados que podem coexistir **no mesmo servidor** sem risco de colisão de dados:

| Aspecto | Desenvolvimento | Produção |
|---|---|---|
| **Arquivo Docker Compose** | `docker-compose.yml` | `docker-compose.prod.yml` |
| **Nome do Projeto** | `siscont_dev` | `siscont_prod` |
| **Rede Docker** | `siscont_dev_default` (automática) | `siscont_prod_default` (automática) |
| **Volume do Banco** | `siscont_pg_data_dev` | `siscont_pg_data_prod` |
| **Porta Externa** | `8000` (Django runserver) | `80` (Nginx) |
| **Credenciais do Banco** | `admin_contratos` / `gestao_contratos_db` | Definidas no `.env.prod` |

### Como o Isolamento Funciona

O isolamento é garantido pelo atributo `name:` na primeira linha de cada arquivo Docker Compose (recurso do Docker Compose V2):

```yaml
# docker-compose.yml (Desenvolvimento)
name: siscont_dev

# docker-compose.prod.yml (Produção)
name: siscont_prod
```

Esse atributo automaticamente:
1. **Cria uma rede interna exclusiva** para cada ambiente (`siscont_dev_default` e `siscont_prod_default`). Os containers de um ambiente **não conseguem resolver DNS** para containers do outro.
2. **Prefixa todos os containers** com o nome do projeto (ex: `siscont_prod-db-1`, `siscont_dev-web-1`), evitando conflitos de ciclo de vida.
3. **Isola os volumes** com nomes explícitos definidos no bloco `volumes:` de cada arquivo.

### Camadas de Defesa (Resumo)

| Camada | Mecanismo | Efeito |
|---|---|---|
| **Rede** | Redes Docker separadas | Dev não encontra o banco de Prod |
| **Namespace** | Atributo `name:` distinto | Docker não mistura containers |
| **Disco** | Volumes com nomes explícitos | Dados em diretórios físicos separados |
| **Porta** | Prod usa 80, Dev usa 8000 | Sem conflito de porta |
| **Autenticação** | Credenciais diferentes | Dev é rejeitado pelo Postgres de Prod |

> **⚠️ IMPORTANTE — Volumes Legados:** Em servidores onde o sistema foi instalado antes da segregação, podem existir volumes antigos com o prefixo `app_contratos_` (ex: `app_contratos_postgres_data`). Estes volumes podem ser removidos com `docker volume rm <nome>` **somente após confirmação de que a migração dos dados para os novos volumes nomeados já foi concluída.**

> Para consultar o guia técnico completo sobre o isolamento, veja: **[Guia de Isolamento Docker: Produção vs Desenvolvimento](../../Guia%20de%20Isolamento%20Docker_%20Produção%20vs%20Desenvolvimento.md)**.

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

### 3.4 Atualizar Arquivos Estáticos (Imagens, CSS, JS)

> **⚠️ ATENÇÃO — Comportamento importante do Docker:** O volume `static_volume` **persiste os arquivos entre builds**. Isso significa que, mesmo após reconstruir a imagem com uma nova imagem ou CSS, o Nginx pode continuar a servir a versão anterior do arquivo estático.

Para garantir que os arquivos estáticos sejam totalmente atualizados após um deploy que altere imagens, estilos ou scripts:

```bash
# Apaga os estáticos antigos do volume e recopia os novos
docker compose -f docker-compose.prod.yml exec web python manage.py collectstatic --noinput --clear
```

Alternativamente, para atualizar um arquivo específico sem refazer tudo:

```bash
docker cp caminho/local/arquivo.png app_contratos-web-1:/app/staticfiles/caminho/destino/arquivo.png
```

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
| Ativar modo de manutenção | `bash scripts/maintenance_on.sh` |
| Desativar modo de manutenção | `bash scripts/maintenance_off.sh` |

---

## 6. Modo de Manutenção (Página de Indisponibilidade)

O sistema possui uma funcionalidade integrada para exibir uma **página de manutenção** a todos os usuários enquanto ajustes estão sendo realizados. Essa página é servida diretamente pelo Nginx, sem depender do Django.

### Como Funciona

1. O Nginx verifica, a cada requisição, se o arquivo `/usr/share/nginx/html/maintenance.on` existe dentro do container.
2. Se o arquivo existir, **todas as requisições** retornam HTTP 503 com a página `maintenance.html` (uma tela estilizada informando sobre a manutenção).
3. Se o arquivo não existir, as requisições são encaminhadas normalmente para o Django.

> **Nota:** A mudança de estado é **instantânea** e **não requer reinicialização** de nenhum container.

### Ativar o Modo de Manutenção

No terminal do servidor, na pasta raiz do projeto:
```bash
cd /opt/app_contratos
bash scripts/maintenance_on.sh
```

Saída esperada:
```
✅ Modo de manutenção ATIVADO.
   Todos os acessos receberão a página de manutenção (HTTP 503).
```

### Desativar o Modo de Manutenção

```bash
cd /opt/app_contratos
bash scripts/maintenance_off.sh
```

Saída esperada:
```
✅ Modo de manutenção DESATIVADO.
   O sistema voltou ao funcionamento normal.
```

### Ativação/Desativação Manual (Alternativa)

Caso prefira não usar os scripts, os comandos equivalentes são:
```bash
# Ativar
docker exec siscont_prod-nginx-1 touch /usr/share/nginx/html/maintenance.on

# Desativar
docker exec siscont_prod-nginx-1 rm -f /usr/share/nginx/html/maintenance.on
```

> **⚠️ ATENÇÃO:** Certifique-se de **desativar** o modo de manutenção após concluir os ajustes. Caso contrário, o sistema permanecerá inacessível para todos os usuários.

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

### Erro `fatal: detected dubious ownership in repository` no Git
Este erro ocorre quando o usuário que está rodando o comando `git` (ex: `root`) não é o mesmo usuário que é dono da pasta `/opt/app_contratos` (ou o local onde você colocou o projeto), o que é uma medida de segurança introduzida em versões recentes do Git. Nas máquinas de produção é um problema muito comum.
Para resolver de forma global para esse servidor, adicione a pasta à lista de exceções de segurança do Git rodando:
```bash
git config --global --add safe.directory /opt/app_contratos
```
*(Atenção: verifique se o caminho bate com o caminho real do repositório no seu servidor)*
