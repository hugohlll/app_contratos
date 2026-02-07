# Manual de Instalação e Atualização (Equipe de TI)

Este documento descreve os procedimentos para instalar, configurar e atualizar a aplicação no servidor de produção da Organização Militar.

## Requisitos do Servidor

- Sistema Operacional: Linux (Debian/Ubuntu recomendado)
- Docker Engine e Docker Compose instalados
- Acesso à Internet (para baixar imagens base e atualizações) ou repositório local configurado

## 1. Instalação Inicial

1. **Clonar o Repositório**
   Baixe o código-fonte para o diretório `/opt/app_contratos` (ou outro de sua preferência):
   ```bash
   git clone https://github.com/seu-usuario/app_contratos.git /opt/app_contratos
   cd /opt/app_contratos
   ```

2. **Configurar Variáveis de Ambiente**
   Copie o modelo de configuração e edite com os dados reais da OM:
   ```bash
   cp .env.prod.example .env.prod
   nano .env.prod
   ```
   **Atenção:**
   - `SECRET_KEY`: Use uma chave longa e aleatória.
   - `POSTGRES_PASSWORD`: Defina uma senha forte para o banco.
   - `DJANGO_ALLOWED_HOSTS`: Coloque o IP ou Domínio do servidor (ex: `10.0.0.5,portal.om.eb.mil.br`).

3. **Iniciar a Aplicação**
   ```bash
   docker-compose -f docker-compose.prod.yml up -d --build
   ```

4. **Inicializar o Banco de Dados**
   ```bash
   docker-compose -f docker-compose.prod.yml exec web python manage.py migrate
   ```

5. **Criar o Primeiro Administrador**
   ```bash
   docker-compose -f docker-compose.prod.yml exec web python manage.py createsuperuser
   ```

---

## 2. Procedimento de Atualização

Sempre que houver uma nova versão do sistema (commit no Git), siga estes passos:

1. **Baixar Atualizações**
   ```bash
   cd /opt/app_contratos
   git pull origin master
   ```

2. **Reconstruir e Reiniciar Containers**
   Isso garante que novas dependências e alterações de código sejam aplicadas:
   ```bash
   docker-compose -f docker-compose.prod.yml up -d --build
   ```

3. **Aplicar Migrações (Se houver)**
   Caso a atualização envolva mudanças no banco de dados:
   ```bash
   docker-compose -f docker-compose.prod.yml exec web python manage.py migrate
   ```

4. **Coletar Arquivos Estáticos (Opcional, mas recomendado)**
   Geralmente o build já faz isso, mas para garantir:
   ```bash
   docker-compose -f docker-compose.prod.yml exec web python manage.py collectstatic --noinput
   ```

---

## 3. Comandos Úteis de Manutenção

- **Verificar Logs (Erros):**
  ```bash
  docker-compose -f docker-compose.prod.yml logs -f --tail=50
  ```

- **Backup do Banco de Dados:**
  ```bash
  docker-compose -f docker-compose.prod.yml exec db pg_dump -U admin siscont_db > backup_$(date +%F).sql
  ```

- **Reiniciar Serviços:**
  ```bash
  docker-compose -f docker-compose.prod.yml restart
  ```
