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
    assert len(dados["fontes"]) == 8
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
