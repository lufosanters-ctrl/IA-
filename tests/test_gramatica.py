"""Testes dos motores determinísticos de gramática portuguesa."""

import pytest

from app.gramatica import analisar_frase, consultar_verbo
from app.gramatica.colocacao import ENCLISE, PROCLISE, analisar_colocacao
from app.gramatica.concordancia import analisar_concordancia
from app.gramatica.crase import DEPENDE, FACULTATIVA, OBRIGATORIA, PROIBIDA, analisar_crase
from app.gramatica.lexico import genero
from app.gramatica.regencia import REGENCIA_VERBAL, verbos_na_frase


# --------------------------------------------------------------------------
# Léxico
# --------------------------------------------------------------------------

@pytest.mark.parametrize("palavra,esperado", [
    ("casa", "feminino"), ("livro", "masculino"), ("problema", "masculino"),
    ("mão", "feminino"), ("cidade", "feminino"), ("programa", "masculino"),
    ("questão", "feminino"), ("dia", "masculino"), ("liberdade", "feminino"),
    ("professor", "masculino"), ("viagem", "feminino"),
])
def test_genero_das_palavras(palavra, esperado):
    assert genero(palavra) == esperado


# --------------------------------------------------------------------------
# Crase — proibições
# --------------------------------------------------------------------------

@pytest.mark.parametrize("frase,regra", [
    ("Ele começou à chorar.", "antes de verbo"),
    ("Entreguei o livro à ela.", "antes de pronome pessoal"),
    ("Refiro-me à esta questão.", "antes de pronome demonstrativo"),
    ("Refiro-me à alguma coisa.", "antes de pronome indefinido"),
    ("Escrevi à Vossa Excelência.", "antes de pronome de tratamento"),
    ("Referiu-se à pessoas ausentes.", "“a” singular diante de plural"),
])
def test_crase_proibida(frase, regra):
    ocorrencias = [o for o in analisar_crase(frase) if o.situacao == PROIBIDA]
    assert ocorrencias, f"não detectou proibição em: {frase}"
    assert any(regra in o.regra for o in ocorrencias)
    assert all(o.correto is False for o in ocorrencias)


def test_crase_proibida_antes_de_masculino():
    ocorrencias = analisar_crase("Vou à supermercado agora.")
    assert any(o.situacao == PROIBIDA and "masculina" in o.regra for o in ocorrencias)


def test_palavras_repetidas_nao_levam_crase():
    ocorrencias = analisar_crase("Ficaram cara a cara na discussão.")
    assert any(o.regra == "entre palavras repetidas" for o in ocorrencias)


# --------------------------------------------------------------------------
# Crase — obrigatórias
# --------------------------------------------------------------------------

@pytest.mark.parametrize("frase", [
    "Saímos às pressas de casa.",
    "Trabalha à noite todos os dias.",
    "Resolveu tudo à revelia do chefe.",
    "Ficou à frente de todos.",
    "À medida que estudava, melhorava.",
])
def test_locucoes_femininas_levam_crase(frase):
    ocorrencias = analisar_crase(frase)
    assert any(o.situacao == OBRIGATORIA and o.correto for o in ocorrencias)


def test_locucao_feminina_sem_acento_e_erro():
    ocorrencias = analisar_crase("Saimos as pressas de casa.")
    assert any(o.situacao == OBRIGATORIA and o.correto is False for o in ocorrencias)


def test_horas_determinadas():
    ocorrencias = analisar_crase("A reunião começa às 14 horas.")
    assert any(o.regra == "horas determinadas" and o.correto for o in ocorrencias)


def test_locucao_masculina_nao_leva_crase():
    ocorrencias = analisar_crase("Fomos a pé até o mercado.")
    assert any(o.situacao == PROIBIDA and "locução" in o.regra for o in ocorrencias)


# --------------------------------------------------------------------------
# Crase — regência decide
# --------------------------------------------------------------------------

def test_regencia_inequivoca_conclui_pela_crase():
    """“Ir” exige “a” em todos os sentidos: o motor pode decidir sozinho."""
    ocorrencias = analisar_crase("Vou à praia amanhã.")
    assert ocorrencias[0].situacao == OBRIGATORIA
    assert ocorrencias[0].correto is True
    assert "ir" in ocorrencias[0].verbos_regentes


def test_mesma_frase_sem_acento_e_apontada_como_erro():
    ocorrencias = analisar_crase("Vou a praia amanhã.")
    assert ocorrencias[0].situacao == OBRIGATORIA
    assert ocorrencias[0].correto is False


def test_verbo_ambiguo_devolve_a_pergunta_em_vez_da_resposta():
    """“Assistir” muda de regência com o sentido: quem decide é o estudante."""
    ocorrencias = analisar_crase("Assisti à sessão de cinema.")
    assert ocorrencias[0].situacao == DEPENDE
    assert "assistir" in ocorrencias[0].pergunta_guia


# --------------------------------------------------------------------------
# Crase — facultativas
# --------------------------------------------------------------------------

@pytest.mark.parametrize("frase", [
    "Entreguei o convite a Maria.",
    "Referiu-se a minha proposta.",
    "Andamos até a esquina.",
])
def test_casos_facultativos_nao_viram_erro(frase):
    ocorrencias = [o for o in analisar_crase(frase) if o.situacao == FACULTATIVA]
    assert ocorrencias
    assert all(o.correto for o in ocorrencias)
    assert "ambas" in ocorrencias[0].forma_correta


# --------------------------------------------------------------------------
# Regência
# --------------------------------------------------------------------------

def test_assistir_tem_sentidos_com_regencias_diferentes():
    sentidos = consultar_verbo("assistir")
    assert len(sentidos) >= 3
    assert any(s.exige_a for s in sentidos)
    assert any(s.transitividade == "direto" for s in sentidos)


