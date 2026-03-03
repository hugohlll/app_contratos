# **🛠️ Guia de Atualização: Dashboard de Sobrecarga de Fiscais**

Este documento detalha os passos necessários para alterar o dashboard de "Sobrecarga de Agentes" para "Sobrecarga de Fiscais" no sistema SISCONT.

A nova regra de negócio contabiliza **apenas militares com a função exata de "Fiscal"** e estabelece uma linha de limite baseada na média de **Contratos por Fiscal** (Nº Total de Contratos Ativos / Total de Fiscais Únicos).

## **📋 Resumo das Alterações**

1. **contratos/views/auditoria.py**: Atualizar a lógica de filtragem, o cálculo matemático da média e a função de exportação CSV.  
2. **contratos/urls.py**: Atualizar a rota de exportação para refletir o novo nome da *view*.  
3. **contratos/templates/contratos/painel\_controle.html**: Ajustar os textos, ícones e a lógica do gráfico (Chart.js) para renderizar a nova média, aplicando **práticas seguras de injeção de dados** para evitar quebras de renderização.  
4. **Testes de Validação**: Executar o protocolo de testes obrigatório para garantir a renderização correta de todos os elementos visuais.

## **Passo 1: Atualizar o Backend (contratos/views/auditoria.py)**

### **1.1. Importar a biblioteca math**

No topo do ficheiro auditoria.py, certifique-se de que a biblioteca math está importada, pois usaremos a função math.ceil para arredondar a média para cima:

import math

### **1.2. Atualizar a lógica na função painel\_controle**

Localize a secção comentada como \# 4\. SOBRECARGA E RISCOS dentro da função painel\_controle(request) e substitua todo esse bloco de código pelo seguinte:

    \# 4\. SOBRECARGA DE FISCAIS E RISCOS  
    \# Filtra apenas as designações ativas onde o título da função é exatamente "Fiscal"  
    integrantes\_fiscais \= Integrante.objects.filter(filtro\_ativos, funcao\_\_titulo='Fiscal')  
      
    \# Agrupa os agentes e conta as suas atuações exclusivas como Fiscais  
    fiscais\_sobrecarregados \= Agente.objects.filter(  
        integrante\_\_in=integrantes\_fiscais  
    ).annotate(  
        total\_atuacoes=Count('integrante', filter=Q(integrante\_\_in=integrantes\_fiscais))  
    ).filter(total\_atuacoes\_\_gt=0).order\_by('-total\_atuacoes')\[:10\]  
      
    total\_contratos\_ativos \= Contrato.objects.filter(vigencia\_fim\_\_gte=hoje).count()  
      
    \# Conta a quantidade de Fiscais ÚNICOS (agentes distintos) atuando no momento  
    total\_fiscais\_unicos \= integrantes\_fiscais.values('agente').distinct().count()  
      
    \# NOVO CÁLCULO DO LIMITE: (Nº Total de Contratos) / (Total de Fiscais Únicos)  
    media\_limite\_fiscais \= math.ceil(total\_contratos\_ativos / total\_fiscais\_unicos) if total\_fiscais\_unicos \> 0 else 0  
      
    \# Dados para gráfico de sobrecarga \- serializado como JSON  
    sobrecarga\_labels \= \[f"{ag.posto.sigla} {ag.nome\_de\_guerra}" for ag in fiscais\_sobrecarregados\]  
    sobrecarga\_valores \= \[ag.total\_atuacoes for ag in fiscais\_sobrecarregados\]  
    sobrecarga\_labels\_json \= mark\_safe(json.dumps(sobrecarga\_labels, ensure\_ascii=False))  
    sobrecarga\_valores\_json \= mark\_safe(json.dumps(sobrecarga\_valores))  
    tem\_sobrecarga \= len(sobrecarga\_labels) \> 0

### **1.3. Atualizar o contexto (Context Dictionary)**

