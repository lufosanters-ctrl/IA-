"""Testes da orquestração da resolução e do modo socrático."""

import pytest

from app.matematica.criacao import GERADORES, conferir_questao, criar_parametrica
from app.matematica.resolucao import Problema, dar_pista, resolver

pytestmark = pytest.mark.asyncio


async def test_resolve_sem_modelo_usando_algebra():
    """Sem chave de API, a álgebra computacional ainda resolve e verifica."""
    r = await resolver(Problema(enunciado="Resolva a equação x^2 - 5x + 6 = 0."))
    assert r.modo == "simbolico"
    assert r.verificado
    assert "2" in r.texto and "3" in r.texto
    assert "## Verificação" in r.texto
    assert "## Resposta" in r.texto


async def test_resolucao_traz_diagnostico_e_passes():
    r = await resolver(Problema(enunciado="Resolva a equação x^2 - 5x + 6 = 0."))
    assert r.diagnostico.topico_nome
    assert "diagnóstico" in r.passes
    assert "álgebra computacional" in r.passes


async def test_problema_sem_equacao_nao_quebra():
    r = await resolver(Problema(enunciado="Quantos anagramas tem a palavra ARARA?"))
    assert r.texto
    assert r.diagnostico.topico == "combinatoria"
    # Sem equação para resolver, o motor entrega o protocolo do assunto.
    assert "Caminhos a considerar" in r.texto or "Verificação" in r.texto


async def test_sistema_linear_e_resolvido_em_conjunto():
    r = await resolver(Problema(enunciado="Sabendo que x + y = 10 e x - y = 4, determine x e y."))
    assert "7" in r.texto and "3" in r.texto
    assert r.verificado


async def test_expressao_maliciosa_no_enunciado_nao_executa():
    r = await resolver(Problema(enunciado='Calcule __import__("os").system("ls") = 0'))
    assert r.texto          # responde algo
    assert not r.analise.equacoes


async def test_pista_nao_entrega_a_resposta():
    problema = Problema(enunciado="Resolva a equação x^2 - 5x + 6 = 0.")
    pista = await dar_pista(problema, nivel=1)
    assert pista.texto
    assert pista.nivel == 1
    assert "x = 2" not in pista.texto and "x = 3" not in pista.texto


async def test_pistas_crescem_em_ajuda():
    problema = Problema(enunciado="Determine as raízes do polinômio x^3 - 6x^2 + 11x - 6.")
    primeira = await dar_pista(problema, nivel=1)
    ultima = await dar_pista(problema, nivel=4)
    assert primeira.texto != ultima.texto
    assert len(ultima.texto) > len(primeira.texto)


async def test_nivel_da_pista_fica_na_escala():
    problema = Problema(enunciado="Calcule a derivada de x^2.")
    assert (await dar_pista(problema, nivel=0)).nivel == 1
    assert (await dar_pista(problema, nivel=99)).nivel == 4


# --------------------------------------------------------------------------
# Criação de questões
# --------------------------------------------------------------------------

@pytest.mark.parametrize("topico", sorted(GERADORES))
async def test_gerador_parametrico_produz_questao_valida(topico):
    questao = criar_parametrica(topico, semente=11)
    aprovada, motivo = conferir_questao(questao)
    assert aprovada, f"{topico}: {motivo}"
    assert questao.enunciado and questao.solucao and questao.ideia_central
    assert len(questao.alternativas) == 4
    assert len(set(questao.alternativas)) == 4, "alternativas repetidas"
    assert questao.erros_dos_distratores[questao.correta] == "-"
    for indice, erro in enumerate(questao.erros_dos_distratores):
        if indice != questao.correta:
            assert erro and erro != "-", "distrator sem erro declarado"


async def test_questao_e_reprodutivel_pela_semente():
    a = criar_parametrica("polinomios", semente=42)
    b = criar_parametrica("polinomios", semente=42)
    assert a.enunciado == b.enunciado
    assert a.alternativas == b.alternativas


async def test_sementes_diferentes_geram_questoes_diferentes():
    enunciados = {criar_parametrica("complexos", semente=i).enunciado for i in range(8)}
    assert len(enunciados) > 1


async def test_conferencia_reprova_questao_mal_formada():
    questao = criar_parametrica("polinomios", semente=1)
    questao.alternativas = [questao.alternativas[0]] * 4
    aprovada, motivo = conferir_questao(questao)
    assert not aprovada and "repetidas" in motivo


async def test_conferencia_reprova_gabarito_fora_da_lista():
    questao = criar_parametrica("polinomios", semente=1)
    questao.correta = 9
    aprovada, motivo = conferir_questao(questao)
    assert not aprovada and "gabarito" in motivo
