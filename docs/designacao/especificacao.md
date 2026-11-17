# Escala de designação de comissões: especificação

Este documento é a referência das regras da escala de designação de fiscais e membros de comissão. Ele registra as decisões tomadas na sessão de levantamento de requisitos de novembro de 2026. As issues do milestone "Escala de designação de comissões" apontam para as seções daqui.

## 1. Objetivo e princípios

- **Distribuir a carga de forma justa**, sem sobrecarregar uns em detrimento da folga de outros.
- **Direcionar os mais capacitados para os contratos de maior complexidade e risco**, sem penalizá-los com carga excessiva justamente por serem capacitados.
- **O sistema propõe e o gestor decide.** Neste milestone o sistema **não lança designações automaticamente**. Ele gera a proposta, e as designações continuam sendo lançadas manualmente (seção 9).
- **A regra precisa ser explicável.** Toda posição na proposta mostra os motivos.
- **Os parâmetros são configuráveis.** Pesos, fatores, margem, teto e faixas ficam numa tela de parâmetros, não no código.

## 2. Glossário

| Termo | Significado |
|---|---|
| Peso | Nota de 1 a 5 de uma comissão. Representa ao mesmo tempo complexidade, risco e esforço. Um peso 4 corresponde a aproximadamente o trabalho de dois de peso 2. |
| Fator da função | Multiplicador do peso conforme a função exercida na comissão. |
| Pontuação (carga) | Soma de peso × fator de todas as designações ativas do militar. |
| Média (carga-alvo) | Pontuação total ativa dividida pelo número de militares aptos. É a mesma para todos, independentemente do nível. |
| Teto | Média × (1 + percentual configurável). |
| Nível | Capacitação do militar, de 1 a 5, atribuída manualmente. |
| Área de conhecimento | TI, Engenharia, Educação Física, Saúde etc. O militar possui áreas, e o contrato pode exigi-las ou preferi-las. |
| Chefe da comissão | A função que dirige a comissão: Fiscal na fiscalização, Presidente nas demais. |
| Margem | Tolerância de pontuação, contada a partir do candidato com menor pontuação, dentro da qual os candidatos são considerados praticamente empatados. |

## 3. Parametrização

### 3.1 Categorias de objeto

Cadastro editável. Cada categoria tem **peso base** e, opcionalmente, uma **área exigida padrão**. Valores iniciais:

| Categoria | Peso base | Área exigida padrão |
|---|---|---|
| Aquisição/fornecimento | 1 | – |
| Receita (cessão/permissão de uso) | 1 | – |
| Serviço contínuo sem mão de obra exclusiva | 2 | – |
| Serviço contínuo com mão de obra exclusiva | 3 | – |
| Tecnologia da informação | 3 | TI |
| Obras e serviços de engenharia | 3 | Engenharia |

### 3.2 Áreas de conhecimento

Cadastro editável. Cada área tem a marca **"reservar especialistas"** (sim/não):

- **Sim** (ex.: TI, Engenharia): os especialistas são escassos. Dentro da margem, eles ficam atrás dos não especialistas nas vagas que não exigem a área (seção 7.2).
- **Não** (ex.: Educação Física): não há prejuízo em o pessoal da área concorrer normalmente a outros contratos.

### 3.3 Funções (`Funcao`)

Novos campos (os valores abaixo são padrões, editáveis no cadastro):

- **Fator** (padrão 1,0).
- **Segue a exigência de área do contrato** (sim/não).
- **Chefe da comissão** (sim/não).

| Função | Fator | Segue a área exigida | Chefe |
|---|---|---|---|
| Fiscal | 1,0 | sim | sim |
| Presidente | 1,0 | sim | sim |
| Fiscal Técnico | 0,8 | sim | não |
| Fiscal Administrativo | 0,8 | não | não |
| Membro | 0,7 | sim | não |
| Fiscal Substituto | 0,5 | sim | não |
| Presidente Substituto | 0,5 | sim | não |

