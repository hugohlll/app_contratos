# Instruções para Carga Inicial de Dados em Produção

Este documento detalha o procedimento para importar os agentes (efetivo) e empresas no banco de dados de produção do projeto SISCONT.

## 1. Preparação
Certifique-se de que os arquivos abaixo estão na mesma pasta do projeto no seu servidor de produção:
- `load_data.py` (Script de importação criado)
- `efetivo_1.csv` (Planilha com dados dos militares/agentes)
- `empresas (3).csv` (Planilha com dados das empresas)

## 2. Copiando os arquivos de dados para o Container
Como o ambiente de produção isola os arquivos, precisamos copiar os arquivos de planilhas CSV para dentro do container `web`. O script de importação (`scripts/load_data.py`) já se encontra embarcado nativamente na imagem do sistema.

No terminal do servidor, na pasta do projeto (`app_contratos`), execute os comandos:

```bash
# Copiar os arquivos CSV (renomeamos o de empresas para simplificar)
docker compose -f docker-compose.prod.yml cp efetivo_1.csv web:/app/efetivo_1.csv
docker compose -f docker-compose.prod.yml cp "empresas (3).csv" web:/app/empresas.csv
```

> **Nota:** Se você não estiver usando a v2 do Docker Compose (`docker compose`), o subcomando `cp` nativo pode não funcionar diretamente no docker-compose. Nesse caso, use o `docker cp` nativo:
> `docker cp efetivo_1.csv <NOME_DO_CONTAINER_WEB>:/app/efetivo_1.csv`

## 3. Executando o Script
Agora vamos rodar o arquivo Python dentro do container para que os registros sejam validados e inseridos no Banco de Dados em produção.

Execute o seguinte comando:
```bash
docker compose -f docker-compose.prod.yml exec web python scripts/load_data.py /app/efetivo_1.csv /app/empresas.csv
```

## 4. Resultado Esperado
O script iniciará e fará as seguintes ações de forma segura (`get_or_create` que impede duplicatas em caso de interrupção):
1. **Agentes:** Ele verifica a existência dos dados pelo campo `SARAM` (Matrícula). Postos/Graduações inexistentes serão criados automaticamente.
2. **Empresas:** Ele verifica a existência pelo rastreio do campo `CNPJ`.
3. Os logs informarão na tela quantos registros foram inseridos ou atualizados, e se houve algum problema em alguma das linhas.
