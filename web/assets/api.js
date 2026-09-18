/* ==========================================================================
   Camada de acesso à API do Núcleo.
   ========================================================================== */
(function (global) {
  "use strict";

  async function requisitar(caminho, opcoes) {
    const config = Object.assign({ headers: { "Content-Type": "application/json" } }, opcoes);
    let resposta;
    try {
      resposta = await fetch(caminho, config);
    } catch (erro) {
      throw new Error("Não consegui falar com o servidor. Ele ainda está rodando?");
    }
    if (!resposta.ok) {
      let detalhe = `Erro ${resposta.status}`;
      try {
        const corpo = await resposta.json();
        if (corpo && corpo.detail) {
          detalhe = typeof corpo.detail === "string"
            ? corpo.detail
            : JSON.stringify(corpo.detail);
        }
      } catch (_) { /* resposta sem JSON */ }
      throw new Error(detalhe);
    }
    if (resposta.status === 204) return null;
    return resposta.json();
  }

  const obter = (caminho) => requisitar(caminho);
  const enviar = (caminho, corpo) =>
    requisitar(caminho, { method: "POST", body: JSON.stringify(corpo || {}) });
  const remover = (caminho) => requisitar(caminho, { method: "DELETE" });

  /**
   * Pesquisa com transmissão em tempo real (Server-Sent Events).
   * `aoEvento` recebe cada evento do servidor; devolve uma função para cancelar.
   */
  function pesquisarEmFluxo(parametros, aoEvento, aoErro) {
    const query = new URLSearchParams({
      pergunta: parametros.pergunta,
      fontes: (parametros.fontes || []).join(","),
      idioma: parametros.idioma || "pt",
      profundidade: parametros.profundidade || "media",
      salvar: parametros.salvar === false ? "false" : "true",
    });
    const origem = new EventSource(`/api/pesquisar/fluxo?${query}`);
    let finalizado = false;

    origem.onmessage = (evento) => {
      let dados;
      try { dados = JSON.parse(evento.data); } catch (_) { return; }
      if (dados.tipo === "fim" || dados.tipo === "erro") finalizado = true;
      aoEvento(dados);
      if (dados.tipo === "salvo") origem.close();
    };
    origem.onerror = () => {
      origem.close();
      if (!finalizado && aoErro) {
        aoErro(new Error("A conexão com o servidor caiu durante a pesquisa."));
      }
    };
    return () => origem.close();
  }

  global.API = {
    saude: () => obter("/api/saude"),
    fontes: () => obter("/api/fontes"),
    pesquisar: (corpo) => enviar("/api/pesquisar", corpo),
    pesquisarEmFluxo,
    flashcards: (corpo) => enviar("/api/flashcards", corpo),
    quiz: (corpo) => enviar("/api/quiz", corpo),
    plano: (corpo) => enviar("/api/plano", corpo),
    explicar: (corpo) => enviar("/api/explicar", corpo),
    historico: () => obter("/api/historico"),
    historicoItem: (id) => obter(`/api/historico/${id}`),
    apagarHistorico: (id) => remover(`/api/historico/${id}`),
    baralhos: () => obter("/api/baralhos"),
    criarBaralho: (corpo) => enviar("/api/baralhos", corpo),
    apagarBaralho: (id) => remover(`/api/baralhos/${id}`),
    salvarCartoes: (id, cartoes) => enviar(`/api/baralhos/${id}/cartoes`, { cartoes }),
    revisao: (baralhoId) =>
      obter("/api/revisao" + (baralhoId ? `?baralho_id=${baralhoId}` : "")),
    registrarRevisao: (cartaoId, nota) => enviar(`/api/revisao/${cartaoId}`, { nota }),
    estatisticas: () => obter("/api/estatisticas"),
  };
})(window);
