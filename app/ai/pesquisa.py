"""Pipeline de pesquisa: entende a pergunta, consulta as bases e sintetiza.

Fluxo completo:

    pergunta
      -> classificacao da intencao (definicao, procedimento, estado da arte...)
      -> roteamento por area do conhecimento
      -> ponte bilingue: a versao em ingles vai para as bases academicas
      -> consulta paralela as bases (com cache) + biblioteca local
      -> fragmentacao e ranqueamento BM25 com pesos ajustados pela intencao
      -> (modo profundo) segunda rodada com os termos aprendidos na primeira
      -> selecao diversa (MMR), equilibrada entre fontes
      -> sintese com citacoes numeradas
      -> checagem de fundamentacao de cada afirmacao
"""

from __future__ import annotations

import asyncio
import hashlib
from dataclasses import dataclass, field
from typing import Any

import httpx

from ..cache import CacheTTL
from ..config import obter_config
from ..consulta import (
    Intencao,
    classificar_intencao,
    consulta_expandida,
    termos_de_realimentacao,
    versao_em_ingles,
)
from ..ranking import pontuar_bm25, selecionar_diversos
from ..sources import Documento
from ..sources.registro import FONTES, detectar_area, escolher_fontes, rotular_area
from ..texto import Trecho, dividir_em_trechos, resumir_extrativo, truncar
from .llm import ErroModelo, obter_motor
from .verificacao import Relatorio, verificar_fundamentacao

_cfg = obter_config()
_cache = CacheTTL(_cfg.cache_ttl_segundos, _cfg.cache_max_itens)

# Bases cujo acervo e predominantemente em ingles: recebem a consulta traduzida.
FONTES_EM_INGLES = {
    "arxiv", "pubmed", "openalex", "semanticscholar", "crossref",
    "openlibrary", "stackexchange",
}
# A biblioteca local pode ter livros nos dois idiomas: recebe as duas versoes.
FONTES_BILINGUES = {"biblioteca"}

SISTEMA_PESQUISA = """Voce e o Nucleo, um tutor academico que responde em portugues do Brasil.

Regras invioláveis:
1. Baseie-se APENAS nos trechos numerados fornecidos. Nao use conhecimento externo.
2. Cite a origem de cada afirmacao com marcadores no formato [1], [2]. Toda
   afirmacao factual precisa de pelo menos uma citacao.
3. Se os trechos nao responderem a pergunta, diga isso com clareza e explique o
   que falta. Nunca invente dados, numeros, autores ou datas.
4. Numero, data ou nome proprio so podem aparecer se estiverem literalmente no
   trecho citado.
5. Quando as fontes divergirem, apresente as versoes e indique a divergencia.
6. Trechos vindos de livro didatico ("Sua biblioteca") sao material de estudo
   curado: prefira-os para explicar fundamentos, e use os artigos para
   atualizar ou complementar.

Formato da resposta (markdown):
- Um paragrafo curto de resposta direta.
- Uma secao "## " com titulo adequado ao tema, desenvolvendo a explicacao.
- Secao "## Para fixar" com 2 a 4 pontos-chave que valem memorizar.
- Se houver controversia ou limite de evidencia, uma secao "## Atencao".

Tom: didatico, direto, sem enrolacao. Explique jargao na primeira vez que usar."""


@dataclass(slots=True)
class Citacao:
    """Fonte numerada exibida ao lado da resposta."""

    numero: int
    titulo: str
    url: str
    fonte: str
    autores: list[str] = field(default_factory=list)
    ano: int | None = None
    trecho: str = ""
    identificador: str = ""
    extra: dict[str, Any] = field(default_factory=dict)

    def para_dict(self) -> dict[str, Any]:
        return {
            "numero": self.numero,
            "titulo": self.titulo,
            "url": self.url,
            "fonte": self.fonte,
            "autores": self.autores[:4],
            "ano": self.ano,
            "trecho": self.trecho,
            "identificador": self.identificador,
            "extra": self.extra,
        }


