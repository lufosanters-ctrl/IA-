"""Leitura de questao fotografada, com confirmacao antes de resolver.

A tentacao e olhar a foto e ja resolver. O problema e que erro de LEITURA
produz resolucao perfeita da questao errada — e o estudante nao tem como
perceber, porque a conta fecha.

Por isso o fluxo aqui e:

    IMAGEM → LEITURA → CONFIRMACAO → INTERPRETACAO → RESOLUCAO

A etapa de confirmacao devolve ao estudante exatamente o que foi lido:
enunciado, alternativas, anotacoes manuscritas e os trechos que ficaram
ambiguos. So depois de ele confirmar e que a tutoria comeca. Nada e inventado:
o que nao deu para ler e declarado como ilegivel, com a regiao indicada.
"""

from __future__ import annotations

import base64
from dataclasses import dataclass, field
from typing import Any

from ..ai.llm import ErroModelo, obter_motor

FORMATOS_ACEITOS = {"jpeg", "jpg", "png", "webp", "gif"}
MIME = {"jpeg": "image/jpeg", "jpg": "image/jpeg", "png": "image/png",
        "webp": "image/webp", "gif": "image/gif"}
LIMITE_BYTES = 8 * 1024 * 1024

SISTEMA_LEITURA = """Voce le questoes fotografadas. NESTA ETAPA VOCE NAO RESOLVE NADA.

Sua unica tarefa e transcrever fielmente o que esta na imagem, separando o que e enunciado do que e anotacao do estudante.

Cuidados obrigatorios:
- Leia o enunciado INTEIRO, inclusive o que ficou no rodape ou na margem.
- Copie sinais, expoentes, indices e fracoes com exatidao. Um expoente lido errado muda a questao inteira.
- Se ha mais de uma questao na foto, transcreva todas, numeradas.
- Distinga o texto impresso da anotacao manuscrita. Rabisco a lapis do estudante NAO e parte do enunciado.
- Transcreva TODAS as alternativas, na ordem, com suas letras.
- O que estiver realmente ilegivel entra em "ilegivel" com a descricao de onde fica. Nao adivinhe, e tambem nao declare ilegivel aquilo que da para ler com atencao.

Responda em JSON:
{"questoes": [{"numero": str, "enunciado": str,
               "alternativas": [{"letra": str, "texto": str}],
               "materia_provavel": str}],
 "anotacoes_do_estudante": str,
 "alternativa_marcada": str,
 "ilegivel": [str],
 "observacoes": str}

Em "alternativa_marcada", a letra que o estudante circulou ou marcou, se houver; senao, string vazia.
Em "anotacoes_do_estudante", a transcricao do que ele escreveu a mao, que pode conter a tentativa de resolucao."""


class ErroLeitura(RuntimeError):
    """A imagem nao pode ser lida."""


@dataclass(slots=True)
class QuestaoLida:
    """Uma questão transcrita da foto."""

    numero: str = ""
    enunciado: str = ""
    alternativas: list[dict[str, str]] = field(default_factory=list)
    materia_provavel: str = ""

    def para_dict(self) -> dict[str, Any]:
        return {
            "numero": self.numero, "enunciado": self.enunciado,
            "alternativas": self.alternativas,
            "materia_provavel": self.materia_provavel,
        }


@dataclass(slots=True)
class Leitura:
    """O que foi lido da imagem, para o estudante confirmar."""

    questoes: list[QuestaoLida] = field(default_factory=list)
    anotacoes_do_estudante: str = ""
    alternativa_marcada: str = ""
    ilegivel: list[str] = field(default_factory=list)
    observacoes: str = ""
    modo: str = "neural"

    @property
    def confiavel(self) -> bool:
        return bool(self.questoes) and not self.ilegivel

    def para_dict(self) -> dict[str, Any]:
        return {
            "questoes": [q.para_dict() for q in self.questoes],
            "anotacoes_do_estudante": self.anotacoes_do_estudante,
            "alternativa_marcada": self.alternativa_marcada,
            "ilegivel": self.ilegivel,
            "observacoes": self.observacoes,
            "confiavel": self.confiavel,
            "modo": self.modo,
        }


def detectar_tipo(conteudo: bytes) -> str:
    """Identifica o formato pela assinatura do arquivo.

    A biblioteca `imghdr` da padrão foi removida no Python 3.13, e confiar na
    extensão do nome enviado seria confiar no cliente. As assinaturas abaixo
    são as dos formatos que o modelo de visão aceita.
    """
    if conteudo[:3] == b"\xff\xd8\xff":
        return "jpeg"
    if conteudo[:8] == b"\x89PNG\r\n\x1a\n":
        return "png"
    if conteudo[:4] == b"RIFF" and conteudo[8:12] == b"WEBP":
        return "webp"
    if conteudo[:6] in (b"GIF87a", b"GIF89a"):
        return "gif"
    return ""


