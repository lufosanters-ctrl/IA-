"""Schemas de entrada e saida da API."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class PedidoPesquisa(BaseModel):
    pergunta: str = Field(min_length=2, max_length=500)
    fontes: list[str] | None = None
    idioma: Literal["pt", "en"] = "pt"
    profundidade: Literal["rapida", "media", "profunda"] = "media"
    salvar: bool = True


class PedidoFlashcards(BaseModel):
    pergunta: str = Field(min_length=2, max_length=500)
    fontes: list[str] | None = None
    quantidade: int = Field(default=8, ge=1, le=20)


class PedidoQuiz(BaseModel):
    pergunta: str = Field(min_length=2, max_length=500)
    fontes: list[str] | None = None
    quantidade: int = Field(default=5, ge=1, le=15)


class PedidoPlano(BaseModel):
    tema: str = Field(min_length=2, max_length=200)
    semanas: int = Field(default=4, ge=1, le=52)
    horas_semana: int = Field(default=5, ge=1, le=60)
    nivel: Literal["iniciante", "intermediario", "avancado"] = "iniciante"
    usar_fontes: bool = True


class PedidoExplicacao(BaseModel):
    conceito: str = Field(min_length=2, max_length=300)
    nivel: Literal["iniciante", "intermediario", "avancado"] = "intermediario"
    fontes: list[str] | None = None


class PedidoBaralho(BaseModel):
    nome: str = Field(min_length=1, max_length=120)
    descricao: str = Field(default="", max_length=400)


class CartaoEntrada(BaseModel):
    frente: str = Field(min_length=1, max_length=500)
    verso: str = Field(min_length=1, max_length=2000)
    fonte_url: str = ""
    fonte_titulo: str = ""
    dificuldade: Literal["facil", "media", "dificil"] = "media"


class PedidoSalvarCartoes(BaseModel):
    cartoes: list[CartaoEntrada]


class PedidoRevisao(BaseModel):
    nota: int = Field(ge=0, le=5, description="0 = esqueci, 5 = lembrei na hora")


class PedidoCatalogo(BaseModel):
    area: str = Field(default="", max_length=40)
    chaves: list[str] = Field(default_factory=list, max_length=20)


class PedidoIndexarPasta(BaseModel):
    area: str = Field(default="", max_length=40)


class PedidoMatematica(BaseModel):
    enunciado: str = Field(min_length=3, max_length=4000)
    tentativa: str = Field(default="", max_length=4000)
    nivel_aluno: Literal["iniciante", "intermediario", "avancado"] = "intermediario"


class PedidoPista(BaseModel):
    enunciado: str = Field(min_length=3, max_length=4000)
    tentativa: str = Field(default="", max_length=4000)
    nivel: int = Field(default=1, ge=1, le=4)


class PedidoQuestao(BaseModel):
    topico: str = Field(default="", max_length=40)
    dificuldade: int = Field(default=3, ge=1, le=4)
    contexto: str = Field(default="", max_length=500)
    semente: int | None = None


class PedidoConferencia(BaseModel):
    enunciado: str = Field(min_length=3, max_length=4000)
    resposta: str = Field(min_length=1, max_length=2000)


# --- Tutoria -------------------------------------------------------------

class PedidoSessaoTutor(BaseModel):
    enunciado: str = Field(min_length=3, max_length=6000)
    materia: Literal["", "matematica", "portugues", "ingles", "geral"] = ""
    tentativa: str = Field(default="", max_length=6000)


class PedidoAjuda(BaseModel):
    pedido: str = Field(default="", max_length=400,
                        description="o que o estudante escreveu ao pedir ajuda")


class PedidoTentativa(BaseModel):
    texto: str = Field(min_length=1, max_length=6000)


class PedidoAnaliseGramatical(BaseModel):
    frase: str = Field(min_length=2, max_length=2000)


class PedidoRegencia(BaseModel):
    verbo: str = Field(min_length=2, max_length=40)


class PedidoIngles(BaseModel):
    texto: str = Field(min_length=2, max_length=2000)


class RespostaSaude(BaseModel):
    nome: str
    versao: str
    modelo_disponivel: bool
    modelo: str
    fontes: list[dict[str, Any]]
    cache: dict[str, int]