A função **Fiscal Setorial** deixa de existir. "Setorial" passa a ser só a abrangência de uma designação de Fiscal Técnico ou Administrativo (seção 4.4) e usa o fator normal da função.

> A exigência de área nas funções Presidente, Membro e Presidente Substituto só tem efeito quando a comissão exige área. O Fiscal Administrativo e o substituto dele nunca seguem a exigência de área.

### 3.4 Peso padrão por tipo de comissão

| Tipo | Peso |
|---|---|
| Fiscalização | **herda o peso do contrato** |
| Recebimento (de contrato) | 1 |
| Recebimento geral | 1 |
| Planejamento | 2 |
| Licitação/contratação | 3 |
| Avaliação | 1 |
| Exame | 1 |
| Diversas | 1 |

O peso é ajustável na criação de cada comissão.

### 3.5 Composição-modelo por tipo de comissão

Define quais vagas a proposta preenche. Exemplos iniciais:

- **Fiscalização**: Fiscal e Fiscal Substituto.
- **Fiscalização com área exigida** (TI, engenharia): Fiscal, Fiscal Substituto, Fiscal Técnico, Fiscal Administrativo e o substituto do Administrativo.
- **Recebimento**: Presidente e 2 Membros.

O gestor pode acrescentar ou remover vagas na hora de gerar a proposta.

### 3.6 Tabela de segregação

Pares de tipos de comissão que **não podem ter o mesmo militar para o mesmo contrato**. Valores iniciais, todos ativos:

- Planejamento × Fiscalização
- Licitação × Fiscalização
- Fiscalização × Recebimento

A regra só se aplica quando as comissões estão vinculadas ao mesmo contrato (seção 4.2).

### 3.7 Parâmetros globais

| Parâmetro | Padrão |
|---|---|
| 1ª faixa de valor anualizado (+1 no peso) | R$ 1.000.000 |
| 2ª faixa de valor anualizado (+2 no peso) | R$ 5.000.000 |
| Incremento por mão de obra exclusiva | já embutido na categoria |
| Incremento por essencialidade | +1 |
| Margem de empate | 2 pontos |
| Teto | média + 30% |
| Janela do histórico | 24 meses |

## 4. Classificação de contratos, comissões e militares

### 4.1 Contrato

- Novos campos: **categoria**, **essencial à operação** (sim/não), **peso sugerido** (calculado), **peso ajustado** com **justificativa**, e **áreas** no modo *exigida* ou *preferencial*.
- **Peso sugerido** = peso base da categoria + incremento da faixa de valor anualizado + 1 se essencial, limitado a 1–5.
- O peso efetivo é o ajustado, quando houver, ou o sugerido. Ele pode ser editado a qualquer tempo, e a mudança vale na hora para a escala (seção 5).
- A área exigida padrão da categoria vem preenchida, e o gestor pode alterá-la. O gestor pode também exigir ou preferir áreas em qualquer contrato. Exemplo: Educação Física **preferencial** num contrato de equipamentos de academia.
- Contratos ainda não classificados recebem o peso sugerido pelos demais critérios, com base 2, e ficam marcados como **"não revisado"**.

### 4.2 Comissões

- Comissões de **fiscalização** usam o peso e as áreas do contrato.
- **Recebimento de contrato**: o **nível exigido** é o peso do contrato, mas a **carga** gerada é o peso próprio da comissão (padrão 1).
- **Comissões "Outras"** (planejamento, licitação, avaliação, exame, diversas):
  - recebem peso (padrão por tipo, ajustável);
  - o nível exigido é igual ao peso;
  - podem ter áreas exigidas ou preferenciais;
  - têm **vínculo opcional ao contrato** que originaram, o que permite aplicar a segregação.

### 4.3 Militar (`Agente`)

