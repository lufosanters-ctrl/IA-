"""API HTTP da plataforma Nucleo.

Sobe com:  python -m app         ou       uvicorn app.main:app --reload
"""

from __future__ import annotations

import json
import logging
from contextlib import asynccontextmanager
from typing import Any

from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from . import __version__, banco, biblioteca
from . import matematica
from .ai import estudo, pesquisa
from .catalogo import baixar_catalogo, listar_catalogo
from .matematica.classificacao import NIVEIS, TOPICOS, classificar
from .matematica.criacao import GERADORES, criar as criar_questao
from .matematica.resolucao import Problema, dar_pista, resolver as resolver_problema
from .livros import FORMATOS
from .config import obter_config
from .schemas import (
    PedidoBaralho,
    PedidoCatalogo,
    PedidoExplicacao,
    PedidoFlashcards,
    PedidoConferencia,
    PedidoIndexarPasta,
    PedidoMatematica,
    PedidoPista,
    PedidoPesquisa,
    PedidoPlano,
    PedidoQuestao,
    PedidoQuiz,
    PedidoRevisao,
    PedidoSalvarCartoes,
)
from .sources.registro import listar_fontes, rotular_area

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
)
log = logging.getLogger("nucleo")
cfg = obter_config()


@asynccontextmanager
async def ciclo_de_vida(app: FastAPI):
    banco.iniciar_banco()
    biblioteca.iniciar()
    acervo = biblioteca.estatisticas()
    log.info(
        "Nucleo %s pronto | modelo=%s | LLM=%s | biblioteca: %d livros, %d trechos",
        __version__, cfg.modelo, "ativo" if cfg.tem_llm else "modo extrativo",
        acervo["livros"], acervo["trechos"],
    )
    yield
    log.info("Nucleo encerrado")


