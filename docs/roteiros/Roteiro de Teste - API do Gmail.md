# **Roteiro de Teste: Envio de E-mails via Gmail API (HTTPS)**

Este documento descreve o passo a passo para configurar e testar o envio automatizado de e-mails utilizando a API do Gmail com Python. Essa abordagem foi escolhida por utilizar tráfego HTTPS (porta 443), permitindo contornar bloqueios de portas SMTP (587/465) comuns em firewalls e proxies de redes corporativas.

## **Passo 1: Configuração do Projeto no Google Cloud**

1. Acesse o [Google Cloud Console](https://console.cloud.google.com/).  
2. Crie um novo projeto (ex: SISCONT-Notificacoes ou Agente-IA-Alertas).  
3. No menu lateral, acesse **APIs e Serviços \> Biblioteca**.  
4. Pesquise por **Gmail API** e clique em **Ativar**.

## **Passo 2: Configuração da Tela de Permissão OAuth**

Como estamos em fase de desenvolvimento e validação técnica:

1. Acesse **APIs e Serviços \> Tela de permissão OAuth**.  
2. Selecione o tipo de usuário como **Externo** e clique em Criar.  
3. Preencha os campos obrigatórios (Nome do App, E-mail de suporte).  
4. Na etapa de **Escopos**, adicione o escopo: https://www.googleapis.com/auth/gmail.send.  
5. **MUITO IMPORTANTE:** Na etapa de **Usuários de teste**, adicione o seu e-mail pessoal do Gmail. *Apenas os e-mails listados aqui conseguirão autorizar o envio durante a fase de testes.*

## **Passo 3: Geração das Credenciais (Client ID)**

1. Acesse **APIs e Serviços \> Credenciais**.  
2. Clique em **\+ Criar Credenciais** e escolha **ID do cliente OAuth**.  
3. Em "Tipo de aplicativo", selecione **Aplicativo de computador** (ou *Desktop App*). Essa escolha evita problemas de redirecionamento (localhost) no nosso script.  
4. Dê um nome (ex: siscont\_python) e clique em Criar.  
5. Uma janela pop-up será exibida com a confirmação ("Cliente OAuth criado").  
6. Clique no botão **Baixar o JSON** no canto inferior esquerdo desta janela.  
7. Renomeie o arquivo baixado para credentials.json e coloque-o na pasta onde você criará o script Python.

**Atenção:** O Google só permite baixar o JSON com a chave secreta neste exato momento da criação. Se perder a tela, será necessário gerar uma nova chave secreta (*Add secret*).

## **Passo 4: Preparação do Ambiente Local**

No terminal da sua máquina de desenvolvimento, instale as bibliotecas oficiais do Google para Python:

pip install \--upgrade google-api-python-client google-auth-httplib2 google-auth-oauthlib

## **Passo 5: O Script de Teste (Local)**

Crie um arquivo chamado teste\_email.py na mesma pasta do seu credentials.json e insira o código abaixo. Lembre-se de substituir os e-mails na seção de Construção da Mensagem.

import os  
import base64  
from email.message import EmailMessage  
from google.oauth2.credentials import Credentials  
from google\_auth\_oauthlib.flow import InstalledAppFlow  
from google.auth.transport.requests import Request  
from googleapiclient.discovery import build  
from googleapiclient.errors import HttpError

\# Escopo restrito apenas para envio de e-mails  
SCOPES \= \['\[https://www.googleapis.com/auth/gmail.send\](https://www.googleapis.com/auth/gmail.send)'\]

def autenticar\_gmail():  
    creds \= None  
    \# Verifica se já existe um token salvo de um login anterior  
    if os.path.exists('token.json'):  
        creds \= Credentials.from\_authorized\_user\_file('token.json', SCOPES)  
      
    \# Se não houver credenciais válidas, solicita o login  
    if not creds or not creds.valid:  
        if creds and creds.expired and creds.refresh\_token:  
            creds.refresh(Request())  
        else:  
            flow \= InstalledAppFlow.from\_client\_secrets\_file('credentials.json', SCOPES)  
            \# A porta 0 busca uma porta local livre automaticamente  
            creds \= flow.run\_local\_server(port=0)  
          
        \# Salva as credenciais para as próximas execuções invisíveis  
        with open('token.json', 'w') as token:  
            token.write(creds.to\_json())  
              
    return creds

def enviar\_email\_teste():  
    try:  
        creds \= autenticar\_gmail()  
        service \= build('gmail', 'v1', credentials=creds)

        \# Construção da mensagem  
        mensagem \= EmailMessage()  
        mensagem.set\_content('Olá\! Este é um teste automatizado de envio de e-mail disparado via API.')  
          
        \# SUBSTITUA AQUI PELOS SEUS E-MAILS DE TESTE  
        mensagem\['To'\] \= 'seu-email-pessoal@gmail.com'  
        mensagem\['From'\] \= 'seu-email-pessoal@gmail.com'  
        mensagem\['Subject'\] \= '\[Teste\] Validação de disparo via Gmail API'

        \# Codificação exigida pela API do Gmail  
        encoded\_message \= base64.urlsafe\_b64encode(mensagem.as\_bytes()).decode()  
        create\_message \= {'raw': encoded\_message}

        \# Executa o envio  
        send\_message \= service.users().messages().send(userId="me", body=create\_message).execute()  
          
        print(f"Sucesso\! E-mail enviado. ID da mensagem: {send\_message\['id'\]}")

    except HttpError as error:  
        print(f"Ocorreu um erro na API: {error}")  
    except Exception as e:  
        print(f"Erro inesperado: {e}")

if \_\_name\_\_ \== '\_\_main\_\_':  
    enviar\_email\_teste()

## **Passo 6: Executando e Autorizando o App**

1. Execute o script no terminal: python teste\_email.py.  
2. O seu navegador padrão será aberto automaticamente.  
3. Escolha a sua conta do Gmail (a mesma cadastrada como Usuário de Teste no Passo 2).  
4. Como o aplicativo ainda está em fase de teste, o Google exibirá a tela "O Google não verificou este app".  
5. Clique em **Avançado** e depois em **Acessar \[Nome\_do\_seu\_app\] (não seguro)**.  
6. Clique em **Continuar** para conceder a permissão de envio de e-mails.  
7. O navegador exibirá uma mensagem de sucesso ("The authentication flow has completed"). Pode fechar a aba.  
8. Verifique o seu terminal: a mensagem de sucesso com o ID do e-mail deverá aparecer.  
9. Verifique sua caixa de entrada para confirmar o recebimento\!

## **Passo 7: Próximos Passos (Produção / Proxy)**

Após o Passo 6, um arquivo chamado token.json será criado na sua pasta. **Esse é o arquivo de ouro.**

Quando você for implementar essa rotina no servidor oficial da empresa (que roda atrás de um proxy corporativo e não possui navegador), você não fará mais o login manual. Você apenas precisará:

1. Copiar os arquivos credentials.json e token.json para o servidor.  
2. Garantir que as variáveis de ambiente de proxy (http\_proxy e https\_proxy) estejam configuradas no sistema operacional do servidor ou no próprio script Python (via os.environ).  
3. O script lerá o token.json e fará os disparos silenciosamente usando HTTPS, passando tranquilamente pelo proxy.