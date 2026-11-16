/*
 * Drill-down dos dashboards: ao clicar num gráfico, cartão ou legenda,
 * abre um painel lateral (offcanvas do Bootstrap) com os registros do segmento.
 *
 * Marcação esperada:
 *   <div id="offcanvasDetalhe" data-url-modelo=".../auditoria/detalhe/indicador-modelo/"> ... </div>
 *   qualquer elemento com data-drill-indicador e data-drill-segmento abre o detalhe ao ser clicado.
 *
 * O estado fica na URL (?detalhe=indicador:segmento) para que o link reabra o mesmo detalhe.
 */
(function () {
    'use strict';

    const PARAM = 'detalhe';
    let painel, offcanvas, corpo, titulo, controlador;

    function urlDetalhe(indicador, segmento) {
        const base = painel.dataset.urlModelo.replace('indicador-modelo', encodeURIComponent(indicador));
        return base + '?segmento=' + encodeURIComponent(segmento);
    }

    function gravarEstado(valor) {
        const url = new URL(window.location.href);
        if (valor) url.searchParams.set(PARAM, valor);
        else url.searchParams.delete(PARAM);
        window.history.replaceState(null, '', url);
    }

    function mostrarCarregando() {
        corpo.innerHTML =
            '<div class="d-flex justify-content-center align-items-center py-5 text-muted">' +
            '<div class="spinner-border spinner-border-sm me-2" role="status"></div>Carregando...</div>';
    }

    function mostrarErro(mensagem) {
        corpo.innerHTML = '';
        const alerta = document.createElement('div');
        alerta.className = 'alert alert-warning';
        alerta.textContent = mensagem;
        corpo.appendChild(alerta);
    }

    function ligarBusca() {
        const busca = corpo.querySelector('.detalhe-busca');
        if (!busca) return;
        const linhas = Array.from(corpo.querySelectorAll('tbody tr'));
        const contagem = corpo.querySelector('.detalhe-contagem');
        const semResultado = corpo.querySelector('.detalhe-sem-resultado');
        busca.addEventListener('input', function () {
            const termo = busca.value.trim().toLowerCase();
            let visiveis = 0;
            linhas.forEach(function (tr) {
                const mostra = !termo || tr.textContent.toLowerCase().includes(termo);
                tr.classList.toggle('d-none', !mostra);
                if (mostra) visiveis++;
            });
            if (contagem) contagem.textContent = visiveis;
            if (semResultado) semResultado.classList.toggle('d-none', visiveis > 0);
        });
    }

    function abrir(indicador, segmento) {
        if (!painel) return;
        segmento = segmento === undefined || segmento === null || segmento === '' ? 'todos' : String(segmento);

        if (controlador) controlador.abort();
        controlador = new AbortController();

        titulo.textContent = 'Detalhe';
        mostrarCarregando();
        offcanvas.show();
        gravarEstado(indicador + ':' + segmento);

        fetch(urlDetalhe(indicador, segmento), {
            headers: { 'X-Requested-With': 'XMLHttpRequest' },
            credentials: 'same-origin',
            signal: controlador.signal
        })
            .then(function (resp) {
                if (resp.redirected || resp.status === 401 || resp.status === 403) {
                    throw new Error('Sua sessão expirou. Recarregue a página e entre novamente.');
                }
                if (!resp.ok) throw new Error('Não foi possível carregar o detalhe (erro ' + resp.status + ').');
                return resp.text();
            })
            .then(function (html) {
                corpo.innerHTML = html;
                const raiz = corpo.querySelector('.detalhe-indicador');
                if (raiz) titulo.textContent = raiz.dataset.titulo;
                ligarBusca();
            })
            .catch(function (erro) {
                if (erro.name === 'AbortError') return;
                mostrarErro(erro.message);
            });
    }

    /*
     * Opções de clique para um gráfico Chart.js.
     *   segmentoDe(indiceDoElemento) -> chave do segmento
     */
    function opcoesGrafico(indicador, segmentoDe) {
        return {
            onClick: function (evento, elementos) {
                if (!elementos.length) return;
                abrir(indicador, segmentoDe(elementos[0].index));
            },
            onHover: function (evento, elementos) {
                evento.native.target.style.cursor = elementos.length ? 'pointer' : 'default';
            }
        };
    }

    function iniciar() {
        painel = document.getElementById('offcanvasDetalhe');
        if (!painel || !window.bootstrap) return;
        offcanvas = bootstrap.Offcanvas.getOrCreateInstance(painel);
        corpo = painel.querySelector('.offcanvas-body');
        titulo = painel.querySelector('.offcanvas-title');

        painel.addEventListener('hidden.bs.offcanvas', function () {
            if (controlador) controlador.abort();
            gravarEstado(null);
        });

        document.addEventListener('click', function (evento) {
            const alvo = evento.target.closest('[data-drill-indicador]');
            if (!alvo) return;
            evento.preventDefault();
            abrir(alvo.dataset.drillIndicador, alvo.dataset.drillSegmento);
        });
        document.addEventListener('keydown', function (evento) {
            if (evento.key !== 'Enter' && evento.key !== ' ') return;
            const alvo = evento.target.closest('[data-drill-indicador][role="button"]');
            if (!alvo) return;
            evento.preventDefault();
            abrir(alvo.dataset.drillIndicador, alvo.dataset.drillSegmento);
        });

        const inicial = new URL(window.location.href).searchParams.get(PARAM);
        if (inicial && inicial.includes(':')) {
            const partes = inicial.split(':');
            abrir(partes[0], partes.slice(1).join(':'));
        }
    }

    window.DashboardDrill = { abrir: abrir, opcoesGrafico: opcoesGrafico };

    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', iniciar);
    else iniciar();
})();