app = FastAPI(
    title=cfg.nome_app,
    description=cfg.descricao_app,
    version=__version__,
    lifespan=ciclo_de_vida,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --------------------------------------------------------------------------
# Diagnostico
# --------------------------------------------------------------------------

@app.get("/api/saude", tags=["sistema"])
async def saude() -> dict[str, Any]:
    """Estado da plataforma, fontes disponiveis e situacao do modelo."""
    return {
        "nome": cfg.nome_app,
        "versao": __version__,
        "modelo_disponivel": cfg.tem_llm,
        "modelo": cfg.modelo if cfg.tem_llm else "",
        "modo": "neural" if cfg.tem_llm else "extrativo",
        "fontes": listar_fontes(),
        "cache": pesquisa.estatisticas_cache(),
        "biblioteca": biblioteca.estatisticas(),
    }


@app.get("/api/fontes", tags=["sistema"])
async def fontes() -> list[dict[str, Any]]:
    """Lista as bases de dados publicas que a IA sabe consultar."""
    return listar_fontes()


@app.post("/api/cache/limpar", tags=["sistema"])
async def limpar_cache() -> dict[str, str]:
    pesquisa.limpar_cache()
    return {"status": "cache limpo"}


# --------------------------------------------------------------------------
# Pesquisa
# --------------------------------------------------------------------------

@app.post("/api/pesquisar", tags=["pesquisa"])
async def pesquisar(pedido: PedidoPesquisa) -> dict[str, Any]:
    """Pesquisa nas bases publicas e devolve a resposta com citacoes."""
    resultado = await pesquisa.pesquisar(
        pedido.pergunta,
        fontes=pedido.fontes,
        idioma=pedido.idioma,
        profundidade=pedido.profundidade,
    )
    pesquisa.registrar_resultado(resultado, pedido.fontes)

    dados = resultado.para_dict()
    dados["area"] = rotular_area(resultado.area)
    if pedido.salvar:
        dados["id"] = banco.salvar_pesquisa(
            resultado.pergunta,
            resultado.resposta,
            resultado.area,
            resultado.modo,
            [c.para_dict() for c in resultado.citacoes],
        )
    return dados


@app.get("/api/pesquisar/fluxo", tags=["pesquisa"])
async def pesquisar_fluxo(
    pergunta: str = Query(min_length=2, max_length=500),
    fontes: str = Query(default=""),
    idioma: str = Query(default="pt"),
    profundidade: str = Query(default="media"),
    salvar: bool = Query(default=True),
) -> StreamingResponse:
    """Mesma pesquisa, transmitida em tempo real via Server-Sent Events."""
    lista_fontes = [f for f in fontes.split(",") if f.strip()] or None

    async def gerar():
        final: dict[str, Any] = {}
        try:
            async for evento in pesquisa.pesquisar_em_fluxo(
                pergunta, lista_fontes, idioma, profundidade
            ):
                if evento.get("tipo") == "fim":
                    final = evento
                yield f"data: {json.dumps(evento, ensure_ascii=False)}\n\n"
        except Exception as exc:  # pragma: no cover - rede
            log.exception("falha no fluxo de pesquisa")
            erro = {"tipo": "erro", "mensagem": str(exc)}
            yield f"data: {json.dumps(erro, ensure_ascii=False)}\n\n"
            return

        if salvar and final:
            try:
                identificador = banco.salvar_pesquisa(
                    pergunta,
                    final.get("resposta", ""),
                    final.get("area", ""),
                    final.get("modo", ""),
                    [],
                )
                yield f"data: {json.dumps({'tipo': 'salvo', 'id': identificador})}\n\n"
            except Exception:
                log.exception("falha ao salvar historico")

    return StreamingResponse(
        gerar(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# --------------------------------------------------------------------------
# Ferramentas de estudo
# --------------------------------------------------------------------------

@app.post("/api/flashcards", tags=["estudo"])
async def flashcards(pedido: PedidoFlashcards) -> dict[str, Any]:
    """Gera flashcards a partir do material encontrado para o tema."""
    resultado = await pesquisa.recuperar_resultado(pedido.pergunta, pedido.fontes)
    if not resultado.citacoes:
        raise HTTPException(404, "Nenhuma fonte encontrada para gerar cartões.")
    dados = await estudo.gerar_flashcards(resultado, pedido.quantidade)
    mapa = {c.numero: c for c in resultado.citacoes}
    for cartao in dados["cartoes"]:
        citacao = mapa.get(cartao.get("citacao", 0))
        cartao["fonte_url"] = citacao.url if citacao else ""
        cartao["fonte_titulo"] = citacao.titulo if citacao else ""
    dados["pergunta"] = pedido.pergunta
    return dados


@app.post("/api/quiz", tags=["estudo"])
async def quiz(pedido: PedidoQuiz) -> dict[str, Any]:
    """Gera um questionario de multipla escolha sobre o tema."""
    resultado = await pesquisa.recuperar_resultado(pedido.pergunta, pedido.fontes)
    if not resultado.citacoes:
        raise HTTPException(404, "Nenhuma fonte encontrada para gerar o quiz.")
    dados = await estudo.gerar_quiz(resultado, pedido.quantidade)
    dados["pergunta"] = pedido.pergunta
    dados["citacoes"] = [c.para_dict() for c in resultado.citacoes]
    return dados


@app.post("/api/plano", tags=["estudo"])
async def plano(pedido: PedidoPlano) -> dict[str, Any]:
    """Monta um plano de estudo sequenciado para o tema."""
    resultado = None
    if pedido.usar_fontes:
        resultado = await pesquisa.recuperar_resultado(pedido.tema, None)
    return await estudo.gerar_plano(
        pedido.tema, pedido.semanas, pedido.horas_semana, pedido.nivel, resultado
    )


@app.post("/api/explicar", tags=["estudo"])
async def explicar(pedido: PedidoExplicacao) -> dict[str, Any]:
    """Reexplica um conceito no nivel escolhido, com base nas fontes."""
    resultado = await pesquisa.recuperar_resultado(pedido.conceito, pedido.fontes)
    if not resultado.citacoes:
        raise HTTPException(404, "Nenhuma fonte encontrada para este conceito.")
    dados = await estudo.explicar(pedido.conceito, pedido.nivel, resultado)
    dados["citacoes"] = [c.para_dict() for c in resultado.citacoes]
    return dados


# --------------------------------------------------------------------------
# Historico
# --------------------------------------------------------------------------

@app.get("/api/historico", tags=["historico"])
async def historico(limite: int = Query(default=30, ge=1, le=200)) -> list[dict[str, Any]]:
    return banco.listar_pesquisas(limite)


@app.get("/api/historico/{pesquisa_id}", tags=["historico"])
async def historico_item(pesquisa_id: int) -> dict[str, Any]:
    item = banco.obter_pesquisa(pesquisa_id)
    if item is None:
        raise HTTPException(404, "Pesquisa não encontrada.")
    return item


@app.delete("/api/historico/{pesquisa_id}", tags=["historico"])
async def apagar_historico(pesquisa_id: int) -> dict[str, str]:
    if not banco.apagar_pesquisa(pesquisa_id):
        raise HTTPException(404, "Pesquisa não encontrada.")
    return {"status": "removida"}


# --------------------------------------------------------------------------
# Baralhos e revisao espacada
# --------------------------------------------------------------------------

@app.get("/api/baralhos", tags=["revisao"])
async def baralhos() -> list[dict[str, Any]]:
    return banco.listar_baralhos()


@app.post("/api/baralhos", tags=["revisao"])
async def criar_baralho(pedido: PedidoBaralho) -> dict[str, Any]:
    identificador = banco.criar_baralho(pedido.nome.strip(), pedido.descricao.strip())
    return {"id": identificador, "nome": pedido.nome.strip()}


@app.delete("/api/baralhos/{baralho_id}", tags=["revisao"])
async def apagar_baralho(baralho_id: int) -> dict[str, str]:
    if not banco.apagar_baralho(baralho_id):
        raise HTTPException(404, "Baralho não encontrado.")
    return {"status": "removido"}


@app.get("/api/baralhos/{baralho_id}/cartoes", tags=["revisao"])
async def cartoes(baralho_id: int) -> list[dict[str, Any]]:
    return banco.cartoes_do_baralho(baralho_id)


@app.post("/api/baralhos/{baralho_id}/cartoes", tags=["revisao"])
async def salvar_cartoes(baralho_id: int, pedido: PedidoSalvarCartoes) -> dict[str, Any]:
    inseridos = banco.salvar_cartoes(
        baralho_id, [c.model_dump() for c in pedido.cartoes]
    )
    return {"inseridos": inseridos, "enviados": len(pedido.cartoes)}


@app.delete("/api/cartoes/{cartao_id}", tags=["revisao"])
async def apagar_cartao(cartao_id: int) -> dict[str, str]:
    if not banco.apagar_cartao(cartao_id):
        raise HTTPException(404, "Cartão não encontrado.")
    return {"status": "removido"}


@app.get("/api/revisao", tags=["revisao"])
async def revisao(
    baralho_id: int | None = Query(default=None),
    limite: int = Query(default=30, ge=1, le=100),
) -> list[dict[str, Any]]:
    """Cartoes que o algoritmo SM-2 marcou para revisar hoje."""
    return banco.cartoes_devidos(baralho_id, limite)


@app.post("/api/revisao/{cartao_id}", tags=["revisao"])
async def registrar_revisao(cartao_id: int, pedido: PedidoRevisao) -> dict[str, Any]:
    """Registra a nota da revisao (0 a 5) e reagenda o cartao."""
    dados = banco.revisar_cartao(cartao_id, pedido.nota)
    if dados is None:
        raise HTTPException(404, "Cartão não encontrado.")
    return dados


@app.get("/api/estatisticas", tags=["revisao"])
async def estatisticas() -> dict[str, Any]:
    return banco.estatisticas()


# --------------------------------------------------------------------------
# Biblioteca do estudante
# --------------------------------------------------------------------------

@app.get("/api/biblioteca", tags=["biblioteca"])
async def biblioteca_estado() -> dict[str, Any]:
    """Livros indexados, estatisticas e o catalogo aberto disponivel."""
    return {
        "livros": biblioteca.listar_livros(),
        "estatisticas": biblioteca.estatisticas(),
        "catalogo": listar_catalogo(),
        "pasta": str(biblioteca.diretorio_livros()),
        "formatos": sorted(FORMATOS),
    }


@app.post("/api/biblioteca/enviar", tags=["biblioteca"])
async def biblioteca_enviar(
    arquivos: list[UploadFile] = File(...),
    area: str = Form(default=""),
) -> dict[str, Any]:
    """Recebe livros enviados pela interface, guarda e indexa."""
    destino = biblioteca.diretorio_livros()
    limite = cfg.max_mb_por_livro * 1024 * 1024
    resultados: list[dict[str, Any]] = []

    for enviado in arquivos:
        nome = Path(enviado.filename or "livro").name
        if Path(nome).suffix.lower() not in FORMATOS:
            resultados.append({
                "arquivo": nome, "estado": "erro",
                "detalhe": f"formato não suportado (aceitos: {', '.join(sorted(FORMATOS))})",
            })
            continue

        caminho = destino / nome
        tamanho = 0
        try:
            with open(caminho, "wb") as saida:
                while bloco := await enviado.read(1 << 20):
                    tamanho += len(bloco)
                    if tamanho > limite:
                        raise ValueError("arquivo maior que o limite")
                    saida.write(bloco)
        except ValueError:
            caminho.unlink(missing_ok=True)
            resultados.append({
                "arquivo": nome, "estado": "erro",
                "detalhe": f"o arquivo passa de {cfg.max_mb_por_livro} MB",
            })
            continue
        except OSError as exc:
            resultados.append({"arquivo": nome, "estado": "erro",
                               "detalhe": f"falha ao gravar: {exc.strerror}"})
            continue

        resultado = biblioteca.indexar(caminho, area=area)
        if resultado.estado == "erro":
            caminho.unlink(missing_ok=True)
        resultados.append(resultado.para_dict())

    return {"resultados": resultados, "estatisticas": biblioteca.estatisticas()}


@app.post("/api/biblioteca/indexar", tags=["biblioteca"])
async def biblioteca_indexar(pedido: PedidoIndexarPasta) -> dict[str, Any]:
    """Varre a pasta biblioteca/ e indexa o que ainda nao esta no indice."""
    resultados = biblioteca.indexar_pasta(area=pedido.area)
    return {
        "resultados": [r.para_dict() for r in resultados],
        "estatisticas": biblioteca.estatisticas(),
    }


@app.post("/api/biblioteca/catalogo", tags=["biblioteca"])
async def biblioteca_catalogo(pedido: PedidoCatalogo) -> dict[str, Any]:
    """Baixa e indexa livros didaticos abertos (Wikilivros e Project Gutenberg)."""
    resultados = await baixar_catalogo(area=pedido.area, chaves=pedido.chaves or None)
    return {
        "resultados": [r.para_dict() for r in resultados],
        "estatisticas": biblioteca.estatisticas(),
    }


@app.get("/api/biblioteca/trecho/{trecho_id}", tags=["biblioteca"])
async def biblioteca_trecho(trecho_id: int) -> dict[str, Any]:
    """Devolve um trecho do livro junto com os vizinhos, para ler em contexto."""
    texto = biblioteca.contexto_do_trecho(trecho_id, janela=1)
    if not texto:
        raise HTTPException(404, "Trecho não encontrado.")
    return {"trecho_id": trecho_id, "texto": texto}


@app.delete("/api/biblioteca/{livro_id}", tags=["biblioteca"])
async def biblioteca_remover(livro_id: int) -> dict[str, str]:
    if not biblioteca.remover_livro(livro_id):
        raise HTTPException(404, "Livro não encontrado.")
    return {"status": "removido"}


# --------------------------------------------------------------------------
# Motor matemático
# --------------------------------------------------------------------------

@app.get("/api/matematica/topicos", tags=["matemática"])
async def matematica_topicos() -> dict[str, Any]:
    """Assuntos que o motor reconhece e o que ele sabe gerar."""
    return {
        "topicos": [
            {
                "chave": t.chave,
                "nome": t.nome,
                "estrategias": list(t.estrategias),
                "verificacoes": list(t.verificacoes),
                "gera_questao": t.chave in GERADORES,
            }
            for t in TOPICOS
        ],
        "niveis": {str(k): {"nome": v[0], "descricao": v[1]} for k, v in NIVEIS.items()},
    }


@app.post("/api/matematica/diagnostico", tags=["matemática"])
async def matematica_diagnostico(pedido: PedidoMatematica) -> dict[str, Any]:
    """Só o diagnóstico: assunto, dificuldade e o que a álgebra já consegue ver.

    É barato e não chama o modelo, então a interface pode mostrar o rumo da
    resolução assim que o estudante termina de digitar.
    """
    diagnostico = classificar(pedido.enunciado)
    analise = await matematica.analisar_enunciado(
        pedido.enunciado, diagnostico.topico == "probabilidade"
    )
    return {"diagnostico": diagnostico.para_dict(), "analise": analise.para_dict()}


@app.post("/api/matematica/resolver", tags=["matemática"])
async def matematica_resolver(pedido: PedidoMatematica) -> dict[str, Any]:
    """Resolve o problema com profundidade proporcional à sua dificuldade."""
    resolucao = await resolver_problema(
        Problema(
            enunciado=pedido.enunciado,
            tentativa=pedido.tentativa,
            nivel_aluno=pedido.nivel_aluno,
        )
    )
    return resolucao.para_dict()


@app.post("/api/matematica/pista", tags=["matemática"])
async def matematica_pista(pedido: PedidoPista) -> dict[str, Any]:
    """Modo socrático: a menor ajuda capaz de destravar, sem entregar a resposta."""
    pista = await dar_pista(
        Problema(enunciado=pedido.enunciado, tentativa=pedido.tentativa),
        nivel=pedido.nivel,
    )
    return pista.para_dict()


@app.post("/api/matematica/conferir", tags=["matemática"])
async def matematica_conferir(pedido: PedidoConferencia) -> dict[str, Any]:
    """Confronta a resposta do estudante com o sistema de álgebra computacional."""
    analise = await matematica.analisar_enunciado(pedido.enunciado, False)
    confronto = await matematica.confrontar_resposta(pedido.enunciado, pedido.resposta)
    checagens = list(analise.checagens) + list(confronto)
    return {
        "analise": analise.para_dict(),
        "confronto": [c.para_dict() for c in confronto],
        "veredito": (
            "confere" if checagens and all(c.passou for c in checagens)
            else "nao_confere" if any(not c.passou for c in checagens)
            else "indeterminado"
        ),
    }


@app.post("/api/matematica/criar", tags=["matemática"])
async def matematica_criar(pedido: PedidoQuestao) -> dict[str, Any]:
    """Cria uma questão objetiva no padrão ITA/IME, com o gabarito conferido."""
    questao = await criar_questao(
        topico=pedido.topico,
        dificuldade=pedido.dificuldade,
        contexto=pedido.contexto,
        semente=pedido.semente,
    )
    return questao.para_dict()


# --------------------------------------------------------------------------
# Interface web
# --------------------------------------------------------------------------

if cfg.diretorio_web.exists():
    app.mount(
        "/assets",
        StaticFiles(directory=cfg.diretorio_web / "assets"),
        name="assets",
    )

    @app.get("/", include_in_schema=False)
    async def raiz() -> FileResponse:
        return FileResponse(cfg.diretorio_web / "index.html")




