# Manual de Instalação e Atualização (Equipe de TI)

Este documento descreve os procedimentos para instalar, configurar e atualizar a aplicação **SISCONT** no servidor de produção da Organização Militar.

## Requisitos do Servidor

- Sistema Operacional: Linux (Debian/Ubuntu recomendado)
- Docker Engine (v20+) e Docker Compose v2 instalados
- Acesso à Internet (para baixar imagens base e atualizações) ou repositório local configurado
- Porta **80** (HTTP) disponível no servidor

## 1. Instalação Inicial

### 1.1 Clonar o Repositório
Baixe o código-fonte para o diretório `/opt/app_contratos` (ou outro de sua preferência):
```bash
git clone https://github.com/hugohlll/app_contratos.git /opt/app_contratos
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
| `DEBUG` | Modo de depuração — **deve ser `False` em produção** | `False` |
| `EMAIL_PADRAO` | Remetente/destinatário padrão das notificações por e-mail (opcional) | `notificacoes@om.eb.mil.br` |

> **⚠️ IMPORTANTE:** O `DATABASE_URL` deve conter exatamente o mesmo usuário, senha e nome de banco definidos em `POSTGRES_USER`, `POSTGRES_PASSWORD` e `POSTGRES_DB`.

> **⚠️ Evite o caractere `$`** na `SECRET_KEY` e nas senhas: o Docker Compose o interpreta como variável (veja a Seção 7).

### 1.3 Preparar a Pasta `secrets/`
O `docker-compose.prod.yml` monta os arquivos `secrets/credentials.json` e `secrets/token.json` nos serviços `web` e `cron`, e o script `deploy_prod.sh` **se recusa a executar** se eles não existirem. Por isso, a pasta deve ser preparada **antes** de subir os containers:

- **Se for usar o envio de e-mails (Gmail API):** siga o Passo 1.9 e coloque os arquivos reais na pasta.
- **Se ainda não for usar e-mails:** crie arquivos vazios apenas para satisfazer as montagens. A aplicação funciona normalmente; apenas o envio de e-mails fica indisponível (o comando `testar_email` retorna erro) e a verificação diária do token (01h00) registrará um erro em `/var/log/cron.log` do container `cron` até que as credenciais reais sejam colocadas:
  ```bash
  mkdir -p /opt/app_contratos/secrets
  touch /opt/app_contratos/secrets/credentials.json /opt/app_contratos/secrets/token.json
  ```

> **⚠️ Atenção:** Se os arquivos não existirem quando os containers subirem, o Docker criará **diretórios** (pertencentes ao `root`) com esses nomes no lugar dos arquivos. O `deploy_prod.sh` **não detecta** essa situação (ele só verifica se o caminho existe). Confira com `ls -l secrets/`: se aparecerem como diretórios (`d` no início), remova-os (`sudo rm -rf secrets/credentials.json secrets/token.json`), crie os arquivos corretamente e recrie os serviços (`docker compose -f docker-compose.prod.yml up -d --force-recreate web cron`).

### 1.4 Habilitar Inicialização Automática do Docker
Para que a aplicação inicie automaticamente quando o servidor for ligado ou reiniciado:
```bash
sudo systemctl enable docker
```
Combinado com a diretiva `restart: always` nos serviços do `docker-compose.prod.yml`, isso garante:
- **Servidor liga** → Docker inicia → containers sobem automaticamente → aplicação online.

### 1.5 Construir a Imagem e Iniciar a Aplicação
```bash
cd /opt/app_contratos
docker build --network host -f Dockerfile.prod -t app_contratos-web:latest .
docker compose -f docker-compose.prod.yml up -d
```

> **Nota:** Não use `docker compose -f docker-compose.prod.yml up -d --build`. No Docker Compose v5+ esse comando falha por causa da opção `network: host` do build (veja a Seção 7). Após a instalação inicial, as atualizações devem ser feitas com o script `deploy_prod.sh` (Seção 3).

### 1.6 Verificar se os Containers Estão Saudáveis
```bash
docker compose -f docker-compose.prod.yml ps
```
Todos os 4 serviços devem estar com status `Up` (o `web` e o `nginx` devem indicar `healthy`):

| Serviço | Função | Porta |
|---|---|---|
| `db` | Banco de dados PostgreSQL | 5432 (interna) |
| `web` | Aplicação Django via Gunicorn | 8000 (interna) |
| `cron` | Rotinas agendadas (ver tabela abaixo) | - |
| `nginx` | Proxy reverso e arquivos estáticos | **80** (externa) |

> **Nota:** O `nginx` só sobe depois que o `web` passa no health check (acesso a `/login/`).

Rotinas executadas pelo serviço `cron` (definidas em `crontab.prod`, log em `/var/log/cron.log` dentro do container):

| Horário | Rotina |
|---|---|
| 00h00 | Desativa comissões encerradas e ativa comissões iniciadas |
| 01h00 | Verifica/renova o token do Gmail (`scripts/check_gmail_health.py`) |
| 02h00 | Executa a rotina de backup (`executar_backup`), conforme a periodicidade definida em **⚙️ Configurações** |

### 1.7 Inicializar o Banco de Dados
```bash
docker compose -f docker-compose.prod.yml exec web python manage.py migrate
```

### 1.8 Criar o Primeiro Administrador
```bash
docker compose -f docker-compose.prod.yml exec web python manage.py createsuperuser
```
Informe nome de usuário, e-mail e senha quando solicitado.

### 1.9 Configurar Envio Automático de E-mails (Gmail API)
O sistema suporta o envio automático de alertas (ex: vencimento de comissões e contratos) via Gmail API. Para habilitar essa funcionalidade:

1. Acesse o guia completo na documentação da aplicação: **[Roteiro de Implementação: Gmail API](../roteiros/ROTEIRO_PRODUCAO_GMAIL_API.md)**.
2. O guia explicará como criar as credenciais OAuth 2.0 no Google Cloud.
3. Ao gerar as credenciais, você baixará um arquivo chamado `credentials.json` e, após a autenticação inicial simulada no script, também será gerado o arquivo `token.json`.
4. Mova ambos os arquivos JSON para a pasta `secrets/` na raiz do projeto (onde fica o `docker-compose.prod.yml`), substituindo os arquivos vazios criados no Passo 1.3, se for o caso:
   ```bash
   mkdir -p /opt/app_contratos/secrets
   mv credentials.json /opt/app_contratos/secrets/
   mv token.json /opt/app_contratos/secrets/
   ```
5. O `docker-compose.prod.yml` já está configurado de fábrica para ler as credenciais automaticamente desta pasta nos serviços `web` e `cron`. Reinicie esses serviços para carregar os novos arquivos:
   ```bash
   docker compose -f docker-compose.prod.yml restart web cron
   ```

---

## 2. Modos de Operação

### A. Homologação / Treinamento (Dados Fictícios)
Para ambientes de teste com uma massa de dados realistas, use o **ambiente de desenvolvimento** (`docker-compose.yml`):

```bash
docker compose exec web python manage.py populate_db
```

> **⚠️ Nota:** O comando `populate_db` **não existe na imagem de produção** — o `Dockerfile.prod` o remove propositalmente para evitar a carga acidental de dados fictícios. Executá-lo com `-f docker-compose.prod.yml` resultará em `Unknown command: 'populate_db'`.

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
1. **NÃO EXECUTE** o `populate_db` (ele não está disponível na imagem de produção).
2. Crie apenas o superusuário (Passo 1.8).
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

Sempre que houver uma nova versão do sistema (commit no Git), siga o procedimento automatizado abaixo.

### 3.1 Método Automatizado (Recomendado)

O script `scripts/deploy_prod.sh` executa, em ordem, as seguintes etapas:
1. **Pré-verificações:** confirma que o Docker está acessível e que existem os arquivos `docker-compose.prod.yml`, `Dockerfile.prod`, `.env.prod`, `secrets/credentials.json` e `secrets/token.json`; detecta caracteres `$` no `.env.prod` que seriam interpretados como variáveis pelo Compose;
2. **Atualização do código** (somente com `--pull`): executa `git pull origin master`;
3. **Backup preventivo** do banco e da mídia (`executar_backup`) usando o container `web` ou `cron` em execução;
4. **Salvaguarda da imagem atual** com a tag `app_contratos-web:previous`, para possibilitar rollback;
5. **Build** da nova imagem com `docker build --network host` (evitando a restrição do Bake no Docker Compose v5+);
6. **Recriação dos containers** (`up -d --remove-orphans`);
7. **Health check** do container `web` (aguarda até 180 s pelo status `healthy`);
8. **Salvaguarda de migrações** (`makemigrations --check --dry-run`);
9. **Aplicação das migrações** (`migrate --noinput`);
10. **Atualização dos arquivos estáticos** no volume persistente (`collectstatic --clear`).

#### Pré-requisitos de execução
- Execute com `sudo` (ou com um usuário pertencente ao grupo `docker`). O script pode ser chamado de qualquer diretório — ele se posiciona automaticamente na raiz do repositório.
- A pasta `secrets/` deve estar preparada (Passo 1.3).
- Para usar `--pull`, o repositório no servidor **não pode ter alterações locais nem arquivos novos não versionados** (o script verifica `git status --porcelain` e aborta caso existam — até um documento solto na pasta do projeto bloqueia o deploy). Isso inclui o `core/settings.py`, que é montado diretamente do servidor no container `web`: ajustes locais nesse arquivo bloqueiam os deploys com `--pull`. Ao ser executado via `sudo`, o `git pull` roda com o usuário que chamou o `sudo` (`SUDO_USER`), evitando o erro de *dubious ownership*.

#### Opções disponíveis

| Opção | Efeito |
|---|---|
| *(nenhuma)* | Deploy usando o código já presente em disco |
| `--pull` | Executa `git pull origin master` antes do deploy |
| `--manutencao` | Ativa a página de manutenção durante o deploy (é **sempre desativada ao final**, mesmo em caso de falha) |
| `--sem-backup` | Pula o backup preventivo |
| `--prune` | Remove imagens Docker sem uso ao final (`docker image prune -f`) |
| `--rollback` | Restaura imediatamente a imagem anterior (`:previous`) e encerra |
| `--dry-run` | Apenas exibe os passos que seriam executados, sem aplicar alterações |
| `-h`, `--help` | Exibe a ajuda |

**Comando padrão (com download do código mais recente):**
```bash
cd /opt/app_contratos
sudo ./scripts/deploy_prod.sh --pull
```

**Comandos adicionais úteis:**
```bash
# Deploy ativando página de manutenção durante a troca de versão
# (recomendado quando a nova versão contém migrações de banco):
sudo ./scripts/deploy_prod.sh --pull --manutencao