- **Nível** de 1 a 5, atribuído manualmente pelo gestor. A tela mostra os elementos de apoio: posto, experiência acumulada (quantidade e peso das comissões que já integrou) e validade do curso.
- **Áreas de conhecimento**.
- **Apto a designações** (sim/não), para excluir permanentemente quem não deve entrar na escala, como o comandante ou um chefe com cargo incompatível.
- **Períodos de indisponibilidade**, com início, fim e motivo (férias, missão, curso, licença, transferência prevista).
- **Militar sem nível não aparece nas sugestões** até ser classificado.
- **Curso de gestão vencido ou inexistente não impede a designação** nem muda a posição na escala. Ele gera uma **ressalva** na proposta e uma **etiqueta** ("Sem curso válido") na designação, que aparece nos relatórios.

### 4.4 Designação (`Integrante`)

- Novo campo opcional **abrangência** (texto/setor). Quando preenchido, marca uma designação de Fiscal Técnico ou Administrativo como **setorial**, em contratos com várias áreas distintas.
- As designações existentes com a função "Fiscal Setorial" são migradas para Fiscal Técnico ou Administrativo, com a abrangência preenchida, e depois a função é desativada.

## 5. Pontuação

```
pontuação(militar) = Σ  peso_da_comissão × fator_da_função
                      (designações ativas)
```

- **Carga viva**: a pontuação é calculada a partir dos dados atuais. Se o peso de um contrato muda, a pontuação de todos os seus integrantes muda na hora.
- **Não entram na pontuação**: nível, curso, quantidade de contratos e histórico.
- **Média** = soma das pontuações dos militares aptos ÷ número de aptos.
- **Teto** = média × (1 + percentual). O teto é verificado com a **pontuação projetada**, isto é, depois de assumir a vaga.
- **Histórico** (só para desempate) = Σ peso × fator × (meses designado ÷ 12), nas designações dos últimos 24 meses.

### 5.1 Exemplo

| Comissão | Peso | Designações |
|---|---|---|
| C1 Limpeza com postos | 3 | Fiscal Borges, Substituto Alves |
| C2 Reforma do hangar | 4 | Fiscal Alves, Substituto Costa |
| C3 Elevadores | 2 | Fiscal Dias, Substituto Eloy |
| C4 Link de internet (TI) | 3 | Fiscal Técnico Borges, Fiscal Administrativo Costa |
| C5 Material de expediente | 1 | Fiscal Faria, Substituto Eloy |
| C6 Cantina (receita) | 1 | Fiscal Eloy, Substituto Faria |
| P1 Planejamento | 2 | Presidente Dias, Membro Faria |

| Militar | Cálculo | Pontos | Designações |
|---|---|---|---|
| Cap Alves | 4×1,0 + 3×0,5 | 5,5 | 2 |
| Ten Borges | 3×1,0 + 3×0,8 | 5,4 | 2 |
| SO Costa | 4×0,5 + 3×0,8 | 4,4 | 2 |
| 1S Dias | 2×1,0 + 2×1,0 | 4,0 | 2 |
| 3S Faria | 1×1,0 + 1×0,5 + 2×0,7 | 2,9 | 3 |
| 2S Eloy | 2×0,5 + 1×0,5 + 1×1,0 | 2,5 | 3 |

A média é 24,7 ÷ 6 = 4,12 e o teto é 5,35. Os mais capacitados têm menos designações e pontuação próxima à dos demais.

## 6. Elegibilidade (filtros eliminatórios)

Um candidato só entra na lista de uma vaga se passar por todos os filtros:

1. **Apto** a designações.
2. **Disponível**: nenhum período de indisponibilidade cruza o início da comissão.
3. **Nível suficiente**:
   - chefe e funções titulares: nível ≥ peso;
   - substitutos e membros: nível ≥ peso − 1.
4. **Área exigida**, quando a função segue a exigência e o contrato ou a comissão exige área.
5. **Não ocupa outra vaga** na mesma comissão.
6. **Segregação** (seção 3.6).
7. **Antiguidade**: nas vagas que não são de chefe, o candidato precisa ser **mais moderno que o chefe** da comissão.