def test_todo_verbo_catalogado_tem_exemplo():
    for verbo, sentidos in REGENCIA_VERBAL.items():
        for sentido in sentidos:
            assert sentido.exemplo, f"{verbo}: sentido sem exemplo"
            assert sentido.transitividade, f"{verbo}: sentido sem transitividade"


@pytest.mark.parametrize("frase,verbo", [
    ("Vou ao mercado.", "ir"),
    ("Cheguei ao aeroporto cedo.", "chegar"),
    ("Refiro-me ao artigo anterior.", "referir"),
    ("Obedeço às normas.", "obedecer"),
    ("Prefiro cinema a teatro.", "preferir"),
    ("Assisti ao filme.", "assistir"),
])
def test_deteccao_de_verbo_conjugado(frase, verbo):
    assert verbo in [v for v, _ in verbos_na_frase(frase)]


# --------------------------------------------------------------------------
# Colocação pronominal
# --------------------------------------------------------------------------

def test_palavra_atrativa_exige_proclise():
    ocorrencias = analisar_colocacao("Não me disseram a verdade.")
    assert ocorrencias
    assert ocorrencias[0].posicao_correta == PROCLISE
    assert ocorrencias[0].correto


def test_enclise_apos_negacao_e_erro():
    ocorrencias = analisar_colocacao("Não disseram-me a verdade.")
    assert any(not o.correto and o.posicao_correta == PROCLISE for o in ocorrencias)


def test_enclise_sem_atrativa_esta_correta():
    ocorrencias = analisar_colocacao("Entregaram-me o prêmio ontem.")
    assert ocorrencias
    assert ocorrencias[0].posicao_usada == ENCLISE
    assert ocorrencias[0].correto


def test_frase_sem_pronome_atono():
    assert analisar_colocacao("O aluno resolveu a questão.") == []


# --------------------------------------------------------------------------
# Concordância
# --------------------------------------------------------------------------

def test_haver_no_plural_e_erro():
    achados = analisar_concordancia("Haviam muitas pessoas na fila.")
    erros = [a for a in achados if a.veredito == "erro"]
    assert erros and "haver" in erros[0].configuracao


def test_haver_no_singular_esta_correto():
    achados = analisar_concordancia("Havia muitas pessoas na fila.")
    assert any(a.veredito == "correto" for a in achados)


def test_fazer_temporal_no_plural_e_erro():
    achados = analisar_concordancia("Fazem dois anos que não o vejo.")
    assert any(a.veredito == "erro" and "fazer" in a.configuracao for a in achados)


def test_se_indeterminacao_mantem_singular():
    achados = analisar_concordancia("Precisa-se de professores.")
    assert any("indeterminação" in a.configuracao for a in achados)


def test_todo_achado_traz_regra_e_teste():
    achados = analisar_concordancia("Haviam problemas e fazem dois anos disso.")
    assert achados
    for achado in achados:
        assert achado.regra and achado.teste


# --------------------------------------------------------------------------
# Análise integrada
# --------------------------------------------------------------------------

def test_analise_reune_os_motores():
    analise = analisar_frase("Não disseram-me que haviam pessoas à esperando.")
    assert analise.tem_erro
    assert len(analise.topicos_envolvidos) >= 2


def test_frase_vazia_nao_quebra():
    analise = analisar_frase("")
    assert analise.achados == []
    assert not analise.tem_erro


def test_frase_correta_nao_gera_erro():
    analise = analisar_frase("Entregaram-me o prêmio ontem.")
    assert not analise.tem_erro


# --------------------------------------------------------------------------
# Regressões encontradas ao exercitar os motores
# --------------------------------------------------------------------------

def test_preposicao_anterior_impede_crase():
    """“desde as 8 horas”: “desde” já é a preposição, não sobra outra."""
    ocorrencias = analisar_crase("Esperava desde as 8 horas.")
    assert ocorrencias[0].situacao == PROIBIDA
    assert "outra preposição" in ocorrencias[0].regra
    assert ocorrencias[0].correto is True


def test_preposicao_anterior_vence_a_regra_das_horas():
    ocorrencias = analisar_crase("Esperava desde às 8 horas.")
    assert ocorrencias[0].correto is False


def test_para_a_nao_leva_crase():
    ocorrencias = analisar_crase("Vou para a praia.")
    assert ocorrencias[0].situacao == PROIBIDA


def test_ate_continua_facultativo():
    ocorrencias = analisar_crase("Fui até à praia.")
    assert ocorrencias[0].situacao == FACULTATIVA


def test_regencia_so_alcanca_a_ocorrencia_que_o_verbo_rege():
    """Numa frase com vários “a”, o verbo rege um deles, não todos."""
    ocorrencias = analisar_crase("Assinale se a crase está correta: Vou a praia.")
    assert len(ocorrencias) == 2
    longe, perto = ocorrencias
    assert longe.termo_seguinte.lower() == "crase"
    assert longe.situacao == DEPENDE          # nenhum verbo regente por perto
    assert perto.termo_seguinte.lower() == "praia"
    assert perto.situacao == OBRIGATORIA      # regido por “Vou”


def test_se_conjuncao_nao_vira_proclise():
    """Regressão: “Assinale se a crase…” não tem pronome átono nenhum."""
    assert analisar_colocacao("Assinale se a crase está correta.") == []


def test_topicos_vem_por_relevancia_e_nao_em_ordem_alfabetica():
    analise = analisar_frase("Não disseram-me que haviam pessoas à espera.")
    assert analise.topicos_envolvidos[0] in {"colocacao", "concordancia"}
    assert "crase" in analise.topicos_envolvidos