# Simular o deploy sem alterar nada:
sudo ./scripts/deploy_prod.sh --pull --dry-run

# Deploy sem baixar alterações do Git (usando o código já em disco):
sudo ./scripts/deploy_prod.sh

# Reverter imediatamente para a versão estável anterior em caso de emergência:
sudo ./scripts/deploy_prod.sh --rollback
```

Cada execução grava um log completo em `logs/deploy_AAAAMMDD_HHMMSS.log`.

> **💡 Quando usar `--manutencao`:** os containers com a nova versão entram no ar (etapa 6) **antes** da aplicação das migrações (etapa 9). Durante esse intervalo, o código novo atende requisições sobre o banco ainda não migrado, o que pode gerar erros momentâneos aos usuários. Com `--manutencao`, os usuários veem a página de indisponibilidade durante toda a troca.

#### Comportamento em caso de falha

| Situação | O que o script faz |
|---|---|
| Falha no backup preventivo | **Apenas avisa e continua** o deploy. Se nenhum container estiver em execução (ex.: primeira instalação), o backup não é feito. |
| `web` não fica `healthy` em 180 s | Exibe os últimos 50 logs do `web` e faz **rollback automático** para `:previous` |
| Models alterados sem migração versionada | Interrompe e faz **rollback automático** para `:previous` (ver Seção 7) |
| Falha no `migrate` ou no `collectstatic` | Interrompe **sem rollback** — a nova versão permanece no ar. Analise o log e corrija, ou use `--rollback` manualmente (ver limitações abaixo). |

> **⚠️ Limitações do rollback (`--rollback` ou automático):**
> - Apenas a **imagem Docker** é revertida. As **migrações já aplicadas no banco não são desfeitas** — se a versão nova alterou o esquema do banco, a versão anterior pode não funcionar corretamente. Em caso de dúvida, restaure o backup preventivo (Seção 4.2).
> - O **código em disco não é revertido** (o `git pull` permanece). Um novo deploy sem `--pull` reconstruirá a versão problemática; para voltar o código, use `git checkout <commit>` antes de um novo deploy.
> - Existe **apenas uma versão guardada** (`:previous`), que é sempre a imagem imediatamente anterior ao último deploy.

---

### 3.2 Método Manual Passo a Passo (Alternativa)

Caso prefira executar cada comando individualmente:

```bash
cd /opt/app_contratos