### 6.1 Antiguidade

A antiguidade é comparada pela ordem do posto (`PostoGraduacao.senioridade`) e, dentro do mesmo posto, pela ordem manual (`Agente.ordem_manual`). Quando a integração com o SIGPES estiver pronta, o campo `antiguidade` do SIGPES substitui a ordem manual.

### 6.2 Validações bloqueantes

As regras de nível suficiente, área exigida, duplicidade, segregação e **chefe mais antigo que todos os demais integrantes** **bloqueiam o salvamento**, inclusive nos lançamentos manuais.

Conflitos que surgem **depois** do lançamento não invalidam a portaria. Exemplos: a promoção de um membro que passa o chefe, ou comissões antigas que já violavam a regra. Esses casos geram alerta no painel de pendências e sugestão de recomposição no próximo momento natural (seção 8.2).

## 7. Ordenação da proposta

### 7.1 Ordem de avaliação

1. **Teto**: primeiro os que ficam abaixo do teto depois de assumir a vaga. Os que o ultrapassariam vão para o fim, com alerta.
2. **Margem**: o candidato de menor pontuação define o limite, que é a pontuação dele + margem.
3. **Dentro da margem**, nesta ordem:
   1. tem a **área preferencial** do contrato;
   2. **não tem área reservada sobrando** (não é especialista em área reservada que a vaga não exige);
   3. **menor nível suficiente**;
   4. **menor pontuação**;
   5. **menor histórico** em 24 meses;
   6. **mais moderno**.
4. **Fora da margem**: por pontuação, com os mesmos desempates.
5. Por fim, **os que ficariam acima do teto**, com alerta.

O curso não altera a posição, só gera a ressalva. A preferência por área atua **só dentro da margem**. Se o gestor quiser direcionar com mais força, ele torna a área exigida naquele contrato.

### 7.2 Exemplo: vaga de Fiscal na C8, copeiragem e recepção com postos

O contrato é da categoria "serviço contínuo com mão de obra exclusiva", com peso 3. A vaga exige nível ≥ 3. A média da unidade é 7,0 e o teto é 9,1.

| Militar | Nível | Áreas | Pontos | Resultado |
|---|---|---|---|---|
| Maj Jorge | 5 | – | 3,0 | ❌ não apto |
| Ten Gomes | 4 | – | 8,0 | ❌ indisponível |
| SO Costa | 3 | Eng. | 6,0 | ❌ segregação (planejamento da C8) |
| 1S Dias, 2S Eloy | 2 | – | – | ❌ nível insuficiente |
| **1S Klein** | 3 | – | 6,0 | **1º** (nível exato, menor histórico) |
| SO Hilário ⚠️ sem curso | 3 | – | 6,0 | 2º |
| Cap Lopes | 4 | – | 7,0 | 3º |
| Ten Borges | 4 | TI (reservada) | 5,5 | 4º (especialista guardado) |
| Cap Alves | 5 | Eng. (reservada) | 7,0 | 5º |
| 1S Inácio ⚠️ acima do teto | 3 | – | 9,5 | 6º |

O limite da margem é 5,5 (Borges) + 2 = 7,5.

### 7.3 Exemplo: área preferencial, equipamentos de academia

O contrato tem peso 2, com Educação Física como área preferencial. Para a vaga de Fiscal, o 1S Melo (EF, nível 2, 6,5 pontos) fica à frente do 2S Eloy (sem área, nível 2, 5,0 pontos), porque os dois estão na margem (até 7,0). O SO Prado (EF, 8,0 pontos) fica fora da margem, e a afinidade não o salva.

### 7.4 Preenchimento das vagas e a regra do chefe

