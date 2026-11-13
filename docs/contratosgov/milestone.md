# Milestone: Integração com o Contratos.gov.br

> Criado no GitHub em 13/11/2026: milestone 2, issues #21 a #29.
> Detalhes de campos em [mapeamento-campos.md](mapeamento-campos.md).

## Descrição do milestone

**Objetivo:** manter os contratos do SISCONT sincronizados com o Contratos.gov.br via API, eliminando o cadastro e a atualização manual de contratos e empresas.

**Meta:** zero lançamentos manuais de dados que já constam no Contratos.gov.br (número, objeto, empresa, vigência, valor e termos aditivos).

**Escopo:**
- Nenhum campo é absorvido só por ter o mesmo nome nas duas aplicações. Cada campo tem o significado e a funcionalidade real validados antes de ser sincronizado, com a decisão registrada no mapeamento.
- Contratos ativos e inativos da UG do GAP-BR sincronizados diariamente, mais atualização sob demanda de um contrato.
- Integração só de leitura, apenas com os endpoints públicos (sem token): o SISCONT nunca escreve no Contratos.gov.br.
- Campos vindos do Contratos.gov.br ficam somente leitura no SISCONT. Os demais dados (PAG, comissões, Livro do Fiscal) continuam locais.
- Empresas criadas e atualizadas pelo CNPJ.
- Termos aditivos, apostilamentos e rescisões registrados no histórico do contrato; a vigência atualizada alimenta os alertas de aditivo.
- Contrato encerrado é inativado, nunca apagado. Há alerta quando ele ainda tem comissão ativa.
- Carga inicial casa os contratos existentes pelo número e CNPJ e gera relatório de divergências.
- Acesso pela internet só pelo proxy da Intraer, configurado em variável própria (sem proxy global).
- Cada execução é registrada em log, com e-mail em caso de falha ou alerta. Falha ou instabilidade da API nunca apaga nem inativa dados.