@dataclass(slots=True)
class ResultadoPesquisa:
    """Pacote devolvido ao cliente da API."""

    pergunta: str
    resposta: str
    citacoes: list[Citacao]
    documentos: list[Documento]
    area: str
    fontes_consultadas: list[dict[str, Any]]
    modo: str                      # "neural" ou "extrativo"
    intencao: str = "geral"
    intencao_rotulo: str = ""
    consulta_en: str = ""
    origem_traducao: str = ""
    termos_aprendidos: list[str] = field(default_factory=list)
    verificacao: Relatorio | None = None
    duracao_ms: int = 0
    aviso: str = ""

    def para_dict(self) -> dict[str, Any]:
        return {
            "pergunta": self.pergunta,
            "resposta": self.resposta,
            "citacoes": [c.para_dict() for c in self.citacoes],
            "documentos": [d.para_dict() for d in self.documentos],
            "area": rotular_area(self.area),
            "fontes_consultadas": self.fontes_consultadas,
            "modo": self.modo,
            "intencao": self.intencao,
            "intencao_rotulo": self.intencao_rotulo,
            "consulta_en": self.consulta_en,
            "origem_traducao": self.origem_traducao,
            "termos_aprendidos": self.termos_aprendidos,
            "verificacao": self.verificacao.para_dict() if self.verificacao else None,
            "duracao_ms": self.duracao_ms,
            "aviso": self.aviso,
        }


def _chave_cache(fonte: str, consulta: str, limite: int, idioma: str) -> str:
    bruto = f"{fonte}|{consulta.strip().lower()}|{limite}|{idioma}"
    return hashlib.sha1(bruto.encode("utf-8")).hexdigest()


def criar_cliente() -> httpx.AsyncClient:
    """Cliente HTTP compartilhado, com cabecalhos de boa cidadania."""
    return httpx.AsyncClient(
        timeout=httpx.Timeout(_cfg.timeout_http),
        follow_redirects=True,
        headers={
            "User-Agent": _cfg.user_agent,
            "Accept": "application/json, text/xml, */*",
            "Accept-Encoding": "gzip, deflate",
        },
    )


def consulta_para_fonte(fonte: str, consulta: str, consulta_en: str) -> str:
    """Escolhe qual versao da pergunta mandar para cada base."""
    if not consulta_en or consulta_en.strip().lower() == consulta.strip().lower():
        return consulta
    if fonte in FONTES_BILINGUES:
        return f"{consulta} {consulta_en}"
    if fonte in FONTES_EM_INGLES:
        return consulta_en
    return consulta


async def coletar_documentos(
    consulta: str,
    fontes: list[str],
    limite_por_fonte: int,
    idioma: str = "pt",
    cliente: httpx.AsyncClient | None = None,
    consulta_en: str = "",
) -> tuple[list[Documento], list[dict[str, Any]]]:
    """Consulta as bases em paralelo e devolve documentos + diagnostico."""
    proprio = cliente is None
    cliente = cliente or criar_cliente()
    try:
        tarefas = []
        pendentes: list[str] = []
        documentos: list[Documento] = []
        diagnostico: list[dict[str, Any]] = []

        for fonte_id in fontes:
            fonte = FONTES.get(fonte_id)
            if fonte is None:
                continue
            alvo = consulta_para_fonte(fonte_id, consulta, consulta_en)
            chave = _chave_cache(fonte_id, alvo, limite_por_fonte, idioma)
            guardado = _cache.obter(chave)
            if guardado is not None:
                documentos.extend(guardado)
                diagnostico.append({
                    "fonte": fonte_id, "nome": fonte.nome, "itens": len(guardado),
                    "erro": "", "duracao_ms": 0, "cache": True, "consulta": alvo,
                })
                continue
            pendentes.append(fonte_id)
            tarefas.append(fonte.executar(cliente, alvo, limite_por_fonte, idioma))

        if tarefas:
            resultados = await asyncio.gather(*tarefas, return_exceptions=True)
            for fonte_id, resultado in zip(pendentes, resultados):
                fonte = FONTES[fonte_id]
                alvo = consulta_para_fonte(fonte_id, consulta, consulta_en)
                if isinstance(resultado, BaseException):
                    diagnostico.append({
                        "fonte": fonte_id, "nome": fonte.nome, "itens": 0,
                        "erro": f"falha inesperada: {type(resultado).__name__}",
                        "duracao_ms": 0, "cache": False, "consulta": alvo,
                    })
                    continue
                if not resultado.erro:
                    _cache.guardar(
                        _chave_cache(fonte_id, alvo, limite_por_fonte, idioma),
                        resultado.documentos,
                    )
                documentos.extend(resultado.documentos)
                diagnostico.append({
                    "fonte": fonte_id, "nome": fonte.nome,
                    "itens": len(resultado.documentos), "erro": resultado.erro,
                    "duracao_ms": resultado.duracao_ms, "cache": False,
                    "consulta": alvo,
                })
        return documentos, diagnostico
    finally:
        if proprio:
            await cliente.aclose()


