# Guia de Melhorias de UI/UX: Livro do Fiscal Digital

Para otimizar a experiência visual em formulários com alta densidade de informações administrativas e de fiscalização de contratos, o principal objetivo é reduzir a carga cognitiva. O usuário deve bater o olho na tela e saber imediatamente o que é apenas **contexto** (leitura) e o que exige **ação** (preenchimento).

Abaixo estão as diretrizes detalhadas para melhorar a visualização e o destaque dos campos:

## 1. Contraste entre Leitura e Edição (Read-only vs. Inputs)
Os dados de leitura da Seção de Identificação (ex: *Contrato*, *Empresa*, *Objeto*) e os campos editáveis (ex: *Fiscal Responsável*) precisam ter diferenciação clara de fundo.
* **Ação:** Aplique um fundo levemente cinza (ex: `#F4F6F8` ou `#F9FAFB`) na área geral do formulário e garanta que os campos interativos (inputs, textareas, dropdowns) tenham o fundo branco puro (`#FFFFFF`) com uma borda cinza ligeiramente mais escura (ex: `#D1D5DB`). 
* **Efeito:** Os campos a serem preenchidos vão "saltar" da tela como blocos que precisam ser completados.

## 2. Destaque Estrutural para Campos Obrigatórios
A convenção do asterisco vermelho (`*`) é ideal, mas pode ser reforçada visualmente sem poluir a interface.
* **Borda Lateral Indicativa:** Adicione uma borda esquerda um pouco mais espessa e colorida apenas nos campos obrigatórios. Pode ser uma linha azul (acompanhando a cor principal do sistema) ou vermelha bem sutil (ex: `border-left: 3px solid #0066FF;`).
* **Fundo Condicional (Opcional):** Aplique um fundo com um tom de amarelo ou azul extremamente claro nos campos obrigatórios *enquanto eles estiverem vazios*. Assim que o usuário preencher, o fundo volta ao branco padrão, transmitindo a sensação de "tarefa concluída".

## 3. Melhoria nos Estados de Foco (Focus State)
Quando o usuário interage com um campo, como o detalhamento de status, o sistema deve dar um feedback visual forte.
* **Ação:** Ao focar em um campo (clique ou navegação por Tab), a borda deve mudar para a cor principal do tema (o azul dos cabeçalhos) e ganhar um leve sombreamento (`box-shadow`). 
* **Efeito:** Isso guia o olho do usuário exatamente para onde o cursor está ativo, evitando que ele se perca na tela.

## 4. Transformação dos Radio Buttons (Sim / Não)
Muitas verificações de prazos e lançamentos possuem respostas binárias (Sim/Não). No formato tradicional de "bolinha", elas exigem um clique muito preciso.
* **Ação:** Transforme esses *Radio Buttons* em **Segmented Controls** (botões agrupados em formato de pílula ou bloco). 
* **Efeito:** O usuário clica em um retângulo claro de "Sim" ou "Não". O botão selecionado fica preenchido com a cor de destaque (ex: azul), e o não selecionado fica com fundo branco/cinza. Isso aumenta a área de clique (touch target) e torna a leitura das respostas instantânea.

## 5. Delimitação de Áreas de Ação
Blocos que exigem criação de novos registros (como o cadastro de "Nova Ocorrência") devem se destacar do histórico consolidado.
* **Ação:** Envolva o bloco de cadastro inteiro dentro de um "Card" (um contêiner com fundo branco, bordas arredondadas e uma sombra muito leve). 
* **Efeito:** Separa psicologicamente o que é o histórico (tabelas de leitura) da ação que o usuário precisa executar (preenchimento do novo formulário).
