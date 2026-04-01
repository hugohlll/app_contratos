# 📧 Roteiro de Implementação: Gmail API em Produção

**Sistema:** Gestão de Contratos  
**Funcionalidade:** Envio automatizado de e-mails via Gmail API  
**Versão:** 1.0  
**Data:** 30/03/2026

---

## 📋 Sumário

1. [Visão Geral](#visão-geral)
2. [Pré-requisitos](#pré-requisitos)
3. [Configuração no Google Cloud](#configuração-no-google-cloud)
4. [Adaptações para Produção](#adaptações-para-produção)
5. [Configuração do Ambiente Docker](#configuração-do-ambiente-docker)
6. [Integração com Django](#integração-com-django)
7. [Scripts de Produção](#scripts-de-produção)
8. [Testes em Produção](#testes-em-produção)
9. [Monitoramento e Troubleshooting](#monitoramento-e-troubleshooting)
10. [Checklist de Implantação](#checklist-de-implantação)

---

## 🎯 Visão Geral

Este documento descreve o processo completo para implementar o envio automatizado de e-mails utilizando a **Gmail API** em ambiente de produção com Docker Compose.

### Por que Gmail API e não SMTP?

| Vantagem | Descrição |
|----------|-----------|
| 🔒 HTTPS | Tráfego criptografado na porta 443 |
| 🏢 Proxy-friendly | Contorna bloqueios de portas SMTP (587/465) |
| 📊 Limites maiores | Até 2.000 destinatários/dia (vs 500 do SMTP) |
| 🔐 OAuth 2.0 | Autenticação moderna e segura |

---

## ✅ Pré-requisitos

### Técnicos
- [ ] Docker Compose instalado no servidor
- [ ] Acesso ao Google Cloud Console
- [ ] Conta do Gmail corporativa para envio
- [ ] Permissões de administrador no Google Workspace (se aplicável)

### Arquivos Necessários
- [ ] `credentials.json` - Chave de API do Google Cloud
- [ ] `token.json` - Token de acesso OAuth (gerado após autenticação)

---

## 🔧 Configuração no Google Cloud

### Passo 1: Criar Projeto

1. Acesse [Google Cloud Console](https://console.cloud.google.com/)
2. Clique em **"Selecionar Projeto"** → **"Novo Projeto"**
3. Nome sugerido: `SISCONT-Notificacoes` ou `[NOME_EMPRESA]-Contratos-API`
4. Clique em **"Criar"**

### Passo 2: Ativar Gmail API

1. No menu lateral, acesse **APIs e Serviços** → **Biblioteca**
2. Pesquise por **"Gmail API"**
3. Clique em **"Ativar"**

### Passo 3: Configurar Tela de Permissão OAuth

> ⚠️ **IMPORTANTE:** Para produção, você deve solicitar verificação do app se for usar contas fora do domínio do projeto.

1. Acesse **APIs e Serviços** → **Tela de permissão OAuth**
2. Selecione **Tipo de usuário: Externo**
3. Preencha os campos obrigatórios:

| Campo | Valor Sugerido |
|-------|----------------|
| Nome do app | Sistema de Gestão de Contratos |
| E-mail de suporte | suporte@[suaempresa].com.br |
| Nome da organização | [Nome da Empresa] |
| E-mail de desenvolvimento | dev@[suaempresa].com.br |

4. **Escopos:** Adicione apenas o necessário:
   ```
   https://www.googleapis.com/auth/gmail.send
   ```

5. **Usuários de teste:**
   - **Desenvolvimento:** Adicione e-mails de teste (ex: hugohlllima@gmail.com)
   - **Produção:** Se for usar apenas contas do seu domínio Google Workspace, não é necessário listar

6. Clique em **"Salvar e Continuar"** até finalizar

### Passo 4: Criar Credenciais (Client ID)

1. Acesse **APIs e Serviços** → **Credenciais**
2. Clique em **"+ Criar Credenciais"** → **"ID do cliente OAuth"**
3. Configure:

| Campo | Valor |
|-------|-------|
| Tipo de aplicativo | **Aplicativo de computador** (Desktop) |
| Nome | siscont-producao |

4. Clique em **"Criar"**
5. **Baixe o JSON** imediatamente (o Google só permite baixar uma vez!)
6. Renomeie para `credentials.json`

> 🔐 **Segurança:** O arquivo `credentials.json` contém segredos. Nunca o commit no Git!

---

## 🚀 Adaptações para Produção

### Diferenças: Desenvolvimento vs Produção

| Aspecto | Desenvolvimento | Produção |
|---------|-----------------|----------|
| Autenticação | Navegador local | Token pré-gerado |
| credentials.json | Pasta do projeto | Volume Docker seguro |
| token.json | Gerado automaticamente | Copiado manualmente |
| Proxy | Não necessário | Pode ser necessário |
| Logs | Console | Arquivo/Sistema centralizado |

### Fluxo de Autenticação em Produção

```
┌─────────────────────────────────────────────────────────────┐
│  AMBIENTE DE DESENVOLVIMENTO (Máquina Local)                │
│  1. Executa script de autenticação com navegador            │
│  2. Faz login no Google e concede permissão                 │
│  3. Gera arquivo token.json                                 │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
                    [Copiar arquivos]
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│  AMBIENTE DE PRODUÇÃO (Servidor Docker)                     │
│  1. Recebe credentials.json + token.json                    │
│  2. Container lê token.json diretamente                     │
│  3. Envia e-mails sem interação manual                      │
│  4. Token é renovado automaticamente via refresh_token      │
└─────────────────────────────────────────────────────────────┘
```

---

## 🐳 Configuração do Ambiente Docker

### 1. Estrutura de Volumes Seguros

```yaml
# docker-compose.prod.yml
services:
  web:
    volumes:
      # NÃO monte .:/app no docker-compose. Use apenas arquivos específicos:
      - static_volume:/app/staticfiles
      - ./secrets/credentials.json:/app/credentials.json:ro
      # token.json SEM :ro — precisa de escrita para renovação automática do OAuth
      - ./secrets/token.json:/app/token.json
    environment:
      - GMAIL_CREDENTIALS_PATH=/app/credentials.json
      - GMAIL_TOKEN_PATH=/app/token.json
```

### 2. Configuração de DNS (Essencial para Produção)

```yaml
services:
  web:
    dns:
      - 8.8.8.8
      - 8.8.4.4
      - 1.1.1.1
```

### 3. Configuração de Proxy Corporativo (Se Aplicável)

Se sua empresa usa proxy para saída de internet:

```yaml
services:
  web:
    environment:
      - HTTP_PROXY=http://proxy.suaempresa.com.br:8080
      - HTTPS_PROXY=http://proxy.suaempresa.com.br:8080
      - NO_PROXY=localhost,127.0.0.1,db
```

### 4. Dockerfile de Produção

```dockerfile
# Dockerfile.prod
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

WORKDIR /app

# Instalação de dependências do sistema para PostgreSQL e Cron
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev gcc cron \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# Instalação de dependências Python
COPY requirements.txt .
RUN pip install --no-cache-dir setuptools -r requirements.txt
RUN pip install gunicorn

# Cópia do código fonte (Certifique-se de que secrets/ está no .dockerignore)
COPY . .

# Execução do Collectstatic (Agrupar ficheiros CSS/JS)
RUN python manage.py collectstatic --noinput

# Inicialização com Gunicorn (Apontando para core.wsgi)
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "3", "core.wsgi:application"]
```

---

## 🔗 Integração com Django

### 1. Módulo de E-mail (`contratos/utils_gmail.py`)

```python
"""
Módulo utilitário para envio de e-mails via Gmail API
"""
import os
import base64
import logging
from email.message import EmailMessage
from django.conf import settings
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

logger = logging.getLogger(__name__)

SCOPES = ['https://www.googleapis.com/auth/gmail.send']

class GmailAPIClient:
    """Cliente para envio de e-mails via Gmail API"""
    
    def __init__(self):
        self.credentials_path = getattr(
            settings, 
            'GMAIL_CREDENTIALS_PATH', 
            os.path.join(settings.BASE_DIR, 'credentials.json')
        )
        self.token_path = getattr(
            settings, 
            'GMAIL_TOKEN_PATH', 
            os.path.join(settings.BASE_DIR, 'token.json')
        )
        self._service = None
    
    def autenticar(self):
        """Autentica e retorna serviço Gmail"""
        if self._service:
            return self._service
            
        creds = None
        
        if os.path.exists(self.token_path):
            creds = Credentials.from_authorized_user_file(
                self.token_path, 
                SCOPES
            )
        
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                try:
                    creds.refresh(Request())
                    # Salva token renovado
                    with open(self.token_path, 'w') as token:
                        token.write(creds.to_json())
                except Exception as e:
                    logger.error(f"Falha ao renovar token: {e}")
                    raise
            else:
                raise RuntimeError(
                    "Token inválido. É necessário reautenticar manualmente."
                )
        
        self._service = build('gmail', 'v1', credentials=creds)
        return self._service
    
    def enviar_email(self, destinatario, assunto, mensagem, remetente=None):
        """
        Envia um e-mail
        
        Args:
            destinatario: E-mail do destinatário
            assunto: Assunto do e-mail
            mensagem: Corpo do e-mail (texto puro)
            remetente: E-mail do remetente (opcional)
        
        Returns:
            dict: {'status': 'sucesso', 'id_mensagem': '...'}
        
        Raises:
            GmailAPIError: Em caso de falha no envio
        """
        try:
            service = self.autenticar()
            
            email_msg = EmailMessage()
            email_msg.set_content(mensagem)
            email_msg['To'] = destinatario
            email_msg['From'] = remetente or settings.EMAIL_PADRAO
            email_msg['Subject'] = assunto
            
            encoded_message = base64.urlsafe_b64encode(
                email_msg.as_bytes()
            ).decode()
            
            response = service.users().messages().send(
                userId="me", 
                body={'raw': encoded_message}
            ).execute()
            
            logger.info(f"E-mail enviado para {destinatario}. ID: {response['id']}")
            
            return {
                'status': 'sucesso',
                'id_mensagem': response['id']
            }
            
        except HttpError as error:
            logger.error(f"Erro na Gmail API: {error}")
            raise GmailAPIError(f"Erro na API: {error}")
        except Exception as e:
            logger.error(f"Erro inesperado: {e}")
            raise GmailAPIError(f"Erro inesperado: {e}")
    
    def enviar_email_html(self, destinatario, assunto, texto, html, remetente=None):
        """
        Envia e-mail com versão HTML e texto puro
        """
        try:
            service = self.autenticar()
            
            email_msg = EmailMessage()
            email_msg.set_alternatives(
                [(texto, 'plain'), (html, 'html')]
            )
            email_msg['To'] = destinatario
            email_msg['From'] = remetente or settings.EMAIL_PADRAO
            email_msg['Subject'] = assunto
            
            encoded_message = base64.urlsafe_b64encode(
                email_msg.as_bytes()
            ).decode()
            
            response = service.users().messages().send(
                userId="me", 
                body={'raw': encoded_message}
            ).execute()
            
            logger.info(f"E-mail HTML enviado para {destinatario}. ID: {response['id']}")
            
            return {
                'status': 'sucesso',
                'id_mensagem': response['id']
            }
            
        except Exception as e:
            logger.error(f"Erro ao enviar e-mail HTML: {e}")
            raise GmailAPIError(f"Erro ao enviar e-mail HTML: {e}")


class GmailAPIError(Exception):
    """Exceção personalizada para erros da Gmail API"""
    pass


# Instância singleton para reutilização
gmail_client = GmailAPIClient()
```

### 2. Configurações no `settings.py`

```python
# core/settings.py

# Configurações Gmail API
GMAIL_CREDENTIALS_PATH = os.getenv('GMAIL_CREDENTIALS_PATH', os.path.join(BASE_DIR, 'credentials.json'))
GMAIL_TOKEN_PATH = os.getenv('GMAIL_TOKEN_PATH', os.path.join(BASE_DIR, 'token.json'))
EMAIL_PADRAO = os.getenv('EMAIL_PADRAO', 'notificacoes@suaempresa.com.br')

# Logging para e-mails
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'email_file': {
            'level': 'INFO',
            'class': 'logging.FileHandler',
            'filename': os.path.join(BASE_DIR, 'logs', 'email.log'),
        },
    },
    'loggers': {
        'contratos.utils.email': {
            'handlers': ['email_file'],
            'level': 'INFO',
            'propagate': False,
        },
    },
}
```

### 3. Management Command para Testes

```python
# contratos/management/commands/testar_email.py

from django.core.management.base import BaseCommand
from contratos.utils_gmail import gmail_client, GmailAPIError

class Command(BaseCommand):
    help = 'Testa envio de e-mail via Gmail API'

    def add_arguments(self, parser):
        parser.add_argument(
            '--destinatario',
            type=str,
            help='E-mail do destinatário para teste'
        )

    def handle(self, *args, **options):
        destinatario = options.get('destinatario') or 'teste@suaempresa.com.br'
        
        self.stdout.write(f'Enviando e-mail de teste para {destinatario}...')
        
        try:
            resultado = gmail_client.enviar_email(
                destinatario=destinatario,
                assunto='[TESTE] Gmail API - Produção',
                mensagem='Este é um e-mail de teste da integração com Gmail API.'
            )
            
            self.stdout.write(
                self.style.SUCCESS(f"✓ E-mail enviado com sucesso! ID: {resultado['id_mensagem']}")
            )
            
        except GmailAPIError as e:
            self.stdout.write(
                self.style.ERROR(f"✗ Erro ao enviar e-mail: {e}")
            )
```

### 4. Task Assíncrona (Opcional - Requer configuração de Celery)

> 💡 **Nota:** O projeto atual ainda não possui Celery configurado. Esta seção é opcional e para referência futura.

```python
# contratos/tasks.py

from celery import shared_task
from contratos.utils_gmail import gmail_client, GmailAPIError
import logging

logger = logging.getLogger(__name__)

@shared_task(bind=True, max_retries=3)
def enviar_notificacao_vencimento(self, contrato_id, destinatario, dias_para_vencimento):
    """
    Task assíncrona para notificação de vencimento de contrato
    """
    try:
        from contratos.models import Contrato
        contrato = Contrato.objects.get(id=contrato_id)
        
        assunto = f'[ALERTA] Vencimento de Contrato - {dias_para_vencimento} dias'
        mensagem = f"""
Olá,

O contrato abaixo está próximo do vencimento:

Contrato: {contrato.numero}
Fornecedor: {contrato.fornecedor}
Valor: R$ {contrato.valor:.2f}
Vencimento: {contrato.data_vencimento.strftime('%d/%m/%Y')}

Prazo restante: {dias_para_vencimento} dias úteis.

Atenciosamente,
Sistema de Gestão de Contratos
        """
        
        resultado = gmail_client.enviar_email(
            destinatario=destinatario,
            assunto=assunto,
            mensagem=mensagem
        )
        
        logger.info(f"Notificação enviada para contrato {contrato_id}: {resultado}")
        return resultado
        
    except Exception as e:
        logger.error(f"Erro ao enviar notificação: {e}")
        # Reagendar task em caso de falha
        raise self.retry(exc=e, countdown=300)  # Tenta novamente em 5 minutos
```

---

## 📜 Scripts de Produção

### 1. Script de Autenticação Inicial

Execute este script **apenas uma vez** em máquina local para gerar o `token.json`:

```python
# scripts/autenticar_gmail.py
"""
Script para gerar token.json inicial
Execute APENAS uma vez em máquina com navegador
"""
import os
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ['https://www.googleapis.com/auth/gmail.send']

def main():
    print("=" * 60)
    print("AUTENTICAÇÃO GMAIL API - GERAÇÃO DE TOKEN")
    print("=" * 60)
    
    # Verifica se credentials.json existe
    if not os.path.exists('credentials.json'):
        print("❌ Erro: credentials.json não encontrado!")
        print("Baixe o arquivo do Google Cloud Console e coloque nesta pasta.")
        return
    
    print("\n1. Abrindo navegador para autenticação...")
    print("2. Faça login com a conta do Gmail corporativa")
    print("3. Conceda a permissão de envio de e-mails")
    print("4. O navegador mostrará 'The authentication flow has completed'")
    
    flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
    creds = flow.run_local_server(port=0)
    
    # Salva token
    with open('token.json', 'w') as token:
        token.write(creds.to_json())
    
    print("\n✅ Token gerado com sucesso!")
    print("📁 Arquivo salvo: token.json")
    print("\nPróximos passos:")
    print("1. Copie credentials.json e token.json para o servidor de produção")
    print("2. Coloque-os na mesma pasta do manage.py")
    print("3. Reinicie o container Docker")

if __name__ == '__main__':
    main()
```

### 2. Script de Verificação de Saúde

```python
# scripts/check_gmail_health.py
"""
Script de health check para Gmail API
Use em monitoramento (cron, Kubernetes, etc.)
"""
import sys
import json
from datetime import datetime
from contratos.utils_gmail import gmail_client, GmailAPIError

def check_health():
    """Verifica se a Gmail API está funcionando"""
    resultado = {
        'timestamp': datetime.now().isoformat(),
        'status': 'ok',
        'detalhes': {}
    }
    
    try:
        # Tenta autenticar
        gmail_client.autenticar()
        resultado['detalhes']['autenticacao'] = 'ok'
        
        # Verifica validade do token
        creds = gmail_client._service._http.credentials
        if creds.expired:
            resultado['detalhes']['token'] = 'expirado'
            resultado['status'] = 'warning'
        else:
            resultado['detalhes']['token'] = 'valido'
            
    except GmailAPIError as e:
        resultado['status'] = 'error'
        resultado['detalhes']['erro'] = str(e)
    
    print(json.dumps(resultado, indent=2))
    
    # Código de saída para scripts
    if resultado['status'] == 'error':
        sys.exit(1)
    sys.exit(0)

if __name__ == '__main__':
    check_health()
```

### 3. Script de Renovação de Token

```python
# scripts/refresh_gmail_token.py
"""
Script para renovação manual do token
Use se a renovação automática falhar
"""
import os
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request

SCOPES = ['https://www.googleapis.com/auth/gmail.send']

def main():
    print("=" * 60)
    print("RENOVAÇÃO DE TOKEN - GMAIL API")
    print("=" * 60)
    
    token_path = 'token.json'
    creds_path = 'credentials.json'
    
    # Tenta renovar token existente
    if os.path.exists(token_path):
        print("\nTentando renovar token existente...")
        creds = Credentials.from_authorized_user_file(token_path, SCOPES)
        
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
                with open(token_path, 'w') as token:
                    token.write(creds.to_json())
                print("✅ Token renovado com sucesso!")
                return
            except Exception as e:
                print(f"❌ Falha na renovação: {e}")
        else:
            print("Token não pode ser renovado automaticamente.")
    
    # Gera novo token
    print("\nGerando novo token...")
    flow = InstalledAppFlow.from_client_secrets_file(creds_path, SCOPES)
    creds = flow.run_local_server(port=0)
    
    with open(token_path, 'w') as token:
        token.write(creds.to_json())
    
    print("✅ Novo token gerado!")

if __name__ == '__main__':
    main()
```

---

## 🧪 Testes em Produção

### Checklist de Testes

```markdown
## Testes Funcionais

- [ ] **Teste 1:** Envio de e-mail simples
  ```bash
  docker-compose exec web python manage.py testar_email --destinatario=admin@suaempresa.com.br
  ```

- [ ] **Teste 2:** Health check da API
  ```bash
  docker-compose exec web python scripts/check_gmail_health.py
  ```

- [ ] **Teste 3:** Verificação de logs
  ```bash
  docker-compose exec web tail -f logs/email.log
  ```

## Testes de Integração

- [ ] **Teste 5:** Notificação automática de contrato vencendo
  - Criar contrato com vencimento em 5 dias
  - Executar comando de notificação
  - Verificar recebimento do e-mail

- [ ] **Teste 6:** Notificação de contrato expirado
  - Criar contrato com vencimento no passado
  - Executar comando de notificação
  - Verificar recebimento do e-mail

## Testes de Resiliência

- [ ] **Teste 7:** Token expirado
  - Simular token expirado
  - Verificar renovação automática
  - Confirmar envio de e-mail

- [ ] **Teste 8:** Falha de rede
  - Simular indisponibilidade de rede
  - Verificar retry e logging de erro
```

### Comandos de Teste

```bash
# 1. Teste básico de envio
docker-compose exec web python manage.py testar_email \
  --destinatario="seu-email@suaempresa.com.br"

# 2. Verificar status do container
docker-compose ps

# 3. Verificar logs em tempo real
docker-compose logs -f web

# 4. Verificar logs específicos de e-mail
docker-compose exec web tail -100 logs/email.log

# 5. Health check
docker-compose exec web python scripts/check_gmail_health.py

# 6. Verificar se arquivos de credencial existem
docker-compose exec web ls -la credentials.json token.json
```

---

## 📊 Monitoramento e Troubleshooting

### Logs e Monitoramento

**Arquivo de log:** `logs/email.log`

**Padrão de log esperado:**
```
2026-03-30 14:30:00 INFO - E-mail enviado para gestor@suaempresa.com.br. ID: 19d3fc97fe97e3b1
2026-03-30 14:35:00 INFO - Token renovado automaticamente
2026-03-30 14:40:00 ERROR - Erro na Gmail API: 401 Unauthorized
```

### Problemas Comuns e Soluções

| Problema | Causa Provável | Solução |
|----------|----------------|---------|
| `NameResolutionError` | DNS não configurado | Adicionar `dns: 8.8.8.8` no docker-compose |
| `Token expired` | Token vencido sem refresh | Executar `refresh_gmail_token.py` |
| `403 Insufficient Permission` | Escopo incorreto | Verificar escopo `gmail.send` no Google Cloud |
| `Connection refused` | Proxy bloqueando | Configurar `HTTP_PROXY` e `HTTPS_PROXY` |
| `credentials.json not found` | Arquivo não montado | Verificar volumes no docker-compose |

### Comandos de Debug

```bash
# Verificar conectividade de rede
docker-compose exec web curl -I https://oauth2.googleapis.com

# Verificar variáveis de ambiente
docker-compose exec web env | grep -E "PROXY|GMAIL"

# Verificar permissões dos arquivos
docker-compose exec web ls -la credentials.json token.json

# Testar autenticação manualmente
docker-compose exec web python -c "from contratos.utils_gmail import gmail_client; gmail_client.autenticar(); print('OK')"
```

---

## ✅ Checklist de Implantação

### Pré-Implantação

- [ ] Projeto criado no Google Cloud Console
- [ ] Gmail API ativada
- [ ] Tela de permissão OAuth configurada
- [ ] Credenciais (credentials.json) geradas e baixadas
- [ ] Token inicial (token.json) gerado em máquina local
- [ ] requirements.txt atualizado com bibliotecas do Google
- [ ] docker-compose.yml configurado com DNS e volumes seguros

### Implantação

- [ ] Copiar `credentials.json` para servidor (pasta segura)
- [ ] Copiar `token.json` para servidor (pasta segura)
- [ ] Configurar permissões dos arquivos (chmod 600)
- [ ] Rebuild do container: `docker-compose build --no-cache web`
- [ ] Subir containers: `docker-compose up -d`
- [ ] Verificar status: `docker-compose ps`

### Pós-Implantação

- [ ] Executar teste de envio de e-mail
- [ ] Verificar logs de e-mail
- [ ] Confirmar recebimento dos e-mails de teste
- [ ] Configurar monitoramento (health check)
- [ ] Documentar procedimento de renovação de token
- [ ] Treinar equipe de suporte

### Segurança

- [ ] `credentials.json` e `token.json` no `.dockerignore`
- [ ] `credentials.json` e `token.json` no `.gitignore`
- [ ] Permissões restritas nos arquivos (chmod 600)
- [ ] Volumes montados como read-only (:ro)
- [ ] Segredos não expostos em logs

---

## 📞 Suporte

### Contatos Úteis

| Função | Contato |
|--------|---------|
| Admin Google Cloud | admin@suaempresa.com.br |
| Suporte Técnico | suporte@suaempresa.com.br |
| Desenvolvedor Responsável | dev@suaempresa.com.br |

### Links Úteis

- [Documentação Oficial Gmail API](https://developers.google.com/gmail/api)
- [Google Cloud Console](https://console.cloud.google.com/)
- [Quotas e Limites Gmail API](https://developers.google.com/gmail/api/limits)
- [OAuth 2.0 para Aplicativos Desktop](https://developers.google.com/identity/protocols/oauth2/native-app)

---

**Documento criado em:** 30/03/2026  
**Última atualização:** 30/03/2026  
**Versão:** 1.0
