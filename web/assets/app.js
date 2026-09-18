/* ==========================================================================
   Núcleo — aplicação da interface
   ========================================================================== */
(function () {
  "use strict";

  const $  = (seletor, raiz) => (raiz || document).querySelector(seletor);
  const $$ = (seletor, raiz) => Array.from((raiz || document).querySelectorAll(seletor));

  const estado = {
    fontes: [],
    fontesSelecionadas: new Set(),
    profundidade: "media",
    idioma: "pt",
    nivel: "iniciante",
    pesquisaAtual: null,
    flashcardsAtuais: [],
    baralhos: [],
    filaRevisao: [],
    indiceRevisao: 0,
    modeloDisponivel: false,
  };

  const NOMES_FONTE = {};

  /* ======================================================================
     Utilidades de interface
     ====================================================================== */

  function avisar(mensagem, tipo) {
    const caixa = document.createElement("div");
    caixa.className = "toast" + (tipo === "erro" ? " erro" : "");
    caixa.textContent = mensagem;
    $("#avisos").appendChild(caixa);
    setTimeout(() => {
      caixa.classList.add("saindo");
      setTimeout(() => caixa.remove(), 260);
    }, tipo === "erro" ? 6000 : 3600);
  }

  function escapar(texto) { return window.Markdown.escapar(texto == null ? "" : texto); }

  function formatarData(iso) {
    if (!iso) return "";
    const data = new Date(iso);
    if (Number.isNaN(data.getTime())) return iso;
    return data.toLocaleString("pt-BR", {
      day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit",
    });
  }

  function trocarAba(nome) {
    $$(".nav-item").forEach((b) => b.classList.toggle("ativo", b.dataset.aba === nome));
    $$(".aba").forEach((s) => s.classList.toggle("ativa", s.id === `aba-${nome}`));
    window.scrollTo({ top: 0, behavior: "smooth" });
    if (nome === "historico") carregarHistorico();
    if (nome === "revisao") carregarBaralhos();
  }

  function ligarSegmentado(seletor, aoEscolher) {
    $$(`${seletor} button`).forEach((botao) => {
      botao.addEventListener("click", () => {
        $$(`${seletor} button`).forEach((b) => b.classList.remove("ativo"));
        botao.classList.add("ativo");
        aoEscolher(botao.dataset.valor);
      });
    });
  }

  /* ======================================================================
     Arranque
     ====================================================================== */

  async function iniciar() {
    aplicarTemaSalvo();
    ligarEventos();
    try {
      const saude = await window.API.saude();
      estado.fontes = saude.fontes || [];
      estado.modeloDisponivel = !!saude.modelo_disponivel;
      saude.fontes.forEach((f) => { NOMES_FONTE[f.id] = f.nome; });
      desenharFichasFontes();
      desenharGradeFontes();
      marcarEstadoModelo(saude);
    } catch (erro) {
      avisar(erro.message, "erro");
    }
    atualizarProgresso();
  }

  function marcarEstadoModelo(saude) {
    const caixa = $("#estado-modelo");
    const texto = $("#estado-texto");
    if (saude.modelo_disponivel) {
      caixa.classList.add("neural");
      texto.textContent = "Síntese neural ativa";
      caixa.title = `Modelo: ${saude.modelo}`;
    } else {
      caixa.classList.add("extrativo");
      texto.textContent = "Modo extrativo";
      caixa.title = "Sem ANTHROPIC_API_KEY: as respostas usam apenas trechos literais das fontes.";
    }
  }

  function aplicarTemaSalvo() {
    const salvo = localStorage.getItem("nucleo-tema");
    if (salvo) document.documentElement.dataset.tema = salvo;
  }

  function ligarEventos() {
    $$(".nav-item").forEach((b) => b.addEventListener("click", () => trocarAba(b.dataset.aba)));

    $("#alternar-tema").addEventListener("click", () => {
      const atual = document.documentElement.dataset.tema === "claro" ? "escuro" : "claro";
      document.documentElement.dataset.tema = atual;
      localStorage.setItem("nucleo-tema", atual);
    });

    ligarSegmentado("#seg-profundidade", (v) => { estado.profundidade = v; });
    ligarSegmentado("#seg-idioma", (v) => { estado.idioma = v; });
    ligarSegmentado("#seg-nivel", (v) => { estado.nivel = v; });

    $("#form-busca").addEventListener("submit", (evento) => {
      evento.preventDefault();
      pesquisar($("#entrada-pergunta").value.trim());
    });

    $$("#sugestoes button").forEach((botao) => {
      botao.addEventListener("click", () => {
        $("#entrada-pergunta").value = botao.dataset.q;
        pesquisar(botao.dataset.q);
      });
    });

    $("#btn-copiar").addEventListener("click", async () => {
      if (!estado.pesquisaAtual) return;
      try {
        await navigator.clipboard.writeText(estado.pesquisaAtual.resposta);
        avisar("Resposta copiada.");
      } catch (_) { avisar("Não consegui copiar.", "erro"); }
    });

    $$(".ferramenta").forEach((botao) => {
      botao.addEventListener("click", () => usarFerramenta(botao.dataset.ferramenta, botao));
    });

    $("#texto-resposta").addEventListener("click", (evento) => {
      const marca = evento.target.closest(".citacao-marca");
      if (!marca) return;
      evento.preventDefault();
      destacarCitacao(marca.dataset.citacao);
    });

    $("#form-plano").addEventListener("submit", (evento) => {
      evento.preventDefault();
      montarPlano();
    });

    $("#btn-novo-baralho").addEventListener("click", criarBaralho);
    $("#btn-iniciar-revisao").addEventListener("click", iniciarRevisao);

    document.addEventListener("keydown", (evento) => {
      if ((evento.ctrlKey || evento.metaKey) && evento.key === "k") {
        evento.preventDefault();
        trocarAba("pesquisar");
        $("#entrada-pergunta").focus();
      }
    });
  }

  /* ======================================================================
     Fontes
     ====================================================================== */

  function desenharFichasFontes() {
    const caixa = $("#fichas-fontes");
    caixa.innerHTML = "";
    estado.fontes.forEach((fonte) => {
      const ficha = document.createElement("button");
      ficha.type = "button";
      ficha.className = "ficha";
      ficha.dataset.fonte = fonte.id;
      ficha.title = fonte.descricao;
      ficha.innerHTML = `<span class="marcador"></span>${escapar(fonte.nome)}`;
      ficha.addEventListener("click", () => {
        if (estado.fontesSelecionadas.has(fonte.id)) {
          estado.fontesSelecionadas.delete(fonte.id);
          ficha.classList.remove("ativa");
        } else {
          estado.fontesSelecionadas.add(fonte.id);
          ficha.classList.add("ativa");
        }
        $("#rotulo-auto").textContent = estado.fontesSelecionadas.size
          ? `(${estado.fontesSelecionadas.size} escolhida(s))`
          : "(automático pela área da pergunta)";
      });
      caixa.appendChild(ficha);
    });
  }

  function desenharGradeFontes() {
    $("#grade-fontes").innerHTML = estado.fontes.map((fonte) => `
      <article class="fonte-cartao">
        <h3>${escapar(fonte.nome)}</h3>
        <span class="dominio">${escapar(fonte.dominio)}</span>
        <p>${escapar(fonte.descricao)}</p>
        <div class="areas">${(fonte.areas || [])
          .map((a) => `<span class="area-tag">${escapar(a)}</span>`).join("")}</div>
      </article>`).join("");
  }

  /* ======================================================================
     Pesquisa
     ====================================================================== */

  function pesquisar(pergunta) {
    if (!pergunta) { avisar("Escreva uma pergunta primeiro.", "erro"); return; }

    const botao = $("#botao-buscar");
    botao.disabled = true;
    $("#cabecalho-inicial").style.display = "none";
    $("#sugestoes").hidden = true;
    $("#progresso-busca").hidden = false;
    $("#etapas").innerHTML = "";
    $("#resultado").hidden = true;
    $("#area-ferramenta").innerHTML = "";
    $("#texto-resposta").innerHTML = "";
    $("#aviso-resposta").hidden = true;

    let acumulado = "";
    const parcial = { pergunta, resposta: "", citacoes: [] };

    const encerrar = () => { botao.disabled = false; $("#progresso-busca").hidden = true; };

    window.API.pesquisarEmFluxo(
      {
        pergunta,
        fontes: Array.from(estado.fontesSelecionadas),
        idioma: estado.idioma,
        profundidade: estado.profundidade,
      },
      (evento) => {
        switch (evento.tipo) {
          case "etapa":
            registrarEtapa(evento.rotulo);
            break;

          case "fontes":
            registrarEtapa(`${evento.documentos} documentos recuperados`);
            desenharDiagnostico(evento.itens);
            break;

          case "citacoes":
            parcial.citacoes = evento.itens || [];
            parcial.documentos = evento.documentos || [];
            desenharCitacoes(parcial.citacoes);
            $("#resultado").hidden = false;
            break;

          case "texto":
            acumulado += evento.conteudo;
            $("#texto-resposta").innerHTML =
              window.Markdown.renderizar(acumulado, { citacoes: true });
            $("#texto-resposta").classList.add("cursor-digitando");
            break;

          case "fim": {
            $("#texto-resposta").classList.remove("cursor-digitando");
            parcial.resposta = evento.resposta || acumulado;
            parcial.area = evento.area;
            parcial.modo = evento.modo;
            estado.pesquisaAtual = parcial;
            $("#texto-resposta").innerHTML =
              window.Markdown.renderizar(parcial.resposta, { citacoes: true });
            desenharMeta(evento, parcial.citacoes.length);
            if (evento.aviso) {
              $("#aviso-resposta").textContent = evento.aviso;
              $("#aviso-resposta").hidden = false;
            }
            encerrar();
            atualizarProgresso();
            break;
          }

          case "erro":
            avisar(evento.mensagem || "Falha na pesquisa.", "erro");
            encerrar();
            break;
        }
      },
      (erro) => { avisar(erro.message, "erro"); encerrar(); }
    );
  }

  function registrarEtapa(rotulo) {
    const lista = $("#etapas");
    $$("li", lista).forEach((li) => li.classList.add("concluida"));
    const item = document.createElement("li");
    item.textContent = rotulo;
    lista.appendChild(item);
  }

  function desenharMeta(evento, quantasCitacoes) {
    const modo = evento.modo === "neural"
      ? '<span class="pilula jade">síntese neural</span>'
      : '<span class="pilula ambar">modo extrativo</span>';
    $("#pilulas-meta").innerHTML = [
      modo,
      `<span class="pilula violeta">área: ${escapar(evento.area || "geral")}</span>`,
      `<span class="pilula">${quantasCitacoes} referências</span>`,
      `<span class="pilula">${((evento.duracao_ms || 0) / 1000).toFixed(1)}s</span>`,
    ].join("");
  }

  function desenharCitacoes(citacoes) {
    $("#contagem-citacoes").textContent = citacoes.length;
    if (!citacoes.length) {
      $("#lista-citacoes").innerHTML =
        '<p style="color:var(--texto-3);font-size:13px">Nenhuma fonte encontrada.</p>';
      return;
    }
    $("#lista-citacoes").innerHTML = citacoes.map((c) => {
      const autores = (c.autores || []).slice(0, 2).join(", ");
      const meta = [
        `<span class="etiqueta-fonte">${escapar(NOMES_FONTE[c.fonte] || c.fonte)}</span>`,
        autores ? `<span>${escapar(autores)}${(c.autores || []).length > 2 ? " et al." : ""}</span>` : "",
        c.ano ? `<span>${c.ano}</span>` : "",
        (c.extra && c.extra.citacoes) ? `<span>${c.extra.citacoes} citações</span>` : "",
      ].filter(Boolean).join("");
      return `
        <li class="citacao" id="citacao-${c.numero}">
          <span class="citacao-numero">${c.numero}</span>
          <div>
            <a class="citacao-titulo" href="${escapar(c.url)}" target="_blank" rel="noopener noreferrer">
              ${escapar(c.titulo)}
            </a>
            <div class="citacao-meta">${meta}</div>
          </div>
        </li>`;
    }).join("");
  }

  function destacarCitacao(numero) {
    const alvo = $(`#citacao-${numero}`);
    if (!alvo) return;
    $$(".citacao").forEach((c) => c.classList.remove("destacada"));
    alvo.classList.add("destacada");
    alvo.scrollIntoView({ behavior: "smooth", block: "center" });
    setTimeout(() => alvo.classList.remove("destacada"), 2400);
  }

  function desenharDiagnostico(itens) {
    $("#lista-diagnostico").innerHTML = (itens || []).map((item) => {
      const classe = item.erro ? "falha" : (item.itens ? "ok" : "vazio");
      const detalhe = item.erro
        ? escapar(item.erro)
        : (item.cache ? "em cache" : `${item.duracao_ms} ms`);
      return `
        <li class="diag" title="${escapar(item.erro || "")}">
          <span class="status ${classe}"></span>
          <span>${escapar(item.nome)}</span>
          <span class="quanto">${item.itens} · ${detalhe}</span>
        </li>`;
    }).join("");
  }

  /* ======================================================================
     Ferramentas de estudo
     ====================================================================== */

  async function usarFerramenta(nome, botao) {
    if (!estado.pesquisaAtual) { avisar("Faça uma pesquisa primeiro.", "erro"); return; }
    const pergunta = estado.pesquisaAtual.pergunta;
    const fontes = Array.from(estado.fontesSelecionadas);
    botao.classList.add("carregando");
    const area = $("#area-ferramenta");
    area.innerHTML = '<div class="cartao"><div class="esqueleto" style="height:16px;width:40%"></div>'
      + '<div class="esqueleto" style="height:12px;margin-top:12px"></div>'
      + '<div class="esqueleto" style="height:12px;margin-top:8px;width:80%"></div></div>';

    try {
      if (nome === "flashcards") {
        const dados = await window.API.flashcards({ pergunta, fontes, quantidade: 8 });
        estado.flashcardsAtuais = dados.cartoes || [];
        desenharFlashcards(dados);
      } else if (nome === "quiz") {
        const dados = await window.API.quiz({ pergunta, fontes, quantidade: 5 });
        desenharQuiz(dados);
      } else {
        const dados = await window.API.explicar({
          conceito: pergunta, nivel: estado.nivel, fontes,
        });
        desenharExplicacao(dados, pergunta, fontes);
      }
    } catch (erro) {
      area.innerHTML = "";
      avisar(erro.message, "erro");
    } finally {
      botao.classList.remove("carregando");
    }
  }

  function desenharFlashcards(dados) {
    const cartoes = dados.cartoes || [];
    if (!cartoes.length) {
      $("#area-ferramenta").innerHTML =
        '<div class="cartao"><p>Não consegui extrair cartões deste material.</p></div>';
      return;
    }
    const selo = dados.modo === "neural"
      ? '<span class="pilula jade">gerados pelo modelo</span>'
      : '<span class="pilula ambar">extraídos das fontes</span>';

    $("#area-ferramenta").innerHTML = `
      <div class="cartao">
        <h2 class="titulo-secao">Flashcards <span class="contagem">${cartoes.length}</span></h2>
        <div class="pilulas">${selo}<span class="pilula">clique para virar</span></div>
        <div class="grade-cartoes">
          ${cartoes.map((c, i) => `
            <div class="flashcard" data-indice="${i}">
              <div class="flashcard-interno">
                <div class="flashcard-face">
                  ${c.citacao ? `<span class="origem">[${c.citacao}]</span>` : ""}
                  <b>${escapar(c.frente)}</b>
                  <span class="dica">virar ↻</span>
                </div>
                <div class="flashcard-face verso">
                  <span>${escapar(c.verso)}</span>
                  <span class="dica">↻</span>
                </div>
              </div>
            </div>`).join("")}
        </div>
        <div class="barra-salvar">
          <select class="seletor" id="destino-baralho"></select>
          <button class="botao-primario" id="btn-salvar-cartoes">
            Salvar ${cartoes.length} cartões para revisão
          </button>
        </div>
      </div>`;

    $$("#area-ferramenta .flashcard").forEach((el) =>
      el.addEventListener("click", () => el.classList.toggle("virado")));

    preencherSeletorBaralhos("#destino-baralho").then(() => {
      $("#btn-salvar-cartoes").addEventListener("click", salvarFlashcards);
    });
  }

  async function salvarFlashcards() {
    const seletor = $("#destino-baralho");
    const baralhoId = Number(seletor.value);
    if (!baralhoId) { avisar("Crie um baralho antes de salvar.", "erro"); return; }
    const cartoes = estado.flashcardsAtuais.map((c) => ({
      frente: c.frente,
      verso: c.verso,
      fonte_url: c.fonte_url || "",
      fonte_titulo: c.fonte_titulo || "",
      dificuldade: ["facil", "media", "dificil"].includes(c.dificuldade) ? c.dificuldade : "media",
    }));
    try {
      const resultado = await window.API.salvarCartoes(baralhoId, cartoes);
      const repetidos = resultado.enviados - resultado.inseridos;
      avisar(`${resultado.inseridos} cartões salvos.`
        + (repetidos > 0 ? ` ${repetidos} já existiam no baralho.` : ""));
      atualizarProgresso();
    } catch (erro) { avisar(erro.message, "erro"); }
  }

  function desenharQuiz(dados) {
    const questoes = dados.questoes || [];
    if (!questoes.length) {
      $("#area-ferramenta").innerHTML =
        '<div class="cartao"><p>Não consegui montar questões com este material.</p></div>';
      return;
    }
    const selo = dados.modo === "neural"
      ? '<span class="pilula jade">geradas pelo modelo</span>'
      : '<span class="pilula ambar">lacunas extraídas das fontes</span>';
    const letras = ["A", "B", "C", "D", "E"];

    $("#area-ferramenta").innerHTML = `
      <div class="cartao">
        <h2 class="titulo-secao">Quiz <span class="contagem">${questoes.length}</span></h2>
        <div class="pilulas">${selo}</div>
        ${questoes.map((q, i) => `
          <div class="questao" data-questao="${i}" data-correta="${q.correta}">
            <p class="questao-enunciado">
              <span class="indice">${i + 1}</span>
              <span>${escapar(q.pergunta)}</span>
            </p>
            <div class="alternativas">
              ${q.alternativas.map((alternativa, j) => `
                <button class="alternativa" data-opcao="${j}">
                  <span class="letra">${letras[j]}</span>
                  <span>${escapar(alternativa)}</span>
                </button>`).join("")}
            </div>
            <div class="explicacao" hidden>${escapar(q.explicacao || "")}
              ${q.citacao ? ` <a class="citacao-marca" href="#citacao-${q.citacao}">${q.citacao}</a>` : ""}
            </div>
          </div>`).join("")}
        <div class="placar" id="placar" hidden><b>0</b><span></span></div>
      </div>`;

    let respondidas = 0, acertos = 0;
    $$("#area-ferramenta .questao").forEach((caixa) => {
      const correta = Number(caixa.dataset.correta);
      $$(".alternativa", caixa).forEach((botao) => {
        botao.addEventListener("click", () => {
          if (caixa.dataset.respondida) return;
          caixa.dataset.respondida = "1";
          const escolha = Number(botao.dataset.opcao);
          $$(".alternativa", caixa).forEach((b, indice) => {
            b.disabled = true;
            if (indice === correta) b.classList.add("certa");
            else if (indice === escolha) b.classList.add("errada");
          });
          $(".explicacao", caixa).hidden = false;
          respondidas += 1;
          if (escolha === correta) acertos += 1;
          const placar = $("#placar");
          placar.hidden = false;
          $("b", placar).textContent = `${acertos}/${respondidas}`;
          $("span", placar).textContent = respondidas === $$("#area-ferramenta .questao").length
            ? (acertos === respondidas
                ? "Gabaritou. Salve os flashcards e revise em 3 dias."
                : "Revise as questões erradas e gere flashcards sobre elas.")
            : "continue respondendo…";
        });
      });
    });
  }

  function desenharExplicacao(dados, pergunta, fontes) {
    const niveis = [
      ["iniciante", "Do zero"],
      ["intermediario", "Graduação"],
      ["avancado", "Avançado"],
    ];
    $("#area-ferramenta").innerHTML = `
      <div class="cartao">
        <h2 class="titulo-secao">Explicação</h2>
        <div class="segmentado" id="seg-explicacao" style="margin-bottom:14px">
          ${niveis.map(([valor, rotulo]) => `
            <button type="button" data-valor="${valor}"
              class="${valor === dados.nivel ? "ativo" : ""}">${rotulo}</button>`).join("")}
        </div>
        <article class="markdown" id="texto-explicacao">
          ${window.Markdown.renderizar(dados.texto || "", { citacoes: true })}
        </article>
      </div>`;

    $$("#seg-explicacao button").forEach((botao) => {
      botao.addEventListener("click", async () => {
        $$("#seg-explicacao button").forEach((b) => b.classList.remove("ativo"));
        botao.classList.add("ativo");
        estado.nivel = botao.dataset.valor;
        $("#texto-explicacao").innerHTML = '<div class="esqueleto" style="height:14px"></div>';
        try {
          const novo = await window.API.explicar({
            conceito: pergunta, nivel: botao.dataset.valor, fontes,
          });
          $("#texto-explicacao").innerHTML =
            window.Markdown.renderizar(novo.texto || "", { citacoes: true });
        } catch (erro) { avisar(erro.message, "erro"); }
      });
    });
  }

  /* ======================================================================
     Plano de estudo
     ====================================================================== */

  async function montarPlano() {
    const tema = $("#plano-tema").value.trim();
    if (!tema) return;
    const area = $("#area-plano");
    area.innerHTML = '<div class="cartao"><div class="esqueleto" style="height:16px;width:50%"></div>'
      + '<div class="esqueleto" style="height:12px;margin-top:14px"></div>'
      + '<div class="esqueleto" style="height:12px;margin-top:8px;width:70%"></div></div>';
    try {
      const plano = await window.API.plano({
        tema,
        semanas: Number($("#plano-semanas").value) || 4,
        horas_semana: Number($("#plano-horas").value) || 5,
        nivel: estado.nivel,
        usar_fontes: true,
      });
      desenharPlano(plano);
    } catch (erro) {
      area.innerHTML = "";
      avisar(erro.message, "erro");
    }
  }

  function desenharPlano(plano) {
    const sessoes = plano.sessoes || [];
    const selo = plano.modo === "neural"
      ? '<span class="pilula jade">montado pelo modelo</span>'
      : '<span class="pilula ambar">montado a partir das fontes</span>';

    $("#area-plano").innerHTML = `
      <div class="cartao">
        <div class="pilulas" style="margin-bottom:12px">
          ${selo}<span class="pilula">${sessoes.length} sessões</span>
        </div>
        <h2 style="margin:0 0 6px;font-size:22px">${escapar(plano.titulo || "")}</h2>
        <p style="color:var(--texto-2);margin:0">${escapar(plano.resumo || "")}</p>

        ${(plano.pre_requisitos || []).length ? `
          <h3 style="font-size:14px;margin:20px 0 8px">Pré-requisitos</h3>
          <div class="areas">${plano.pre_requisitos
            .map((p) => `<span class="area-tag">${escapar(p)}</span>`).join("")}</div>` : ""}

        <div class="linha-tempo">
          ${sessoes.map((s) => `
            <div class="sessao">
              <h4>${escapar(s.titulo || `Sessão ${s.numero}`)}</h4>
              <p class="objetivo">${escapar(s.objetivo || "")}</p>
              ${s.atividade ? `<div class="atividade">${escapar(s.atividade)}</div>` : ""}
              <div class="rodape">
                ${(s.topicos || []).map((t) => `<span class="area-tag">${escapar(t)}</span>`).join("")}
                ${s.duracao_min ? `<span class="area-tag">${s.duracao_min} min</span>` : ""}
              </div>
            </div>`).join("")}
        </div>

        ${plano.avaliacao ? `
          <h3 style="font-size:14px;margin:18px 0 8px">Como se avaliar</h3>
          <p style="color:var(--texto-2);margin:0;font-size:14px">${escapar(plano.avaliacao)}</p>` : ""}

        ${(plano.recursos || []).length ? `
          <h3 style="font-size:14px;margin:18px 0 8px">Recursos</h3>
          <ul style="margin:0;padding-left:18px;font-size:13.4px">
            ${plano.recursos.map((r) => `<li><a href="${escapar(r)}" target="_blank"
              rel="noopener noreferrer" style="color:var(--azul)">${escapar(r)}</a></li>`).join("")}
          </ul>` : ""}
      </div>`;
  }

  /* ======================================================================
     Histórico
     ====================================================================== */

  async function carregarHistorico() {
    try {
      const itens = await window.API.historico();
      const lista = $("#lista-historico");
      if (!itens.length) {
        lista.innerHTML = '<p style="color:var(--texto-3);font-size:14px;margin:0">'
          + "Nada por aqui ainda. Suas pesquisas aparecem nesta lista.</p>";
        return;
      }
      lista.innerHTML = itens.map((item) => `
        <li class="item-historico" data-id="${item.id}">
          <div class="texto">
            <b>${escapar(item.pergunta)}</b>
            <small>${escapar(item.area)} · ${item.modo === "neural" ? "neural" : "extrativo"}
              · ${formatarData(item.criada_em)}</small>
          </div>
          <button data-acao="abrir" title="Abrir">abrir</button>
          <button data-acao="apagar" title="Apagar">✕</button>
        </li>`).join("");

      $$(".item-historico").forEach((li) => {
        const id = Number(li.dataset.id);
        $('[data-acao="abrir"]', li).addEventListener("click", () => abrirHistorico(id));
        $('[data-acao="apagar"]', li).addEventListener("click", async () => {
          try {
            await window.API.apagarHistorico(id);
            li.remove();
            atualizarProgresso();
          } catch (erro) { avisar(erro.message, "erro"); }
        });
      });
    } catch (erro) { avisar(erro.message, "erro"); }
  }

  async function abrirHistorico(id) {
    try {
      const item = await window.API.historicoItem(id);
      trocarAba("pesquisar");
      $("#cabecalho-inicial").style.display = "none";
      $("#sugestoes").hidden = true;
      $("#resultado").hidden = false;
      $("#entrada-pergunta").value = item.pergunta;
      $("#texto-resposta").innerHTML =
        window.Markdown.renderizar(item.resposta || "", { citacoes: true });
      desenharCitacoes(item.citacoes || []);
      $("#lista-diagnostico").innerHTML =
        '<li class="diag"><span class="status vazio"></span><span>registro salvo</span></li>';
      $("#pilulas-meta").innerHTML =
        `<span class="pilula violeta">área: ${escapar(item.area || "geral")}</span>`
        + `<span class="pilula">${(item.citacoes || []).length} referências</span>`
        + `<span class="pilula">${formatarData(item.criada_em)}</span>`;
      estado.pesquisaAtual = {
        pergunta: item.pergunta, resposta: item.resposta, citacoes: item.citacoes || [],
      };
    } catch (erro) { avisar(erro.message, "erro"); }
  }

  /* ======================================================================
     Baralhos e revisão espaçada
     ====================================================================== */

  async function carregarBaralhos() {
    try {
      estado.baralhos = await window.API.baralhos();
    } catch (erro) { avisar(erro.message, "erro"); return; }

    const seletor = $("#seletor-baralho");
    seletor.innerHTML = estado.baralhos.map((b) =>
      `<option value="${b.id}">${escapar(b.nome)} (${b.devidos} para hoje)</option>`).join("");

    $("#grade-baralhos").innerHTML = estado.baralhos.length
      ? estado.baralhos.map((b) => `
          <div class="baralho">
            <h4>${escapar(b.nome)}</h4>
            <p>${escapar(b.descricao || "sem descrição")}</p>
            <div class="numeros">
              <span><b>${b.total}</b> cartões</span>
              <span><b>${b.devidos}</b> para hoje</span>
            </div>
          </div>`).join("")
      : '<p style="color:var(--texto-3);font-size:14px;margin:0">Nenhum baralho ainda.</p>';
  }

  async function preencherSeletorBaralhos(seletorCss) {
    if (!estado.baralhos.length) {
      try { estado.baralhos = await window.API.baralhos(); } catch (_) { estado.baralhos = []; }
    }
    const elemento = $(seletorCss);
    if (!elemento) return;
    elemento.innerHTML = estado.baralhos.map((b) =>
      `<option value="${b.id}">${escapar(b.nome)}</option>`).join("");
  }

  async function criarBaralho() {
    const nome = prompt("Nome do novo baralho:");
    if (!nome || !nome.trim()) return;
    try {
      await window.API.criarBaralho({ nome: nome.trim(), descricao: "" });
      await carregarBaralhos();
      avisar("Baralho criado.");
    } catch (erro) { avisar(erro.message, "erro"); }
  }

  async function iniciarRevisao() {
    const baralhoId = Number($("#seletor-baralho").value) || null;
    try {
      estado.filaRevisao = await window.API.revisao(baralhoId);
    } catch (erro) { avisar(erro.message, "erro"); return; }

    if (!estado.filaRevisao.length) {
      $("#area-revisao").innerHTML = `
        <div class="vazio">
          <svg viewBox="0 0 24 24"><path d="M20 6 9 17l-5-5"/></svg>
          <p>Nada para revisar neste baralho hoje. O SM-2 já reagendou tudo.</p>
        </div>`;
      return;
    }
    estado.indiceRevisao = 0;
    mostrarCartaoRevisao();
  }

  function mostrarCartaoRevisao() {
    const total = estado.filaRevisao.length;
    const indice = estado.indiceRevisao;

    if (indice >= total) {
      $("#area-revisao").innerHTML = `
        <div class="vazio">
          <svg viewBox="0 0 24 24"><path d="M20 6 9 17l-5-5"/></svg>
          <p>Sessão concluída: ${total} cartões revisados. Bom trabalho.</p>
        </div>`;
      carregarBaralhos();
      atualizarProgresso();
      return;
    }

    const cartao = estado.filaRevisao[indice];
    $("#area-revisao").innerHTML = `
      <div class="revisor">
        <div class="revisor-progresso">
          <span>Cartão ${indice + 1} de ${total}</span>
          <span>intervalo atual: ${cartao.intervalo} dia(s)</span>
        </div>
        <div class="revisor-barra"><i style="width:${(indice / total) * 100}%"></i></div>
        <div class="cartao-revisao">
          <div class="frente">${escapar(cartao.frente)}</div>
          <div class="verso" id="verso-revisao" hidden>
            ${escapar(cartao.verso)}
            ${cartao.fonte_url ? `<br><a href="${escapar(cartao.fonte_url)}" target="_blank"
              rel="noopener noreferrer">${escapar(cartao.fonte_titulo || "fonte")}</a>` : ""}
          </div>
        </div>
        <div id="controles-revisao">
          <button class="botao-primario" id="btn-mostrar-verso"
                  style="width:100%;justify-content:center;margin-top:16px">
            Mostrar resposta
          </button>
        </div>
      </div>`;

    $("#btn-mostrar-verso").addEventListener("click", () => {
      $("#verso-revisao").hidden = false;
      $("#controles-revisao").innerHTML = `
        <div class="notas">
          <button class="nota" data-nota="0"><b>Esqueci</b><small>recomeça</small></button>
          <button class="nota" data-nota="3"><b>Difícil</b><small>lembrei com esforço</small></button>
          <button class="nota" data-nota="4"><b>Bom</b><small>lembrei</small></button>
          <button class="nota" data-nota="5"><b>Fácil</b><small>na hora</small></button>
        </div>`;
      $$(".nota").forEach((botao) => {
        botao.addEventListener("click", () => registrarNota(cartao.id, Number(botao.dataset.nota)));
      });
    });
  }

  async function registrarNota(cartaoId, nota) {
    try {
      const dados = await window.API.registrarRevisao(cartaoId, nota);
      avisar(`Próxima revisão em ${dados.intervalo} dia(s).`);
    } catch (erro) { avisar(erro.message, "erro"); }
    estado.indiceRevisao += 1;
    mostrarCartaoRevisao();
  }

  /* ======================================================================
     Progresso
     ====================================================================== */

  async function atualizarProgresso() {
    try {
      const dados = await window.API.estatisticas();
      $("#m-cartoes").textContent = dados.total_cartoes;
      $("#m-devidos").textContent = dados.cartoes_devidos;
      $("#m-dominados").textContent = dados.cartoes_dominados;
      $("#m-acerto").textContent = `${dados.taxa_acerto}%`;
      const selo = $("#selo-devidos");
      selo.textContent = dados.cartoes_devidos;
      selo.hidden = dados.cartoes_devidos === 0;
    } catch (_) { /* painel é secundário */ }
  }

  document.addEventListener("DOMContentLoaded", iniciar);
})();
