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
| `EMAIL_BACKEND` | Liga o envio real de e-mails (opcional; sem ele nada é enviado) | `contratos.email_backend.IntraerSMTPBackend` |
| `EMAIL_HOST_USER` | Conta institucional que envia os e-mails | `scipg.gapbr@fab.mil.br` |
| `EMAIL_HOST_PASSWORD` | **Código de aplicativo** da conta (não a senha) — veja o Passo 1.9 | `abcd1234...` |

> **⚠️ IMPORTANTE:** O `DATABASE_URL` deve conter exatamente o mesmo usuário, senha e nome de banco definidos em `POSTGRES_USER`, `POSTGRES_PASSWORD` e `POSTGRES_DB`.

> **⚠️ Evite o caractere `$`** na `SECRET_KEY` e nas senhas: o Docker Compose o interpreta como variável (veja a Seção 7).

### 1.3 Proteger o `.env.prod`
O `.env.prod` guarda senhas e o código de aplicativo do e-mail. Restrinja a leitura ao dono do arquivo:
```bash
chmod 600 /opt/app_contratos/.env.prod
```

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
| A cada 2 min | Envia os e-mails pendentes da fila (`processar_fila_email`) |
| 02h00 | Executa a rotina de backup (`executar_backup`), conforme a periodicidade definida em **⚙️ Configurações**, e envia o relatório por e-mail |

### 1.7 Inicializar o Banco de Dados
```bash
docker compose -f docker-compose.prod.yml exec web python manage.py migrate
```

### 1.8 Criar o Primeiro Administrador
```bash
docker compose -f docker-compose.prod.yml exec web python manage.py createsuperuser
```
Informe nome de usuário, e-mail e senha quando solicitado.

### 1.9 Configurar Envio Automático de E-mails (SMTP do Intraer)
O SISCONT envia e-mails pelo servidor `mail.intraer` (porta 587, STARTTLS), autenticado com uma conta institucional. Hoje o único e-mail automático é o **relatório de cada backup**.

1. **Código de aplicativo:** as contas do FAB Mail usam autenticação de dois fatores, então a senha normal é recusada (`535 authentication failed`). Entre no FAB Mail com a conta institucional, vá em **Preferências > Contas > Aplicativos > Adicionar código do aplicativo**, dê o nome `SISCONT` e copie o código (ele aparece uma única vez).
2. **Configuração:** preencha no `.env.prod` as variáveis `EMAIL_BACKEND`, `EMAIL_HOST_USER` e `EMAIL_HOST_PASSWORD` (veja o `.env.prod.example`) e recrie os serviços:
   ```bash
   docker compose -f docker-compose.prod.yml up -d --force-recreate web cron
   ```
3. **Teste:** envie um e-mail de teste (use `--direto` para ver a resposta do servidor sem passar pela fila):
   ```bash
   docker compose -f docker-compose.prod.yml exec web python manage.py testar_email seu.email@fab.mil.br
   ```
4. **Destinatários do backup:** em **⚙️ Configurações**, preencha *Destinatários do Relatório de Backup* e clique em **Executar Backup Agora** para receber o primeiro relatório.

> **Rede:** a porta 25 do `mail.intraer` é bloqueada; use sempre a 587. Os containers `web` e `cron` usam o DNS interno (`10.228.68.1`) para encontrar `mail.intraer`.
>
> **Certificado:** o servidor apresenta um certificado `*.fab.mil.br`, que não corresponde a `mail.intraer`. Por isso a conexão é criptografada **sem verificar o certificado** (`EMAIL_SSL_VERIFY=False`, padrão).
>
> **Acompanhamento:** a fila de e-mails (enviados, pendentes e com falha) fica no Django Admin, em **Fila de E-mails**, com a ação *Reenviar e-mails que falharam*.

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
1. **Pré-verificações:** confirma que o Docker está acessível e que existem os arquivos `docker-compose.prod.yml`, `Dockerfile.prod`, e `.env.prod`; detecta caracteres `$` no `.env.prod` que seriam interpretados como variáveis pelo Compose;
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
- O `.env.prod` deve estar preenchido e protegido (Passos 1.2 e 1.3).
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
> - Apenas a **imagem Docker** é revertida. As **migrações já aplicadas no banco não são desfeitas** — se a versão nova alterou o esquema do banco, a versão anterior pode não funcionar corretamente. Em caso de dúvida, restaure o backup preventivo (Seção 4.3).
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

