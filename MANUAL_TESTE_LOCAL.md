# Manual de Teste Local em Produção (Simulação)

Este guia descreve como rodar o ambiente de produção (Docker + Nginx + Gunicorn + Postgres) na sua máquina local para testes antes do deploy real.

## Pré-requisitos

- Docker Desktop ou Docker Engine instalado
- Git instalado

## Passo a Passo

1. **Configurar Variáveis de Ambiente**
   Crie um arquivo `.env.prod` na raiz do projeto com o seguinte conteúdo (ajuste as senhas se desejar):

   ```env
   DEBUG=False
   SECRET_KEY=sua_chave_secreta_teste
   DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1
   
   POSTGRES_USER=admin
   POSTGRES_PASSWORD=admin
   POSTGRES_DB=siscont_db
   
   DATABASE_URL=postgres://admin:admin@db:5432/siscont_db
   ```

2. **Construir e Subir os Containers**
   Execute o seguinte comando para construir as imagens e iniciar os serviços:

   ```bash
   docker-compose -f docker-compose.prod.yml up -d --build
   ```

3. **Executar Migrações do Banco de Dados**
   Para criar as tabelas no banco de dados (que inicia vazio):

   ```bash
   docker-compose -f docker-compose.prod.yml exec web python manage.py migrate
   ```

4. **Criar Superusuário**
   Para acessar o painel administrativo (`/admin`):

   ```bash
   docker-compose -f docker-compose.prod.yml exec web python manage.py createsuperuser
   ```

5. **Acessar a Aplicação**
   Abra o navegador em: [http://localhost](http://localhost)

## Parar e Limpar

Para parar os serviços e remover os volumes (apagando todos os dados do banco de teste):

```bash
docker-compose -f docker-compose.prod.yml down -v
```