# 1. Baixar atualizações do repositório
git pull origin master

# 2. Construir a imagem com rede host (obrigatório para resolver DNS corporativo)
docker build --network host -f Dockerfile.prod -t app_contratos-web:latest .

# 3. Subir os containers (sem a flag --build)
docker compose -f docker-compose.prod.yml up -d

# 4. Verificar se há models sem migração versionada (deve terminar sem erro)
docker compose -f docker-compose.prod.yml exec web python manage.py makemigrations --check --dry-run

# 5. Aplicar migrações do banco
docker compose -f docker-compose.prod.yml exec web python manage.py migrate --noinput

# 6. Atualizar os arquivos estáticos persistidos no volume
docker compose -f docker-compose.prod.yml exec web python manage.py collectstatic --noinput --clear
```

> **Nota:** O método manual **não** faz backup preventivo nem rollback automático. Recomenda-se executar `docker compose -f docker-compose.prod.yml exec web python manage.py executar_backup` antes do passo 1.

> **⚠️ Atenção — Por que não usar `docker compose up -d --build` diretamente?**  
> No Docker Compose v5+, o comando `compose build` utiliza internamente o Docker Bake, que exige permissão explícita para `network: host` (`--allow=network.host`). Como o `docker compose` não repassa essa permissão, o build falha. O build direto via `docker build --network host` ou o script `deploy_prod.sh` contornam essa limitação.

---

## 4. Backup e Restauração

### 4.1 Criação de Backup (Automático e Manual)

O sistema possui uma rotina de backup **totalmente automatizada** que roda internamente via Docker, dispensando o uso do cron do sistema operacional host.

#### Backup Automático (Recomendado)
1. Acesse o sistema como superusuário e vá em **⚙️ Configurações**.
2. Defina a periodicidade (Diário, Semanal ou Mensal).
3. O sistema fará o dump do PostgreSQL e o ZIP dos arquivos de mídia (`/mediafiles`) no horário agendado (padrão: `02h00`).
4. Os arquivos serão salvos **automaticamente na pasta física** mapeada do servidor host (padrão: `/opt/app_contratos/backups`).

> **💡 Como alterar o diretório de destino do backup no Host:**
> Como o sistema é conteinerizado, a aplicação gravará os backups sempre no diretório interno `/backups`. Para alterar onde esses arquivos vão parar no seu servidor físico, você deve editar a seção `volumes` dos serviços `web` e `cron` no arquivo `docker-compose.prod.yml`:
> ```yaml
> services:
>   web:
>     volumes:
>       - /seu/novo/caminho/de/backup:/backups  # Mude aqui
>   ...
>   cron:
>     volumes:
>       - /seu/novo/caminho/de/backup:/backups  # Mude aqui também
> ```
> Após a alteração, reinicie os containers: `docker compose -f docker-compose.prod.yml up -d`

#### Backup Manual (Linha de Comando)
Caso precise gerar um backup imediatamente ou fora do agendamento, você pode forçar a execução do script Python nativo:
```bash
docker compose -f docker-compose.prod.yml exec cron python manage.py executar_backup
```
Ou, se preferir extrair apenas o banco (método antigo via `pg_dump` puro):
```bash
docker compose -f docker-compose.prod.yml exec db pg_dump -U admin_siscont siscont_db -F p -f /tmp/backup.sql
docker cp $(docker compose -f docker-compose.prod.yml ps -q db):/tmp/backup.sql ./backups/backup_manual_$(date +%F).sql
```
> **Nota:** Certifique-se de usar as credenciais definidas no `.env.prod`.

### 4.2 Restaurar Backup

**Atenção:** Restaurações apagam/sobresscrevem o banco de dados atual. 

Se você for restaurar um backup gerado pela **rotina automática** ou manual (que usa formato texto puro `-F p`), utilize o `psql`:

```bash
# 1. Copiar o arquivo de backup para dentro do container
docker cp backups/db_backup_20260601.sql $(docker compose -f docker-compose.prod.yml ps -q db):/tmp/backup.sql

