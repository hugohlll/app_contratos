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
```

### 2. Construir e Subir os Containers
```bash
docker compose -f docker-compose.prod.yml up -d --build
```

### 3. Verificar se Tudo Subiu
```bash
docker compose -f docker-compose.prod.yml ps
```
Deve mostrar 3 serviços com status `Up`: **db**, **web** e **nginx**.

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
