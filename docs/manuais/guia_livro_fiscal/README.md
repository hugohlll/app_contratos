# Guia Ilustrado do Livro do Fiscal Digital (SISCONT / GAP-BR)

Este diretório contém o **Guia Ilustrado do Livro do Fiscal Digital — Versão 2.0**, elaborado pela **Assessoria de Controle Interno (ACI)** do Grupamento de Apoio de Brasília (GAP-BR) para orientar os fiscais de contratos administrativos quanto ao preenchimento, ateste e consolidação do Livro do Fiscal, em cumprimento ao art. 117 da Lei nº 14.133/2021 e à NPA 009/SCON/2025.

---

## 🚀 Principais Novidades da Versão 2.0

1. **Fluxo Unificado de Ocorrências:** Fim da separação entre "Caso 1 (Tempestivo)" e "Caso 2 (Extemporâneo)". A gestão de ocorrências é centralizada na interface `/execucao/fiscais/<id>/ocorrencias/`, com roteamento automático baseado na data do fato gerador.
2. **Remoção dos Rótulos de Tempestividade:** Eliminação dos badges visuais de tempestividade (*"Tempestivo"* e *"Agrupado / Extemporâneo"*) da interface gráfica e do espelho em PDF do SILOMS.
3. **Novo Modal de Finalização/Ateste e Diálogo com a ACI:** Introdução do campo opcional *"Observações para a ACI (Trâmites)"*, permitindo troca de mensagens direta e contextualizada com a equipe de controle interno, sem poluir as observações do Livro formal ("Nada mais a declarar").
4. **Formato Otimizado (30 Slides):** Apresentação concisa e direta em 30 slides no formato **A4 Paisagem (1 passo por slide)**, eliminando redundâncias e focando na jornada operacional prática do fiscal.

---

## 📁 Estrutura de Arquivos

| Arquivo / Diretório | Descrição |
| :--- | :--- |
| **`Apresentacao_Pratica_Fiscal_v2.0.pdf`** | **Apresentação Didática de Capacitação Rápida para Fiscais em PDF (14 slides Widescreen 16:9)**. Foco na utilização prática: como lançar ocorrências contínuas (técnicas e administrativas), fechamento e ateste mensal com o campo de trâmites da ACI e acompanhamento de auditoria/saneamento de apontamentos. |
| **`apresentacao_pratica_fiscal.html`** | Código-fonte em HTML5/CSS3 da apresentação didática widescreen 16:9 para treinamento e capacitação rápida de fiscais de contrato. |
| **`Apresentacao_Livro_do_Fiscal_v2.0.pdf`** | **Apresentação Executiva Institucional em PDF (15 slides Widescreen 16:9)** voltada para divulgação e incentivo à adesão. Foco estratégico nos benefícios do sistema vs. riscos do método manual "por conta própria". |
| **`apresentacao_livro_fiscal.html`** | Código-fonte em HTML5/CSS3 da apresentação executiva institucional widescreen 16:9. |
| **`Guia_Ilustrado_Livro_do_Fiscal_v2.0.pdf`** | **Manual Operacional Completo em PDF (30 slides A4 Paisagem, 1 passo por slide)** detalhando o passo a passo com capturas de tela anotadas com pins e legendas operacionais. |
| **`guia_livro_fiscal.html`** | Código-fonte em HTML5/CSS3 do manual operacional de 30 slides em A4 paisagem. |
| **`img/`** | Diretório com todas as capturas de tela em alta resolução (DPI 2x) devidamente anotadas com marcadores numéricos (① ② ③ ④ ⑤) e espelhos do PDF oficial extraídos em alta fidelidade. |
| `Guia_Ilustrado_Livro_do_Fiscal_v1.0.pdf` | Versão legada do guia operacional (40 slides, mantida para fins de histórico e auditoria). |

---

## 🎯 Conteúdo dos Slides (30 Slides &bull; 1 Passo por Slide)

### Seção I — Capa, Visão Geral e Fundamentação Jurídica
1. **Slide 1 — Capa Oficial:** Identificação institucional (FAB / GAP-BR / ACI), fundamentação na Lei 14.133/2021 e NPA 009/SCON/2025 — Versão 2.0.
2. **Slide 2 — Visão Geral do Ciclo Mensal Unificado:** Diagrama conceitual do ciclo mensal (Lançamento Contínuo &rarr; Ateste Mensal até o 2º dia útil &rarr; Auditoria ACI &rarr; Homologação).
3. **Slide 3 — Fundamentação Normativa e Importância da Tempestividade:** Jurisprudência do TCU (Acórdãos 2748/2019-P, 9240/2016-2ªC), dever legal de registro contemporâneo (art. 117 da Lei 14.133/21), integridade e proteção pessoal do fiscal.

### Seção II — Acesso Inicial e Painel do Fiscal
4. **Slide 4 — Passo 1:** Acesso à página inicial do Portal de Prestação de Contas (`/prestacoes/`).
5. **Slide 5 — Passo 2:** Seleção e filtragem do Contrato sob responsabilidade do fiscal (`/prestacoes/fiscais/`).
6. **Slide 6 — Passo 3:** Painel individual do contrato e localização da aba *"1. Livro do Fiscal"*.