def montar_trechos(documentos: list[Documento]) -> list[Trecho]:
    """Transforma documentos em trechos ranqueaveis."""
    trechos: list[Trecho] = []
    for doc in documentos:
        blocos = dividir_em_trechos(
            doc.conteudo or doc.resumo,
            _cfg.tamanho_trecho,
            _cfg.sobreposicao_trecho,
        )
        for indice, bloco in enumerate(blocos[:6]):
            trechos.append(
                Trecho(
                    texto=bloco, doc_id=doc.id, titulo=doc.titulo,
                    url=doc.url, fonte=doc.fonte, indice=indice,
                )
            )
    return trechos


def _juntar_documentos(*listas: list[Documento]) -> list[Documento]:
    """Une resultados de varias rodadas sem repetir o mesmo documento."""
    vistos: set[str] = set()
    juntos: list[Documento] = []
    for lista in listas:
        for doc in lista:
            if doc.id in vistos:
                continue
            vistos.add(doc.id)
            juntos.append(doc)
    return juntos


def _numerar_citacoes(
    selecionados: list[Trecho],
    documentos: list[Documento],
) -> tuple[list[Citacao], dict[str, int], str]:
    """Cria a lista de citacoes e o bloco de contexto numerado."""
    por_id = {doc.id: doc for doc in documentos}
    numeros: dict[str, int] = {}
    citacoes: list[Citacao] = []
    partes: list[str] = []

    for trecho in selecionados:
        if trecho.doc_id not in numeros:
            numeros[trecho.doc_id] = len(numeros) + 1
            doc = por_id.get(trecho.doc_id)
            citacoes.append(
                Citacao(
                    numero=numeros[trecho.doc_id],
                    titulo=trecho.titulo,
                    url=trecho.url,
                    fonte=trecho.fonte,
                    autores=doc.autores if doc else [],
                    ano=doc.ano if doc else None,
                    trecho=truncar(trecho.texto, 420),
                    identificador=doc.identificador if doc else "",
                    extra=doc.extra if doc else {},
                )
            )
        numero = numeros[trecho.doc_id]
        nome_fonte = FONTES[trecho.fonte].nome if trecho.fonte in FONTES else trecho.fonte
        partes.append(f"[{numero}] {trecho.titulo} — {nome_fonte}\n{trecho.texto}")

    return citacoes, numeros, "\n\n---\n\n".join(partes)


def sintetizar_extrativo(
    pergunta: str,
    selecionados: list[Trecho],
    numeros: dict[str, int],
) -> str:
    """Resposta construida sem modelo neural, so com os textos das fontes."""
    if not selecionados:
        return (
            "Não encontrei material nas bases consultadas para esta pergunta. "
            "Tente reformular com termos mais específicos ou marcar outras fontes."
        )

    linhas = [
        f"**{pergunta.strip().rstrip('?')}** — síntese dos trechos mais relevantes "
        f"encontrados em {len({t.fonte for t in selecionados})} base(s):",
        "",
    ]
    vistos: set[str] = set()
    for trecho in selecionados[:6]:
        if trecho.doc_id in vistos:
            continue
        vistos.add(trecho.doc_id)
        resumo = resumir_extrativo(trecho.texto, pergunta, max_frases=2)
        numero = numeros.get(trecho.doc_id, 0)
        linhas.append(f"- {resumo} [{numero}]")

    linhas += [
        "",
        "## Para fixar",
        "- Compare as fontes acima antes de concluir: elas não foram reescritas, "
        "apenas selecionadas por relevância.",
        "- Abra as referências numeradas para ler o texto completo.",
        "",
        "> _Modo extrativo: sem chave de API configurada, o Núcleo apenas seleciona "
        "e ordena trechos reais das bases, sem reescrever o conteúdo._",
    ]
    return "\n".join(linhas)


def _montar_prompt(pergunta: str, area: str, intencao: Intencao, contexto: str) -> str:
    orientacao = f"\nOrientacao para este tipo de pergunta: {intencao.orientacao}\n" \
        if intencao.orientacao else ""
    return (
        f"Pergunta do estudante: {pergunta}\n\n"
        f"Area provavel: {rotular_area(area)}\n"
        f"Tipo de pergunta: {intencao.rotulo}\n{orientacao}\n"
        f"Trechos recuperados das bases publicas e da biblioteca do estudante:\n\n"
        f"{contexto}\n\n"
        "Escreva a resposta seguindo as regras do sistema, citando [n]."
    )


