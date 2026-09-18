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
    livros: [],
    catalogo: [],
    nivelAluno: "intermediario",
    nivelPista: 0,
    topicosMat: [],
    topicoMat: "",
    sessaoTutor: null,
    escadaDegraus: [],
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

  function trocarAba(nome, comFoco) {
    const existe = $$(".nav-item").some((b) => b.dataset.aba === nome);
    if (!existe) nome = "pesquisar";

    $$(".nav-item").forEach((b) => {
      const ativo = b.dataset.aba === nome;
      b.classList.toggle("ativo", ativo);
      b.setAttribute("aria-selected", ativo ? "true" : "false");
      b.tabIndex = ativo ? 0 : -1;
      if (ativo && comFoco) b.focus();
    });
    $$(".aba").forEach((s) => s.classList.toggle("ativa", s.id === `aba-${nome}`));

    /* A aba entra no endereço: recarregar a página mantém onde você estava,
       e o link pode ser compartilhado. */
    if (window.location.hash !== `#${nome}`) {
      window.history.replaceState(null, "", `#${nome}`);
    }
    try { localStorage.setItem("nucleo-aba", nome); } catch (_) { /* modo privado */ }

    window.scrollTo({ top: 0, behavior: "smooth" });
    if (nome === "historico") carregarHistorico();
    if (nome === "revisao") carregarBaralhos();
    if (nome === "biblioteca") carregarBiblioteca();
    if (nome === "matematica") carregarTopicosMat();
    if (nome === "tutor") carregarEscada();
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
    ligarPaleta();
    ligarCapturaDeErros();
    restaurarAba();
    try {
      const saude = await window.API.saude();
      estado.fontes = saude.fontes || [];
      estado.modeloDisponivel = !!saude.modelo_disponivel;
      saude.fontes.forEach((f) => { NOMES_FONTE[f.id] = f.nome; });
      desenharFichasFontes();
      desenharGradeFontes();
      marcarEstadoModelo(saude);
      marcarAcervo(saude.biblioteca);
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

  /** Volta para a aba do endereço ou para a última usada. */
  function restaurarAba() {
    const doEndereco = window.location.hash.replace("#", "");
    let salva = "";
    try { salva = localStorage.getItem("nucleo-aba") || ""; } catch (_) { /* modo privado */ }
    const alvo = doEndereco || salva;
    if (alvo && alvo !== "pesquisar") trocarAba(alvo);
  }

  /** Falha não tratada precisa aparecer, não sumir no console. */
  function ligarCapturaDeErros() {
    window.addEventListener("unhandledrejection", (evento) => {
      const motivo = evento.reason;
      const mensagem = (motivo && motivo.message) || String(motivo || "erro desconhecido");
      avisar(`Algo falhou: ${mensagem}`, "erro");
    });
    window.addEventListener("error", (evento) => {
      if (evento.message) avisar(`Erro na página: ${evento.message}`, "erro");
    });
  }

  function aplicarTemaSalvo() {
    try {
      const salvo = localStorage.getItem("nucleo-tema");
      if (salvo) document.documentElement.dataset.tema = salvo;
    } catch (_) { /* modo privado: fica no tema padrão */ }
  }

  function alternarTema() {
    const atual = document.documentElement.dataset.tema === "claro" ? "escuro" : "claro";
    document.documentElement.dataset.tema = atual;
    try { localStorage.setItem("nucleo-tema", atual); } catch (_) { /* modo privado */ }
  }

  function abasDisponiveis() {
    return $$(".nav-item").map((b) => b.dataset.aba);
  }

  function ligarEventos() {
    $$(".nav-item").forEach((botao) => {
      botao.addEventListener("click", () => trocarAba(botao.dataset.aba));
      botao.addEventListener("keydown", (evento) => {
        const abas = abasDisponiveis();
        const atual = abas.indexOf(botao.dataset.aba);
        const passo = { ArrowDown: 1, ArrowRight: 1, ArrowUp: -1, ArrowLeft: -1 }[evento.key];
        if (passo) {
          evento.preventDefault();
          trocarAba(abas[(atual + passo + abas.length) % abas.length], true);
        } else if (evento.key === "Home") {
          evento.preventDefault();
          trocarAba(abas[0], true);
        } else if (evento.key === "End") {
          evento.preventDefault();
          trocarAba(abas[abas.length - 1], true);
        }
      });
    });

    window.addEventListener("hashchange", () => {
      const alvo = window.location.hash.replace("#", "");
      if (alvo) trocarAba(alvo);
    });

    $("#alternar-tema").addEventListener("click", alternarTema);
    $("#abrir-paleta").addEventListener("click", abrirPaleta);
    $("#btn-aferir").addEventListener("click", rodarAfericao);

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

    ligarEnvioDeLivros();
    ligarMatematica();
    ligarTutor();
    ligarGramatica();
    $("#btn-novo-baralho").addEventListener("click", criarBaralho);
    $("#btn-iniciar-revisao").addEventListener("click", iniciarRevisao);

    document.addEventListener("keydown", (evento) => {
      if ((evento.ctrlKey || evento.metaKey) && evento.key.toLowerCase() === "k") {
        evento.preventDefault();
        abrirPaleta();
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
            desenharBasesConsultadas(evento.itens);
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

          case "verificacao":
            desenharVerificacao(evento.relatorio);
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
            marcarFrasesFracas();
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
    const pilulas = [
      evento.modo === "neural"
        ? '<span class="pilula jade">síntese neural</span>'
        : '<span class="pilula ambar">modo extrativo</span>',
      `<span class="pilula violeta">área: ${escapar(evento.area || "geral")}</span>`,
    ];
    if (evento.intencao_rotulo) {
      pilulas.push(`<span class="pilula">pergunta de ${escapar(evento.intencao_rotulo)}</span>`);
    }
    if (evento.consulta_en) {
      pilulas.push(
        `<span class="pilula" title="As bases em inglês receberam este termo">`
        + `também buscou “${escapar(evento.consulta_en)}”</span>`
      );
    }
    if ((evento.termos_aprendidos || []).length) {
      pilulas.push(
        `<span class="pilula" title="Termos aprendidos na 1ª rodada e usados na 2ª">`
        + `2ª rodada: ${escapar(evento.termos_aprendidos.slice(0, 3).join(", "))}</span>`
      );
    }
    pilulas.push(`<span class="pilula">${quantasCitacoes} referências</span>`);
    pilulas.push(`<span class="pilula">${((evento.duracao_ms || 0) / 1000).toFixed(1)}s</span>`);
    $("#pilulas-meta").innerHTML = pilulas.join("");
  }

  function desenharCitacoes(citacoes) {
    $("#contagem-citacoes").textContent = citacoes.length;
    if (!citacoes.length) {
      $("#lista-citacoes").innerHTML =
        '<p style="color:var(--texto-3);font-size:13px">Nenhuma fonte encontrada.</p>';
      return;
    }
    $("#lista-citacoes").innerHTML = citacoes.map((c) => {
      const extra = c.extra || {};
      const deLivro = !!extra.local;
      const autores = (c.autores || []).slice(0, 2).join(", ");
      const meta = [
        `<span class="etiqueta-fonte">${escapar(NOMES_FONTE[c.fonte] || c.fonte)}</span>`,
        autores ? `<span>${escapar(autores)}${(c.autores || []).length > 2 ? " et al." : ""}</span>` : "",
        c.ano ? `<span>${escapar(c.ano)}</span>` : "",
        extra.citacoes ? `<span>${numero(extra.citacoes)} citações</span>` : "",
        deLivro && extra.paginado && extra.pagina
          ? `<span>página ${numero(extra.pagina)}</span>` : "",
        deLivro && extra.capitulo ? `<span>${escapar(extra.capitulo)}</span>` : "",
      ].filter(Boolean).join("");

      /* Livro local não tem link externo: abre o trecho em contexto. */
      const titulo = deLivro && !c.url
        ? `<span class="citacao-titulo sem-link" data-trecho="${identificador(extra.trecho_id)}"
             title="Ver o trecho no livro">${escapar(c.titulo)}</span>`
        : `<a class="citacao-titulo" href="${endereco(c.url)}" target="_blank"
             rel="noopener noreferrer">${escapar(c.titulo)}</a>`;

      return `
        <li class="citacao${deLivro ? " de-livro" : ""}" id="citacao-${identificador(c.numero)}">
          <span class="citacao-numero">${escapar(c.numero)}</span>
          <div>
            ${titulo}
            <div class="citacao-meta">${meta}</div>
          </div>
        </li>`;
    }).join("");

    $$("#lista-citacoes .citacao-titulo.sem-link").forEach((elemento) => {
      elemento.addEventListener("click", () => abrirTrechoDoLivro(elemento));
    });
  }

  async function abrirTrechoDoLivro(elemento) {
    const caixa = elemento.closest(".citacao");
    const existente = $(".trecho-livro", caixa);
    if (existente) { existente.remove(); return; }
    const id = elemento.dataset.trecho;
    if (!id) return;
    try {
      const dados = await window.API.trechoDoLivro(id);
      const painel = document.createElement("div");
      painel.className = "trecho-livro";
      painel.textContent = dados.texto;
      caixa.appendChild(painel);
    } catch (erro) { avisar(erro.message, "erro"); }
  }

  /* ====================================================================
     Checagem de fundamentação
     ==================================================================== */

  function faixa(valor) {
    if (valor >= 0.75) return "alto";
    if (valor >= 0.45) return "medio";
    return "baixo";
  }

  function desenharVerificacao(relatorio) {
    if (!relatorio) { $("#cartao-verificacao").hidden = true; return; }
    estado.verificacao = relatorio;

    const cobertura = Math.round((relatorio.cobertura || 0) * 100);
    const solidez = Math.round((relatorio.solidez || 0) * 100);
    const veredito = relatorio.confiavel
      ? '<div class="veredito ok">✓ Cada afirmação confere com a fonte citada</div>'
      : '<div class="veredito atencao">⚠ Confira os pontos abaixo antes de estudar por eles</div>';

    $("#corpo-verificacao").innerHTML = `
      ${veredito}
      <div class="medidor">
        <div class="medidor-linha">
          <span class="rotulo" title="Afirmações que trazem citação">com citação</span>
          <span class="medidor-barra"><i class="${faixa(relatorio.cobertura)}" style="width:${cobertura}%"></i></span>
          <span class="valor">${cobertura}%</span>
        </div>
        <div class="medidor-linha">
          <span class="rotulo" title="Citações cujo texto realmente sustenta a afirmação">sustentadas</span>
          <span class="medidor-barra"><i class="${faixa(relatorio.solidez)}" style="width:${solidez}%"></i></span>
          <span class="valor">${solidez}%</span>
        </div>
      </div>
      ${(relatorio.alertas || [])
        .map((a) => `<div class="alerta-verificacao">${escapar(a)}</div>`).join("")}`;
    $("#cartao-verificacao").hidden = false;
  }

  /** Sublinha no texto da resposta as frases que a checagem marcou como frágeis. */
  function marcarFrasesFracas() {
    const relatorio = estado.verificacao;
    if (!relatorio) return;
    const fracas = (relatorio.afirmacoes || [])
      .filter((a) => a.estado === "fraca")
      .map((a) => a.frase.slice(0, 60))
      .filter((t) => t.length > 25);
    if (!fracas.length) return;

    $$("#texto-resposta p, #texto-resposta li").forEach((bloco) => {
      const texto = bloco.textContent;
      if (fracas.some((inicio) => texto.includes(inicio))) {
        bloco.classList.add("frase-fraca");
        bloco.title = "A fonte citada não parece sustentar esta afirmação.";
      }
    });
  }

  function destacarCitacao(numero) {
    const alvo = $(`#citacao-${numero}`);
    if (!alvo) return;
    $$(".citacao").forEach((c) => c.classList.remove("destacada"));
    alvo.classList.add("destacada");
    alvo.scrollIntoView({ behavior: "smooth", block: "center" });
    setTimeout(() => alvo.classList.remove("destacada"), 2400);
  }

  function desenharBasesConsultadas(itens) {
    $("#lista-diagnostico").innerHTML = (itens || []).map((item) => {
      const classe = item.erro ? "falha" : (item.itens ? "ok" : "vazio");
      const detalhe = item.erro
        ? escapar(item.erro)
        : (item.cache ? "em cache" : `${numero(item.duracao_ms, "?")} ms`);
      return `
        <li class="diag" title="${escapar(item.erro || "")}">
          <span class="status ${classe}"></span>
          <span>${escapar(item.nome)}</span>
          <span class="quanto">${numero(item.itens, "0")} · ${detalhe}</span>
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
    if (botao.disabled) return;   // clique duplo disparava duas requisições
    botao.disabled = true;
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
      mostrarErro(area, erro.message,
        "Faça uma pesquisa que traga fontes e tente de novo — estas "
        + "ferramentas trabalham em cima do material recuperado.");
      avisar(erro.message, "erro");
    } finally {
      botao.classList.remove("carregando");
      botao.disabled = false;
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
                  ${c.citacao ? `<span class="origem">[${escapar(c.citacao)}]</span>` : ""}
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
              ${q.citacao ? ` <a class="citacao-marca" href="#citacao-${identificador(q.citacao)}">${escapar(q.citacao)}</a>` : ""}
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
      mostrarErro(area, erro.message);
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
                ${s.duracao_min ? `<span class="area-tag">${numero(s.duracao_min)} min</span>` : ""}
              </div>
            </div>`).join("")}
        </div>

        ${plano.avaliacao ? `
          <h3 style="font-size:14px;margin:18px 0 8px">Como se avaliar</h3>
          <p style="color:var(--texto-2);margin:0;font-size:14px">${escapar(plano.avaliacao)}</p>` : ""}

        ${(plano.recursos || []).length ? `
          <h3 style="font-size:14px;margin:18px 0 8px">Recursos</h3>
          <ul style="margin:0;padding-left:18px;font-size:13.4px">
            ${plano.recursos.map((r) => `<li><a href="${endereco(r)}" target="_blank"
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
              <span><b>${numero(b.total, "0")}</b> cartões</span>
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
          <span>intervalo atual: ${numero(cartao.intervalo, "?")} dia(s)</span>
        </div>
        <div class="revisor-barra"><i style="width:${(indice / total) * 100}%"></i></div>
        <div class="cartao-revisao">
          <div class="frente">${escapar(cartao.frente)}</div>
          <div class="verso" id="verso-revisao" hidden>
            ${escapar(cartao.verso)}
            ${cartao.fonte_url ? `<br><a href="${endereco(cartao.fonte_url)}" target="_blank"
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


  /* ====================================================================
     Biblioteca do estudante
     ==================================================================== */

  function marcarAcervo(estatisticas) {
    const selo = $("#selo-livros");
    const quantos = (estatisticas && estatisticas.livros) || 0;
    selo.textContent = quantos;
    selo.hidden = quantos === 0;
  }

  function ligarEnvioDeLivros() {
    const area = $("#area-envio");
    const entrada = $("#entrada-arquivos");

    area.addEventListener("click", () => entrada.click());
    // `role="button"` promete teclado: Enter e Espaço abrem o seletor.
    area.addEventListener("keydown", (evento) => {
      if (evento.key === "Enter" || evento.key === " ") {
        evento.preventDefault();
        entrada.click();
      }
    });
    entrada.addEventListener("change", () => {
      if (entrada.files.length) enviarLivros(entrada.files);
      entrada.value = "";
    });

    ["dragenter", "dragover"].forEach((evento) =>
      area.addEventListener(evento, (e) => {
        e.preventDefault();
        area.classList.add("sobre");
      })
    );
    ["dragleave", "drop"].forEach((evento) =>
      area.addEventListener(evento, (e) => {
        e.preventDefault();
        area.classList.remove("sobre");
      })
    );
    area.addEventListener("drop", (e) => {
      const arquivos = e.dataTransfer && e.dataTransfer.files;
      if (arquivos && arquivos.length) enviarLivros(arquivos);
    });
  }

  const MARCA_ESTADO = { indexado: "✓", duplicado: "·", erro: "✕" };

  function mostrarResultadosDeEnvio(resultados) {
    const lista = $("#resultado-envio");
    (resultados || []).forEach((resultado) => {
      const item = document.createElement("li");
      const marca = MARCA_ESTADO[resultado.estado] || "?";
      const detalhe = resultado.estado === "indexado"
        ? `${resultado.trechos} trechos indexados`
        : (resultado.detalhe || "");
      item.innerHTML = `
        <span class="marca ${escapar(resultado.estado)}">${marca}</span>
        <span>${escapar(resultado.titulo || resultado.arquivo)}</span>
        <span class="detalhe">${escapar(detalhe)}</span>`;
      lista.prepend(item);
    });
  }

  async function enviarLivros(arquivos) {
    const progresso = $("#progresso-envio");
    const quantos = arquivos.length;
    progresso.hidden = false;
    $("#texto-envio").textContent =
      `lendo e indexando ${quantos} arquivo(s)… livros grandes levam alguns segundos`;
    try {
      const dados = await window.API.enviarLivros(arquivos, "");
      mostrarResultadosDeEnvio(dados.resultados);
      const indexados = dados.resultados.filter((r) => r.estado === "indexado").length;
      if (indexados) {
        avisar(`${indexados} livro(s) adicionados à sua biblioteca.`);
      } else {
        avisar("Nenhum livro novo foi indexado.", "erro");
      }
      await carregarBiblioteca();
    } catch (erro) {
      avisar(erro.message, "erro");
    } finally {
      progresso.hidden = true;
    }
  }

  async function carregarBiblioteca() {
    let dados;
    try {
      dados = await window.API.biblioteca();
    } catch (erro) { avisar(erro.message, "erro"); return; }

    estado.livros = dados.livros || [];
    estado.catalogo = dados.catalogo || [];
    const estatisticas = dados.estatisticas || {};
    marcarAcervo(estatisticas);

    const milhar = (n) => (n || 0).toLocaleString("pt-BR");
    $("#metricas-biblioteca").innerHTML = `
      <div class="metrica-grande"><b>${milhar(estatisticas.livros)}</b><span>livros</span></div>
      <div class="metrica-grande"><b>${milhar(estatisticas.trechos)}</b><span>trechos indexados</span></div>
      <div class="metrica-grande"><b>${milhar(estatisticas.palavras)}</b><span>palavras pesquisáveis</span></div>
      <div class="metrica-grande"><b>${escapar(dados.formatos.length)}</b><span>formatos aceitos</span></div>`;

    desenharCatalogo();
    desenharLivros();
  }

  function desenharCatalogo() {
    const jaTem = new Set(estado.livros.map((l) => (l.titulo || "").toLowerCase()));
    $("#contagem-catalogo").textContent = estado.catalogo.length;
    $("#grade-catalogo").innerHTML = estado.catalogo.map((item) => {
      const baixado = jaTem.has(item.titulo.toLowerCase());
      return `
        <button class="item-catalogo${baixado ? " baixado" : ""}" data-chave="${escapar(item.chave)}">
          <b>${escapar(item.titulo)}</b>
          <small>${escapar(item.descricao || "")}</small>
          <span class="rodape">
            <span class="origem">${escapar(item.origem)}</span>
            <span class="area-livro">${escapar(item.area)}</span>
          </span>
        </button>`;
    }).join("");

    $$("#grade-catalogo .item-catalogo").forEach((botao) => {
      botao.addEventListener("click", () => baixarDoCatalogo(botao));
    });
  }

  async function baixarDoCatalogo(botao) {
    const chave = botao.dataset.chave;
    const rotulo = $("b", botao).textContent;
    botao.disabled = true;
    $("small", botao).textContent = "baixando e indexando…";
    try {
      const dados = await window.API.baixarCatalogo([chave]);
      mostrarResultadosDeEnvio(dados.resultados);
      const resultado = (dados.resultados || [])[0] || {};
      if (resultado.estado === "indexado") {
        avisar(`“${rotulo}” entrou na sua biblioteca.`);
      } else {
        avisar(`${rotulo}: ${resultado.detalhe || "não foi possível baixar"}`, "erro");
      }
      await carregarBiblioteca();
    } catch (erro) {
      avisar(erro.message, "erro");
      botao.disabled = false;
    }
  }

  function desenharLivros() {
    $("#contagem-livros").textContent = estado.livros.length;
    if (!estado.livros.length) {
      $("#grade-livros").innerHTML =
        '<p style="color:var(--texto-3);font-size:14px;margin:0">'
        + "Nenhum livro ainda. Envie os seus acima ou baixe um do catálogo aberto.</p>";
      return;
    }
    const milhar = (n) => (n || 0).toLocaleString("pt-BR");
    $("#grade-livros").innerHTML = estado.livros.map((livro) => `
      <article class="livro" data-id="${livro.id}">
        <button class="remover" title="Remover da biblioteca">✕</button>
        <h4>${escapar(livro.titulo)}</h4>
        ${livro.autores ? `<div class="autor">${escapar(livro.autores)}</div>` : ""}
        <div class="numeros">
          <span><b>${milhar(livro.trechos)}</b> trechos</span>
          <span><b>${milhar(livro.palavras)}</b> palavras</span>
          <span>${escapar(livro.formato)}</span>
          ${livro.area ? `<span>${escapar(livro.area)}</span>` : ""}
        </div>
        ${livro.licenca ? `<div class="licenca">${escapar(livro.licenca)}</div>` : ""}
      </article>`).join("");

    $$("#grade-livros .livro").forEach((cartao) => {
      $(".remover", cartao).addEventListener("click", async () => {
        const titulo = $("h4", cartao).textContent;
        if (!confirm(`Remover “${titulo}” da biblioteca?\n\n`
                     + "O arquivo continua na pasta biblioteca/; só o índice é apagado.")) return;
        try {
          await window.API.removerLivro(Number(cartao.dataset.id));
          avisar("Livro removido do índice.");
          await carregarBiblioteca();
        } catch (erro) { avisar(erro.message, "erro"); }
      });
    });
  }


  /* ====================================================================
     Motor matemático
     ==================================================================== */

  /* Conversões de LaTeX para texto, usadas só quando o KaTeX não carrega
     (máquina offline, CDN bloqueada). Não é um renderizador: é o suficiente
     para a fórmula continuar legível em vez de virar uma sopa de contrabarras. */
  const LATEX_PARA_TEXTO = [
    [/\\left|\\right|\\,|\\!|\\;/g, ""],
    /* sqrt antes de frac: \frac{81 \sqrt{2}}{2} tem chave aninhada, e o
       padrão de frac só casa conteúdo sem chaves. */
    [/\\sqrt\s*\[([^\]]*)\]\s*\{([^{}]*)\}/g, "raiz$1($2)"],
    [/\\sqrt\s*\{([^{}]*)\}/g, "√($1)"],
    [/\\d?frac\s*\{([^{}]*)\}\s*\{([^{}]*)\}/g, "($1)/($2)"],
    [/\\mathrm\s*\{([^{}]*)\}/g, "$1"],
    [/\^\{([^{}]*)\}/g, "^$1"],
    [/_\{([^{}]*)\}/g, "_$1"],
    [/\\in\b/g, "∈"], [/\\cdot\b/g, "·"], [/\\times\b/g, "×"],
    [/\\pi\b/g, "π"], [/\\theta\b/g, "θ"], [/\\Delta\b/g, "Δ"],
    [/\\alpha\b/g, "α"], [/\\beta\b/g, "β"], [/\\lambda\b/g, "λ"],
    [/\\infty\b/g, "∞"], [/\\varnothing\b/g, "∅"], [/\\emptyset\b/g, "∅"],
    [/\\leq\b/g, "≤"], [/\\geq\b/g, "≥"], [/\\neq\b/g, "≠"],
    [/\\pm\b/g, "±"], [/\\approx\b/g, "≈"], [/\\cup\b/g, "∪"], [/\\cap\b/g, "∩"],
    [/\\sen\b|\\sin\b/g, "sen"], [/\\cos\b/g, "cos"], [/\\tan\b|\\tg\b/g, "tg"],
    [/\\log\b/g, "log"], [/\\ln\b/g, "ln"],
    [/\\\{/g, "{"], [/\\\}/g, "}"], [/\\\\/g, " "],
    [/\s{2,}/g, " "],
  ];

  // Expoentes e índices em Unicode. Sem o KaTeX — quando a rede cai ou o
  // estudante está offline — "x^2" vira "x²" em vez de ficar com o acento
  // circunflexo cru no meio da conta.
  const SOBRESCRITOS = {
    0: "⁰", 1: "¹", 2: "²", 3: "³", 4: "⁴", 5: "⁵", 6: "⁶", 7: "⁷",
    8: "⁸", 9: "⁹", "+": "⁺", "-": "⁻", n: "ⁿ", i: "ⁱ",
  };
  const SUBSCRITOS = {
    0: "₀", 1: "₁", 2: "₂", 3: "₃", 4: "₄", 5: "₅", 6: "₆", 7: "₇",
    8: "₈", 9: "₉", "+": "₊", "-": "₋",
    a: "ₐ", e: "ₑ", i: "ᵢ", j: "ⱼ", k: "ₖ", m: "ₘ", n: "ₙ", p: "ₚ",
    x: "ₓ", t: "ₜ",
  };

  /** Converte `x^2` e `r_1` em `x²` e `r₁`, quando todo caractere tem mapa. */
  function emUnicode(texto, mapa, marcador) {
    const padrao = new RegExp(`\\${marcador}([A-Za-z0-9+\\-]+)`, "g");
    return texto.replace(padrao, (inteiro, corpo) => {
      const convertido = [...corpo].map((c) => mapa[c]).join("");
      // Se algum caractere não tem equivalente, mantém a notação original:
      // meia conversão ("x²k") confunde mais do que o texto cru.
      return convertido.length === corpo.length ? convertido : inteiro;
    });
  }

  function textoDeLatex(formula) {
    let saida = formula.replace(/^\$\$?|\$\$?$/g, "");
    // Três passadas: uma fração dentro de outra precisa que a interna
    // desapareça antes de a externa poder casar.
    for (let passada = 0; passada < 3; passada += 1) {
      LATEX_PARA_TEXTO.forEach(([de, para]) => { saida = saida.replace(de, para); });
    }
    saida = emUnicode(saida, SOBRESCRITOS, "^");
    saida = emUnicode(saida, SUBSCRITOS, "_");
    return saida.trim();
  }

  /** Substitui as fórmulas por texto legível quando o KaTeX não está presente. */
  function degradarFormulas(raiz) {
    const percorrer = document.createTreeWalker(raiz, NodeFilter.SHOW_TEXT);
    const alvos = [];
    while (percorrer.nextNode()) {
      if (/\$[^$]/.test(percorrer.currentNode.nodeValue)) alvos.push(percorrer.currentNode);
    }
    alvos.forEach((no) => {
      no.nodeValue = no.nodeValue.replace(
        /(\$\$[^$]+\$\$|\$[^$\n]+\$)/g, (f) => textoDeLatex(f)
      );
    });
  }

  /** Renderiza as fórmulas com KaTeX; sem ele, converte para texto legível. */
  function renderizarFormulas(raiz) {
    if (typeof window.renderMathInElement !== "function") {
      degradarFormulas(raiz);
      return;
    }
    try {
      window.renderMathInElement(raiz, {
        delimiters: [
          { left: "$$", right: "$$", display: true },
          { left: "$", right: "$", display: false },
          { left: "\\[", right: "\\]", display: true },
          { left: "\\(", right: "\\)", display: false },
        ],
        throwOnError: false,
        ignoredTags: ["script", "noscript", "style", "textarea", "pre", "code"],
      });
    } catch (_) { /* fórmula malformada não pode derrubar a página */ }
  }

  function markdownComFormulas(texto) {
    return window.Markdown.renderizar(texto || "", { citacoes: false });
  }

  function ligarMatematica() {
    ligarSegmentado("#seg-nivel-aluno", (v) => { estado.nivelAluno = v; });

    const enunciado = $("#mat-enunciado");
    let temporizador = null;
    enunciado.addEventListener("input", () => {
      estado.nivelPista = 0;
      clearTimeout(temporizador);
      temporizador = setTimeout(diagnosticar, 700);
    });

    $("#mat-resolver").addEventListener("click", resolverMatematica);
    $("#mat-pista").addEventListener("click", pedirPista);
    $("#mat-conferir").addEventListener("click", conferirResposta);
    $("#mat-criar").addEventListener("click", gerarQuestao);
  }

  function enunciadoAtual() {
    const texto = $("#mat-enunciado").value.trim();
    if (texto.length < 3) {
      avisar("Escreva o enunciado do problema primeiro.", "erro");
      return "";
    }
    return texto;
  }

  /* --- diagnóstico ao vivo, sem chamar o modelo --- */
  async function diagnosticar() {
    const texto = $("#mat-enunciado").value.trim();
    const painel = $("#mat-diagnostico");
    if (texto.length < 12) { painel.hidden = true; return; }
    try {
      const dados = await window.API.matDiagnostico({ enunciado: texto });
      const d = dados.diagnostico;
      const nivel = d.dificuldade;
      const classe = nivel >= 4 ? "forte" : nivel === 3 ? "quente" : "";
      const barras = [1, 2, 3, 4]
        .map((i) => `<i class="${i <= nivel ? "aceso " + classe : ""}"></i>`).join("");
      const equacoes = (dados.analise.equacoes || []).length;

      painel.innerHTML = `
        <span class="rotulo-diag">diagnóstico</span>
        <span class="pilula violeta">${escapar(d.topico_nome)}</span>
        <span class="medidor-nivel" title="${escapar(d.dificuldade_descricao)}">
          ${barras}
        </span>
        <span class="pilula">${escapar(d.dificuldade_nome)}</span>
        ${d.pede_demonstracao ? '<span class="pilula ambar">pede demonstração</span>' : ""}
        ${equacoes ? `<span class="pilula jade">${equacoes} equação(ões) lida(s)</span>` : ""}
        ${(d.sinais || []).slice(0, 2)
          .map((s) => `<span class="pilula">${escapar(s)}</span>`).join("")}`;
      painel.hidden = false;
    } catch (_) { painel.hidden = true; }
  }

  function trilhaDePasses(passes) {
    if (!passes || !passes.length) return "";
    return `<div class="trilha-passes">${passes
      .map((p) => `<span class="passe">${escapar(p)}</span>`)
      .join('<span class="seta">→</span>')}</div>`;
  }

  function listaDeChecagens(checagens) {
    if (!checagens || !checagens.length) return "";
    return checagens.map((c) => `
      <div class="checagem ${c.passou ? "passou" : "falhou"}">
        <span class="marca-check">${c.passou ? "✓" : "✕"}</span>
        <span><b>${escapar(c.nome)}</b><br>
          <span class="detalhe-check">${escapar(c.detalhe)}</span></span>
      </div>`).join("");
  }

  function blocoEstrategias(estrategias) {
    const caminhos = (estrategias && estrategias.caminhos) || [];
    if (!caminhos.length) return "";
    const escolhido = estrategias.escolhido || "";
    return `
      <details class="fase">
        <summary>Fase de exploração — ${caminhos.length} caminhos considerados</summary>
        <div class="corpo-fase">
          ${estrategias.estrutura_escondida ? `
            <p><b>Estrutura identificada:</b> ${escapar(estrategias.estrutura_escondida)}</p>` : ""}
          ${caminhos.map((c) => {
            const eEscolhido = c.nome && escolhido && c.nome.trim() === escolhido.trim();
            return `
            <div class="caminho ${eEscolhido ? "escolhido" : ""}">
              ${eEscolhido ? '<span class="selo-escolhido">escolhido</span>' : ""}
              <b>${escapar(c.nome || "")}</b>
              <div>${escapar(c.descricao || "")}</div>
              ${c.risco ? `<div class="risco">Onde pode travar: ${escapar(c.risco)}</div>` : ""}
            </div>`;
          }).join("")}
          ${estrategias.por_que ? `<p><b>Por quê:</b> ${escapar(estrategias.por_que)}</p>` : ""}
        </div>
      </details>`;
  }

  function blocoCritica(critica) {
    if (!critica || !Object.keys(critica).length) return "";
    const problemas = critica.problemas || [];
    const veredito = critica.veredito || "";
    const rotulo = { correta: "nada a corrigir", corrigir: "correções aplicadas",
                     refazer: "solução refeita" }[veredito] || veredito;
    return `
      <details class="fase" ${problemas.length ? "open" : ""}>
        <summary>Crítica interna — ${escapar(rotulo)}</summary>
        <div class="corpo-fase">
          ${problemas.length
            ? problemas.map((p) => `
              <div class="problema-critico ${escapar(p.gravidade || "menor")}">
                <b>${escapar(p.onde || "")}</b> — ${escapar(p.qual || "")}
                ${p.como_corrigir ? `<br><i>Correção: ${escapar(p.como_corrigir)}</i>` : ""}
              </div>`).join("")
            : "<p>A revisão não encontrou salto lógico, caso perdido nem divisão por zero.</p>"}
          ${critica.comentario ? `<p>${escapar(critica.comentario)}</p>` : ""}
        </div>
      </details>`;
  }

  async function resolverMatematica() {
    const texto = enunciadoAtual();
    if (!texto) return;
    const botao = $("#mat-resolver");
    const saida = $("#mat-saida");
    botao.disabled = true;
    saida.innerHTML = `
      <div class="cartao" style="margin-top:16px">
        <div class="esqueleto" style="height:15px;width:45%"></div>
        <div class="esqueleto" style="height:12px;margin-top:14px"></div>
        <div class="esqueleto" style="height:12px;margin-top:8px;width:82%"></div>
        <div class="esqueleto" style="height:12px;margin-top:8px;width:60%"></div>
      </div>`;
    try {
      const r = await window.API.matResolver({
        enunciado: texto,
        tentativa: $("#mat-tentativa").value,
        nivel_aluno: estado.nivelAluno,
      });
      desenharResolucao(r);
    } catch (erro) {
      mostrarErro(saida, erro.message);
      avisar(erro.message, "erro");
    } finally {
      botao.disabled = false;
    }
  }

  function desenharResolucao(r) {
    const d = r.diagnostico;
    const checagens = (r.analise.checagens || []).concat(r.confronto || []);
    const veredito = r.verificado
      ? '<div class="veredito ok">✓ Verificação independente confirmou o resultado</div>'
      : r.tem_alerta
        ? '<div class="veredito atencao">⚠ A verificação não fechou — leia as checagens</div>'
        : "";

    $("#mat-saida").innerHTML = `
      <div class="cartao" style="margin-top:16px">
        <div class="pilulas" style="margin-bottom:12px">
          <span class="pilula ${r.modo === "neural" ? "jade" : "ambar"}">
            ${r.modo === "neural" ? "resolução explicada" : "modo simbólico"}</span>
          <span class="pilula violeta">${escapar(d.topico_nome)}</span>
          <span class="pilula">nível ${d.dificuldade} · ${escapar(d.dificuldade_nome)}</span>
          <span class="pilula">${((r.duracao_ms || 0) / 1000).toFixed(1)}s</span>
        </div>
        ${trilhaDePasses(r.passes)}
        ${blocoEstrategias(r.estrategias)}
        <article class="markdown" id="mat-texto">${markdownComFormulas(r.texto)}</article>
        ${r.aviso ? `<div class="aviso">${escapar(r.aviso)}</div>` : ""}
      </div>

      <div class="cartao" style="margin-top:14px">
        <h2 class="titulo-secao">
          <svg viewBox="0 0 24 24"><path d="M12 3 4 6v6c0 4.4 3.4 8.5 8 9.5 4.6-1 8-5.1 8-9.5V6l-8-3z"/><path d="m9 12 2 2 4-4"/></svg>
          Verificação independente
        </h2>
        ${veredito}
        ${checagens.length
          ? listaDeChecagens(checagens)
          : `<p style="font-size:13.4px;color:var(--texto-2);margin:0 0 10px">
               Nenhuma checagem automática se aplicou a este enunciado.
               Confira manualmente:</p>
             <ul style="font-size:13.4px;color:var(--texto-2);margin:0;padding-left:20px">
               ${(d.verificacoes || []).map((v) => `<li>${escapar(v)}</li>`).join("")}
             </ul>`}
        ${(r.analise.observacoes || []).map((o) =>
          `<p style="font-size:12.8px;color:var(--texto-3);margin:8px 0 0">${escapar(o)}</p>`).join("")}
        ${blocoCritica(r.critica)}
      </div>`;

    renderizarFormulas($("#mat-saida"));
  }

  async function pedirPista() {
    const texto = enunciadoAtual();
    if (!texto) return;
    estado.nivelPista = Math.min(4, estado.nivelPista + 1);
    const botao = $("#mat-pista");
    botao.disabled = true;
    try {
      const p = await window.API.matPista({
        enunciado: texto,
        tentativa: $("#mat-tentativa").value,
        nivel: estado.nivelPista,
      });
      const restam = 4 - p.nivel;
      $("#mat-saida").innerHTML = `
        <div class="pista">
          <div class="pista-topo">
            <span class="pista-nivel">pista ${p.nivel} de 4</span>
            <span class="pilula ${p.modo === "neural" ? "jade" : "ambar"}">
              ${p.modo === "neural" ? "socrático" : "estrutural"}</span>
          </div>
          <article class="markdown">${markdownComFormulas(p.texto)}</article>
          <div class="mais-pista">
            ${restam > 0
              ? `<button class="botao-secundario" id="mat-mais-pista">
                   Ainda travei — próxima pista (${restam} restante${restam > 1 ? "s" : ""})
                 </button>`
              : `<button class="botao-primario" id="mat-resolver-agora">
                   Ver a resolução completa</button>`}
          </div>
        </div>`;
      renderizarFormulas($("#mat-saida"));
      const proxima = $("#mat-mais-pista");
      if (proxima) proxima.addEventListener("click", pedirPista);
      const resolverAgora = $("#mat-resolver-agora");
      if (resolverAgora) resolverAgora.addEventListener("click", resolverMatematica);
    } catch (erro) {
      avisar(erro.message, "erro");
    } finally {
      botao.disabled = false;
    }
  }

  async function conferirResposta() {
    const texto = enunciadoAtual();
    if (!texto) return;
    const minha = prompt("Qual é a sua resposta? (o sistema algébrico vai conferir)");
    if (!minha || !minha.trim()) return;
    try {
      const r = await window.API.matConferir({ enunciado: texto, resposta: minha.trim() });
      const checagens = (r.analise.checagens || []).concat(r.confronto || []);
      const rotulo = {
        confere: ['<div class="veredito ok">✓ Sua resposta confere com a álgebra</div>', "ok"],
        nao_confere: ['<div class="veredito atencao">⚠ A álgebra não confirma sua resposta</div>', "erro"],
        indeterminado: ['<div class="veredito atencao">Não consegui ler equação no enunciado para conferir automaticamente</div>', "ok"],
      }[r.veredito] || ["", "ok"];

      $("#mat-saida").innerHTML = `
        <div class="cartao" style="margin-top:16px">
          <h2 class="titulo-secao">Conferência da sua resposta</h2>
          <p style="font-size:13.6px;color:var(--texto-2);margin:0 0 12px">
            Você respondeu: <b>${escapar(minha.trim())}</b></p>
          ${rotulo[0]}
          ${listaDeChecagens(checagens)}
          ${(r.analise.observacoes || []).map((o) =>
            `<p style="font-size:12.8px;color:var(--texto-3);margin:8px 0 0">${escapar(o)}</p>`).join("")}
        </div>`;
      renderizarFormulas($("#mat-saida"));
    } catch (erro) { avisar(erro.message, "erro"); }
  }

  async function carregarTopicosMat() {
    if (estado.topicosMat.length) return;
    try {
      const dados = await window.API.matTopicos();
      estado.topicosMat = dados.topicos || [];
    } catch (erro) { avisar(erro.message, "erro"); return; }

    const caixa = $("#mat-topicos");
    caixa.innerHTML = estado.topicosMat
      .filter((t) => t.gera_questao)
      .map((t) => `<button class="ficha" data-topico="${escapar(t.chave)}">
                     <span class="marcador"></span>${escapar(t.nome)}</button>`)
      .join("");

    $$("#mat-topicos .ficha").forEach((ficha) => {
      ficha.addEventListener("click", () => {
        const ja = ficha.classList.contains("ativa");
        $$("#mat-topicos .ficha").forEach((f) => f.classList.remove("ativa"));
        if (!ja) ficha.classList.add("ativa");
        estado.topicoMat = ja ? "" : ficha.dataset.topico;
      });
    });
  }

  async function gerarQuestao() {
    const botao = $("#mat-criar");
    botao.disabled = true;
    try {
      const q = await window.API.matCriar({
        topico: estado.topicoMat,
        dificuldade: 3,
        semente: Math.floor(Math.random() * 1e6),
      });
      desenharQuestao(q);
    } catch (erro) {
      avisar(erro.message, "erro");
    } finally {
      botao.disabled = false;
    }
  }

  function desenharQuestao(q) {
    const letras = ["A", "B", "C", "D", "E"];
    $("#mat-questao").innerHTML = `
      <div class="questao-gerada">
        <div class="pilulas" style="margin-bottom:12px">
          <span class="pilula ${q.origem === "neural" ? "jade" : "violeta"}">
            ${q.origem === "neural" ? "criada pelo modelo" : "molde paramétrico"}</span>
          <span class="pilula">nível ${q.dificuldade}</span>
          ${(q.topicos || []).map((t) => `<span class="pilula">${escapar(t)}</span>`).join("")}
          <!-- O selo diz o que a conferência realmente apurou. "Conferido"
               para uma checagem que só olhou a estrutura seria um selo não
               ganho, e é justamente o gabarito que o estudante confia. -->
          <span class="selo-gabarito ${q.conferida ? "" : "nao"}"
                title="${escapar(q.observacao_da_conferencia || "")}">
            ${q.conferida
              ? (String(q.observacao_da_conferencia || "").includes("sem equação")
                  ? "✓ estrutura conferida"
                  : "✓ gabarito conferido pela álgebra")
              : "⚠ gabarito não conferido"}</span>
        </div>
        <div class="questao">
          <p class="questao-enunciado"><span>${markdownComFormulas(q.enunciado)}</span></p>
          <div class="alternativas">
            ${q.alternativas.map((a, i) => `
              <button class="alternativa" data-opcao="${i}">
                <span class="letra">${letras[i]}</span>
                <span>${markdownComFormulas(a)}</span>
              </button>`).join("")}
          </div>
          <div class="explicacao" hidden>
            ${q.ideia_central ? `<b>Ideia central:</b> ${markdownComFormulas(q.ideia_central)}` : ""}
            ${q.solucao ? `<div style="margin-top:8px">${markdownComFormulas(q.solucao)}</div>` : ""}
          </div>
        </div>
      </div>`;

    const caixa = $("#mat-questao .questao");
    $$(".alternativa", caixa).forEach((botao, indice) => {
      botao.addEventListener("click", () => {
        if (caixa.dataset.respondida) return;
        caixa.dataset.respondida = "1";
        $$(".alternativa", caixa).forEach((b, i) => {
          b.disabled = true;
          if (i === q.correta) b.classList.add("certa");
          else if (i === indice) b.classList.add("errada");
          const erro = (q.erros_dos_distratores || [])[i];
          if (i !== q.correta && erro && erro !== "-") {
            const nota = document.createElement("span");
            nota.className = "erro-distrator";
            nota.innerHTML = markdownComFormulas(erro);
            $("span:last-child", b).appendChild(nota);
          }
        });
        $(".explicacao", caixa).hidden = false;
        renderizarFormulas(caixa);
        avisar(indice === q.correta ? "Correto." : "Veja o erro que leva a cada alternativa.");
      });
    });

    renderizarFormulas($("#mat-questao"));
  }


  /* ====================================================================
     Modo tutor: escada de ajuda
     ==================================================================== */

  function ligarTutor() {
    $("#tut-comecar").addEventListener("click", comecarTutoria);
    $("#tut-padroes").addEventListener("click", mostrarPadroes);
    $("#tut-treinar").addEventListener("click", () => montarTreino(""));

    const area = $("#tut-area-imagem");
    const entrada = $("#tut-imagem");
    area.addEventListener("click", () => entrada.click());
    // `role="button"` promete teclado: Enter e Espaço abrem o seletor.
    area.addEventListener("keydown", (evento) => {
      if (evento.key === "Enter" || evento.key === " ") {
        evento.preventDefault();
        entrada.click();
      }
    });
    entrada.addEventListener("change", () => {
      if (entrada.files.length) enviarFoto(entrada.files[0]);
      entrada.value = "";
    });
    ["dragenter", "dragover"].forEach((e) =>
      area.addEventListener(e, (ev) => { ev.preventDefault(); area.classList.add("sobre"); }));
    ["dragleave", "drop"].forEach((e) =>
      area.addEventListener(e, (ev) => { ev.preventDefault(); area.classList.remove("sobre"); }));
    area.addEventListener("drop", (ev) => {
      const arquivos = ev.dataTransfer && ev.dataTransfer.files;
      if (arquivos && arquivos.length) enviarFoto(arquivos[0]);
    });
  }

  async function carregarEscada() {
    if (estado.escadaDegraus.length) return;
    try {
      const dados = await window.API.tutEscada();
      estado.escadaDegraus = dados.degraus || [];
    } catch (erro) { avisar(erro.message, "erro"); }
  }

  function desenharEscada(nivelAtual) {
    const caixa = $("#tut-escada");
    if (!estado.escadaDegraus.length) { caixa.hidden = true; return; }
    caixa.innerHTML = estado.escadaDegraus.map((d) => {
      const classes = [
        "escada-degrau",
        d.nivel < nivelAtual ? "passado" : "",
        d.nivel === nivelAtual ? "atual" : "",
        d.revela_resposta ? "revela" : "",
      ].filter(Boolean).join(" ");
      return `<div class="${classes}" title="${escapar(d.objetivo)}">
                <span class="barra"></span>
                <small>${escapar(d.nome)}</small>
              </div>`;
    }).join("");
    caixa.hidden = false;
  }

  async function comecarTutoria() {
    const enunciado = $("#tut-enunciado").value.trim();
    if (enunciado.length < 3) {
      avisar("Cole a questão primeiro.", "erro");
      return;
    }
    const botao = $("#tut-comecar");
    botao.disabled = true;
    $("#tut-saida").innerHTML = '<div class="cartao" style="margin-top:16px">'
      + '<div class="esqueleto" style="height:14px;width:40%"></div>'
      + '<div class="esqueleto" style="height:12px;margin-top:12px"></div></div>';
    try {
      await carregarEscada();
      const dados = await window.API.tutAbrirSessao({ enunciado });
      estado.sessaoTutor = dados.sessao;
      desenharEscada(dados.ajuda.nivel);
      desenharAjuda(dados.ajuda);
    } catch (erro) {
      mostrarErro($("#tut-saida"), erro.message);
      avisar(erro.message, "erro");
    } finally {
      botao.disabled = false;
    }
  }

  function desenharAjuda(ajuda) {
    const revela = ajuda.revela_resposta;
    $("#tut-saida").innerHTML = `
      <div class="bloco-ajuda ${revela ? "revela" : ""}">
        <div class="ajuda-topo">
          <span class="ajuda-nivel">
            degrau ${ajuda.nivel} · ${escapar(ajuda.nome_do_degrau)}
          </span>
          <div class="pilulas">
            <span class="pilula violeta">${escapar(ajuda.materia)}</span>
            <span class="pilula ${ajuda.modo === "neural" ? "jade" : "ambar"}">
              ${ajuda.modo === "neural" ? "tutor" : "verificadores"}</span>
          </div>
        </div>
        <article class="markdown">${markdownComFormulas(ajuda.texto)}</article>
        <div class="acoes-tutor">
          ${ajuda.pode_subir
            ? '<button class="botao-secundario" id="tut-mais">Ainda travei — mais uma pista</button>'
            : ""}
          <button class="botao-secundario" id="tut-resolver">Ver a resolução completa</button>
        </div>
      </div>

      <div class="cartao caixa-tentativa">
        <label class="campo">
          <span>Minha tentativa</span>
          <textarea id="tut-tentativa" rows="3" maxlength="6000"
            placeholder="Escreva o que você fez. O tutor aponta só o primeiro erro."></textarea>
        </label>
        <div class="barra-acoes" style="margin-bottom:0">
          <button class="botao-primario" id="tut-enviar-tentativa">Enviar tentativa</button>
        </div>
      </div>`;

    renderizarFormulas($("#tut-saida"));
    const mais = $("#tut-mais");
    if (mais) mais.addEventListener("click", () => pedirMaisAjuda(""));
    $("#tut-resolver").addEventListener("click", () =>
      pedirMaisAjuda("mostre a resolução completa"));
    $("#tut-enviar-tentativa").addEventListener("click", enviarTentativa);
  }

  async function pedirMaisAjuda(pedido) {
    if (!estado.sessaoTutor) return;
    try {
      const dados = await window.API.tutAjuda(estado.sessaoTutor.id, pedido);
      desenharEscada(dados.nivel);
      desenharAjuda(dados.ajuda);
    } catch (erro) { avisar(erro.message, "erro"); }
  }

  async function enviarTentativa() {
    if (!estado.sessaoTutor) return;
    const campo = $("#tut-tentativa");
    const texto = campo.value.trim();
    if (!texto) { avisar("Escreva sua tentativa primeiro.", "erro"); return; }

    const botao = $("#tut-enviar-tentativa");
    botao.disabled = true;
    try {
      const dados = await window.API.tutTentativa(estado.sessaoTutor.id, texto);
      desenharEscada(dados.nivel);
      desenharDiagnosticoDaTentativa(dados, texto);
    } catch (erro) {
      avisar(erro.message, "erro");
    } finally {
      botao.disabled = false;
    }
  }

  function desenharDiagnosticoDaTentativa(dados, tentativa) {
    const d = dados.diagnostico;
    const correto = d.veredito === "correto";
    const rotuloVeredito = {
      correto: "acertou", parcial: "parcialmente certo",
      incorreto: "há um erro", indeterminado: "não consegui decidir",
    }[d.veredito] || d.veredito;

    const bloco = document.createElement("div");
    bloco.className = `bloco-diagnostico ${correto ? "correto" : ""}`;
    bloco.innerHTML = `
      <div class="tira-diagnostico">
        <span class="pilula ${correto ? "jade" : "erro"}">${escapar(rotuloVeredito)}</span>
        ${d.tipo_erro ? `<span class="pilula">${escapar(d.tipo_erro)}</span>` : ""}
        ${d.quase_la ? '<span class="pilula jade">quase lá</span>' : ""}
        <span class="pilula ${d.modo === "neural" ? "" : "ambar"}">
          ${d.modo === "neural" ? "análise do tutor" : "verificadores"}</span>
      </div>
      <article class="markdown">${markdownComFormulas(d.resposta)}</article>
      ${d.pergunta_que_faltou ? `
        <div class="generalizacao">
          <b>a pergunta que faltou</b>${escapar(d.pergunta_que_faltou)}
        </div>` : ""}
      ${dados.generalizacao ? `
        <div class="generalizacao">
          <b>regra para levar para outras questões</b>
          ${escapar(dados.generalizacao)}
        </div>` : ""}`;

    $("#tut-saida").appendChild(bloco);
    renderizarFormulas(bloco);
    bloco.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }

  async function enviarFoto(arquivo) {
    $("#tut-saida").innerHTML = '<div class="cartao" style="margin-top:16px">'
      + '<div class="esqueleto" style="height:14px;width:55%"></div>'
      + '<div class="esqueleto" style="height:12px;margin-top:12px"></div></div>';
    try {
      const dados = await window.API.tutImagem(arquivo);
      const leitura = dados.leitura;
      $("#tut-saida").innerHTML = `
        <div class="bloco-ajuda">
          <div class="ajuda-topo">
            <span class="ajuda-nivel">leitura da imagem</span>
            <span class="pilula ${leitura.confiavel ? "jade" : "ambar"}">
              ${leitura.confiavel ? "transcrição completa" : "há trechos ilegíveis"}</span>
          </div>
          <article class="markdown">${markdownComFormulas(dados.confirmacao)}</article>
          <div class="acoes-tutor">
            <button class="botao-primario" id="tut-confirmar-leitura">
              Está certo — estudar esta questão</button>
          </div>
        </div>`;
      renderizarFormulas($("#tut-saida"));
      $("#tut-confirmar-leitura").addEventListener("click", () => {
        const primeira = (leitura.questoes || [])[0];
        if (!primeira) return;
        const alternativas = (primeira.alternativas || [])
          .map((a) => `${a.letra}) ${a.texto}`).join("\n");
        $("#tut-enunciado").value =
          primeira.enunciado + (alternativas ? `\n\n${alternativas}` : "");
        comecarTutoria();
      });
    } catch (erro) {
      mostrarErro($("#tut-saida"), erro.message);
      avisar(erro.message, "erro");
    }
  }

  async function mostrarPadroes() {
    try {
      const dados = await window.API.tutPadroes();
      const recorrentes = dados.recorrentes || [];
      const dominio = dados.dominio || [];
      $("#tut-saida").innerHTML = `
        <div class="cartao" style="margin-top:16px">
          <h2 class="titulo-secao">Seus padrões de erro</h2>
          ${recorrentes.length ? recorrentes.map((p) => `
            <div class="padrao-erro">
              <span class="contador">${p.ocorrencias}</span>
              <div>
                <b>${escapar(p.tipo)}</b>
                <small>${escapar(p.descricao)}</small>
                <span class="estrategia">${escapar(p.estrategia)}</span>
                <button class="botao-texto treinar-padrao" data-erro="${escapar(p.tipo)}">
                  Treinar este erro
                </button>
              </div>
            </div>`).join("")
            : '<p style="color:var(--texto-3);font-size:14px;margin:0">'
              + "Ainda não há erros suficientes para um padrão. Estude algumas "
              + "questões e volte aqui.</p>"}

          ${dominio.length ? `
            <h2 class="titulo-secao" style="margin-top:20px">Domínio por assunto</h2>
            ${dominio.map((d) => (d.taxa === null || d.taxa === undefined ? `
              <div class="medidor-linha">
                <span class="rotulo">${escapar(d.topico)}</span>
                <span class="medidor-barra"><i style="width:0"></i></span>
                <span class="valor sem-dado">sem tentativa julgada</span>
              </div>` : `
              <div class="medidor-linha">
                <span class="rotulo">${escapar(d.topico)}</span>
                <span class="medidor-barra">
                  <i class="${faixa(d.taxa / 100)}" style="width:${Number(d.taxa)}%"></i>
                </span>
                <span class="valor">${Number(d.taxa)}%</span>
              </div>`)).join("")}` : ""}
        </div>`;
      $("#tut-saida").querySelectorAll(".treinar-padrao").forEach((botao) => {
        botao.addEventListener("click", () => montarTreino("", botao.dataset.erro));
      });
    } catch (erro) { avisar(erro.message, "erro"); }
  }

  /* --- treino dirigido ------------------------------------------------ */

  // O gabarito fica só aqui, no cliente, e só depois da resposta. Pedir com
  // `com_gabarito` antes de responder seria entregar o peixe.
  const treinoAtual = { itens: [], respondidas: new Set() };

  async function montarTreino(materia, tipoErro) {
    const caixa = $("#tut-saida");
    caixa.innerHTML = '<div class="cartao" style="margin-top:16px">'
      + '<p style="margin:0;color:var(--texto-3)">Montando o treino…</p></div>';
    try {
      const dados = await window.API.tutTreino({
        materia: materia || "",
        tipo_erro: tipoErro || "",
        quantidade: 5,
        com_gabarito: true,
      });
      treinoAtual.itens = dados.itens || [];
      treinoAtual.respondidas = new Set();
      desenharTreino(dados);
    } catch (erro) {
      avisar(erro.message, "erro");
      mostrarErro(caixa, erro.message,
        "Tente de novo em instantes. Se persistir, estude algumas questões "
        + "no modo tutor para o treino ter material de onde partir.");
    }
  }

  function desenharTreino(dados) {
    const itens = dados.itens || [];
    if (!itens.length) {
      $("#tut-saida").innerHTML = `
        <div class="cartao" style="margin-top:16px">
          <h2 class="titulo-secao">Treino dirigido</h2>
          <p style="margin:0;color:var(--texto-3);font-size:14px">
            Ainda não há material de treino para este perfil. Estude algumas
            questões no modo tutor e volte aqui.</p>
        </div>`;
      return;
    }
    $("#tut-saida").innerHTML = `
      <div class="cartao" style="margin-top:16px">
        <h2 class="titulo-secao">Treino dirigido</h2>
        <p class="motivo-treino">${escapar(dados.motivo || "")}</p>
        ${dados.estrategia ? `<div class="teste" style="margin-bottom:16px">
          <b>estratégia preventiva</b><br>${escapar(dados.estrategia)}</div>` : ""}
        <div class="pilulas" style="margin-bottom:16px">
          ${dados.tipo_erro ? `<span class="pilula ambar">${escapar(dados.tipo_erro)}</span>` : ""}
          <span class="pilula">${escapar(dados.origem || "")}</span>
          <span class="pilula violeta">${itens.length} exercícios</span>
        </div>
        ${itens.map((item, indice) => `
          <div class="item-treino" id="treino-item-${indice}">
            <div class="numero-treino">${indice + 1}</div>
            <div class="corpo-treino">
              <p class="enunciado-treino">${escapar(item.enunciado)}</p>
              ${(item.alternativas || []).length
                ? `<div class="alternativas-treino">
                     ${item.alternativas.map((alt, letra) => `
                       <button class="alternativa-treino" data-item="${indice}" data-alt="${letra}">
                         <span class="letra">${String.fromCharCode(65 + letra)}</span>
                         ${escapar(alt)}
                       </button>`).join("")}
                   </div>`
                : `<div class="resposta-aberta">
                     <input type="text" class="campo-treino" data-item="${indice}"
                       placeholder="Escreva sua resposta e pressione Enter">
                   </div>`}
              <div class="veredito-treino" hidden></div>
            </div>
          </div>`).join("")}
        <div class="barra-acoes" style="margin-top:18px">
          <button class="botao-secundario" id="treino-outro">Outro treino</button>
        </div>
      </div>`;

    $("#tut-saida").querySelectorAll(".alternativa-treino").forEach((botao) => {
      botao.addEventListener("click", () => {
        responderTreino(Number(botao.dataset.item), Number(botao.dataset.alt), botao);
      });
    });
    $("#tut-saida").querySelectorAll(".campo-treino").forEach((campo) => {
      campo.addEventListener("keydown", (evento) => {
        if (evento.key !== "Enter") return;
        responderAberta(Number(campo.dataset.item), campo.value.trim(), campo);
      });
    });
    const outro = $("#treino-outro");
    if (outro) outro.addEventListener("click", () => montarTreino(""));
    renderizarFormulas($("#tut-saida"));
  }

  function mostrarVeredito(indice, acertou, item) {
    const caixa = $(`#treino-item-${indice} .veredito-treino`);
    if (!caixa) return;
    caixa.hidden = false;
    caixa.className = `veredito-treino ${acertou ? "acerto" : "erro"}`;
    caixa.innerHTML = `
      <b>${acertou ? "✓ Certo." : "✗ Não é essa."}</b>
      ${!acertou ? ` A resposta é <b>${escapar(item.resposta)}</b>.` : ""}
      ${item.explicacao ? `<br><span class="porque">${escapar(item.explicacao)}</span>` : ""}`;
    renderizarFormulas(caixa);
  }

  function responderTreino(indice, escolha, botao) {
    if (treinoAtual.respondidas.has(indice)) return;
    const item = treinoAtual.itens[indice];
    if (!item) return;
    treinoAtual.respondidas.add(indice);
    const acertou = escolha === item.correta;
    const grupo = botao.parentElement;
    grupo.querySelectorAll(".alternativa-treino").forEach((outro, letra) => {
      outro.disabled = true;
      if (letra === item.correta) outro.classList.add("certa");
      else if (letra === escolha) outro.classList.add("errada");
    });
    mostrarVeredito(indice, acertou, item);
  }

  function responderAberta(indice, texto, campo) {
    if (!texto || treinoAtual.respondidas.has(indice)) return;
    const item = treinoAtual.itens[indice];
    if (!item) return;
    treinoAtual.respondidas.add(indice);
    campo.disabled = true;
    const normalizar = (v) => String(v).toLowerCase()
      .normalize("NFD").replace(/[\u0300-\u036f]/g, "").replace(/\s+/g, " ").trim();
    const acertou = normalizar(texto) === normalizar(item.resposta || "");
    campo.classList.add(acertou ? "certa" : "errada");
    mostrarVeredito(indice, acertou, item);
  }

  /* ====================================================================
     Gramática
     ==================================================================== */

  function ligarGramatica() {
    $("#gram-analisar").addEventListener("click", analisarGramatica);
    $("#gram-consultar").addEventListener("click", consultarRegencia);
    $("#gram-verbos").addEventListener("click", listarVerbos);
    $("#gram-verbo").addEventListener("keydown", (e) => {
      if (e.key === "Enter") consultarRegencia();
    });
  }

  /* ====================================================================
     Saneamento de dados vindos da API

     Tudo que chega do backend passou antes por bases externas (Wikipedia,
     Crossref, Open Library, arXiv). Título, ano, URL e número de citações são
     texto de terceiro, não constante nossa: interpolar isso direto no HTML é
     execução de código na sessão de quem estuda.
     ==================================================================== */

  /** Número seguro para interpolar: devolve string vazia se não for número. */
  function numero(valor, padrao = "") {
    const n = Number(valor);
    return Number.isFinite(n) ? String(n) : padrao;
  }

  /** Identificador seguro para `id=` e `href="#..."`: só dígitos e letras. */
  function identificador(valor) {
    return String(valor == null ? "" : valor).replace(/[^A-Za-z0-9_-]/g, "");
  }

  /* `escapar` protege o CONTEÚDO de um atributo, não o seu significado:
     href="javascript:..." passa intacto pelo escape de &<>"'. Só http(s) e
     mailto viram link; qualquer outro esquema vira link nenhum. */
  const ESQUEMAS_PERMITIDOS = /^(?:https?:|mailto:)/i;

  function endereco(valor) {
    const bruto = String(valor == null ? "" : valor).trim();
    if (!bruto) return "";
    // Relativo ao próprio site é seguro; esquema estranho, não.
    if (bruto.startsWith("/") || bruto.startsWith("#")) return escapar(bruto);
    return ESQUEMAS_PERMITIDOS.test(bruto) ? escapar(bruto) : "";
  }

  /** Cartão de erro que permanece na tela.

     Limpar o painel e mandar a mensagem para um aviso que some em seis
     segundos deixava o botão parecendo quebrado: passados alguns segundos, a
     tela voltava a ser idêntica à de antes do clique, e quem não estava
     olhando o canto naquele instante nunca soube o que houve.
   */
  function mostrarErro(area, mensagem, sugestao) {
    if (!area) return;
    area.innerHTML = `
      <div class="cartao cartao-erro" role="alert">
        <div class="erro-topo">
          <svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="9"/>
            <path d="M12 8v5M12 16.5v.01"/></svg>
          <b>Não deu para concluir</b>
        </div>
        <p>${escapar(mensagem || "Erro desconhecido.")}</p>
        ${sugestao ? `<p class="erro-sugestao">${escapar(sugestao)}</p>` : ""}
      </div>`;
  }

  const ROTULO_VEREDITO = {
    erro: "erro", correto: "correto", depende: "depende do contexto",
    atencao: "atenção",
  };

  async function analisarGramatica() {
    const frase = $("#gram-frase").value.trim();
    if (frase.length < 2) { avisar("Escreva a frase primeiro.", "erro"); return; }
    try {
      const dados = await window.API.gramAnalisar(frase);
      const achados = dados.achados || [];
      $("#gram-saida").innerHTML = `
        <div class="cartao" style="margin-top:16px">
          <div class="pilulas" style="margin-bottom:14px">
            <span class="pilula ${dados.tem_erro ? "ambar" : "jade"}">
              ${dados.tem_erro ? "há erro na frase" : "nenhum erro detectado"}</span>
            ${(dados.topicos_envolvidos || []).map((t) =>
              `<span class="pilula violeta">${escapar(t)}</span>`).join("")}
          </div>
          ${achados.length ? achados.map((a) => `
            <div class="achado-gramatical ${escapar(a.veredito)}">
              <div class="achado-topo">
                <span class="marca-topico">${escapar(a.topico)}</span>
                <b>${escapar(a.regra)}</b>
                <span class="pilula">${escapar(ROTULO_VEREDITO[a.veredito] || a.veredito)}</span>
              </div>
              <p>${escapar(a.explicacao)}</p>
              ${a.teste ? `<div class="teste"><b>teste</b><br>${escapar(a.teste)}</div>` : ""}
              ${a.pergunta_guia ? `<div class="teste" style="margin-top:6px">
                <b>pergunte-se</b><br>${escapar(a.pergunta_guia)}</div>` : ""}
            </div>`).join("")
            : '<p style="color:var(--texto-3);font-size:14px;margin:0">'
              + "Nenhuma das armadilhas clássicas apareceu nesta frase.</p>"}
        </div>`;
    } catch (erro) { avisar(erro.message, "erro"); }
  }

  async function consultarRegencia() {
    const verbo = $("#gram-verbo").value.trim();
    if (!verbo) return;
    try {
      const dados = await window.API.gramRegencia(verbo);
      $("#gram-regencia").innerHTML = `
        <div style="margin-top:14px">
          <div class="pilulas" style="margin-bottom:10px">
            <span class="pilula violeta">${escapar(dados.verbo)}</span>
            <span class="pilula ${dados.muda_com_o_sentido ? "ambar" : "jade"}">
              ${dados.muda_com_o_sentido
                ? "muda de regência conforme o sentido"
                : "regência única"}</span>
          </div>
          ${dados.sentidos.map((s) => `
            <div class="sentido-verbo">
              <div class="cabeca">
                <span class="sentido">${escapar(s.sentido)}</span>
                <span class="pilula">${escapar(s.transitividade)}</span>
                ${s.preposicoes.length
                  ? `<span class="pilula ${s.exige_a ? "jade" : ""}">
                       ${escapar(s.preposicoes.join(" / "))}</span>`
                  : ""}
              </div>
              <div class="exemplo">${escapar(s.exemplo)}</div>
              ${s.observacao ? `<div class="observacao">${escapar(s.observacao)}</div>` : ""}
            </div>`).join("")}
        </div>`;
    } catch (erro) {
      $("#gram-regencia").innerHTML =
        `<p style="margin-top:12px;color:var(--ambar);font-size:13.5px">${escapar(erro.message)}</p>`;
    }
  }

  async function listarVerbos() {
    try {
      const dados = await window.API.gramVerbos();
      $("#gram-saida").innerHTML = `
        <div class="cartao" style="margin-top:16px">
          <h2 class="titulo-secao">
            Verbos catalogados <span class="contagem">${dados.verbos.length}</span>
          </h2>
          <div class="fichas">
            ${dados.verbos.map((v) =>
              `<button class="ficha" data-verbo="${escapar(v)}">${escapar(v)}</button>`).join("")}
          </div>
          <h2 class="titulo-secao" style="margin-top:20px">
            Regência nominal <span class="contagem">${dados.nomes.length}</span>
          </h2>
          <div class="fichas">
            ${dados.nomes.map((n) => `<span class="ficha">${escapar(n)}</span>`).join("")}
          </div>
        </div>`;
      $$("#gram-saida .ficha[data-verbo]").forEach((ficha) => {
        ficha.addEventListener("click", () => {
          $("#gram-verbo").value = ficha.dataset.verbo;
          consultarRegencia();
          $("#gram-regencia").scrollIntoView({ behavior: "smooth", block: "center" });
        });
      });
    } catch (erro) { avisar(erro.message, "erro"); }
  }


  /* ====================================================================
     Aferição dos motores
     ==================================================================== */

  // As áreas viajam como identificadores sem acento; a tela mostra o nome.
  const ROTULO_AREA = {
    algebra: "álgebra simbólica",
    colocacao: "colocação pronominal",
    concordancia: "concordância verbal",
    crase: "crase",
    ingles: "inglês",
    lexico: "léxico (gênero e classe)",
    materia: "roteamento de matéria",
    regencia: "regência (dicionário)",
    regencia_uso: "regência (uso na frase)",
    topico: "assunto de matemática",
  };

  const rotularArea = (area) => ROTULO_AREA[area] || area;

  async function rodarAfericao() {
    const botao = $("#btn-aferir");
    const saida = $("#saida-afericao");
    botao.disabled = true;
    saida.innerHTML = '<div class="esqueleto" style="height:12px;margin-top:16px"></div>';
    try {
      const dados = await window.API.afericao();
      const areas = Object.entries(dados.por_area || {})
        .sort(([a], [b]) => a.localeCompare(b));

      saida.innerHTML = `
        <div class="resumo-afericao ${dados.taxa === 100 ? "pleno" : "parcial"}">
          <b>${numero(dados.acertos, "0")}/${numero(dados.total, "0")}</b>
          <span>${dados.taxa}% dos casos de referência</span>
        </div>
        <div class="medidor" style="margin-top:14px">
          ${areas.map(([area, d]) => `
            <div class="medidor-linha">
              <span class="rotulo">${escapar(rotularArea(area))}</span>
              <span class="medidor-barra">
                <i class="${faixa(d.taxa / 100)}" style="width:${d.taxa}%"></i>
              </span>
              <span class="valor">${numero(d.acertos, "0")}/${numero(d.total, "0")}</span>
            </div>`).join("")}
        </div>
        ${(dados.falhas || []).length ? `
          <h3 style="font-size:13px;margin:18px 0 8px;color:var(--rosa)">
            ${dados.falhas.length} caso(s) errado(s)</h3>
          ${dados.falhas.map((f) => `
            <div class="achado-gramatical erro">
              <div class="achado-topo">
                <span class="marca-topico">${escapar(rotularArea(f.area))}</span>
                <b>${escapar(f.entrada)}</b>
              </div>
              <p>esperado <b>${escapar(f.esperado)}</b>, obtido
                 <b>${escapar(f.obtido)}</b>${f.porque ? ` — ${escapar(f.porque)}` : ""}</p>
            </div>`).join("")}`
          : '<p style="margin-top:14px;font-size:13.4px;color:var(--jade-300)">'
            + "Todos os casos de referência passaram.</p>"}`;
    } catch (erro) {
      mostrarErro(saida, erro.message);
      avisar(erro.message, "erro");
    } finally {
      botao.disabled = false;
    }
  }

  /* ====================================================================
     Paleta de comandos (Ctrl/Cmd + K)
     ==================================================================== */

  /* Com nove seções, procurar a aba certa no olho custa mais que digitar o
     nome dela. A paleta também dá acesso a ações que estão dentro das abas. */
  const COMANDOS = [
    { icone: "🔍", titulo: "Pesquisar nas bases", aba: "pesquisar",
      termos: "buscar procurar fontes wikipedia artigo pergunta",
      foco: "#entrada-pergunta" },
    { icone: "🎓", titulo: "Modo tutor", aba: "tutor",
      termos: "escada ajuda pista socratico dica questao foto imagem",
      foco: "#tut-enunciado" },
    { icone: "∑", titulo: "Resolver problema de matemática", aba: "matematica",
      termos: "equacao calculo algebra ita ime verificar",
      foco: "#mat-enunciado" },
    { icone: "∑", titulo: "Gerar questão no padrão ITA/IME", aba: "matematica",
      termos: "criar questao objetiva distrator gabarito", acao: "gerarQuestao" },
    { icone: "T", titulo: "Analisar frase (crase, regência…)", aba: "gramatica",
      termos: "gramatica portugues crase regencia colocacao concordancia frase",
      foco: "#gram-frase" },
    { icone: "T", titulo: "Consultar regência de um verbo", aba: "gramatica",
      termos: "verbo regencia assistir visar implicar sentido", foco: "#gram-verbo" },
    { icone: "↻", titulo: "Revisar cartões de hoje", aba: "revisao",
      termos: "flashcard repeticao espacada sm2 baralho memorizar" },
    { icone: "📖", titulo: "Minha biblioteca de livros", aba: "biblioteca",
      termos: "livro pdf epub indexar catalogo acervo" },
    { icone: "📅", titulo: "Montar plano de estudo", aba: "plano",
      termos: "cronograma semanas sessoes planejar", foco: "#plano-tema" },
    { icone: "🕐", titulo: "Histórico de pesquisas", aba: "historico",
      termos: "anterior salvo antigas" },
    { icone: "🗄", titulo: "Bases de dados consultadas", aba: "fontes",
      termos: "fontes wikipedia arxiv pubmed openalex catalogo" },
    { icone: "✓", titulo: "Aferir os motores", aba: "fontes",
      termos: "afericao teste acerto qualidade verificar correto gabarito",
      acao: "aferir" },
    { icone: "◐", titulo: "Alternar tema claro/escuro", acao: "tema",
      termos: "cor escuro claro noite dia aparencia" },
  ];

  let paletaSelecionada = 0;
  let paletaFiltrada = COMANDOS;

  function ligarPaleta() {
    const paleta = $("#paleta");
    const entrada = $("#paleta-entrada");

    $(".paleta-fundo", paleta).addEventListener("click", fecharPaleta);
    prenderFocoNaPaleta();
    entrada.addEventListener("input", () => filtrarPaleta(entrada.value));
    entrada.addEventListener("keydown", (evento) => {
      if (evento.key === "Escape") { fecharPaleta(); return; }
      if (evento.key === "ArrowDown" || evento.key === "ArrowUp") {
        evento.preventDefault();
        const passo = evento.key === "ArrowDown" ? 1 : -1;
        const total = paletaFiltrada.length || 1;
        paletaSelecionada = (paletaSelecionada + passo + total) % total;
        desenharPaleta();
      } else if (evento.key === "Enter") {
        evento.preventDefault();
        executarComando(paletaFiltrada[paletaSelecionada]);
      }
    });
  }

  // Quem abriu a paleta. Ao fechar, o foco volta para lá — largar o foco no
  // BODY deixa quem navega por teclado sem ponto de retorno.
  let focoAntesDaPaleta = null;

  function abrirPaleta() {
    const paleta = $("#paleta");
    focoAntesDaPaleta = document.activeElement;
    paleta.hidden = false;
    $("#paleta-entrada").value = "";
    filtrarPaleta("");
    $("#paleta-entrada").focus();
  }

  function fecharPaleta() {
    $("#paleta").hidden = true;
    if (focoAntesDaPaleta && focoAntesDaPaleta.focus) {
      focoAntesDaPaleta.focus();
    }
    focoAntesDaPaleta = null;
  }

  /* `aria-modal="true"` promete que o resto da página está fora de alcance.
     Sem prender o foco, dois Tabs levavam para o BODY atrás do diálogo, e lá
     nem Esc funcionava — o listener está no campo. Aqui o foco circula dentro
     da paleta e Esc vale em qualquer ponto dela. */
  function prenderFocoNaPaleta() {
    const paleta = $("#paleta");
    paleta.addEventListener("keydown", (evento) => {
      if (evento.key === "Escape") {
        evento.preventDefault();
        fecharPaleta();
        return;
      }
      if (evento.key !== "Tab") return;
      const focaveis = paleta.querySelectorAll(
        'input, button, [href], [tabindex]:not([tabindex="-1"])'
      );
      if (!focaveis.length) return;
      const primeiro = focaveis[0];
      const ultimo = focaveis[focaveis.length - 1];
      if (evento.shiftKey && document.activeElement === primeiro) {
        evento.preventDefault();
        ultimo.focus();
      } else if (!evento.shiftKey && document.activeElement === ultimo) {
        evento.preventDefault();
        primeiro.focus();
      }
    });
  }

  /** Pontua um comando contra o que foi digitado.
      Casar o INÍCIO de uma palavra vale muito mais que casar no meio: digitar
      "cra" deve trazer "crase", não "socrático". */
  function pontuarComando(comando, alvo) {
    const titulo = comando.titulo.toLowerCase();
    const termos = `${comando.termos} ${comando.aba || ""}`.toLowerCase();
    const comecaPalavra = (texto) =>
      texto.split(/[\s/,()]+/).some((palavra) => palavra.startsWith(alvo));

    let pontos = 0;
    if (titulo.startsWith(alvo)) pontos += 200;
    if (comecaPalavra(titulo)) pontos += 100;
    if (comecaPalavra(termos)) pontos += 50;
    if (titulo.includes(alvo)) pontos += 10;
    if (termos.includes(alvo)) pontos += 5;
    return pontos;
  }

  function filtrarPaleta(termo) {
    const alvo = termo.trim().toLowerCase();
    if (!alvo) {
      paletaFiltrada = COMANDOS;
    } else {
      paletaFiltrada = COMANDOS
        .map((comando) => ({ comando, pontos: pontuarComando(comando, alvo) }))
        .filter((item) => item.pontos > 0)
        .sort((a, b) => b.pontos - a.pontos)
        .map((item) => item.comando);
    }
    paletaSelecionada = 0;
    desenharPaleta();
  }

  function desenharPaleta() {
    const lista = $("#paleta-lista");
    if (!paletaFiltrada.length) {
      lista.innerHTML = '<li class="paleta-vazia">Nada encontrado por aqui.</li>';
      $("#paleta-entrada").setAttribute("aria-activedescendant", "");
      return;
    }
    lista.innerHTML = paletaFiltrada.map((c, i) => `
      <li class="paleta-item" role="option" data-indice="${i}"
          id="paleta-opcao-${i}"
          aria-selected="${i === paletaSelecionada}">
        <span class="icone">${c.icone}</span>
        <span>${escapar(c.titulo)}</span>
        ${c.aba ? `<small>${escapar(c.aba)}</small>` : ""}
      </li>`).join("");

    $$(".paleta-item", lista).forEach((item) => {
      item.addEventListener("click", () =>
        executarComando(paletaFiltrada[Number(item.dataset.indice)]));
    });
    const ativo = $('.paleta-item[aria-selected="true"]', lista);
    if (ativo) ativo.scrollIntoView({ block: "nearest" });
    // Sem `aria-activedescendant`, o leitor de tela não anuncia qual comando
    // está destacado: as setas mudam a seleção em silêncio.
    $("#paleta-entrada").setAttribute(
      "aria-activedescendant", ativo ? ativo.id : ""
    );
  }

  function executarComando(comando) {
    if (!comando) return;
    fecharPaleta();
    if (comando.aba) trocarAba(comando.aba);
    if (comando.acao === "tema") { alternarTema(); return; }
    if (comando.acao === "aferir") {
      setTimeout(() => { const b = $("#btn-aferir"); if (b) b.click(); }, 150);
      return;
    }
    if (comando.acao === "gerarQuestao") {
      setTimeout(() => { const b = $("#mat-criar"); if (b) b.click(); }, 120);
      return;
    }
    if (comando.foco) {
      setTimeout(() => { const alvo = $(comando.foco); if (alvo) alvo.focus(); }, 140);
    }
  }

  document.addEventListener("DOMContentLoaded", iniciar);
})();