**Pré-requisitos:**
- Confirmar a UG e o acesso à API a partir do container de produção pelo proxy. Não há token a solicitar.
- Validar o significado dos campos com o responsável pela gestão de contratos (#21), antes da adaptação dos modelos.

## Issues

### #21 Mapear e validar a semântica dos campos do Contratos.gov.br `documentation`

Consolidar o mapeamento entre a API pública e os modelos do SISCONT e validar a funcionalidade real de cada campo. A mesma nomenclatura não garante o mesmo significado.

- [x] Especificação OpenAPI salva em `docs/contratosgov/`
- [x] Rascunho do mapeamento em `docs/contratosgov/mapeamento-campos.md`
- [ ] Extrair uma amostra real dos contratos da UG e confrontar, campo a campo, com a base de produção
- [ ] Analisar os campos de risco conhecido (seção 0.2): `tipo`, instrumentos incluídos, `numero`, `vigencia_fim`, valores, `processo`/`pag`, `situacao`, `fornecedor`
- [ ] Classificar cada campo (absorver, absorver com conversão, campo próprio, só referência, não absorver) na seção 0.3
- [ ] Validar as decisões com o responsável pela gestão de contratos
- [ ] Confirmar as pendências da seção 8

Só os campos com decisão registrada entram nas issues seguintes.

### #22 Cliente da API do Contratos.gov.br com proxy e modo simulado `enhancement`

Implementar o cliente da API atrás de uma interface, para que o desenvolvimento avance sem depender da disponibilidade do site.

- [ ] Proxy informado por variável própria em `.env.prod` (ex.: `CONTRATOSGOV_PROXY`), sem `HTTP_PROXY` global
- [ ] Suporte a proxy com autenticação Basic, caso o domínio deixe de ser liberado
- [ ] Modo simulado com fixtures JSON montadas a partir de respostas reais, para dev e testes
- [ ] Conversão de valores e datas (formato brasileiro, `null` como texto)
- [ ] Tratamento de erros (404/403 intermitentes, timeout, resposta HTML em vez de JSON) com novas tentativas
- [ ] Integração somente leitura: só endpoints `GET` públicos
- [ ] Testes automatizados usando o modo simulado

Depende de #21

### #23 Adaptar os modelos Contrato e Empresa para dados do Contratos.gov.br `enhancement`

- [ ] Apenas campos com decisão registrada na seção 0.3 do mapeamento
- [ ] Novos campos do contrato (seção 3 do mapeamento), incluindo `id_contratosgov`, `situacao`, `origem` e `sincronizado_em`
- [ ] Conceitos diferentes com o mesmo nome ganham campo próprio, sem reaproveitar o campo local (ex.: espécie do instrumento × `tipo` receita/despesa)
- [ ] Campos sincronizados somente leitura nos formulários e no admin para contratos de origem Contratos.gov.br
- [ ] Contratos de origem manual continuam editáveis
- [ ] Contratos inativos fora das listas de seleção (comissões, prestação de contas, Livro do Fiscal)
- [ ] Migração sem perda de dados

Depende de #21

### #24 Histórico de termos do contrato `enhancement`

- [ ] Novo modelo `TermoContrato` (seção 5 do mapeamento)
- [ ] Linha do tempo de aditivos, apostilamentos e rescisões na tela do contrato
- [ ] Vigência e valor do contrato atualizados quando houver novo termo

Depende de #23

### #25 Carga inicial e conciliação de contratos `enhancement`

- [ ] Comando de carga que casa os contratos existentes pelo número normalizado e pelo CNPJ
- [ ] Contratos encontrados recebem `id_contratosgov`; os não encontrados ficam com `origem` = `MANUAL`
- [ ] Relatório de divergências (objeto, vigência, valor, empresa) antes de sobrescrever qualquer dado
- [ ] Divergências sistemáticas (ex.: vigência sempre diferente) voltam para a análise da #21, em vez de serem sobrescritas
- [ ] Modo de simulação (`--dry-run`) para revisar o relatório sem gravar

Depende de #23

### #26 Sincronização diária dos contratos `enhancement`

Rotina automática diária que mantém os contratos da UG sincronizados.

- [ ] Comando de gerenciamento agendado no `crontab.prod`
- [ ] Criação e atualização de contratos, empresas e termos conforme o Contratos.gov.br
- [ ] Inativação (nunca exclusão) de contratos encerrados
- [ ] Alerta quando um contrato inativado tiver comissão ativa
- [ ] Execução com falha da API não altera nenhum dado

Depende de #24 e #25

### #27 Log de sincronização e e-mail de falha/alerta `enhancement`

- [ ] Registro de cada execução (início, fim, contagens, erros)
- [ ] E-mail pela fila existente (`EmailPendente`) em caso de falha ou alerta
- [ ] Data da última sincronização visível na tela de contratos

Depende de #26

### #28 Atualização sob demanda de um contrato `enhancement`

- [ ] Botão "Atualizar do Contratos.gov.br" na tela do contrato
- [ ] Busca por número (`/ugorigem/{uasg}/numeroano/{numero}`) para vincular um contrato cadastrado manualmente

Depende de #22 e #23

### #29 Implantar a integração com o Contratos.gov.br em produção `enhancement`

- [ ] Variável do proxy em `.env.prod`
- [ ] Teste de acesso a partir do container `cron` de produção
- [ ] Carga inicial revisada e aplicada
- [ ] Agendamento ativo e primeiro e-mail de log recebido

Depende de #26, #27 e #28

## Próximo milestone (fora deste): Livro do Fiscal com dados do Contratos.gov.br

Itens da seção 7 do mapeamento, a avaliar depois que a sincronização estiver estável. Cada um passa pela mesma análise de funcionalidade real (seção 0), em especial ocorrências, faturas, prepostos e responsáveis, cujos conceitos diferem entre as duas aplicações:

- Pré-preencher preposto (nome, e-mail, telefone) e notas fiscais do mês no Livro do Fiscal
- Mostrar ao fiscal as ocorrências registradas no Contratos.gov.br no período
- Relatório de divergências entre integrantes das comissões e responsáveis no Contratos.gov.br
- Alerta de vencimento de garantia contratual
- Saldo de empenho, itens, cronograma e links para documentos e publicações na tela do contrato
