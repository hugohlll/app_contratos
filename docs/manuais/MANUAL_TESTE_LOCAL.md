# Manual de Teste Local em Produção (Simulação)

Este guia descreve como rodar o ambiente de produção (Docker + Nginx + Gunicorn + Postgres) na sua máquina local para testes antes do deploy real.

## Pré-requisitos

- Docker Desktop ou Docker Engine (v20+) com Docker Compose v2
- Git instalado
- Porta **80** livre (se estiver em uso, pare o serviço que a ocupa)

## Passo a Passo

### 1. Configurar Variáveis de Ambiente
Copie o modelo e ajuste se necessário:
```bash
cp .env.prod.example .env.prod
```

O conteúdo padrão para testes locais:
```env
DEBUG=False
SECRET_KEY=chave-secreta-teste-local-2026
DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1

POSTGRES_USER=admin
POSTGRES_PASSWORD=admin
POSTGRES_DB=siscont_db

DATABASE_URL=postgres://admin:admin@db:5432/siscont_db

# (Opcional) Configurações de envio automático de e-mail (Gmail API)
# EMAIL_PADRAO=notificacoes@suaempresa.com.br
```

> **Dica**: Se quiser testar o envio de e-mails, crie a pasta `secrets/` na raiz do projeto e insira os arquivos `credentials.json` e `token.json` nela antes de subir os containers, conforme descrito no [Roteiro do Gmail API](../roteiros/ROTEIRO_PRODUCAO_GMAIL_API.md).

### 2. Construir e Subir os Containers
```bash
docker compose -f docker-compose.prod.yml up -d --build
```

### 3. Verificar se Tudo Subiu
```bash
docker compose -f docker-compose.prod.yml ps
```
Deve mostrar 4 serviços com status `Up`: **db**, **web**, **cron** e **nginx**.

### 4. Executar Migrações do Banco de Dados
```bash
docker compose -f docker-compose.prod.yml exec web python manage.py migrate
```

### 5. Popular com Dados de Teste
Para simular um ambiente com dados realistas:
```bash
docker compose -f docker-compose.prod.yml exec web python manage.py populate_db
```

Este comando cria automaticamente:
- **200 contratos** (vigentes, vencidos, críticos)
- **200 agentes** militares com postos variados
- **50 empresas** contratadas
- **~300 comissões** (fiscalização e recebimento)

Usuários criados:

| Usuário | Senha | Perfil |
|---|---|---|
| `admin` | `admin` | Superusuário |
| `gestor` | `senha123` | Administrador |
| `auditor` | `senha123` | Auditor |

> **Nota:** Se preferir testar com banco limpo, pule este passo e crie apenas um superusuário:
> ```bash
> docker compose -f docker-compose.prod.yml exec web python manage.py createsuperuser
> ```

### 6. Acessar a Aplicação
Abra o navegador em: **[http://localhost](http://localhost)**

### 7. Testar Modo de Manutenção (Simulação)
É possível simular o Modo de Manutenção no ambiente local de testes (pois a configuração local sobe o Nginx e os scripts apontam para o container `siscont_prod-nginx-1`):

1. **Ative a manutenção** rodando a partir da raiz do projeto:
   ```bash
   bash scripts/maintenance_on.sh
   ```
2. **Acesse** `http://localhost` no navegador. O sistema deverá retornar um erro HTTP 503 com a tela estilizada de manutenção.
3. **Desative a manutenção** para retornar ao normal:
   ```bash
   bash scripts/maintenance_off.sh
   ```
4. **Recarregue a página** `http://localhost` para confirmar que a aplicação voltou a funcionar normalmente.

---

## Parar e Limpar

| Ação | Comando |
|---|---|
| Parar containers (mantém dados) | `docker compose -f docker-compose.prod.yml stop` |
| Parar e remover containers (mantém dados) | `docker compose -f docker-compose.prod.yml down` |
| Parar e **apagar tudo** (inclusive banco) | `docker compose -f docker-compose.prod.yml down -v` |
| Ver logs em tempo real | `docker compose -f docker-compose.prod.yml logs -f` |

---

## Solução de Problemas Comuns

### Porta 80 em uso
```bash
# Verificar o que está usando a porta 80
sudo lsof -i :80
# Parar o serviço (ex: Apache)
sudo systemctl stop apache2
```

### Container `web` não inicia
Verifique os logs:
```bash
docker compose -f docker-compose.prod.yml logs web --tail=30
```
Causa comum: banco de dados ainda inicializando. Aguarde alguns segundos e tente novamente:
```bash
docker compose -f docker-compose.prod.yml restart web
```

### Erro `ModuleNotFoundError: No module named 'distutils'`
Se rodar fora do Docker em Ubuntu 24.04+ (Python 3.12+):
```bash
sudo apt install python3-setuptools
```
**Nota:** O ambiente Docker já possui essa correção.

### Imagens ou estilos não atualizam após rebuild
O Docker volume `static_volume` **persiste os arquivos estáticos** entre builds. Se você alterou uma imagem ou CSS e o site ainda mostra a versão antiga, force a atualização:
```bash
docker compose -f docker-compose.prod.yml exec web python manage.py collectstatic --noinput --clear
```
O `--clear` apaga os arquivos antigos do volume e recopia todos os estáticos da nova imagem.
