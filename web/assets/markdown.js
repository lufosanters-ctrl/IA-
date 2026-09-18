/* ==========================================================================
   Renderizador de markdown minimalista e seguro.
   Escapa HTML antes de qualquer coisa e converte [1] em pílulas de citação.
   ========================================================================== */
(function (global) {
  "use strict";

  function escapar(texto) {
    return String(texto)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  /* Fórmulas em $...$ e $$...$$ precisam atravessar o formatador intactas:
     sem isso, `r_1` e `r_2` na mesma linha viram itálico e a fórmula quebra. */
  const RE_MATEMATICA = /(\$\$[^$]+\$\$|\$[^$\n]+\$)/g;

  function protegerMatematica(texto, cofre) {
    return texto.replace(RE_MATEMATICA, (formula) => {
      const marca = `\u0000M${cofre.length}\u0000`;
      cofre.push(formula);
      return marca;
    });
  }

  function restaurarMatematica(texto, cofre) {
    return texto.replace(/\u0000M(\d+)\u0000/g, (_, indice) => cofre[Number(indice)]);
  }

  /* Formatação dentro de uma linha: negrito, itálico, código, links, citações */
  function embutido(textoOriginal, comCitacoes) {
    const cofre = [];
    const texto = protegerMatematica(textoOriginal, cofre);
    let saida = texto
      .replace(/`([^`]+)`/g, (_, c) => `<code>${c}</code>`)
      .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>")
      .replace(/(^|[^*])\*([^*\n]+)\*/g, "$1<em>$2</em>")
      /* itálico com sublinhado, sem quebrar nomes_com_underline */
      .replace(/(^|[\s(])_([^_\n]+)_(?=$|[\s.,;:!?)])/g, "$1<em>$2</em>")
      .replace(/\[([^\]]+)\]\((https?:[^)\s]+)\)/g,
        '<a href="$2" target="_blank" rel="noopener noreferrer">$1</a>');

    if (comCitacoes !== false) {
      /* [1] ou [1, 2] ou [1][3] viram pílulas clicáveis */
      saida = saida.replace(/\[(\d+(?:\s*,\s*\d+)*)\]/g, (todo, grupo) =>
        grupo.split(",").map((n) => {
          const numero = n.trim();
          return `<a class="citacao-marca" href="#citacao-${numero}" data-citacao="${numero}">${numero}</a>`;
        }).join("")
      );
    }
    return restaurarMatematica(saida, cofre);
  }

  function renderizar(markdown, opcoes) {
    const config = opcoes || {};
    const linhas = String(markdown || "").split("\n");
    const blocos = [];
    let lista = null;      // { tipo: 'ul'|'ol', itens: [] }
    let citacao = [];
    let codigo = null;     // { linguagem, linhas: [] }

    function fecharLista() {
      if (!lista) return;
      const itens = lista.itens.map((i) => `<li>${embutido(i, config.citacoes)}</li>`).join("");
      blocos.push(`<${lista.tipo}>${itens}</${lista.tipo}>`);
      lista = null;
    }
    function fecharCitacao() {
      if (!citacao.length) return;
      blocos.push(`<blockquote>${embutido(citacao.join(" "), config.citacoes)}</blockquote>`);
      citacao = [];
    }
    function fecharTudo() { fecharLista(); fecharCitacao(); }

    for (const bruta of linhas) {
      const linha = bruta.replace(/\s+$/, "");

      /* blocos de código */
      const cerca = linha.match(/^```(\w*)/);
      if (cerca) {
        if (codigo) {
          blocos.push(`<pre><code>${escapar(codigo.linhas.join("\n"))}</code></pre>`);
          codigo = null;
        } else {
          fecharTudo();
          codigo = { linguagem: cerca[1], linhas: [] };
        }
        continue;
      }
      if (codigo) { codigo.linhas.push(bruta); continue; }

      const seguro = escapar(linha);

      if (!linha.trim()) { fecharTudo(); continue; }

      /* títulos */
      const titulo = seguro.match(/^(#{1,4})\s+(.*)$/);
      if (titulo) {
        fecharTudo();
        const nivel = Math.min(titulo[1].length + 1, 4); /* h1 do doc já existe */
        blocos.push(`<h${nivel}>${embutido(titulo[2], config.citacoes)}</h${nivel}>`);
        continue;
      }

      /* régua */
      if (/^(-{3,}|\*{3,}|_{3,})$/.test(linha.trim())) {
        fecharTudo();
        blocos.push("<hr>");
        continue;
      }

      /* citação em bloco */
      const bloco = seguro.match(/^&gt;\s?(.*)$/);
      if (bloco) { fecharLista(); citacao.push(bloco[1]); continue; }
      fecharCitacao();

      /* listas */
      const ordenada = seguro.match(/^\s*\d+[.)]\s+(.*)$/);
      const naoOrdenada = seguro.match(/^\s*[-*+]\s+(.*)$/);
      if (ordenada || naoOrdenada) {
        const tipo = ordenada ? "ol" : "ul";
        if (!lista || lista.tipo !== tipo) { fecharLista(); lista = { tipo, itens: [] }; }
        lista.itens.push((ordenada || naoOrdenada)[1]);
        continue;
      }
      fecharLista();

      blocos.push(`<p>${embutido(seguro, config.citacoes)}</p>`);
    }

    if (codigo) blocos.push(`<pre><code>${escapar(codigo.linhas.join("\n"))}</code></pre>`);
    fecharTudo();
    return blocos.join("\n");
  }

  global.Markdown = { renderizar, escapar };
})(window);
