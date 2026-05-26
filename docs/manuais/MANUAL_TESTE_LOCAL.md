# Manual de Teste Local (Ambiente de Desenvolvimento)

Este guia descreve como rodar o ambiente de **desenvolvimento** na sua máquina local para testes antes do deploy real.

> **⚠️ IMPORTANTE:** Todos os testes devem ser realizados usando o `docker-compose.yml` (desenvolvimento).
> **NUNCA** utilize o `docker-compose.prod.yml` para testes, pois ele se conecta aos contêineres e ao banco de dados de **produção**.

## Pré-requisitos

- Docker Desktop ou Docker Engine (v20+) com Docker Compose v2
- Git instalado
- Porta **8000** livre

## Passo a Passo

### 1. Subir o Ambiente de Desenvolvimento
```bash
docker compose up -d --build
```
> O ambiente de desenvolvimento utiliza o `docker-compose.yml` por padrão (não é necessário especificar `-f`).

### 2. Verificar se Tudo Subiu
```bash
docker compose ps
```
Deve mostrar 2 serviços com status `Up`: **db** e **web**.

### 3. Executar Migrações do Banco de Dados
```bash
docker compose exec web python manage.py migrate
```

### 4. Popular com Dados de Teste
Para simular um ambiente com dados realistas:
```bash
docker compose exec web python manage.py populate_db
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

> **Nota:** O comando `populate_db` **só existe no ambiente de desenvolvimento**. Ele é automaticamente removido da imagem de produção pelo `Dockerfile.prod`, tornando impossível a inserção acidental de dados fictícios no banco real.

Se preferir testar com banco limpo, pule este passo e crie apenas um superusuário:
```bash
docker compose exec web python manage.py createsuperuser
```

### 5. Acessar a Aplicação
Abra o navegador em: **[http://localhost:8000](http://localhost:8000)**

> O ambiente de desenvolvimento roda na porta **8000** (via `runserver` do Django).
> O ambiente de produção roda na porta **80** (via Nginx + Gunicorn).

### 6. Verificar Isolamento (Opcional)
Para confirmar que o ambiente de teste está isolado da produção, execute:
```bash
bash test_isolamento.sh
```
Os 3 testes devem passar, confirmando que:
- O `populate_db.py` **não existe** na imagem de produção.
- O comando é **rejeitado** na imagem de produção.
- O comando **existe** na imagem de desenvolvimento.

---

## Diferenças entre Desenvolvimento e Produção

| Característica | Desenvolvimento | Produção |
|---|---|---|
| **Arquivo Docker Compose** | `docker-compose.yml` | `docker-compose.prod.yml` |
| **Servidor Web** | Django `runserver` | Nginx + Gunicorn |
| **Porta** | 8000 | 80 |
| **Banco de dados** | `gestao_contratos_db` | `siscont_db` |
| **Volume do banco** | `siscont_pg_data_dev` | `siscont_pg_data_prod` |
| **Nome do projeto Docker** | `siscont_dev` | `siscont_prod` |
| **DEBUG** | `True` | `False` |
| **Comando `populate_db`** | ✅ Disponível | ❌ Removido da imagem |
| **Hot Reload** | ✅ Sim (código atualiza ao vivo) | ❌ Não (requer rebuild) |

---

## Parar e Limpar

| Ação | Comando |
|---|---|
| Parar containers (mantém dados) | `docker compose stop` |
| Parar e remover containers (mantém dados) | `docker compose down` |
| Parar e **apagar tudo** (inclusive banco de dev) | `docker compose down -v` |
| Ver logs em tempo real | `docker compose logs -f` |

> **Nota:** O comando `docker compose down -v` no ambiente de desenvolvimento apaga **apenas** o volume `siscont_pg_data_dev`. O banco de produção (`siscont_pg_data_prod`) **não é afetado**.

---

## Solução de Problemas Comuns

### Erro de DNS durante o build (`Could not resolve 'deb.debian.org'`)
O Docker pode ter problemas de resolução DNS durante o build. O `docker-compose.yml` já está configurado com `network: host` na fase de build para contornar isso. Se o erro persistir:
```bash
docker compose build --no-cache
```

### Porta 8000 em uso
```bash
# Verificar o que está usando a porta 8000
sudo lsof -i :8000
```

### Container `web` não inicia
Verifique os logs:
```bash
docker compose logs web --tail=30
```
Causa comum: banco de dados ainda inicializando. Aguarde alguns segundos e tente novamente:
```bash
docker compose restart web
```

### Erro `ModuleNotFoundError: No module named 'distutils'`
Se rodar fora do Docker em Ubuntu 24.04+ (Python 3.12+):
```bash
sudo apt install python3-setuptools
```
**Nota:** O ambiente Docker já possui essa correção.
