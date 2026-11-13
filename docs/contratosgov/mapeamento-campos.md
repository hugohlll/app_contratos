# Mapeamento de campos Contratos.gov.br → SISCONT

> **Rascunho**: issue #21 do milestone *Integração com o Contratos.gov.br*.
> Fonte: especificação OpenAPI da API Contratos.gov.br 1.0 (`docs/contratosgov/contratosgov-api.openapi.json`),
> obtida em `https://contratos.comprasnet.gov.br/docs/api-docs.json` em 13/11/2026.
> Os endpoints usados aqui são **públicos** (sem token). Os de prefixo `/api/v1/...` exigem login no Contratos.gov.br e ficam de fora.
> Acesso pelo proxy da Intraer (`proxy-brasilia.intraer:8080`): o domínio passa **sem autenticação**.
> Nenhuma resposta da UG 120006 foi consultada ainda (o site estava instável no teste): formatos marcados com ⚠️ precisam ser confirmados.
>
> **Todo o mapeamento abaixo é uma hipótese.** Um campo com o mesmo nome nas duas aplicações pode ter
> significado, regra de preenchimento ou momento de atualização diferentes. Nenhum campo é absorvido antes
> de passar pela análise da seção 0.

## 0. Critério de absorção: análise de funcionalidade real

### 0.1 Etapas para cada campo

1. **Significado no Contratos.gov.br.** O que o campo representa, quem o preenche, quando é atualizado e se muda com aditivos.
2. **Significado no SISCONT.** Onde o campo é usado (telas, alertas, Livro do Fiscal, relatórios, portarias) e qual regra depende dele.
3. **Confronto com dados reais.** Comparar os valores da API com os da base de produção nos contratos da UG e listar as diferenças.
4. **Decisão,** registrada na tabela da seção 0.3:
   - **Absorver:** mesmo significado; o campo passa a vir da API e fica somente leitura.
   - **Absorver com conversão:** mesmo conceito, mas com regra de transformação documentada (formato, unidade, normalização).
   - **Campo próprio:** conceito diferente; o dado da API vai para um campo novo e o campo local fica como está.
   - **Só referência:** exibido ao usuário, sem alterar nenhum dado local.
   - **Não absorver:** sem uso, ou com risco (dado pessoal, confiabilidade).

A validação é feita com o usuário responsável pela gestão de contratos, não só com a documentação da API.

### 0.2 Campos com risco conhecido de interpretação diferente

| Campo SISCONT | Campo Contratos.gov.br | Por que precisa de análise |
|---|---|---|
| `Contrato.tipo` | `tipo` / `receita_despesa` | **Mesmo nome, conceitos diferentes.** No SISCONT, `tipo` é Receita/Despesa; na API, `tipo` é a espécie do instrumento (Contrato, Empenho, Carta Contrato…), e Receita/Despesa vem em `receita_despesa` |
| `Contrato` (o próprio registro) | registros de E1/E2 | A API inclui **empenhos com força de contrato** e outros instrumentos. Definir quais o SISCONT acompanha |
| `Contrato.numero` | `numero` | Formato diferente (`00003/2021` × `199/2024`); verificar se é sempre o mesmo número, também em contratos de receita e em instrumentos de outra UG |
| `Contrato.vigencia_fim` | `vigencia_fim` | Os alertas de aditivo (120/90 dias) dependem dela. Verificar se a API traz a vigência atual (com aditivos) ou a original, e quando é atualizada após a assinatura do termo |
| `Contrato.valor_total` | `valor_global` / `valor_inicial` / `valor_acumulado` | Três valores na API. Definir qual corresponde ao "valor total" usado no SISCONT (original, atualizado, por exercício ou acumulado) |
| `Contrato.pag` | `processo` | Pode ser o mesmo NUP ou outro processo (contratação × gestão) |
| `Contrato` ativo | `situacao` = Ativo | "Ativo" na API pode não coincidir com "vigente" (encerramento administrativo pendente, contrato vencido sem baixa). Definir a regra de inativação |
| `Empresa` | `fornecedor` | Pode ser pessoa física (CPF), consórcio ou identificador genérico (`idgener`), não só CNPJ |
| `Funcao` (gestor, fiscal…) | `responsaveis.funcao_id` | As funções e substituições do Contratos.gov.br não seguem necessariamente as funções das comissões do SISCONT |
| `Integrante.data_inicio`/`data_fim` | `responsaveis.data_inicio`/`data_fim` | Designação por portaria × período de acesso ao sistema |
| `OcorrenciaContratual` | `ocorrencias` | No Contratos.gov.br, "ocorrência" inclui atos administrativos (ex.: "EXTRATO DE CONTRATO"), não só falhas na execução (NPA 009) |
| `RegistroFatura.valor` | `faturas.valor` / `valorliquido` | Bruto × líquido de glosas e retenções; mês de referência × mês de emissão |
| `ControleExecucao.preposto_*` | `prepostos` | Preposto cadastrado no sistema × preposto formalmente aceito pelo fiscal |