O sistema possui uma rotina de backup **totalmente automatizada** que roda internamente via Docker (container `cron`), dispensando o uso do cron do sistema operacional host.

#### O que cada backup contém

| Item | Arquivo | Observação |
|---|---|---|
| Banco de dados | `db_backup_AAAAMMDD.sql` | Dump do PostgreSQL em texto puro (`pg_dump -F p`) |
| Anexos (mídia) | `media_backup_AAAAMMDD.zip` | Zip completo do volume de mídia. Diário quando o servidor de arquivos está **desativado**; **um por mês** quando ele está ativado (os anexos novos seguem diariamente pela réplica, ver 4.2) |

Cada execução envia um **relatório por e-mail** (Seção 1.9) com o status:
- **OK**: tudo copiado;
- **PARCIAL**: o banco foi copiado, mas a mídia falhou ou estava vazia, ou o envio ao servidor de arquivos falhou;
- **FALHOU**: o dump do banco não foi feito.

#### Backup Automático (Recomendado)
1. Acesse o sistema como superusuário e vá em **⚙️ Configurações**.
2. Defina a periodicidade (Diário, Semanal ou Mensal) e os destinatários do relatório.
3. Em *Retenção no servidor do SISCONT*, defina quantos backups manter na pasta local (padrão: 7 dumps do banco e 1 zip de anexos). Os mais antigos são apagados automaticamente, **somente depois** que o backup novo do mesmo tipo deu certo. Zips de mídia vazios são sempre apagados.
4. O backup roda no horário agendado em `crontab.prod` (`0 2 * * *`, ou seja, 02h00 **UTC** = 23h00 de Brasília).
5. Os arquivos são salvos na pasta física mapeada do servidor host (padrão: `/opt/app_contratos/backups`).

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

> **Importante:** o serviço `cron` precisa montar o volume de mídia (`media_volume:/app/mediafiles:ro`). Sem ele, o zip de mídia sai vazio e o relatório acusa **PARCIAL**.

#### Backup Manual
- **Pelo portal:** em **⚙️ Configurações**, clique em **Executar Backup Agora**. O backup roda em segundo plano (pode levar alguns minutos) e o resultado chega pelo relatório por e-mail. A saída fica em `/backups/backup_manual.log`.
- **Pela linha de comando:**
```bash
docker compose -f docker-compose.prod.yml exec cron python manage.py executar_backup --force
```

Só um backup roda por vez: se outro estiver em andamento, o novo é ignorado.

### 4.2 Cópia no Servidor de Arquivos da Rede

Um backup guardado apenas no próprio servidor se perde junto com ele em caso de pane. Por isso o SISCONT pode enviar uma cópia de cada backup para uma **pasta compartilhada da rede** (servidor de arquivos Windows/SMB), que normalmente já tem rotinas próprias de segurança e redundância.

A conexão é feita pelo próprio SISCONT, somente durante a cópia: **nada é montado no Ubuntu** e não há configuração no sistema operacional. Se a cópia falhar, o backup local é mantido e o relatório por e-mail acusa **PARCIAL**, com o motivo.

#### Pré-requisitos (com a TI da OM)
1. **Uma pasta no servidor de arquivos** onde o SISCONT terá permissão de **leitura, escrita e exclusão** (a exclusão é usada pela retenção). Sugestão: `\\<servidor>\<compartilhamento>\SISCONT\Backup`.
2. **Uma conta de rede** com acesso a essa pasta. O ideal é uma conta do setor, não vinculada a uma pessoa e com senha que não expira; com a conta pessoal de um militar, o backup para de chegar quando a senha for trocada ou a conta desativada.
3. **Acesso de rede** do servidor do SISCONT ao servidor de arquivos na porta **TCP 445**.
4. **Resolução do nome** do servidor de arquivos dentro dos containers. Os serviços `web` e `cron` do `docker-compose.prod.yml` usam a lista `dns:`; coloque o DNS interno da OM em primeiro lugar. Para testar:
```bash
docker compose -f docker-compose.prod.yml exec cron getent hosts <servidor>
```
   Se não houver DNS interno, use o endereço IP no caminho (`\\10.x.x.x\compartilhamento\...`).