1. A **vaga de chefe é preenchida primeiro**, pela ordem acima.
2. As demais vagas consideram só candidatos **mais modernos que o chefe escolhido**.
3. Se alguma vaga ficar sem candidato, o sistema tenta o **próximo colocado para chefe** e registra o motivo. Exemplo: *"1S Klein preterido para Fiscal: nenhum habilitado em TI mais moderno que ele"*.
4. Se nenhuma combinação for viável, o sistema mostra a vaga que travou, e o gestor decide.

## 8. Substituições e rebalanceamento

### 8.1 Substituição do chefe

- **Afastamento temporário** (férias, missão, curso): o substituto exerce a função, sem nova designação e sem mudança de pontuação.
- **Saída definitiva**, nesta ordem de tentativa:
  1. **Promoção interna**: o substituto do chefe passa a chefe, se atender a todos os requisitos de chefe (nível ≥ peso, área exigida, ser mais antigo que os que ficam, não passar do teto). A vaga de substituto que ele deixa vai para a escala normal.
  2. **Chefe externo** pela escala, mais antigo que todos os que ficam.
  3. **Recomposição completa** da comissão, como se fosse nova, mostrando qual integrante bloqueou cada alternativa.

### 8.2 Rebalanceamento

O sistema **sugere** trocas apenas em momentos naturais: prorrogação do contrato, saída ou transferência de um integrante, ou término da designação. Ele nunca altera designações vigentes por conta própria.

Exemplo: na prorrogação da C1, ele sugeriria "substituir o Cap Alves pelo 2S Eloy no posto de substituto", porque a vaga exige só nível 2 e o Cap Alves está acima do teto.

## 9. Proposta, fotografia e lançamento

1. O gestor gera a proposta de uma comissão, nova ou em recomposição.
2. O sistema grava uma **fotografia imutável**: data, vagas, candidatos em ordem, pontuação, nível, áreas, motivos de eliminação e de posição, e alertas. A proposta pode ser **impressa ou exportada** para instruir o processo da portaria.
3. O gestor **lança as designações manualmente** pela tela atual de integrantes.
4. No lançamento, o sistema **compara com a proposta vigente** daquela comissão. Quando o militar lançado não for o 1º sugerido para a vaga, o sistema pede uma **justificativa curta**.
5. As validações bloqueantes (seção 6.2) se aplicam ao lançamento.

## 10. Painéis e alertas

- **Escala**: pontuação de cada militar, média, teto, número de designações, nível, áreas e ressalvas.
- **Alerta de teto**: militares acima do teto.
- **Alerta de cobertura**, calculado em dois recortes:
  - **por nível**: soma dos pontos das vagas que exigem nível ≥ N, dividida pelo número de militares com nível ≥ N, comparada com a média;
  - **por área**: a mesma conta para as vagas que exigem cada área.

  O alerta indica a necessidade de capacitar ou habilitar mais militares. Exemplo: *"As vagas que exigem TI somam 12 pontos e só há 1 militar habilitado em TI: 12 pontos para ele, contra a média de 7,0."*
- **Pendências de classificação**: contratos "não revisados", militares sem nível, designações "Fiscal Setorial" a migrar, comissões que violam regras (antiguidade, segregação) e conflitos supervenientes.

## 11. Auditoria e permissões

- **Administradores**: configuram parâmetros, pesos, níveis e áreas, e geram propostas.
- **Auditores**: consultam a escala, as propostas históricas e o **relatório de aderência**, que mostra:
  - percentual de designações fora da ordem sugerida, com as justificativas;
  - designações sem curso válido;
  - militares acima do teto.
- O painel de "sobrecarga" atual (`contratos/views/auditoria.py`), que conta só a função "Fiscal", é **substituído** pela escala ponderada.

## 12. Fora deste milestone

- Lançamento automático das designações a partir da proposta.
- Geração da minuta de portaria.
- Aviso por e-mail aos militares designados.
- Alimentação de disponibilidade, situação, cursos e antiguidade pelo SIGPES. Isso depende do milestone "Integração com o SIGPES".