def validar_imagem(conteudo: bytes) -> str:
    """Confere formato e tamanho; devolve o tipo detectado."""
    if not conteudo:
        raise ErroLeitura("arquivo vazio")
    if len(conteudo) > LIMITE_BYTES:
        raise ErroLeitura(
            f"imagem maior que {LIMITE_BYTES // (1024 * 1024)} MB"
        )
    tipo = detectar_tipo(conteudo)
    if tipo not in FORMATOS_ACEITOS:
        raise ErroLeitura(
            "formato não aceito. Envie JPEG, PNG, WebP ou GIF."
        )
    return tipo


async def ler_imagem(conteudo: bytes) -> Leitura:
    """Transcreve a questão da foto, sem resolver."""
    tipo = validar_imagem(conteudo)
    motor = obter_motor()
    if not motor.disponivel:
        raise ErroLeitura(
            "A leitura de imagem depende do modelo de visão. Configure "
            "`ANTHROPIC_API_KEY` ou digite o enunciado à mão."
        )

    dados = base64.standard_b64encode(conteudo).decode("ascii")
    conteudo_mensagem = [
        {
            "type": "image",
            "source": {"type": "base64", "media_type": MIME[tipo], "data": dados},
        },
        {
            "type": "text",
            "text": "Transcreva esta questão seguindo exatamente as regras do sistema.",
        },
    ]

    try:
        bruto = await motor.responder_multimodal(
            SISTEMA_LEITURA, conteudo_mensagem, max_tokens=2500
        )
    except ErroModelo as exc:
        raise ErroLeitura(f"falha ao ler a imagem: {exc}") from exc

    from ..ai.llm import extrair_json

    try:
        estrutura = extrair_json(bruto)
    except ErroModelo as exc:
        raise ErroLeitura("o modelo não devolveu a transcrição em formato legível") from exc

    if not isinstance(estrutura, dict):
        raise ErroLeitura("transcrição em formato inesperado")

    questoes = []
    for item in estrutura.get("questoes", []) or []:
        if not isinstance(item, dict):
            continue
        alternativas = [
            {"letra": str(a.get("letra", "")), "texto": str(a.get("texto", ""))}
            for a in (item.get("alternativas") or []) if isinstance(a, dict)
        ]
        questoes.append(QuestaoLida(
            numero=str(item.get("numero", "")),
            enunciado=str(item.get("enunciado", "")).strip(),
            alternativas=alternativas,
            materia_provavel=str(item.get("materia_provavel", "")),
        ))

    if not questoes:
        raise ErroLeitura(
            "não identifiquei nenhuma questão nesta imagem. Verifique o "
            "enquadramento e a nitidez."
        )

    return Leitura(
        questoes=questoes,
        anotacoes_do_estudante=str(estrutura.get("anotacoes_do_estudante", "")).strip(),
        alternativa_marcada=str(estrutura.get("alternativa_marcada", "")).strip(),
        ilegivel=[str(i) for i in (estrutura.get("ilegivel") or [])],
        observacoes=str(estrutura.get("observacoes", "")).strip(),
    )


def texto_de_confirmacao(leitura: Leitura) -> str:
    """Mensagem que mostra ao estudante o que foi lido, antes de resolver."""
    linhas = ["**Confirme se li corretamente antes de continuarmos.**", ""]
    for questao in leitura.questoes:
        titulo = f"Questão {questao.numero}" if questao.numero else "Questão"
        linhas.append(f"**{titulo}**")
        linhas.append(questao.enunciado)
        for alternativa in questao.alternativas:
            linhas.append(f"- **{alternativa['letra']})** {alternativa['texto']}")
        linhas.append("")

    if leitura.anotacoes_do_estudante:
        linhas += ["**O que você escreveu à mão:**",
                   leitura.anotacoes_do_estudante, ""]
    if leitura.alternativa_marcada:
        linhas.append(f"Você marcou a alternativa **{leitura.alternativa_marcada}**.")
        linhas.append("")
    if leitura.ilegivel:
        linhas.append("**Não consegui ler com segurança:**")
        linhas += [f"- {trecho}" for trecho in leitura.ilegivel]
        linhas.append("")
        linhas.append("Digite essas partes para eu não trabalhar em cima de um palpite.")
    else:
        linhas.append("Se a transcrição estiver certa, seguimos daqui.")
    return "\n".join(linhas)
