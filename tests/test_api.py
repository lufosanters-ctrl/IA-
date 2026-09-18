"""Testes dos endpoints HTTP."""

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def cliente():
    with TestClient(app) as teste:
        yield teste


def test_saude_descreve_a_plataforma(cliente):
    dados = cliente.get("/api/saude").json()
    assert dados["versao"]
    assert len(dados["fontes"]) == 9
    assert dados["modo"] in {"neural", "extrativo"}


def test_listagem_de_fontes(cliente):
    fontes = cliente.get("/api/fontes").json()
    identificadores = {f["id"] for f in fontes}
    assert {"wikipedia", "arxiv", "openalex", "pubmed"} <= identificadores
    assert all(f["nome"] and f["descricao"] for f in fontes)


def test_pesquisa_salva_no_historico(cliente):
    resposta = cliente.post("/api/pesquisar", json={
        "pergunta": "mecanismo de atencao", "fontes": ["wikipedia"],
    })
    assert resposta.status_code == 200
    dados = resposta.json()
    assert dados["resposta"] and dados["citacoes"]
    assert "id" in dados

    historico = cliente.get("/api/historico").json()
    assert any(item["id"] == dados["id"] for item in historico)

    item = cliente.get(f"/api/historico/{dados['id']}").json()
    assert item["pergunta"] == "mecanismo de atencao"

    assert cliente.delete(f"/api/historico/{dados['id']}").status_code == 200
    assert cliente.get(f"/api/historico/{dados['id']}").status_code == 404


def test_pesquisa_sem_salvar(cliente):
    dados = cliente.post("/api/pesquisar", json={
        "pergunta": "atencao", "fontes": ["wikipedia"], "salvar": False,
    }).json()
    assert "id" not in dados


def test_pergunta_vazia_e_rejeitada(cliente):
    assert cliente.post("/api/pesquisar", json={"pergunta": ""}).status_code == 422


def test_profundidade_invalida_e_rejeitada(cliente):
    resposta = cliente.post("/api/pesquisar", json={
        "pergunta": "teste valido", "profundidade": "turbo",
    })
    assert resposta.status_code == 422


def test_fluxo_sse_entrega_eventos(cliente):
    with cliente.stream(
        "GET", "/api/pesquisar/fluxo",
        params={"pergunta": "atencao", "fontes": "wikipedia", "salvar": "false"},
    ) as resposta:
        assert resposta.status_code == 200
        corpo = "".join(resposta.iter_text())
    assert '"tipo": "etapa"' in corpo
    assert '"tipo": "citacoes"' in corpo
    assert '"tipo": "fim"' in corpo


def test_flashcards_e_quiz(cliente):
    flashcards = cliente.post("/api/flashcards", json={
        "pergunta": "mecanismo de atencao", "fontes": ["wikipedia"], "quantidade": 4,
    }).json()
    assert flashcards["cartoes"]
    assert all("fonte_url" in c for c in flashcards["cartoes"])

    quiz = cliente.post("/api/quiz", json={
        "pergunta": "mecanismo de atencao", "fontes": ["wikipedia", "arxiv"],
        "quantidade": 3,
    }).json()
    assert isinstance(quiz["questoes"], list)
    assert quiz["citacoes"]


def test_plano_de_estudo(cliente):
    plano = cliente.post("/api/plano", json={
        "tema": "mecanismo de atencao", "semanas": 2, "horas_semana": 4,
    }).json()
    assert plano["sessoes"]
    assert plano["titulo"]


def test_explicacao_por_nivel(cliente):
    dados = cliente.post("/api/explicar", json={
        "conceito": "mecanismo de atencao", "nivel": "iniciante", "fontes": ["wikipedia"],
    }).json()
    assert dados["texto"]
    assert dados["nivel"] == "iniciante"


def test_ciclo_completo_de_revisao(cliente):
    baralho = cliente.post("/api/baralhos", json={"nome": "Neurociencia"}).json()

    salvos = cliente.post(f"/api/baralhos/{baralho['id']}/cartoes", json={
        "cartoes": [
            {"frente": "O que e sinapse?", "verso": "conexao entre neuronios"},
            {"frente": "O que e axonio?", "verso": "prolongamento do neuronio"},
        ]
    }).json()
    assert salvos["inseridos"] == 2

    devidos = cliente.get(f"/api/revisao?baralho_id={baralho['id']}").json()
    assert len(devidos) == 2

    revisado = cliente.post(f"/api/revisao/{devidos[0]['id']}", json={"nota": 5}).json()
    assert revisado["intervalo"] >= 1

    estatisticas = cliente.get("/api/estatisticas").json()
    assert estatisticas["total_cartoes"] == 2
    assert estatisticas["taxa_acerto"] == 100.0

    assert cliente.delete(f"/api/baralhos/{baralho['id']}").status_code == 200


