"""A aferição precisa continuar em 100%: é o guarda contra regressão de acerto.

Teste de unidade prova que o código faz o que o código diz. Estes casos provam
que os motores ACERTAM — são coisas diferentes, e esta é a que o estudante
sente.
"""

import pytest

from app.afericao import TODOS_OS_CASOS, VERIFICADORES, aferir


def test_nenhum_caso_de_referencia_falha():
    relatorio = aferir()
    if relatorio.falhas:
        detalhe = "\n".join(
            f"  {f.caso.area}: {f.caso.entrada}\n"
            f"    esperado {f.caso.esperado!r}, obtido {f.obtido!r}"
            f"{' (' + f.caso.porque + ')' if f.caso.porque else ''}"
            for f in relatorio.falhas
        )
        pytest.fail(
            f"{len(relatorio.falhas)} de {relatorio.total} casos erraram:\n{detalhe}"
        )
    assert relatorio.taxa == 100.0


@pytest.mark.parametrize("area", sorted(VERIFICADORES))
def test_cada_area_tem_casos_e_acerta_tudo(area):
    relatorio = aferir(area)
    assert relatorio.total >= 5, f"área {area} com poucos casos de referência"
    assert not relatorio.falhas


def test_todo_caso_declara_area_conhecida():
    for caso in TODOS_OS_CASOS:
        assert caso.area in VERIFICADORES, f"caso sem verificador: {caso.area}"
        assert caso.entrada.strip()


def test_relatorio_resume_por_area():
    relatorio = aferir()
    areas = relatorio.por_area()
    assert set(areas) == set(VERIFICADORES)
    assert all(0 <= a["taxa"] <= 100 for a in areas.values())
    assert relatorio.acertos + len(relatorio.falhas) == relatorio.total


def test_area_inexistente_devolve_relatorio_vazio():
    relatorio = aferir("assunto-que-nao-existe")
    assert relatorio.total == 0
    assert relatorio.taxa == 0.0