### 0.3 Registro de decisões

| Campo | Decisão | Regra / observação | Validado com | Data |
|---|---|---|---|---|
| (preencher durante a #21) | | | | |

## 1. Endpoints a usar

| # | Endpoint | Uso no SISCONT |
|---|---|---|
| E1 | `GET /api/contrato/ug/{unidade_codigo}` | Contratos **ativos** da UG 120006 (sincronização diária) |
| E2 | `GET /api/contrato/inativo/ug/{unidade_codigo}` | Contratos **inativos**: detectar encerramento e rescisão |
| E3 | `GET /api/contrato/id/{contrato_id}` | Atualização sob demanda de um contrato |
| E4 | `GET /api/contrato/{contrato_id}/historico` | Termos aditivos, apostilamentos e rescisões |
| E5 | `GET /api/contrato/ugorigem/{codigo_uasg}/numeroano/{numero_contrato}` | Localizar um contrato pelo número (carga inicial e casos não encontrados) |

## 2. Modelo `Contrato`: campos existentes

> Nas seções 2 a 7, a coluna "Tratamento" ou "Aproveitamento" é a **proposta inicial**. Ela só vale depois da decisão registrada na seção 0.3.

| Campo SISCONT | Origem Contratos.gov.br | Endpoint | Tratamento | Observações |
|---|---|---|---|---|
| (novo) `id_contratosgov` | `id` | E1, E2, E3 | **Chave de sincronização** | Estável; dispensa casar por número a cada execução |
| `numero` | `numero` | E1, E2 | Sincronizado, somente leitura | ⚠️ A API usa `00003/2021` (5 dígitos com zeros), a base local usa `199/2024`. Normalizar para comparar |
| `tipo` | `receita_despesa` (**não** o `tipo` da API) | E1, E2 | Sincronizado | `Despesa`/`Receita` → `DESPESA`/`RECEITA`. O `tipo` da API é a espécie do instrumento (ver 0.2). ⚠️ Confirmar se os contratos de receita da UG aparecem na API |
| `objeto` | `objeto` | E1, E2 | Sincronizado, somente leitura | Vem em caixa alta |
| `empresa` (FK) | `fornecedor.cnpj_cpf_idgener` + `fornecedor.nome` | E1, E2 | Casar `Empresa` pelo CNPJ; criar se não existir | Formato `00.000.000/0000-00`, igual ao local. ⚠️ Fornecedor pessoa física (`tipo` = `FISICA`) traz CPF |
| `vigencia_inicio` | `vigencia_inicio` | E1, E2 | Sincronizado, somente leitura | |
| `vigencia_fim` | `vigencia_fim` | E1, E2 | Sincronizado, somente leitura | Alimenta os alertas de aditivo (120/90 dias). ⚠️ Confirmar se já reflete os aditivos de prazo |
| `valor_total` | `valor_global` | E1, E2 | Sincronizado, somente leitura | ⚠️ A documentação mostra `102.000,00`: confirmar se vem como número ou como texto no formato brasileiro |
| `pag` | `processo`? | E1 | **A decidir** | ⚠️ Confirmar se o PAG é o mesmo número de processo (NUP) cadastrado no Contratos.gov.br. Se não for, continua local |

## 3. Modelo `Contrato`: campos novos propostos

| Campo novo | Origem | Uso |
|---|---|---|
| `situacao` | `situacao` + presença em E1/E2 | Ativo/Inativo; o contrato inativo sai das listas de seleção, nunca é apagado |
| `justificativa_inativo` | `justificativa_inativo` | Motivo (encerrado, rescindido…), exibido na tela do contrato |
| `processo` | `processo` | NUP do processo de contratação (ver `pag`) |
| `modalidade` | `modalidade` | Exibição (Pregão, Dispensa…) |
| `licitacao_numero` | `licitacao_numero` | Exibição |
| `amparo_legal` | `amparo_legal` | Exibição; útil no Livro do Fiscal |
| `data_assinatura` | `data_assinatura` | Exibição |
| `valor_inicial` | `valor_inicial` | Comparar com o valor global (acréscimos) |
| `prorrogavel` | `prorrogavel` | Mostrar nos alertas de aditivo se o contrato admite prorrogação |
| `origem` | — | `CONTRATOSGOV` ou `MANUAL` (cadastrados antes da carga e não encontrados) |
| `sincronizado_em` | — | Data/hora da última sincronização bem-sucedida |

Candidatos descartados por enquanto: `contratante` (sempre a própria UG), `codigo_tipo`, `subtipo`,
`categoria`, `subcategoria`, `unidades_requisitantes`, `informacao_complementar`, `codigo_modalidade`,
`unidade_compra`, `sistema_origem_licitacao`, `data_publicacao`, `num_parcelas`, `valor_parcela`, `valor_acumulado`.

## 4. Modelo `Empresa`

| Campo SISCONT | Origem | Tratamento |
|---|---|---|
| `cnpj` | `fornecedor.cnpj_cpf_idgener` | **Chave de casamento** |
| `razao_social` | `fornecedor.nome` | Sincronizado |
| `nome_fantasia` | (não há) | **Local** |

## 5. Novo modelo `TermoContrato` (histórico)

Origem: E4. Um registro por termo do contrato, só leitura.

| Campo | Origem | Observação |
|---|---|---|
| `id_contratosgov` | `id` | Chave |
| `tipo` | `tipo` | Termo Aditivo, Termo de Apostilamento, Termo de Rescisão… |
| `numero` | `numero` | |
| `qualificacao` | `qualificacao_termo[].descricao` | VIGÊNCIA, ACRÉSCIMO, REAJUSTE… |
| `data_assinatura` | `data_assinatura` | |
| `vigencia_fim` | `vigencia_fim` | Nova data de término, quando houver |
| `novo_valor_global` | `novo_valor_global` | |
| `observacao` | `observacao` | |

Uso: linha do tempo de aditivos na tela do contrato e confirmação de que o aditivo de prazo foi formalizado.

## 6. Permanece local (sem correspondente no Contratos.gov.br)

- `Contrato.pag`, se não for o NUP (ver seção 2)
- `Empresa.nome_fantasia`
- Comissões, integrantes, portarias e boletins de designação
- Prestações de contas, Livro do Fiscal (controle de execução) e apontamentos

## 7. Panorama: o que mais do SISCONT a API pública poderia fornecer

Cruzamento de todos os campos digitados hoje no SISCONT com os endpoints públicos por contrato
(`/api/contrato/{id}/...`). As seções 2 a 5 cobrem o núcleo do milestone; aqui fica o restante.

### 7.1 Livro do Fiscal (`ControleExecucao`)

| Campo SISCONT | Origem | Aproveitamento | Observações |
|---|---|---|---|
| `unidade_gestora` | `contratante.orgao.unidade_gestora` (`codigo` + `nome_resumido`) | **Total** | Hoje é fixo `120006 - GAP-BR` |
| `omap` | (não há) | Nenhum | Continua local |
| `preposto_nome` | `/prepostos` → `usuario` (nome após o CPF mascarado) | **Pré-preenchimento** | Preposto com `situacao` = Ativo no período do livro |
| `preposto_email` | `/prepostos` → `email` | **Pré-preenchimento** | |
| `preposto_telefone` | `/prepostos` → `celular` ou `telefonefixo` | **Pré-preenchimento** | |
| `preposto_cpf` | `/prepostos` → `usuario` | Nenhum | O CPF vem mascarado (`***.111.111-**`) |
| `preposto_cargo` | (não há) | Nenhum | |
| Campos de obra (ART, CNO, clima, efetivo…) | (não há) | Nenhum | |
| `relatorio_ocorrencias`, `sem_ocorrencias_periodo` | `/ocorrencias` | Só referência | Mostrar ao fiscal as ocorrências lançadas no Contratos.gov.br no mês, sem substituir o relatório |

### 7.2 Faturas do Livro do Fiscal (`RegistroFatura`)

| Campo SISCONT | Origem | Aproveitamento | Observações |
|---|---|---|---|
| `numero_nf` | `/faturas` → `numero` (+ `numero_serie`) | **Pré-preenchimento** | Filtrar por `mesref`/`anoref` = mês do livro e `nota_cancelada` = Não |
| `valor` | `/faturas` → `valor` (ou `valorliquido`) | **Pré-preenchimento** | ⚠️ Definir se o livro registra o valor bruto ou o líquido |
| `numero_ob` | (só em `/api/v1/ordembancaria/...`, com token) | Nenhum | Continua manual |

Depende de a UG lançar os instrumentos de cobrança no Contratos.gov.br. ⚠️ Verificar se o GAP faz isso para todos os contratos.

### 7.3 Ocorrências (`OcorrenciaContratual`)

| Campo SISCONT | Origem | Aproveitamento |
|---|---|---|
| `data_hora` | `/ocorrencias` → `data` | Só referência |
| `descricao` | `ocorrencia` | Só referência |
| `notificacao_emitida` | `notificapreposto` | Só referência |
| `status_ocorrencia` | `situacao` / `novasituacao` | Só referência |

O SISCONT é o registro formal do fiscal (NPA 009). Importar ocorrências criaria duplicidade. A proposta é exibi-las, não copiá-las.

### 7.4 Comissões e integrantes (`Comissao`, `Integrante`)

| Campo SISCONT | Origem | Aproveitamento | Observações |
|---|---|---|---|
| `Integrante.agente` | `/responsaveis` → `usuario` | **Conferência** | CPF mascarado + nome: casar pelos 6 dígitos centrais do `Agente.cpf` e pelo nome |
| `Integrante.funcao` | `funcao_id` (Gestor, Fiscal Técnico, Fiscal Administrativo, Substituto…) | **Conferência** | Tabela de equivalência com `Funcao` |
| `Integrante.portaria_numero` / `portaria_data` | `portaria` (texto `PORTARIA Nº 80, DE 06 DE FEVEREIRO DE 2020`) | **Conferência** | Exige extrair número e data do texto |
| `Integrante.data_inicio` / `data_fim` | `data_inicio` / `data_fim` | **Conferência** | |
| `Comissao.boletim_*`, `codigo_siloms`, cargos regimentais | (não há) | Nenhum | |

Uso: relatório de divergências entre quem está designado no SISCONT e quem consta como responsável no
Contratos.gov.br (fiscal desligado no SISCONT e ainda ativo lá, e vice-versa). Não substitui a designação
local, que é a fonte das portarias e boletins.

### 7.5 Informações novas, sem campo hoje no SISCONT

| Endpoint | Informação | Possível uso |
|---|---|---|
| `/garantias` | Tipo, valor e vencimento da garantia | Alerta de vencimento da garantia contratual |
| `/itens` | Itens, quantidades e valores unitários, com histórico por aditivo | Consulta na tela do contrato |
| `/cronograma` | Parcelas previstas por mês | Conferir o faturamento do mês no Livro do Fiscal |
| `/empenhos` | Empenhado, liquidado, pago, restos a pagar | Saldo do contrato; alerta de empenho insuficiente |
| `/publicacoes` | Extrato no DOU e link | Link na tela do contrato |
| `/arquivos` | Contrato e termos assinados (PDF) | Link para o documento |
| `/despesas_acessorias` | Despesas acessórias recorrentes | Consulta |

### 7.6 Não usar

| Endpoint | Motivo |
|---|---|
| `/terceirizados` | Traz **CPF completo e salário** dos terceirizados; sem uso no SISCONT (LGPD) |
| Endpoints `/api/v1/...` | Exigem login no Contratos.gov.br; incluem escrita (apropriação, faturas) |

## 8. Pendências para confirmar com dados reais

- [ ] UG correta: `120006` (usada no Livro do Fiscal) ou outra (ex.: UG executora distinta)
- [ ] Formato de `numero` na base de produção e regra de normalização
- [ ] Formato dos valores (`valor_global`): número JSON ou texto `102.000,00`
- [ ] Se `vigencia_fim` do contrato já incorpora os aditivos de prazo
- [ ] Se os contratos de receita da UG constam na API
- [ ] Se `pag` corresponde a `processo`
- [ ] Quantos contratos locais não têm correspondente (cadastrados só no SISCONT)
- [ ] Acesso a partir do container de produção pelo proxy (o host já passa)
- [ ] Estabilidade da API: em 13/11/2026 o site alternou entre 200, 403 e 404 em poucos minutos; a sincronização precisa tolerar falhas sem apagar nada