def test_nota_fora_da_escala_e_rejeitada(cliente):
    baralho = cliente.post("/api/baralhos", json={"nome": "Escala"}).json()
    cliente.post(f"/api/baralhos/{baralho['id']}/cartoes", json={
        "cartoes": [{"frente": "a", "verso": "b"}]
    })
    devidos = cliente.get(f"/api/revisao?baralho_id={baralho['id']}").json()
    resposta = cliente.post(f"/api/revisao/{devidos[0]['id']}", json={"nota": 9})
    assert resposta.status_code == 422


def test_recursos_inexistentes_devolvem_404(cliente):
    assert cliente.get("/api/historico/99999").status_code == 404
    assert cliente.delete("/api/baralhos/99999").status_code == 404
    assert cliente.post("/api/revisao/99999", json={"nota": 4}).status_code == 404


def test_interface_web_e_servida(cliente):
    pagina = cliente.get("/")
    assert pagina.status_code == 200
    assert "Núcleo" in pagina.text
    for arquivo in ("estilo.css", "app.js", "api.js", "markdown.js"):
        assert cliente.get(f"/assets/{arquivo}").status_code == 200


# --------------------------------------------------------------------------
# Biblioteca
# --------------------------------------------------------------------------

LIVRO_ENVIADO = ("""# Apostila de Física

## Capítulo 1 — Cinemática

O movimento retilíneo uniforme ocorre quando a velocidade de um corpo permanece
constante ao longo do tempo, de modo que o deslocamento é proporcional ao
intervalo decorrido. A aceleração, nesse caso, é nula em qualquer instante.

O movimento uniformemente variado tem aceleração constante e diferente de zero,
o que produz uma relação quadrática entre posição e tempo, descrita pela função
horária do deslocamento.
""").encode("utf-8")


def test_estado_da_biblioteca(cliente):
    dados = cliente.get("/api/biblioteca").json()
    assert dados["estatisticas"]["livros"] >= 1
    assert dados["catalogo"]
    assert ".pdf" in dados["formatos"]


def test_enviar_livro_pela_interface(cliente):
    resposta = cliente.post(
        "/api/biblioteca/enviar",
        files=[("arquivos", ("fisica.md", LIVRO_ENVIADO, "text/markdown"))],
        data={"area": "fisica"},
    )
    assert resposta.status_code == 200
    dados = resposta.json()
    assert dados["resultados"][0]["estado"] == "indexado"
    assert dados["estatisticas"]["livros"] >= 2

    # O livro enviado passa a aparecer na pesquisa.
    pesquisa = cliente.post("/api/pesquisar", json={
        "pergunta": "movimento uniformemente variado", "fontes": ["biblioteca"],
    }).json()
    assert any(c["fonte"] == "biblioteca" for c in pesquisa["citacoes"])


def test_enviar_formato_nao_suportado(cliente):
    resposta = cliente.post(
        "/api/biblioteca/enviar",
        files=[("arquivos", ("planilha.xlsx", b"binario", "application/vnd.ms-excel"))],
    )
    assert resposta.status_code == 200
    assert resposta.json()["resultados"][0]["estado"] == "erro"


def test_enviar_o_mesmo_livro_duas_vezes(cliente):
    envio = {"files": [("arquivos", ("repetido.md", LIVRO_ENVIADO, "text/markdown"))]}
    cliente.post("/api/biblioteca/enviar", **envio)
    segunda = cliente.post("/api/biblioteca/enviar", **envio).json()
    assert segunda["resultados"][0]["estado"] == "duplicado"


def test_trecho_em_contexto(cliente):
    cliente.post(
        "/api/biblioteca/enviar",
        files=[("arquivos", ("fisica2.md", LIVRO_ENVIADO, "text/markdown"))],
    )
    pesquisa = cliente.post("/api/pesquisar", json={
        "pergunta": "movimento retilíneo uniforme", "fontes": ["biblioteca"],
    }).json()
    citacao = next(c for c in pesquisa["citacoes"] if c["fonte"] == "biblioteca")
    trecho_id = citacao["extra"]["trecho_id"]
    dados = cliente.get(f"/api/biblioteca/trecho/{trecho_id}").json()
    assert dados["texto"]