> **Quem pode ler os arquivos?** O dump contém todo o banco (inclusive dados pessoais e hashes de senha dos usuários) e os anexos. Todos que tiverem acesso à pasta poderão lê-los. Se possível, peça à TI uma pasta com acesso restrito à conta do SISCONT e aos administradores.

#### Configuração (no portal)
Em **⚙️ Configurações → Cópia no Servidor de Arquivos da Rede**:

| Campo | Exemplo genérico | Exemplo GAP-BR |
|---|---|---|
| Caminho da pasta de destino | `\\servidor\compartilhamento\SISCONT\Backup` (também aceita `smb://servidor/compartilhamento/SISCONT/Backup`) | `\\gapbrserver004\aci$\SISCONT\Backup` |
| Domínio (grupo de trabalho) | `om.intraer` | `gapbr.intraer` |
| Usuário de rede | `usuario.setor` | — |
| Senha de rede | — | — |

1. Preencha os campos, marque **Enviar cópia ao servidor de arquivos** e clique em **Salvar Configurações**. Antes de salvar, o sistema **testa a conexão** (cria a pasta, grava e apaga um arquivo de teste). Se o teste falhar, nada é salvo e a mensagem explica o motivo (usuário/senha recusados, acesso negado, compartilhamento não encontrado, nome não encontrado no DNS, servidor não respondeu).
2. Para trocar a conta (por exemplo, quando a conta do setor for criada), altere usuário e senha e salve. **Deixe a senha em branco** para manter a já cadastrada.
3. O botão **Testar Conexão com o Servidor de Arquivos** (em *Ação Imediata*) testa a configuração salva a qualquer momento.
4. Clique em **Executar Backup Agora** para fazer a primeira cópia. A primeira réplica envia todos os anexos e pode demorar; as seguintes enviam só o que mudou.

**Sobre a senha:** ela nunca aparece na tela e é gravada **cifrada** no banco, com uma chave derivada da `SECRET_KEY` do `.env.prod`. Quem obtiver apenas o dump do banco não consegue lê-la. Consequência: se a `SECRET_KEY` mudar (ou o sistema for restaurado em um servidor com outra `SECRET_KEY`), a senha guardada deixa de ser legível. A página de Configurações e o relatório por e-mail avisam; basta digitar a senha novamente e salvar.

#### Organização da pasta de destino

```
<pasta de destino>\
├── banco\          db_backup_AAAAMMDD.sql   (um por backup)
├── midia\          réplica dos anexos, com as mesmas subpastas do sistema
└── midia_mensal\   media_backup_AAAAMMDD.zip (um zip completo por mês)
```

- **banco**: recebe o dump de cada backup.
- **midia**: recebe só os anexos **novos ou alterados**. A réplica **nunca apaga** arquivos, então um anexo excluído por engano no SISCONT continua lá.
- **midia_mensal**: no primeiro backup de cada mês (qualquer que seja a periodicidade), o zip completo dos anexos é gerado e enviado. Ele protege contra um anexo **alterado/corrompido**, que a réplica sobrescreveria.

#### Retenção no servidor de arquivos (editável nas Configurações)

| Item | Padrão |
|---|---|
| Dumps diários | 30 mais recentes |
| Dumps mensais | além dos diários, o primeiro dump de cada um dos 12 meses mais recentes |
| Zips mensais de anexos | 3 mais recentes |
| Réplica dos anexos | nunca apaga |

Espaço ocupado: aproximadamente `42 × tamanho do dump` + `4 × tamanho dos anexos`. Confirme com a TI se a pasta tem cota.

### 4.3 Restaurar Backup

**Atenção:** a restauração do banco **sobrescreve o banco atual**. Faça antes um backup do estado atual, se ele ainda existir.

Os comandos abaixo usam os nomes do `.env.prod` e do `docker-compose.prod.yml` (`admin_siscont`, `siscont_db`, volume `siscont_media_prod`). Ajuste-os se a sua OM usar outros nomes (veja `POSTGRES_USER`/`POSTGRES_DB` no `.env.prod` e a seção `volumes:` do compose).

#### Passo 1: obter os arquivos de backup