Ainda na função painel\_controle, role até o final onde está o return render(...) e adicione a variável media\_limite\_fiscais ao dicionário:

    return render(request, 'contratos/painel\_controle.html', {  
        \# ... outras variáveis já existentes ...  
        'agentes\_sobrecarregados': fiscais\_sobrecarregados, \# Atualize o nome se desejar, mas mantenha compatibilidade  
        'sobrecarga\_labels': sobrecarga\_labels\_json,  
        'sobrecarga\_valores': sobrecarga\_valores\_json,  
        'tem\_sobrecarga': tem\_sobrecarga,  
        'media\_limite\_fiscais': media\_limite\_fiscais, \# ADICIONE ESTA LINHA  
        \# ... resto do código ...

### **1.4. Substituir a View de Exportação CSV**

Encontre a função exportar\_sobrecarga\_agentes\_csv e substitua-a pela versão abaixo, focada exclusivamente nos fiscais:

@login\_required  
def exportar\_sobrecarga\_fiscais\_csv(request):  
    response \= HttpResponse(content\_type='text/csv; charset=utf-8-sig')  
    response\['Content-Disposition'\] \= 'attachment; filename="sobrecarga\_fiscais.csv"'  
    response.write('\\ufeff')  
      
    writer \= csv.writer(response, delimiter=';')  
    writer.writerow(\['Militar (Fiscal)', 'SARAM', 'Quantidade de Contratos Fiscalizados'\])  
      
    filtro\_ativos \= get\_filtro\_ativos()  
    integrantes\_fiscais \= Integrante.objects.filter(filtro\_ativos, funcao\_\_titulo='Fiscal')  
      
    fiscais\_sobrecarregados \= Agente.objects.filter(  
        integrante\_\_in=integrantes\_fiscais  
    ).annotate(  
        total\_atuacoes=Count('integrante', filter=Q(integrante\_\_in=integrantes\_fiscais))  
    ).filter(total\_atuacoes\_\_gt=0).order\_by('-total\_atuacoes')  
      
    for agente in fiscais\_sobrecarregados:  
        writer.writerow(\[  
            f"{agente.posto.sigla} {agente.nome\_de\_guerra}",  
            agente.saram,  
            agente.total\_atuacoes  
        \])  
          
    return response

## **Passo 2: Atualizar as Rotas (contratos/urls.py)**

Como renomeamos a função de exportação, o Django não a encontrará a menos que atualizemos as rotas.

Abra o ficheiro contratos/urls.py, localize a rota de exportação de sobrecarga e altere para:

\# Modifique o path correspondente à exportação de sobrecarga  
path('auditoria/exportar-sobrecarga-fiscais/', auditoria.exportar\_sobrecarga\_fiscais\_csv, name='exportar\_sobrecarga\_fiscais\_csv'),

## **Passo 3: Atualizar o Frontend (contratos/templates/contratos/painel\_controle.html)**

### **⚠️ Prevenção de Quebras de Código (Renderização de Gráficos)**

**Atenção:** A injeção direta de variáveis do Django ({{ variavel }}) dentro das tags \<script\> do JavaScript pode causar **quebras fatais de código** (ex: *SyntaxError*, *Unexpected token* ou *ReferenceError*). Se uma variável chegar vazia ou contiver aspas não escapadas, o JavaScript aborta a execução e **nenhum gráfico será renderizado no ecrã**.

Para evitar isto, devemos utilizar **blocos de dados JSON seguros** (\<script type="application/json"\>) e aceder aos mesmos através de uma função auxiliar no JS, além de adicionar fallbacks (|default:"0").

### **3.1. Alterar a Estrutura HTML do Gráfico**

Localize a div referente à secção "Sobrecarga de Agentes" e atualize os títulos e botões:

        \<div class="col-md-6"\>  
            \<div class="chart-container h-100"\>  
                \<div class="chart-title"\>  
                    \<span\>⚖️ Sobrecarga de Fiscais\</span\>  
                    \<a href="{% url 'exportar\_sobrecarga\_fiscais\_csv' %}"  
                        class="btn btn-outline-secondary btn-sm rounded-pill"\>  
                        \<i class="bi bi-download me-2"\>\</i\> Ver Dados  
                    \</a\>  
                \</div\>  
                {% if tem\_sobrecarga %}  
                \<div class="chart-wrapper"\>  
                    \<canvas id="chartSobrecarga"\>\</canvas\>  
                \</div\>  
                {% else %}  
                \<div class="text-center py-5 text-muted"\>Nenhuma sobrecarga de fiscais detectada\</div\>  
                {% endif %}  
            \</div\>  
        \</div\>

### **3.2. Atualizar a Injeção de Dados e o JavaScript (Chart.js)**

Vá até ao final do ficheiro (mesmo antes da tag \<script\> principal do Chart.js) e insira os blocos de transferência segura de dados, seguidos do novo código JS atualizado. Substitua todo o bloco referente à Sobrecarga (// 4\. Sobrecarga) para utilizar o carregamento seguro:

\<\!-- TRANSFERÊNCIA SEGURA DE DADOS DJANGO PARA JAVASCRIPT \--\>  
\<script id="data-sob-labels" type="application/json"\>  
    {{ sobrecarga\_labels|safe|default:"\[\]" }}  
\</script\>  
\<script id="data-sob-valores" type="application/json"\>  
    {{ sobrecarga\_valores|safe|default:"\[\]" }}  
\</script\>  
\<script id="data-sob-avg" type="application/json"\>  
    {{ media\_limite\_fiscais|default:"0" }}  
\</script\>

\<script\>  
    document.addEventListener("DOMContentLoaded", function () {  
          
        // Função auxiliar robusta para ler dados JSON (Impede falhas de sintaxe)  
        function getSafeData(elementId, fallback) {  
            const el \= document.getElementById(elementId);  
            if (\!el) return fallback;  
            const txt \= el.textContent.trim();  
            if (txt.includes('{{') || txt.includes('{%')) return fallback;  
            try { return JSON.parse(txt); }   
            catch (e) { return fallback; }  
        }

        // ... (código dos restantes gráficos) ...

        // 4\. Sobrecarga de Fiscais  
        const ctxSob \= document.getElementById('chartSobrecarga');  
          
        // Verifica se o canvas existe antes de tentar desenhar  
        if (ctxSob) {  
            // Ler dados de forma segura (Prevenção de quebra de renderização)  
            const labels \= getSafeData('data-sob-labels', \[\]);  
            const values \= getSafeData('data-sob-valores', \[\]);  
            const avg \= getSafeData('data-sob-avg', 0);

            // Separar em Base e Excesso  
            const baseDataSob \= values.map(v \=\> Math.min(v, avg));  
            const excessDataSob \= values.map(v \=\> Math.max(0, v \- avg));

            const averageLinePlugin \= {  
                id: 'averageLine',  
                afterDraw: (chart) \=\> {  
                    const ctx \= chart.ctx;  
                    const xAxis \= chart.scales.x;  
                    const yAxis \= chart.scales.y;  
                    const yValue \= avg;

                    if (yValue \< yAxis.min || yValue \> yAxis.max) return;

                    const yPixel \= yAxis.getPixelForValue(yValue);  
                    const leftPixel \= xAxis.left;  
                    const rightPixel \= xAxis.right;

                    ctx.save();  
                    ctx.beginPath();  
                    ctx.strokeStyle \= '\#000000'; // Preto  
                    ctx.lineWidth \= 1.5;  
                    ctx.setLineDash(\[5, 5\]); // Tracejado  
                    ctx.moveTo(leftPixel, yPixel);  
                    ctx.lineTo(rightPixel, yPixel);  
                    ctx.stroke();

                    ctx.fillStyle \= '\#000000'; // Preto  
                    ctx.textAlign \= 'right';  
                    ctx.font \= 'bold 12px Arial';  
                    ctx.fillText('limite: ' \+ avg, rightPixel, yPixel \- 5);  
                    ctx.restore();  
                }  
            };

            new Chart(ctxSob, {  
                type: 'bar',  
                data: {  
                    labels: labels,  
                    datasets: \[  
                        {  
                            label: 'Regular',  
                            data: baseDataSob,  
                            backgroundColor: '\#0dcaf0',   
                            borderRadius: 4,  
                            barPercentage: 0.6  
                        },  
                        {  
                            label: 'Excedente',  
                            data: excessDataSob,  
                            borderRadius: 4,  
                            barPercentage: 0.6,  
                            backgroundColor: 'rgba(220, 53, 69, 0.8)'   
                        }  
                    \]  
                },  
                options: {  
                    responsive: true,  
                    maintainAspectRatio: false,  
                    layout: { padding: { top: 20 } },  
                    plugins: {  
                        legend: { display: false },  
                        tooltip: {  
                            callbacks: {  
                                label: function (context) {  
                                    const idx \= context.dataIndex;  
                                    return \`Contratos Fiscalizados: ${values\[idx\]}\`;  
                                }  
                            }  
                        }  
                    },  
                    scales: {  
                        x: {  
                            stacked: true,  
                            grid: { display: false },  
                            title: { display: true, text: 'Fiscais' }  
                        },  
                        y: {  
                            stacked: true,  
                            beginAtZero: true,  
                            ticks: { stepSize: 1 },  
                            title: { display: true, text: 'Contratos Fiscalizados' }  
                        }  
                    }  
                },  
                plugins: \[averageLinePlugin\]  
            });  
        }  
    });  
\</script\>

## **✅ Passo 4: Validação e Teste de Renderização**

Para dar esta tarefa como **concluída**, é estritamente necessário realizar o seguinte protocolo de testes para garantir que não houve quebra de código JavaScript:

1. **Reiniciar o Servidor**: Reinicie o servidor Django (python manage.py runserver) ou reconstrua os contentores Docker (docker compose up \--build \-d).  
2. **Limpar a Cache**: Aceda à página do painel de auditoria (http://localhost:8000/auditoria/) e force a recarga da página (pressione Ctrl \+ F5 ou Cmd \+ Shift \+ R).  
3. **Inspeção Visual (Teste de Renderização)**:  
   * Verifique se **todos** os gráficos (Pizza, Radar e Barras) estão a aparecer corretamente no ecrã.  
   * Se a página carregar mas os gráficos não aparecerem, **houve uma quebra de JavaScript**.  
4. **Verificação da Consola (Troubleshooting)**:  
   * Pressione F12 no navegador e abra a aba "Console" (Consola).  
   * Certifique-se de que não existem erros a vermelho (ex: SyntaxError, ReferenceError: bootstrap is not defined). Se houver erros, reveja o Passo 3.2 para garantir que a injeção segura de dados foi bem aplicada.  
5. **Validação Lógica**:  
   * Confirme que a linha pontilhada do gráfico de Sobrecarga indica um número correspondente a Nº Total de Contratos / Total de Fiscais Únicos.  
6. **Teste de Exportação**:  
   * Clique no botão "Ver Dados" do gráfico de Sobrecarga de Fiscais.  
   * Verifique se o ficheiro sobrecarga\_fiscais.csv é descarregado corretamente e se as colunas refletem os fiscais e as quantidades corretas.