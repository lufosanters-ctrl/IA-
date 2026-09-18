"""API HTTP da plataforma Nucleo.

Sobe com:  python -m app         ou       uvicorn app.main:app --reload
"""

from __future__ import annotations

import asyncio
import json
import logging
import mimetypes
from uuid import uuid4
from contextlib import asynccontextmanager
from typing import Any

from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from . import __version__, banco, biblioteca
from . import gramatica, ingles, matematica, tutor
from .afericao import aferir
from .ai import estudo, pesquisa
from .ingles.dimensoes import DIMENSOES
from .tutor import DEGRAUS, treino, tutoria, visao
from .tutor.escada import detectar_pedido, proximo_degrau
from .tutor.sessao import TIPOS_DE_ERRO
from .catalogo import baixar_catalogo, listar_catalogo
from .matematica.classificacao import NIVEIS, TOPICOS, classificar
from .matematica.criacao import GERADORES, criar as criar_questao
from .matematica.resolucao import Problema, dar_pista, resolver as resolver_problema
from .livros import FORMATOS, nome_de_arquivo_seguro
from .cache import CacheTTL
from .config import obter_config
from .schemas import (
    PedidoBaralho,
    PedidoCatalogo,
    PedidoExplicacao,
    PedidoFlashcards,
    PedidoAjuda,
    PedidoAnaliseGramatical,
    PedidoConferencia,
    PedidoIndexarPasta,
    PedidoIngles,
    PedidoMatematica,
    PedidoPista,
    PedidoPesquisa,
    PedidoPlano,
    PedidoQuestao,
    PedidoQuiz,
    PedidoRegencia,
    PedidoRevisao,
    PedidoSalvarCartoes,
    PedidoSessaoTutor,
    PedidoTentativa,
    PedidoTreino,
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
    tutor.iniciar_banco_tutor()
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
    identificador, criado = banco.criar_baralho(
        pedido.nome.strip(), pedido.descricao.strip()
    )
    return {
        "id": identificador,
        "nome": pedido.nome.strip(),
        "criado": criado,
        # Nome repetido reaproveita o baralho existente e mantem a descricao
        # antiga. Dizer isso evita que o estudante ache que perdeu o envio.
        "aviso": "" if criado else "Já existia um baralho com esse nome; ele foi reaproveitado.",
    }


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
    try:
        inseridos = banco.salvar_cartoes(
            baralho_id, [c.model_dump() for c in pedido.cartoes]
        )
    except banco.BaralhoInexistente as erro:
        raise HTTPException(404, "Baralho não encontrado.") from erro
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


def _nome_livre(pasta: Path, nome: str) -> Path:
    """Caminho que nao sobrescreve nenhum livro ja guardado."""
    alvo = pasta / nome
    if not alvo.exists():
        return alvo
    base, sufixo = Path(nome).stem, Path(nome).suffix
    for n in range(2, 1000):
        candidato = pasta / f"{base} ({n}){sufixo}"
        if not candidato.exists():
            return candidato
    return pasta / f"{base}-{uuid4().hex[:8]}{sufixo}"


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
        # Nome enviado pelo navegador: precisa passar pelas regras do sistema
        # de arquivos antes de virar caminho. "CON.pdf" e "prova:2024.pdf" são
        # aceitos no Linux e recusados no Windows.
        nome = nome_de_arquivo_seguro(enviado.filename or "livro")
        if Path(nome).suffix.lower() not in FORMATOS:
            resultados.append({
                "arquivo": nome, "estado": "erro",
                "detalhe": f"formato não suportado (aceitos: {', '.join(sorted(FORMATOS))})",
            })
            continue

        # Gravar em arquivo temporario e so depois renomear: escrever direto
        # sobre `destino/nome` truncava um livro ja indexado, e o `unlink` do
        # caminho de erro apagava o original do estudante.
        # Nome único por requisição. Com o nome do livro, dois envios do mesmo
        # arquivo — duas abas, ou reenvio antes de terminar — usariam o mesmo
        # caminho, e o laço é assíncrono: o `await` de leitura cede o controle
        # e as duas requisições se intercalam de verdade. No Windows, arquivo
        # aberto por outro processo não pode ser renomeado nem apagado, então
        # a colisão vira "Acesso negado" e deixa um .parcial órfão na pasta.
        temporario = destino / f".{uuid4().hex}.parcial"
        tamanho = 0
        try:
            with open(temporario, "wb") as saida:
                while bloco := await enviado.read(1 << 20):
                    tamanho += len(bloco)
                    if tamanho > limite:
                        raise ValueError("arquivo maior que o limite")
                    saida.write(bloco)
        except ValueError:
            temporario.unlink(missing_ok=True)
            resultados.append({
                "arquivo": nome, "estado": "erro",
                "detalhe": f"o arquivo passa de {cfg.max_mb_por_livro} MB",
            })
            continue
        except OSError as exc:
            temporario.unlink(missing_ok=True)
            resultados.append({"arquivo": nome, "estado": "erro",
                               "detalhe": f"falha ao gravar: {exc.strerror}"})
            continue

        caminho = _nome_livre(destino, nome)
        try:
            temporario.replace(caminho)
        except OSError as exc:
            temporario.unlink(missing_ok=True)
            resultados.append({"arquivo": nome, "estado": "erro",
                               "detalhe": f"falha ao gravar: {exc.strerror}"})
            continue

        # Extracao e indexacao sao CPU pura e sincronas: rodando no event loop,
        # um PDF grande congela a API inteira para todo mundo.
        resultado = await asyncio.to_thread(biblioteca.indexar, caminho, area=area)
        if resultado.estado == "erro":
            caminho.unlink(missing_ok=True)
        resultados.append(resultado.para_dict())

    return {"resultados": resultados, "estatisticas": biblioteca.estatisticas()}


@app.post("/api/biblioteca/indexar", tags=["biblioteca"])
async def biblioteca_indexar(pedido: PedidoIndexarPasta) -> dict[str, Any]:
    """Varre a pasta biblioteca/ e indexa o que ainda nao esta no indice."""
    resultados = await asyncio.to_thread(biblioteca.indexar_pasta, area=pedido.area)
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
        "estatisticas": await asyncio.to_thread(biblioteca.estatisticas),
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

    # O veredito é sobre a resposta DO ESTUDANTE, e quem a compara com a
    # álgebra é o confronto. Somar `analise.checagens` aqui dava "confere"
    # para qualquer coisa — inclusive "1000" e "não sei" — porque a
    # autoverificação do motor sempre passa e o confronto vinha vazio.
    if not confronto:
        veredito = "indeterminado"
        motivo = (
            "Não consegui confrontar a sua resposta com a álgebra. Isso "
            "acontece quando o enunciado não traz equação legível, quando a "
            "pergunta não é pelas raízes, ou quando a sua resposta não traz "
            "valores numéricos para comparar."
        )
    elif all(c.passou for c in confronto):
        veredito = "confere"
        motivo = "Os valores da sua resposta batem com os que a álgebra obteve."
    else:
        veredito = "nao_confere"
        motivo = "Há divergência entre a sua resposta e o resultado simbólico."

    # Uma condição do enunciado que a leitura não aplicou torna o próprio
    # resultado do motor pouco confiável: dizer "não confere" nesse caso pode
    # estar acusando uma resposta certa.
    if analise.ressalvas and veredito == "nao_confere":
        veredito = "indeterminado"
        motivo = (
            "A sua resposta diverge do que a álgebra leu, mas a leitura está "
            "incompleta: " + "; ".join(analise.ressalvas) + ". Sem aplicar "
            "essa condição, não dá para dizer quem está certo."
        )

    return {
        "analise": analise.para_dict(),
        "confronto": [c.para_dict() for c in confronto],
        "veredito": veredito,
        "motivo": motivo,
        "ressalvas": list(analise.ressalvas),
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
# Tutoria: escada de ajuda, diagnóstico e padrões de erro
# --------------------------------------------------------------------------

@app.get("/api/tutor/escada", tags=["tutoria"])
async def tutor_escada() -> dict[str, Any]:
    """Os degraus da escada de ajuda, do mais leve ao mais completo."""
    return {
        "degraus": [d.para_dict() for d in DEGRAUS],
        "tipos_de_erro": TIPOS_DE_ERRO,
    }


@app.post("/api/tutor/sessao", tags=["tutoria"])
async def tutor_abrir_sessao(pedido: PedidoSessaoTutor) -> dict[str, Any]:
    """Abre uma sessão de estudo e entrega o primeiro degrau da escada."""
    contexto = await tutoria.apurar(pedido.enunciado, pedido.materia)
    sessao = tutor.abrir_sessao(
        materia=contexto.materia,
        enunciado=pedido.enunciado,
        topico=contexto.topico,
        dificuldade=contexto.dificuldade,
    )
    resposta = await tutoria.orientar(
        pedido.enunciado, sessao.nivel_atual, contexto.materia,
        pedido.tentativa, contexto,
    )
    return {"sessao": sessao.para_dict(), "ajuda": resposta.para_dict()}


@app.get("/api/tutor/sessao/{sessao_id}", tags=["tutoria"])
async def tutor_obter_sessao(sessao_id: int) -> dict[str, Any]:
    sessao = tutor.obter_sessao(sessao_id)
    if sessao is None:
        raise HTTPException(404, "Sessão não encontrada.")
    return sessao.para_dict()


@app.post("/api/tutor/sessao/{sessao_id}/ajuda", tags=["tutoria"])
async def tutor_mais_ajuda(sessao_id: int, pedido: PedidoAjuda) -> dict[str, Any]:
    """Sobe um degrau da escada — ou vai direto ao fim, se o estudante pedir."""
    sessao = tutor.obter_sessao(sessao_id)
    if sessao is None:
        raise HTTPException(404, "Sessão não encontrada.")

    intencao = detectar_pedido(pedido.pedido)
    ultima = sessao.tentativas[-1] if sessao.tentativas else None
    novo_nivel = proximo_degrau(
        sessao.nivel_atual,
        acertou_algo=bool(ultima and ultima.veredito == "parcial"),
        pediu_resolucao=intencao == "resolucao",
        pediu_autonomia=intencao == "autonomia",
    )
    tutor.subir_degrau(sessao_id, novo_nivel)

    tentativa = ultima.texto if ultima else ""
    resposta = await tutoria.orientar(
        sessao.enunciado, novo_nivel, sessao.materia, tentativa
    )
    return {"ajuda": resposta.para_dict(), "nivel": novo_nivel, "pedido": intencao}


@app.post("/api/tutor/sessao/{sessao_id}/tentativa", tags=["tutoria"])
async def tutor_tentativa(sessao_id: int, pedido: PedidoTentativa) -> dict[str, Any]:
    """Diagnostica a tentativa: aponta o PRIMEIRO erro, não todos."""
    sessao = tutor.obter_sessao(sessao_id)
    if sessao is None:
        raise HTTPException(404, "Sessão não encontrada.")

    contexto = await tutoria.apurar(sessao.enunciado, sessao.materia)
    diagnostico = await tutoria.avaliar_tentativa(
        sessao.enunciado, pedido.texto, sessao.materia, contexto
    )
    tutor.registrar_tentativa(
        sessao_id, pedido.texto, diagnostico.veredito,
        diagnostico.primeiro_erro, diagnostico.tipo_erro, sessao.nivel_atual,
    )

    # Quem está quase lá precisa de MENOS ajuda, não de mais.
    novo_nivel = proximo_degrau(
        sessao.nivel_atual,
        acertou_algo=diagnostico.quase_la or diagnostico.veredito == "parcial",
    )
    if diagnostico.veredito != "correto":
        tutor.subir_degrau(sessao_id, novo_nivel)

    saida: dict[str, Any] = {
        "diagnostico": diagnostico.para_dict(),
        "nivel": novo_nivel if diagnostico.veredito != "correto" else sessao.nivel_atual,
    }
    if diagnostico.veredito == "correto":
        saida["generalizacao"] = await tutoria.generalizar(
            sessao.enunciado, sessao.materia
        )
    return saida


@app.post("/api/tutor/treino", tags=["tutoria"])
async def tutor_treino(pedido: PedidoTreino) -> dict[str, Any]:
    """Monta um treino dirigido ao erro que mais se repete.

    Dizer “cuidado com o sinal” não corrige ninguém. Praticar exatamente o
    ponto em que se erra, sim — e é isso que este endpoint monta, a partir do
    histórico acumulado nas sessões.
    """
    montado = await asyncio.to_thread(
        treino.montar_treino,
        pedido.materia, pedido.tipo_erro, pedido.quantidade, pedido.semente,
    )
    return montado.para_dict(com_gabarito=pedido.com_gabarito)


@app.get("/api/tutor/sessoes", tags=["tutoria"])
async def tutor_sessoes(limite: int = Query(default=20, ge=1, le=100)) -> list[dict[str, Any]]:
    return tutor.listar_sessoes(limite)


@app.get("/api/tutor/padroes", tags=["tutoria"])
async def tutor_padroes(minimo: int = Query(default=2, ge=1, le=20)) -> dict[str, Any]:
    """Erros que se repetem, com a estratégia preventiva de cada um."""
    return tutor.padroes_de_erro(minimo)


@app.post("/api/tutor/imagem", tags=["tutoria"])
async def tutor_imagem(arquivo: UploadFile = File(...)) -> dict[str, Any]:
    """Lê uma questão fotografada e devolve a transcrição para confirmação."""
    # Ler em blocos e abortar no estouro: `await arquivo.read()` sem limite
    # materializava o upload inteiro na memoria ANTES de conferir o tamanho,
    # e um multipart de alguns GB derrubava o processo.
    limite = visao.LIMITE_BYTES
    partes: list[bytes] = []
    total = 0
    while bloco := await arquivo.read(1 << 20):
        total += len(bloco)
        if total > limite:
            raise HTTPException(
                413, f"imagem maior que {limite // (1024 * 1024)} MB"
            )
        partes.append(bloco)
    conteudo = b"".join(partes)
    try:
        leitura = await visao.ler_imagem(conteudo)
    except visao.ErroLeitura as exc:
        raise HTTPException(422, str(exc)) from exc
    return {
        "leitura": leitura.para_dict(),
        "confirmacao": visao.texto_de_confirmacao(leitura),
    }


# --------------------------------------------------------------------------
# Gramática da língua portuguesa
# --------------------------------------------------------------------------

@app.post("/api/gramatica/analisar", tags=["gramática"])
async def gramatica_analisar(pedido: PedidoAnaliseGramatical) -> dict[str, Any]:
    """Passa a frase pelos motores de crase, regência, colocação e concordância."""
    return gramatica.analisar_frase(pedido.frase).para_dict()


@app.post("/api/gramatica/regencia", tags=["gramática"])
async def gramatica_regencia(pedido: PedidoRegencia) -> dict[str, Any]:
    """Todos os sentidos de um verbo, cada um com a sua regência."""
    sentidos = gramatica.consultar_verbo(pedido.verbo)
    if not sentidos:
        raise HTTPException(
            404,
            f"“{pedido.verbo}” não está no dicionário de regências cobradas em prova."
        )
    return {
        "verbo": pedido.verbo.lower(),
        "sentidos": [s.para_dict() for s in sentidos],
        "muda_com_o_sentido": len(sentidos) > 1,
    }


@app.get("/api/gramatica/verbos", tags=["gramática"])
async def gramatica_verbos() -> dict[str, Any]:
    """Lista os verbos e nomes catalogados."""
    return {
        "verbos": sorted(v for v, s in gramatica.REGENCIA_VERBAL.items() if s),
        "nomes": sorted(gramatica.REGENCIA_NOMINAL),
    }


# --------------------------------------------------------------------------
# Gramática da língua inglesa
# --------------------------------------------------------------------------

@app.post("/api/ingles/avaliar", tags=["inglês"])
async def ingles_avaliar(pedido: PedidoIngles) -> dict[str, Any]:
    """Avalia a construção nas cinco dimensões e aponta erros de transferência."""
    return {
        "dimensoes": [
            {"chave": c, "nome": n, "pergunta": p} for c, n, p in DIMENSOES
        ],
        "avaliacoes": [a.para_dict() for a in ingles.avaliar_estrutura(pedido.texto)],
        "contrastes": [
            c.para_dict() for c in ingles.contrastes_relevantes(pedido.texto)
        ],
    }


@app.get("/api/ingles/contrastes", tags=["inglês"])
async def ingles_contrastes(lingua: str = Query(default="")) -> list[dict[str, Any]]:
    """Pares que se confundem, com o critério que decide entre eles."""
    return [
        c.para_dict() for c in ingles.CONTRASTES
        if not lingua or c.lingua == lingua
    ]


# Os casos de referencia sao deterministicos: o resultado so muda quando o
# codigo muda. Sem cache, cada chamada gastava meio segundo de CPU rodando
# sympy de novo para dar exatamente a mesma resposta.
_cache_afericao = CacheTTL(ttl_segundos=300, max_itens=16)


def _afericao_em_cache(area: str) -> dict[str, Any]:
    guardado = _cache_afericao.obter(f"afericao:{area}")
    if guardado is not None:
        return guardado
    dados = aferir(area).para_dict()
    _cache_afericao.guardar(f"afericao:{area}", dados)
    return dados


@app.get("/api/afericao", tags=["sistema"])
async def afericao_do_sistema(area: str = Query(default="")) -> dict[str, Any]:
    """Roda os casos de referência e devolve a taxa de acerto por área.

    É a resposta à pergunta que nenhum teste de unidade responde: os motores
    estão acertando? Os casos têm gabarito conhecido, tirados das regras
    consagradas e do tipo de questão que cai em prova.
    """
    return await asyncio.to_thread(_afericao_em_cache, area)


# --------------------------------------------------------------------------
# Interface web
# --------------------------------------------------------------------------

# O Starlette resolve o Content-Type por `mimetypes.guess_type`. No Windows,
# `mimetypes.init()` lê o registro (HKEY_CLASSES_ROOT) e SOBRESCREVE o mapa
# embutido, e é comum um instalador de terceiro ter deixado ".css" como
# "text/plain". Em modo padrão — que é o nosso, a página declara DOCTYPE — o
# navegador recusa folha de estilo que não venha como "text/css": a interface
# abriria inteira sem estilo, sem erro nenhum no servidor.
for _tipo, _extensao in (
    ("text/css", ".css"),
    ("text/javascript", ".js"),
    ("application/javascript", ".mjs"),
    ("image/svg+xml", ".svg"),
    ("application/json", ".json"),
    ("font/woff2", ".woff2"),
    ("text/html", ".html"),
):
    mimetypes.add_type(_tipo, _extensao)


if cfg.diretorio_web.exists():
    app.mount(
        "/assets",
        StaticFiles(directory=cfg.diretorio_web / "assets"),
        name="assets",
    )

    @app.get("/", include_in_schema=False)
    async def raiz() -> FileResponse:
        return FileResponse(cfg.diretorio_web / "index.html")








