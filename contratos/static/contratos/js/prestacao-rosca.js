/*
 * Roscas "Situação do mês" do painel de Prestação de Contas.
 *
 * Cada rosca alterna entre visões (botões [data-rosca-visao] dentro do próprio cartão) e,
 * ao clicar numa fatia ou num item da legenda, filtra a tabela do mês logo abaixo.
 * O filtro fica na URL (?<param>=visao:status) para que o link reabra o mesmo recorte.
 *
 * Instâncias:
 *   window.RoscaPrestacao  aba Fiscais  (Todos, Prioritários, Livro do Fiscal) ?filtro=
 *   window.RoscaSetores    aba Setores  (Todos, Prioritários)                  ?filtro_setor=
 *
 * Cada instância expõe {atualizar, redimensionar, marcarLinha, linhaPassa, filtrar, limpar}.
 * As linhas da tabela trazem data-segmento-slides e data-prioritario (e, nos fiscais, data-segmento-livro).
 */
(function () {
    'use strict';

    const STATUS = ['ok', 'entregue', 'correcao', 'pendente'];
    const ROTULOS = {
        ok: 'Conformidade (OK!)',
        entregue: 'Aguardando análise',
        correcao: 'Ajustes necessários',
        pendente: 'Pendente'
    };
    const CORES = ['#10b981', '#3b82f6', '#f59e0b', '#9ca3af'];

    function segmento(status) {
        return STATUS.indexOf(status) >= 0 ? status : 'pendente';
    }

    function soma(lista) {
        return lista.reduce(function (a, b) { return a + b; }, 0);
    }

    function pct(valor, total) {
        return total ? Math.round(valor * 100 / total) : 0;
    }

    /*
     * cfg = {
     *   ids: {card, canvas, dados, total, sufixo, legenda, chip, chipRotulo, limpar, tabela},
     *   param: nome do parâmetro da URL,
     *   visoes: {chave: {rotulo, sufixo, chaves: [4 chaves de stats], campo: dataset da linha, soPrioritarios}},
     *   reaplicar: nome da função global que refiltra a tabela
     * }
     */
    function criarRosca(cfg) {
        const VISOES = cfg.visoes;
        let stats = {};
        let visao = Object.keys(VISOES)[0];
        let filtro = null;
        let grafico = null;
        const el = {};

        function valores(v) {
            return VISOES[v].chaves.map(function (chave) { return Number(stats[chave]) || 0; });
        }

        function botoesVisao() {
            return el.card ? el.card.querySelectorAll('[data-rosca-visao]') : [];
        }

        function desenharLegenda() {
            const lista = valores(visao);
            const total = soma(lista);
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
            grafico.data.datasets[0].data = lista;
            grafico.update();
            el.total.textContent = soma(lista);
            el.sufixo.textContent = VISOES[visao].sufixo;
            el.canvas.setAttribute('aria-label', 'Situação do mês, ' + VISOES[visao].rotulo + ': ' +
                STATUS.map(function (s, i) { return ROTULOS[s] + ' ' + lista[i]; }).join(', '));
            botoesVisao().forEach(function (botao) {
                const ativo = botao.dataset.roscaVisao === visao;
                botao.classList.toggle('active', ativo);
                botao.setAttribute('aria-pressed', ativo ? 'true' : 'false');
            });
            desenharLegenda();
        }

        function gravarEstado() {
            const url = new URL(window.location.href);
            if (filtro) url.searchParams.set(cfg.param, filtro.visao + ':' + filtro.status);
            else url.searchParams.delete(cfg.param);
            window.history.replaceState(null, '', url);
        }

        function reaplicarTabela() {
            const fn = window[cfg.reaplicar];
            if (typeof fn === 'function') fn();
        }

        function mostrarFiltro() {
            if (!el.chip) return;
            el.chip.classList.toggle('d-none', !filtro);
            el.chip.classList.toggle('d-inline-flex', !!filtro);
            if (filtro) el.chipRotulo.textContent = VISOES[filtro.visao].rotulo + ' · ' + ROTULOS[filtro.status];
        }

        function limpar() {
            filtro = null;
            gravarEstado();
            mostrarFiltro();
            if (grafico) desenharLegenda();
            reaplicarTabela();
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
            desenharLegenda();
            reaplicarTabela();
            if (rolar && el.tabela) el.tabela.scrollIntoView({ behavior: 'smooth', block: 'start' });
        }

        /* Usado pelo filtro da tabela: a linha atende ao recorte escolhido no gráfico? */
        function linhaPassa(tr) {
            if (!filtro) return true;
            const def = VISOES[filtro.visao];
            if (def.soPrioritarios && tr.dataset.prioritario !== '1') return false;
            return tr.dataset[def.campo] === filtro.status;
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
            el.canvas = document.getElementById(cfg.ids.canvas);
            const dados = document.getElementById(cfg.ids.dados);
            if (!el.canvas || !dados || !window.Chart) return;
            stats = JSON.parse(dados.textContent);
            ['card', 'total', 'sufixo', 'legenda', 'chip', 'chipRotulo', 'tabela'].forEach(function (nome) {
                el[nome] = document.getElementById(cfg.ids[nome]);
            });

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

            botoesVisao().forEach(function (botao) {
                botao.addEventListener('click', function () {
                    visao = botao.dataset.roscaVisao;
                    desenhar();
                });
            });
            el.legenda.addEventListener('click', function (evento) {
                const item = evento.target.closest('.legenda-rosca-item');
                if (item) filtrar(visao, item.dataset.status, true);
            });
            const limparBtn = document.getElementById(cfg.ids.limpar);
            if (limparBtn) limparBtn.addEventListener('click', limpar);

            const inicial = new URL(window.location.href).searchParams.get(cfg.param);
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

        if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', iniciar);
        else iniciar();

        return {
            atualizar: atualizar,
            redimensionar: function () { if (grafico) grafico.resize(); },
            marcarLinha: marcarLinha,
            linhaPassa: linhaPassa,
            filtrar: filtrar,
            limpar: limpar
        };
    }

    window.RoscaPrestacao = criarRosca({
        ids: {
            card: 'cardRoscaPrestacao', canvas: 'roscaPrestacao', dados: 'roscaStatsDados',
            total: 'roscaTotal', sufixo: 'roscaSufixo', legenda: 'roscaLegenda',
            chip: 'filtroGraficoAtivo', chipRotulo: 'filtroGraficoRotulo', limpar: 'filtroGraficoLimpar',
            tabela: 'cardTabelaMesFiscais'
        },
        param: 'filtro',
        reaplicar: 'aplicarFiltroTabelaMesFiscais',
        visoes: {
            todos: {
                rotulo: 'Todos', sufixo: 'contratos', campo: 'segmentoSlides',
                chaves: ['ok_no_mes', 'entregues_no_mes', 'correcao_no_mes', 'pendentes_no_mes']
            },
            prioritarios: {
                rotulo: 'Prioritários', sufixo: 'prioritários', campo: 'segmentoSlides', soPrioritarios: true,
                chaves: ['prio_ok', 'prio_entregues', 'prio_correcao', 'prio_pendentes']
            },
            livro: {
                rotulo: 'Livro do Fiscal', sufixo: 'livros', campo: 'segmentoLivro',
                chaves: ['livro_ok', 'livro_entregues', 'livro_correcao', 'livro_pendentes']
            }
        }
    });

    window.RoscaSetores = criarRosca({
        ids: {
            card: 'cardRoscaSetores', canvas: 'roscaSetores', dados: 'roscaSetoresDados',
            total: 'roscaSetoresTotal', sufixo: 'roscaSetoresSufixo', legenda: 'roscaSetoresLegenda',
            chip: 'filtroGraficoSetoresAtivo', chipRotulo: 'filtroGraficoSetoresRotulo',
            limpar: 'filtroGraficoSetoresLimpar', tabela: 'cardTabelaMesSetores'
        },
        param: 'filtro_setor',
        reaplicar: 'aplicarFiltroTabelaMesSetores',
        visoes: {
            todos: {
                rotulo: 'Todos', sufixo: 'setores', campo: 'segmentoSlides',
                chaves: ['ok_setores_no_mes', 'entregues_setores_no_mes', 'correcao_setores_no_mes', 'pendentes_setores_no_mes']
            },
            prioritarios: {
                rotulo: 'Prioritários', sufixo: 'prioritários', campo: 'segmentoSlides', soPrioritarios: true,
                chaves: ['prio_ok_setores', 'prio_entregues_setores', 'prio_correcao_setores', 'prio_pendentes_setores']
            }
        }
    });
})();
