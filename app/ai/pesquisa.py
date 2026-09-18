"""Pipeline de pesquisa: consulta as bases, ranqueia e sintetiza a resposta.

Fluxo completo:

    pergunta
      -> roteamento por area do conhecimento
      -> consulta paralela as bases publicas (com cache)
      -> fragmentacao dos textos em trechos
      -> ranqueamento BM25 + selecao diversa (MMR)
      -> sintese com citacoes numeradas [1], [2], ...
"""

from __future__ import annotations

import asyncio
import hashlib
from dataclasses import dataclass, field
from typing import Any

import httpx

from ..cache import CacheTTL
from ..config import obter_config
from ..ranking import pontuar_bm25, selecionar_diversos
from ..sources import Documento
from ..sources.registro import FONTES, detectar_area, escolher_fontes
from ..texto import Trecho, dividir_em_trechos, resumir_extrativo, truncar
from .llm import ErroModelo, obter_motor

_cfg = obter_config()
_cache = CacheTTL(_cfg.cache_ttl_segundos, _cfg.cache_max_itens)

SISTEMA_PESQUISA = """Voce e o Nucleo, um tutor academico que responde em portugues do Brasil.

Regras invioláveis:
1. Baseie-se APENAS nos trechos numerados fornecidos. Nao use conhecimento externo.
2. Cite a origem de cada afirmacao com marcadores no formato [1], [2]. Toda
   afirmacao factual precisa de pelo menos uma citacao.
3. Se os trechos nao responderem a pergunta, diga isso com clareza e explique o
   que falta. Nunca invente dados, numeros, autores ou datas.
4. Quando as fontes divergirem, apresente as versoes e indique a divergencia.

Formato da resposta (markdown):
- Um paragrafo curto de resposta direta.
- Secao "## Como funciona" (ou titulo equivalente ao tema) com a explicacao
  desenvolvida, em paragrafos ou lista.
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
    duracao_ms: int = 0
    aviso: str = ""

    def para_dict(self) -> dict[str, Any]:
        return {
            "pergunta": self.pergunta,
            "resposta": self.resposta,
            "citacoes": [c.para_dict() for c in self.citacoes],
            "documentos": [d.para_dict() for d in self.documentos],
            "area": self.area,
            "fontes_consultadas": self.fontes_consultadas,
            "modo": self.modo,
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


async def coletar_documentos(
    consulta: str,
    fontes: list[str],
    limite_por_fonte: int,
    idioma: str = "pt",
    cliente: httpx.AsyncClient | None = None,
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
            chave = _chave_cache(fonte_id, consulta, limite_por_fonte, idioma)
            guardado = _cache.obter(chave)
            if guardado is not None:
                documentos.extend(guardado)
                diagnostico.append(
                    {
                        "fonte": fonte_id,
                        "nome": fonte.nome,
                        "itens": len(guardado),
                        "erro": "",
                        "duracao_ms": 0,
                        "cache": True,
                    }
                )
                continue
            pendentes.append(fonte_id)
            tarefas.append(fonte.executar(cliente, consulta, limite_por_fonte, idioma))

        if tarefas:
            resultados = await asyncio.gather(*tarefas, return_exceptions=True)
            for fonte_id, resultado in zip(pendentes, resultados):
                fonte = FONTES[fonte_id]
                if isinstance(resultado, BaseException):
                    diagnostico.append(
                        {
                            "fonte": fonte_id,
                            "nome": fonte.nome,
                            "itens": 0,
                            "erro": f"falha inesperada: {type(resultado).__name__}",
                            "duracao_ms": 0,
                            "cache": False,
                        }
                    )
                    continue
                if not resultado.erro:
                    _cache.guardar(
                        _chave_cache(fonte_id, consulta, limite_por_fonte, idioma),
                        resultado.documentos,
                    )
                documentos.extend(resultado.documentos)
                diagnostico.append(
                    {
                        "fonte": fonte_id,
                        "nome": fonte.nome,
                        "itens": len(resultado.documentos),
                        "erro": resultado.erro,
                        "duracao_ms": resultado.duracao_ms,
                        "cache": False,
                    }
                )
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
                    texto=bloco,
                    doc_id=doc.id,
                    titulo=doc.titulo,
                    url=doc.url,
                    fonte=doc.fonte,
                    indice=indice,
                )
            )
    return trechos


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
                    trecho=truncar(trecho.texto, 260),
                    identificador=doc.identificador if doc else "",
                    extra=doc.extra if doc else {},
                )
            )
        numero = numeros[trecho.doc_id]
        cabecalho = f"[{numero}] {trecho.titulo} — {FONTES[trecho.fonte].nome}"
        partes.append(f"{cabecalho}\n{trecho.texto}")

    return citacoes, numeros, "\n\n---\n\n".join(partes)


def sintetizar_extrativo(
    pergunta: str,
    selecionados: list[Trecho],
    numeros: dict[str, int],
) -> str:
    """Resposta construida sem modelo neural, so com os textos das fontes.

    Cada paragrafo e um resumo extrativo de um trecho, com a citacao correta.
    Nenhuma frase e inventada: tudo vem literalmente das bases consultadas.
    """
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
    escolhidas = escolher_fontes(pergunta, fontes)

    limites = {"rapida": 3, "media": _cfg.max_resultados_por_fonte, "profunda": 9}
    limite_fonte = limites.get(profundidade, _cfg.max_resultados_por_fonte)
    max_trechos = {"rapida": 8, "media": _cfg.max_trechos_contexto, "profunda": 20}
    limite_trechos = max_trechos.get(profundidade, _cfg.max_trechos_contexto)

    documentos, diagnostico = await coletar_documentos(
        pergunta, escolhidas, limite_fonte, idioma, cliente
    )

    trechos = montar_trechos(documentos)
    ranqueados = pontuar_bm25(pergunta, trechos)
    selecionados = selecionar_diversos(ranqueados, limite_trechos)
    citacoes, numeros, contexto = _numerar_citacoes(selecionados, documentos)

    motor = obter_motor()
    aviso = ""
    if motor.disponivel and contexto:
        prompt = (
            f"Pergunta do estudante: {pergunta}\n\n"
            f"Area provavel: {area}\n\n"
            f"Trechos recuperados das bases publicas:\n\n{contexto}\n\n"
            "Escreva a resposta seguindo as regras do sistema, citando [n]."
        )
        try:
            resposta = await motor.responder(SISTEMA_PESQUISA, prompt)
            modo = "neural"
        except ErroModelo as exc:
            resposta = sintetizar_extrativo(pergunta, selecionados, numeros)
            modo = "extrativo"
            aviso = f"O modelo de linguagem falhou ({exc}); usei o modo extrativo."
    else:
        resposta = sintetizar_extrativo(pergunta, selecionados, numeros)
        modo = "extrativo"
        if not motor.disponivel:
            aviso = (
                "Sem ANTHROPIC_API_KEY configurada: resposta montada apenas com "
                "trechos literais das fontes."
            )

    docs_citados = {c.titulo for c in citacoes}
    ordenados = sorted(documentos, key=lambda d: d.titulo not in docs_citados)

    duracao = int((asyncio.get_running_loop().time() - inicio) * 1000)
    return ResultadoPesquisa(
        pergunta=pergunta,
        resposta=resposta,
        citacoes=citacoes,
        documentos=ordenados[:40],
        area=area,
        fontes_consultadas=diagnostico,
        modo=modo,
        duracao_ms=duracao,
        aviso=aviso,
    )


def estatisticas_cache() -> dict[str, int]:
    return _cache.estatisticas


def limpar_cache() -> None:
    _cache.limpar()


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

    escolhidas = escolher_fontes(pergunta, fontes)
    documentos, diagnostico = await coletar_documentos(
        pergunta, escolhidas, _cfg.max_resultados_por_fonte, "pt", cliente
    )
    trechos = pontuar_bm25(pergunta, montar_trechos(documentos))
    selecionados = selecionar_diversos(trechos, _cfg.max_trechos_contexto)
    citacoes, _, _ = _numerar_citacoes(selecionados, documentos)
    resultado = ResultadoPesquisa(
        pergunta=pergunta,
        resposta="",
        citacoes=citacoes,
        documentos=documentos[:40],
        area=detectar_area(pergunta),
        fontes_consultadas=diagnostico,
        modo="recuperacao",
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
      {"tipo": "etapa", ...}      progresso da recuperacao
      {"tipo": "fontes", ...}     diagnostico por base consultada
      {"tipo": "citacoes", ...}   referencias numeradas
      {"tipo": "texto", ...}      pedaco da resposta
      {"tipo": "fim", ...}        metadados finais
    """
    inicio = asyncio.get_running_loop().time()
    pergunta = pergunta.strip()
    area = detectar_area(pergunta)
    escolhidas = escolher_fontes(pergunta, fontes)

    from ..sources.registro import rotular_area

    yield {
        "tipo": "etapa",
        "rotulo": f"Roteando para a área '{rotular_area(area)}'",
        "fontes": escolhidas,
    }

    limites = {"rapida": 3, "media": _cfg.max_resultados_por_fonte, "profunda": 9}
    limite_fonte = limites.get(profundidade, _cfg.max_resultados_por_fonte)
    limite_trechos = {"rapida": 8, "media": _cfg.max_trechos_contexto, "profunda": 20}.get(
        profundidade, _cfg.max_trechos_contexto
    )

    cliente = criar_cliente()
    try:
        yield {"tipo": "etapa", "rotulo": "Consultando as bases de dados"}
        documentos, diagnostico = await coletar_documentos(
            pergunta, escolhidas, limite_fonte, idioma, cliente
        )
        yield {"tipo": "fontes", "itens": diagnostico, "documentos": len(documentos)}

        yield {"tipo": "etapa", "rotulo": "Ranqueando os trechos mais relevantes"}
        trechos = pontuar_bm25(pergunta, montar_trechos(documentos))
        selecionados = selecionar_diversos(trechos, limite_trechos)
        citacoes, numeros, contexto = _numerar_citacoes(selecionados, documentos)

        yield {
            "tipo": "citacoes",
            "itens": [c.para_dict() for c in citacoes],
            "documentos": [d.para_dict() for d in documentos[:40]],
        }

        motor = obter_motor()
        partes: list[str] = []
        modo = "extrativo"
        aviso = ""

        if motor.disponivel and contexto:
            yield {"tipo": "etapa", "rotulo": "Redigindo a resposta"}
            prompt = (
                f"Pergunta do estudante: {pergunta}\n\n"
                f"Area provavel: {area}\n\n"
                f"Trechos recuperados das bases publicas:\n\n{contexto}\n\n"
                "Escreva a resposta seguindo as regras do sistema, citando [n]."
            )
            try:
                async for pedaco in motor.transmitir(SISTEMA_PESQUISA, prompt):
                    partes.append(pedaco)
                    yield {"tipo": "texto", "conteudo": pedaco}
                modo = "neural"
            except ErroModelo as exc:
                partes = [sintetizar_extrativo(pergunta, selecionados, numeros)]
                aviso = f"O modelo falhou ({exc}); resposta montada em modo extrativo."
                yield {"tipo": "texto", "conteudo": partes[0]}
        else:
            texto = sintetizar_extrativo(pergunta, selecionados, numeros)
            partes = [texto]
            if not motor.disponivel:
                aviso = (
                    "Sem ANTHROPIC_API_KEY configurada: resposta montada apenas com "
                    "trechos literais das fontes."
                )
            yield {"tipo": "texto", "conteudo": texto}

        resposta = "".join(partes)
        resultado = ResultadoPesquisa(
            pergunta=pergunta,
            resposta=resposta,
            citacoes=citacoes,
            documentos=documentos[:40],
            area=area,
            fontes_consultadas=diagnostico,
            modo=modo,
            duracao_ms=int((asyncio.get_running_loop().time() - inicio) * 1000),
            aviso=aviso,
        )
        registrar_resultado(resultado, fontes)
        yield {
            "tipo": "fim",
            "modo": modo,
            "area": rotular_area(area),
            "aviso": aviso,
            "duracao_ms": resultado.duracao_ms,
            "resposta": resposta,
        }
    finally:
        await cliente.aclose()