- **Da pasta local** (`/opt/app_contratos/backups`), se o servidor ainda estiver acessível.
- **Do servidor de arquivos**, em caso de perda do servidor. Em qualquer computador da rede, abra a pasta de destino pelo Explorer e copie os arquivos. No Ubuntu do (novo) servidor do SISCONT, monte a pasta temporariamente, **somente leitura**:
```bash
sudo mkdir -p /mnt/backup_rede
sudo mount -t cifs '//<servidor>/<compartilhamento>' /mnt/backup_rede -o ro,vers=3.0,username=<usuario>,domain=<dominio>
ls /mnt/backup_rede/SISCONT/Backup/banco
```
   (A senha é pedida no terminal. Requer o pacote `cifs-utils`.)

Escolha o dump mais recente que esteja íntegro (o relatório por e-mail daquele dia deve estar **OK**).

#### Passo 2: restaurar o banco de dados

Em uma **instalação nova** (servidor substituído), siga a Seção 1 até o passo 1.6, mas **não** rode as migrações (passo 1.7) antes de restaurar: o dump já contém a estrutura e os dados.

```bash
# 1. Copiar o dump para dentro do container do banco
docker cp /mnt/backup_rede/SISCONT/Backup/banco/db_backup_AAAAMMDD.sql $(docker compose -f docker-compose.prod.yml ps -q db):/tmp/backup.sql

# 2. Recriar o banco vazio e restaurar (pare o web e o cron para não haver conexões abertas)
docker compose -f docker-compose.prod.yml stop web cron
docker compose -f docker-compose.prod.yml exec db bash -c "dropdb -U admin_siscont --if-exists siscont_db && createdb -U admin_siscont siscont_db && psql -U admin_siscont -d siscont_db -v ON_ERROR_STOP=1 < /tmp/backup.sql"

# 3. Subir novamente e aplicar migrações de versões mais novas, se houver
docker compose -f docker-compose.prod.yml up -d
docker compose -f docker-compose.prod.yml exec web python manage.py migrate
```

> **Nota:** Versões antigas do sistema (antes da v1.9.0) utilizavam o formato `-F c`. Se for restaurar um backup muito antigo, troque o `psql` acima por: `pg_restore -U admin_siscont -d siscont_db -1 --clean /tmp/backup.sql`

#### Passo 3: restaurar os anexos

**Opção A: a partir da réplica** (`midia\`, mais atual). Copia todos os arquivos da réplica para o volume de mídia:
```bash
docker run --rm -v siscont_media_prod:/destino -v /mnt/backup_rede/SISCONT/Backup/midia:/origem:ro alpine sh -c 'cp -a /origem/. /destino/'
```

**Opção B: a partir de um zip** (`midia_mensal\` ou da pasta local), para voltar os anexos a uma data específica:
```bash
docker run --rm -v siscont_media_prod:/destino -v /mnt/backup_rede/SISCONT/Backup/midia_mensal:/zips:ro alpine sh -c 'cd /destino && unzip -o /zips/media_backup_AAAAMMDD.zip'
```

A réplica pode conter anexos que foram excluídos no sistema depois do backup; eles ficam no volume mas não aparecem em nenhuma tela, pois não há registro no banco que aponte para eles.

#### Passo 4: finalizar

```bash
sudo umount /mnt/backup_rede
```
1. Acesse o portal e confira alguns contratos e anexos.
2. Em **⚙️ Configurações**, se a `SECRET_KEY` do novo servidor for diferente da antiga, digite novamente a **senha de rede** do servidor de arquivos e salve.
3. Clique em **Executar Backup Agora** e confira o relatório por e-mail.

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

### Erro `ERRO DE MIGRAÇÃO: Existem alterações nos models sem migração gerada no Git`
O script de deploy detectou que um desenvolvedor alterou arquivos `models.py` mas não executou `makemigrations` no ambiente local antes de enviar o código ao repositório.
**Solução:**
1. No seu ambiente de desenvolvimento/local, gere a migração:
   ```bash
   python manage.py makemigrations
   ```
2. Faça commit do novo arquivo `.py` de migração gerado na pasta `contratos/migrations/` e envie ao Git (`git push origin master`).
3. No servidor de produção, execute o deploy novamente (`sudo ./scripts/deploy_prod.sh --pull`).
