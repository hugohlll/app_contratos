/*
 * Rosca "Situação do mês" do painel de Prestação de Contas.
 *
 * Uma única rosca alterna entre três visões (todos os contratos, prioritários e Livro do Fiscal).
 * Clicar numa fatia ou num item da legenda filtra a tabela "Acompanhamento Detalhado".
 *
 * Marcação esperada:
 *   <script id="roscaStatsDados" type="application/json">{...}</script>  (json_script com as contagens)
 *   <canvas id="roscaPrestacao">, #roscaTotal, #roscaSufixo, #roscaLegenda
 *   botões [data-rosca-visao="todos|prioritarios|livro"]
 *   linhas tr.linha-tabela-mes-fiscais com data-segmento-slides, data-segmento-livro e data-prioritario
 *   #filtroGraficoAtivo, #filtroGraficoRotulo, #filtroGraficoLimpar, #cardTabelaMesFiscais
 *
 * O filtro fica na URL (?filtro=visao:status) para que o link reabra o mesmo recorte.
 */
(function () {
    'use strict';

    const PARAM = 'filtro';
    const STATUS = ['ok', 'entregue', 'correcao', 'pendente'];
    const ROTULOS = {
        ok: 'Conformidade (OK!)',
        entregue: 'Aguardando análise',
        correcao: 'Ajustes necessários',
        pendente: 'Pendente'
    };
    const CORES = ['#10b981', '#3b82f6', '#f59e0b', '#9ca3af'];
    const VISOES = {
        todos: {
            rotulo: 'Todos', sufixo: 'contratos',
            chaves: ['ok_no_mes', 'entregues_no_mes', 'correcao_no_mes', 'pendentes_no_mes']
        },
        prioritarios: {
            rotulo: 'Prioritários', sufixo: 'prioritários',
            chaves: ['prio_ok', 'prio_entregues', 'prio_correcao', 'prio_pendentes']
        },
        livro: {
            rotulo: 'Livro do Fiscal', sufixo: 'livros',
            chaves: ['livro_ok', 'livro_entregues', 'livro_correcao', 'livro_pendentes']
        }
    };

    let stats = {};
    let visao = 'todos';
    let filtro = null;
    let grafico = null;
    const el = {};

    function segmento(status) {
        return STATUS.indexOf(status) >= 0 && status !== 'pendente' ? status : 'pendente';
    }

    function valores(v) {
        return VISOES[v].chaves.map(function (chave) { return Number(stats[chave]) || 0; });
    }

    function soma(lista) {
        return lista.reduce(function (a, b) { return a + b; }, 0);
    }

    function pct(valor, total) {
        return total ? Math.round(valor * 100 / total) : 0;
    }

    function desenharLegenda(lista, total) {
        el.legenda.innerHTML = '';
        STATUS.forEach(function (status, i) {
            const botao = document.createElement('button');
            botao.type = 'button';
            botao.className = 'legenda-rosca-item';
            botao.dataset.status = status;
            const ativo = filtro && filtro.visao === visao && filtro.status === status;
            botao.classList.toggle('ativo', !!ativo);
            botao.setAttribute('aria-pressed', ativo ? 'true' : 'false');
            botao.title = 'Filtrar a tabela: ' + VISOES[visao].rotulo + ' · ' + ROTULOS[status];

            const cor = document.createElement('span');
            cor.className = 'legenda-rosca-cor';
            cor.style.background = CORES[i];
            const nome = document.createElement('span');
            nome.className = 'legenda-rosca-nome';
            nome.textContent = ROTULOS[status];
            const valor = document.createElement('strong');
            valor.textContent = pct(lista[i], total) + '% (' + lista[i] + ')';

            botao.append(cor, nome, valor);
            el.legenda.appendChild(botao);
        });
    }

    function desenhar() {
        const lista = valores(visao);
        const total = soma(lista);
        grafico.data.datasets[0].data = lista;
        grafico.update();
        el.total.textContent = total;
        el.sufixo.textContent = VISOES[visao].sufixo;
        el.canvas.setAttribute('aria-label', 'Situação do mês, ' + VISOES[visao].rotulo + ': ' +
            STATUS.map(function (s, i) { return ROTULOS[s] + ' ' + lista[i]; }).join(', '));
        document.querySelectorAll('[data-rosca-visao]').forEach(function (botao) {
            const ativo = botao.dataset.roscaVisao === visao;
            botao.classList.toggle('active', ativo);
            botao.setAttribute('aria-pressed', ativo ? 'true' : 'false');
        });
        desenharLegenda(lista, total);
    }

    function gravarEstado() {
        const url = new URL(window.location.href);
        if (filtro) url.searchParams.set(PARAM, filtro.visao + ':' + filtro.status);
        else url.searchParams.delete(PARAM);
        window.history.replaceState(null, '', url);
    }

    function reaplicarTabela() {
        if (typeof window.aplicarFiltroTabelaMesFiscais === 'function') window.aplicarFiltroTabelaMesFiscais();
    }

    function mostrarFiltro() {
        if (!el.chip) return;
        el.chip.classList.toggle('d-none', !filtro);
        el.chip.classList.toggle('d-inline-flex', !!filtro);
        if (filtro) el.chipRotulo.textContent = VISOES[filtro.visao].rotulo + ' · ' + ROTULOS[filtro.status];
    }

    function filtrar(v, status, rolar) {
        if (!VISOES[v] || STATUS.indexOf(status) < 0) return;
        // Clicar de novo no mesmo segmento desfaz o filtro.
        if (filtro && filtro.visao === v && filtro.status === status) {
            limpar();
            return;
        }
        filtro = { visao: v, status: status };
        gravarEstado();
        mostrarFiltro();
        desenharLegenda(valores(visao), soma(valores(visao)));
        reaplicarTabela();
        if (rolar && el.tabela) el.tabela.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }

    function limpar() {
        filtro = null;
        gravarEstado();
        mostrarFiltro();
        desenharLegenda(valores(visao), soma(valores(visao)));
        reaplicarTabela();
    }

    /* Usado pelo filtro da tabela: a linha atende ao recorte escolhido no gráfico? */
    function linhaPassa(tr) {
        if (!filtro) return true;
        if (filtro.visao === 'livro') return tr.dataset.segmentoLivro === filtro.status;
        if (filtro.visao === 'prioritarios' && tr.dataset.prioritario !== '1') return false;
        return tr.dataset.segmentoSlides === filtro.status;
    }

    /* Atualiza os atributos da linha depois de uma mudança feita na própria página. */
    function marcarLinha(tr, status, prioritario) {
        if (!tr) return;
        if (status !== undefined && status !== null) tr.dataset.segmentoSlides = segmento(status);
        if (prioritario !== undefined && prioritario !== null) tr.dataset.prioritario = prioritario ? '1' : '0';
    }

    /* Recebe as contagens novas (o "stats" devolvido pelas chamadas AJAX do painel). */
    function atualizar(novos) {
        if (!grafico || !novos) return;
        Object.keys(VISOES).forEach(function (v) {
            VISOES[v].chaves.forEach(function (chave) {
                if (novos[chave] !== undefined) stats[chave] = novos[chave];
            });
        });
        desenhar();
        reaplicarTabela();
    }

    function iniciar() {
        el.canvas = document.getElementById('roscaPrestacao');
        const dados = document.getElementById('roscaStatsDados');
        if (!el.canvas || !dados || !window.Chart) return;
        stats = JSON.parse(dados.textContent);
        el.total = document.getElementById('roscaTotal');
        el.sufixo = document.getElementById('roscaSufixo');
        el.legenda = document.getElementById('roscaLegenda');
        el.chip = document.getElementById('filtroGraficoAtivo');
        el.chipRotulo = document.getElementById('filtroGraficoRotulo');
        el.tabela = document.getElementById('cardTabelaMesFiscais');

        grafico = new Chart(el.canvas, {
            type: 'doughnut',
            data: {
                labels: STATUS.map(function (s) { return ROTULOS[s]; }),
                datasets: [{ data: valores(visao), backgroundColor: CORES, borderColor: '#fff', borderWidth: 2 }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                cutout: '62%',
                animation: { duration: 600, easing: 'easeInOutCubic' },
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        callbacks: {
                            label: function (contexto) {
                                const total = soma(contexto.dataset.data);
                                return ' ' + contexto.label + ': ' + pct(contexto.raw, total) + '% (' + contexto.raw + ')';
                            }
                        }
                    }
                },
                onClick: function (evento, elementos) {
                    if (elementos.length) filtrar(visao, STATUS[elementos[0].index], true);
                },
                onHover: function (evento, elementos) {
                    evento.native.target.style.cursor = elementos.length ? 'pointer' : 'default';
                }
            }
        });

        document.querySelectorAll('[data-rosca-visao]').forEach(function (botao) {
            botao.addEventListener('click', function () {
                visao = botao.dataset.roscaVisao;
                desenhar();
            });
        });
        el.legenda.addEventListener('click', function (evento) {
            const item = evento.target.closest('.legenda-rosca-item');
            if (item) filtrar(visao, item.dataset.status, true);
        });
        const limparBtn = document.getElementById('filtroGraficoLimpar');
        if (limparBtn) limparBtn.addEventListener('click', limpar);

        const inicial = new URL(window.location.href).searchParams.get(PARAM);
        if (inicial && inicial.indexOf(':') > 0) {
            const partes = inicial.split(':');
            if (VISOES[partes[0]] && STATUS.indexOf(partes[1]) >= 0) {
                filtro = { visao: partes[0], status: partes[1] };
                visao = partes[0];
            }
        }
        desenhar();
        mostrarFiltro();
        reaplicarTabela();
    }

    window.RoscaPrestacao = {
        atualizar: atualizar,
        redimensionar: function () { if (grafico) grafico.resize(); },
        marcarLinha: marcarLinha,
        linhaPassa: linhaPassa,
        filtrar: filtrar,
        limpar: limpar
    };

    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', iniciar);
    else iniciar();
})();