### Seção III — Gestão Unificada de Ocorrências
7. **Slide 7 — Passo 4:** Visão geral da tela de Gestão Unificada de Ocorrências (`/execucao/fiscais/<id>/ocorrencias/`) e acionamento do botão `+ Nova Ocorrência`.
8. **Slide 8 — Passo 5:** Preenchimento do modal de ocorrência para falha técnica (Data do Fato, Tipo, Gravidade, Descrição e Determinações).
9. **Slide 9 — Passo 6:** Visualização da ocorrência técnica na tabela unificada com ícones de edição e exclusão.
10. **Slide 10 — Passo 7:** Localização e acionamento do botão de edição (lápis azul) para saneamento da pendência.
11. **Slide 11 — Passo 8:** Edição da ocorrência para o status "Resolvido" com registro das ações corretivas adotadas pela contratada.
12. **Slide 12 — Passo 9:** Registro de ocorrência administrativa com Notificação Formal (Notificação nº 012/GAP-BR/2026 e Processo NUP).
13. **Slide 13 — Passo 10:** Tabela consolidada com todas as ocorrências do período organizadas por data.

### Seção IV — Ciclo Mensal, Ateste e Envio à ACI
14. **Slide 14 — Passo 11:** Trava regulatória do mês corrente (demonstração do bloqueio de ateste antes do encerramento do mês).
15. **Slide 15 — Passo 12:** Virada do mês (início de outubro) com liberação do botão `Finalizar e Atestar Mês`.
16. **Slide 16 — Passo 13:** Acesso ao formulário de ateste do Livro do Fiscal do mês fechado.
17. **Slide 17 — Passo 14:** Revisão da tabela de ocorrências no formulário de consolidação mensal (sem rótulos de tempestividade).
18. **Slide 18 — Passo 15:** Novo Modal de Finalização/Ateste destacando o campo opcional *"Observações para a ACI (Trâmites)"* e a Declaração Legal.
19. **Slide 19 — Passo 16:** Confirmação de envio no portal com status oficial atualizado para "Preenchido / Entregue".

### Seção V — Auditoria, Devolução, Saneamento e Homologação
20. **Slide 20 — Passo 17:** Acesso ao Livro do Fiscal pós-ateste com visualização do histórico de trâmites e botão de download do PDF.
21. **Slide 21 — Passo 18:** Localização do botão de download do PDF gerado pelo sistema.
22. **Slide 22 — Passo 19:** Espelho do Livro do Fiscal em PDF Oficial do SILOMS (Termo de Abertura, tabela unificada e declaração legal).
23. **Slide 23 — Passo 20:** Apontamento da ACI com devolução para ajustes (Status "Ajustes Solicitados" e motivo da devolução).
24. **Slide 24 — Passo 21:** Painel de apontamentos da ACI dentro do formulário do Livro do Fiscal.
25. **Slide 25 — Passo 22:** Saneamento do apontamento na ocorrência (inclusão do NUP e documento SEI de notificação).
26. **Slide 26 — Passo 23:** Novo Modal de Reenvio com mensagem de resposta de trâmite destinada à ACI.
27. **Slide 27 — Passo 24:** Homologação final pela ACI com selo verde "Conformidade (OK!)" e encerramento do ciclo.
28. **Slide 28 — Passo 25:** Espelho do PDF Definitivo Homologado do Livro do Fiscal (documento de valor probatório arquivado no processo).

### Seção VI — Governança, Boas Práticas e Checklist
29. **Slide 29 — Boas Práticas, Regras de Ouro e Prazos Regimentais:** Síntese executiva das diretrizes operacionais, prazos regimentais e deveres do fiscal.
30. **Slide 30 — Checklist Operacional do Fiscal de Contrato:** Roteiro prático com checagens diárias, mensais e no encerramento, acompanhado dos canais oficiais de apoio da ACI.

---

## 🔄 Como Recompilar os Documentos em PDF

Caso os arquivos HTML sejam modificados, os PDFs oficiais podem ser recompilados via Google Chrome Headless com os seguintes comandos:

### 1. Apresentação Prática para Fiscais (14 Slides Widescreen 16:9)
```bash
cd docs/manuais/guia_livro_fiscal
google-chrome --headless --disable-gpu --no-sandbox --no-pdf-header-footer \
  --print-to-pdf=Apresentacao_Pratica_Fiscal_v2.0.pdf apresentacao_pratica_fiscal.html
```

### 2. Apresentação Executiva Institucional (15 Slides Widescreen 16:9)
```bash
cd docs/manuais/guia_livro_fiscal
google-chrome --headless --disable-gpu --no-sandbox --no-pdf-header-footer \
  --print-to-pdf=Apresentacao_Livro_do_Fiscal_v2.0.pdf apresentacao_livro_fiscal.html
```

### 3. Manual Operacional Completo (30 Slides A4 Paisagem)
```bash
cd docs/manuais/guia_livro_fiscal
google-chrome --headless --disable-gpu --no-sandbox --no-pdf-header-footer \
  --print-to-pdf=Guia_Ilustrado_Livro_do_Fiscal_v2.0.pdf guia_livro_fiscal.html
```