@dataclass(slots=True)
class _Recuperacao:
    """Estado intermediario compartilhado entre a busca normal e a em fluxo."""

    documentos: list[Documento]
    diagnostico: list[dict[str, Any]]
    selecionados: list[Trecho]
    citacoes: list[Citacao]
    numeros: dict[str, int]
    contexto: str
    termos_aprendidos: list[str]
    consulta_en: str
    origem_traducao: str


async def _recuperar(
    pergunta: str,
    fontes: list[str] | None,
    idioma: str,
    profundidade: str,
    intencao: Intencao,
    cliente: httpx.AsyncClient,
    ao_progredir=None,
) -> _Recuperacao:
    """Executa a recuperacao completa (com as rodadas extras do modo profundo)."""
    escolhidas = escolher_fontes(pergunta, fontes)
    limites = {"rapida": 3, "media": _cfg.max_resultados_por_fonte, "profunda": 9}
    limite_fonte = limites.get(profundidade, _cfg.max_resultados_por_fonte)
    limite_trechos = {
        "rapida": 8, "media": _cfg.max_trechos_contexto, "profunda": 20
    }.get(profundidade, _cfg.max_trechos_contexto)

    # Ponte bilingue: as bases academicas recebem o termo consagrado em ingles.
    consulta_en, origem = "", "original"
    if profundidade != "rapida" and any(f in FONTES_EM_INGLES for f in escolhidas):
        consulta_en, origem = await versao_em_ingles(cliente, pergunta, idioma)
        if consulta_en.strip().lower() == pergunta.strip().lower():
            consulta_en, origem = "", "original"
    if ao_progredir and consulta_en:
        await ao_progredir(f"Buscando também por “{consulta_en}” nas bases em inglês")

    documentos, diagnostico = await coletar_documentos(
        pergunta, escolhidas, limite_fonte, idioma, cliente, consulta_en
    )

    trechos = pontuar_bm25(pergunta, montar_trechos(documentos), intencao.pesos)

    # Segunda rodada: o vocabulario dos melhores trechos afina a busca.
    termos_aprendidos: list[str] = []
    if profundidade == "profunda" and trechos:
        termos_aprendidos = termos_de_realimentacao(trechos, pergunta)
        if termos_aprendidos:
            if ao_progredir:
                await ao_progredir(
                    "Refinando com os termos aprendidos: " + ", ".join(termos_aprendidos)
                )
            refinada = consulta_expandida(pergunta, termos_aprendidos)
            extras, diag_extra = await coletar_documentos(
                refinada, escolhidas, max(3, limite_fonte // 2), idioma, cliente,
                consulta_expandida(consulta_en, termos_aprendidos) if consulta_en else "",
            )
            documentos = _juntar_documentos(documentos, extras)
            for item in diag_extra:
                item["rodada"] = 2
                diagnostico.append(item)
            trechos = pontuar_bm25(refinada, montar_trechos(documentos), intencao.pesos)

    # Teto por fonte: mesmo a melhor base nao pode ocupar mais de um terco do
    # contexto, senao a resposta perde o contraste entre pontos de vista.
    selecionados = selecionar_diversos(
        trechos, limite_trechos, max_por_fonte=max(2, limite_trechos // 3)
    )
    citacoes, numeros, contexto = _numerar_citacoes(selecionados, documentos)

    return _Recuperacao(
        documentos=documentos, diagnostico=diagnostico, selecionados=selecionados,
        citacoes=citacoes, numeros=numeros, contexto=contexto,
        termos_aprendidos=termos_aprendidos, consulta_en=consulta_en,
        origem_traducao=origem,
    )


async def pesquisar(
    pergunta: str,
    fontes: list[str] | None = None,
    idioma: str = "pt",
    profundidade: str = "media",
    cliente: httpx.AsyncClient | None = None,
) -> ResultadoPesquisa:
    """Executa a pesquisa completa e devolve resposta com citacoes."""
    inicio = asyncio.get_running_loop().time()
    pergunta = pergunta.strip()
    area = detectar_area(pergunta)
    intencao = classificar_intencao(pergunta)

    proprio = cliente is None
    cliente = cliente or criar_cliente()
    try:
        recuperado = await _recuperar(
            pergunta, fontes, idioma, profundidade, intencao, cliente
        )
    finally:
        if proprio:
            await cliente.aclose()

    motor = obter_motor()
    aviso = ""
    if motor.disponivel and recuperado.contexto:
        try:
            resposta = await motor.responder(
                SISTEMA_PESQUISA,
                _montar_prompt(pergunta, area, intencao, recuperado.contexto),
            )
            modo = "neural"
        except ErroModelo as exc:
            resposta = sintetizar_extrativo(
                pergunta, recuperado.selecionados, recuperado.numeros
            )
            modo = "extrativo"
            aviso = f"O modelo de linguagem falhou ({exc}); usei o modo extrativo."
    else:
        resposta = sintetizar_extrativo(
            pergunta, recuperado.selecionados, recuperado.numeros
        )
        modo = "extrativo"
        if not motor.disponivel:
            aviso = (
                "Sem ANTHROPIC_API_KEY configurada: resposta montada apenas com "
                "trechos literais das fontes."
            )

    titulos_citados = {c.titulo for c in recuperado.citacoes}
    ordenados = sorted(recuperado.documentos, key=lambda d: d.titulo not in titulos_citados)

    return ResultadoPesquisa(
        pergunta=pergunta,
        resposta=resposta,
        citacoes=recuperado.citacoes,
        documentos=ordenados[:40],
        area=area,
        fontes_consultadas=recuperado.diagnostico,
        modo=modo,
        intencao=intencao.tipo,
        intencao_rotulo=intencao.rotulo,
        consulta_en=recuperado.consulta_en,
        origem_traducao=recuperado.origem_traducao,
        termos_aprendidos=recuperado.termos_aprendidos,
        verificacao=verificar_fundamentacao(resposta, recuperado.citacoes),
        duracao_ms=int((asyncio.get_running_loop().time() - inicio) * 1000),
        aviso=aviso,
    )


# --------------------------------------------------------------------------
# Reaproveitamento de resultados entre chamadas (flashcards, quiz, plano)
# --------------------------------------------------------------------------

_resultados = CacheTTL(ttl_segundos=60 * 60 * 2, max_itens=64)


def chave_resultado(pergunta: str, fontes: list[str] | None) -> str:
    bruto = f"{pergunta.strip().lower()}|{','.join(sorted(fontes or []))}"
    return hashlib.sha1(bruto.encode("utf-8")).hexdigest()[:16]


def registrar_resultado(resultado: ResultadoPesquisa, fontes: list[str] | None) -> str:
    """Guarda o resultado para que as ferramentas de estudo o reutilizem."""
    chave = chave_resultado(resultado.pergunta, fontes)
    _resultados.guardar(chave, resultado)
    return chave


async def recuperar_resultado(
    pergunta: str,
    fontes: list[str] | None = None,
    cliente: httpx.AsyncClient | None = None,
) -> ResultadoPesquisa:
    """Devolve o resultado em memoria ou refaz apenas a recuperacao.

    A reconstrucao nao chama o modelo de linguagem: so busca (com cache HTTP),
    ranqueia e numera as citacoes. E barata e suficiente para gerar flashcards,
    quiz e planos sobre o mesmo material.
    """
    guardado = _resultados.obter(chave_resultado(pergunta, fontes))
    if guardado is not None:
        return guardado

    intencao = classificar_intencao(pergunta)
    proprio = cliente is None
    cliente = cliente or criar_cliente()
    try:
        recuperado = await _recuperar(pergunta, fontes, "pt", "media", intencao, cliente)
    finally:
        if proprio:
            await cliente.aclose()

    resultado = ResultadoPesquisa(
        pergunta=pergunta,
        resposta="",
        citacoes=recuperado.citacoes,
        documentos=recuperado.documentos[:40],
        area=detectar_area(pergunta),
        fontes_consultadas=recuperado.diagnostico,
        modo="recuperacao",
        intencao=intencao.tipo,
        intencao_rotulo=intencao.rotulo,
        consulta_en=recuperado.consulta_en,
        origem_traducao=recuperado.origem_traducao,
    )
    registrar_resultado(resultado, fontes)
    return resultado


async def pesquisar_em_fluxo(
    pergunta: str,
    fontes: list[str] | None = None,
    idioma: str = "pt",
    profundidade: str = "media",
):
    """Versao geradora: emite eventos de progresso e a resposta em pedacos.

    Eventos emitidos (dicionarios prontos para virar SSE):
      {"tipo": "etapa", ...}        progresso da recuperacao
      {"tipo": "fontes", ...}       diagnostico por base consultada
      {"tipo": "citacoes", ...}     referencias numeradas
      {"tipo": "texto", ...}        pedaco da resposta
      {"tipo": "verificacao", ...}  checagem de fundamentacao
      {"tipo": "fim", ...}          metadados finais
    """
    inicio = asyncio.get_running_loop().time()
    pergunta = pergunta.strip()
    area = detectar_area(pergunta)
    intencao = classificar_intencao(pergunta)
    escolhidas = escolher_fontes(pergunta, fontes)

    fila: asyncio.Queue[str] = asyncio.Queue()

    async def anotar(rotulo: str) -> None:
        await fila.put(rotulo)

    yield {
        "tipo": "etapa",
        "rotulo": f"Pergunta do tipo “{intencao.rotulo}”, área {rotular_area(area)}",
        "fontes": escolhidas,
        "intencao": intencao.tipo,
    }

    cliente = criar_cliente()
    try:
        yield {"tipo": "etapa", "rotulo": "Consultando as bases de dados"}

        tarefa = asyncio.create_task(
            _recuperar(pergunta, fontes, idioma, profundidade, intencao, cliente, anotar)
        )
        while not tarefa.done():
            try:
                rotulo = await asyncio.wait_for(fila.get(), timeout=0.25)
                yield {"tipo": "etapa", "rotulo": rotulo}
            except asyncio.TimeoutError:
                continue
        while not fila.empty():
            yield {"tipo": "etapa", "rotulo": fila.get_nowait()}
        recuperado = await tarefa

        yield {
            "tipo": "fontes",
            "itens": recuperado.diagnostico,
            "documentos": len(recuperado.documentos),
        }
        yield {"tipo": "etapa", "rotulo": "Ranqueando os trechos mais relevantes"}
        yield {
            "tipo": "citacoes",
            "itens": [c.para_dict() for c in recuperado.citacoes],
            "documentos": [d.para_dict() for d in recuperado.documentos[:40]],
        }

        motor = obter_motor()
        partes: list[str] = []
        modo = "extrativo"
        aviso = ""

        if motor.disponivel and recuperado.contexto:
            yield {"tipo": "etapa", "rotulo": "Redigindo a resposta"}
            prompt = _montar_prompt(pergunta, area, intencao, recuperado.contexto)
            try:
                async for pedaco in motor.transmitir(SISTEMA_PESQUISA, prompt):
                    partes.append(pedaco)
                    yield {"tipo": "texto", "conteudo": pedaco}
                modo = "neural"
            except ErroModelo as exc:
                partes = [sintetizar_extrativo(
                    pergunta, recuperado.selecionados, recuperado.numeros
                )]
                aviso = f"O modelo falhou ({exc}); resposta montada em modo extrativo."
                yield {"tipo": "texto", "conteudo": partes[0]}
        else:
            texto = sintetizar_extrativo(
                pergunta, recuperado.selecionados, recuperado.numeros
            )
            partes = [texto]
            if not motor.disponivel:
                aviso = (
                    "Sem ANTHROPIC_API_KEY configurada: resposta montada apenas com "
                    "trechos literais das fontes."
                )
            yield {"tipo": "texto", "conteudo": texto}

        resposta = "".join(partes)
        relatorio = verificar_fundamentacao(resposta, recuperado.citacoes)
        yield {"tipo": "verificacao", "relatorio": relatorio.para_dict()}

        resultado = ResultadoPesquisa(
            pergunta=pergunta, resposta=resposta, citacoes=recuperado.citacoes,
            documentos=recuperado.documentos[:40], area=area,
            fontes_consultadas=recuperado.diagnostico, modo=modo,
            intencao=intencao.tipo, intencao_rotulo=intencao.rotulo,
            consulta_en=recuperado.consulta_en,
            origem_traducao=recuperado.origem_traducao,
            termos_aprendidos=recuperado.termos_aprendidos,
            verificacao=relatorio,
            duracao_ms=int((asyncio.get_running_loop().time() - inicio) * 1000),
            aviso=aviso,
        )
        registrar_resultado(resultado, fontes)
        yield {
            "tipo": "fim",
            "modo": modo,
            "area": rotular_area(area),
            "intencao": intencao.tipo,
            "intencao_rotulo": intencao.rotulo,
            "consulta_en": recuperado.consulta_en,
            "origem_traducao": recuperado.origem_traducao,
            "termos_aprendidos": recuperado.termos_aprendidos,
            "aviso": aviso,
            "duracao_ms": resultado.duracao_ms,
            "resposta": resposta,
        }
    finally:
        await cliente.aclose()


def estatisticas_cache() -> dict[str, int]:
    return _cache.estatisticas


def limpar_cache() -> None:
    _cache.limpar()
    _resultados.limpar()