# 2. Restaurar o banco usando psql
docker compose -f docker-compose.prod.yml exec db bash -c "psql -U admin_siscont -d siscont_db < /tmp/backup.sql"
```

> **Nota:** Versões antigas do sistema (antes da v1.9.0) utilizavam o formato `-F c`. Se for restaurar um backup muito antigo, troque o comando `psql` acima por: `pg_restore -U admin_siscont -d siscont_db -1 --clean /tmp/backup.sql`

> **Recomenda-se** manter backups diários em local seguro (pendrive, servidor de rede, etc.). Além do banco de dados, certifique-se de salvar os arquivos ZIP de mídia (`/backups/media_backup_*.zip`) extraindo seu conteúdo para o volume `/opt/app_contratos/mediafiles` se necessário.

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
| Executar testes automatizados | `docker compose -f docker-compose.prod.yml exec web python manage.py test` |
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

## 7. Solução de Problemas Comuns

### Container `web` reiniciando em loop
Verifique os logs:
```bash
docker compose -f docker-compose.prod.yml logs web --tail=30
```
Causas comuns:
- Variáveis de ambiente incorretas no `.env.prod`
- `DATABASE_URL` não corresponde às credenciais do Postgres

### Página retorna erro 502 Bad Gateway
O Nginx está funcionando mas não consegue se comunicar com o Gunicorn (geralmente após uma atualização onde o IP do container web mudou e o Nginx cacheou o IP antigo).
Para resolver, reinicie o container do Nginx para que ele resolva novamente o endereço do `web`:
```bash
docker compose -f docker-compose.prod.yml restart nginx
```
Se persistir, force a recriação: `docker compose -f docker-compose.prod.yml up -d --force-recreate nginx`.

> **Nota:** Recriar o container do Nginx (`--force-recreate`) remove o modo de manutenção, caso esteja ativo. O `restart` simples o preserva.

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

### Erro `additional privileges requested: pass "--allow=network.host"`
Ocorre ao tentar rodar `docker compose up -d --build` no Docker Compose v5+, pois o construtor Bake bloqueia o compartilhamento da rede do host durante o build.
**Solução:** Utilize o script de deploy automatizado:
```bash
sudo ./scripts/deploy_prod.sh --pull
```
Ou construa a imagem separadamente antes de subir os containers:
```bash
docker build --network host -f Dockerfile.prod -t app_contratos-web:latest .
docker compose -f docker-compose.prod.yml up -d
```

### Aviso `The "X" variable is not set. Defaulting to a blank string.`
Ocorre quando o arquivo `.env.prod` possui caracteres de cifrão (`$`) em campos como `SECRET_KEY` ou senhas de banco. O Docker Compose interpreta qualquer string iniciada por `$` como uma variável de ambiente não definida e remove o conteúdo.
**Solução:** Edite o arquivo `.env.prod` e remova o caractere `$` (ou substitua por `$$` caso deseje preservar o caractere literal no Compose).

### Erro `Existem alterações locais não commitadas no repositório. Abortando deploy.`
O `deploy_prod.sh --pull` encontrou arquivos modificados (`M`) ou não versionados (`??`) no servidor, listados logo abaixo da mensagem. Um caso comum é o `core/settings.py`, editado diretamente no servidor.
**Solução:**
- Arquivos modificados (`M`): leve a alteração para o repositório pelo ambiente de desenvolvimento (commit/push) e descarte a cópia local com `git checkout -- <arquivo>`. Se a alteração for descartável, apenas execute o `git checkout`.
- Arquivos não versionados (`??`): mova-os para fora da pasta do projeto (ou apague-os, se forem descartáveis).

Em seguida, repita o deploy.

### Erro `Arquivo/caminho de credenciais não encontrado: secrets/...`
O script exige `secrets/credentials.json` e `secrets/token.json`. Prepare a pasta conforme o Passo 1.3.

### Erro `ERRO DE MIGRAÇÃO: Existem alterações nos models sem migração gerada no Git`
O script de deploy detectou que um desenvolvedor alterou arquivos `models.py` mas não executou `makemigrations` no ambiente local antes de enviar o código ao repositório.
**Solução:**
1. No seu ambiente de desenvolvimento/local, gere a migração:
   ```bash
   python manage.py makemigrations
   ```
2. Faça commit do novo arquivo `.py` de migração gerado na pasta `contratos/migrations/` e envie ao Git (`git push origin master`).
3. No servidor de produção, execute o deploy novamente (`sudo ./scripts/deploy_prod.sh --pull`).