def test_trecho_inexistente(cliente):
    assert cliente.get("/api/biblioteca/trecho/999999").status_code == 404


def test_remover_livro_pela_api(cliente):
    livros = cliente.get("/api/biblioteca").json()["livros"]
    alvo = livros[0]["id"]
    assert cliente.delete(f"/api/biblioteca/{alvo}").status_code == 200
    assert cliente.delete(f"/api/biblioteca/{alvo}").status_code == 404


def test_baixar_do_catalogo(cliente):
    dados = cliente.post("/api/biblioteca/catalogo", json={"chaves": ["calculo"]}).json()
    assert dados["resultados"][0]["estado"] == "indexado"


def test_indexar_pasta_pela_api(cliente):
    assert cliente.post("/api/biblioteca/indexar", json={"area": ""}).status_code == 200


def test_pesquisa_expoe_intencao_e_verificacao(cliente):
    dados = cliente.post("/api/pesquisar", json={
        "pergunta": "O que é fotossíntese?", "fontes": ["biblioteca", "wikipedia"],
    }).json()
    assert dados["intencao"] == "definicao"
    assert dados["intencao_rotulo"]
    assert dados["verificacao"] is not None
    assert "cobertura" in dados["verificacao"]


# --------------------------------------------------------------------------
# Motor matemático
# --------------------------------------------------------------------------

def test_topicos_de_matematica(cliente):
    dados = cliente.get("/api/matematica/topicos").json()
    assert len(dados["topicos"]) >= 12
    assert any(t["gera_questao"] for t in dados["topicos"])
    assert all(t["estrategias"] and t["verificacoes"] for t in dados["topicos"])


def test_diagnostico_nao_chama_o_modelo(cliente):
    dados = cliente.post("/api/matematica/diagnostico", json={
        "enunciado": "Resolva a equação x^2 - 5x + 6 = 0."
    }).json()
    assert dados["diagnostico"]["dificuldade"] in {1, 2, 3, 4}
    assert dados["analise"]["equacoes"]


def test_resolver_problema(cliente):
    r = cliente.post("/api/matematica/resolver", json={
        "enunciado": "Resolva a equação x^2 - 5x + 6 = 0."
    }).json()
    assert r["verificado"] is True
    assert "## Resposta" in r["texto"]
    assert r["analise"]["solucoes"]["x"] == ["2", "3"]


def test_resolver_rejeita_enunciado_curto(cliente):
    assert cliente.post("/api/matematica/resolver", json={"enunciado": "x"}).status_code == 422


def test_pista_respeita_a_escala(cliente):
    for nivel in (1, 4):
        p = cliente.post("/api/matematica/pista", json={
            "enunciado": "Resolva a equação x^2 - 5x + 6 = 0.", "nivel": nivel,
        }).json()
        assert p["nivel"] == nivel
        assert p["texto"]
    assert cliente.post("/api/matematica/pista", json={
        "enunciado": "Resolva x^2 = 4.", "nivel": 9,
    }).status_code == 422


def test_conferir_resposta_certa_e_errada(cliente):
    certa = cliente.post("/api/matematica/conferir", json={
        "enunciado": "Resolva a equação x^2 - 5x + 6 = 0.",
        "resposta": "x = 2 e x = 3",
    }).json()
    assert certa["veredito"] == "confere"

    errada = cliente.post("/api/matematica/conferir", json={
        "enunciado": "Resolva a equação x^2 - 5x + 6 = 0.",
        "resposta": "x = 2",
    }).json()
    assert errada["veredito"] == "nao_confere"


def test_criar_questao_com_gabarito_conferido(cliente):
    q = cliente.post("/api/matematica/criar", json={
        "topico": "trigonometria", "semente": 5,
    }).json()
    assert q["conferida"] is True
    assert len(q["alternativas"]) == 4
    assert 0 <= q["correta"] < 4
    assert q["erros_dos_distratores"][q["correta"]] == "-"


def test_enunciado_malicioso_nao_executa_codigo(cliente):
    r = cliente.post("/api/matematica/resolver", json={
        "enunciado": 'Calcule __import__("os").system("id") = 0 para todo x.'
    })
    assert r.status_code == 200
    assert r.json()["analise"]["equacoes"] == []
