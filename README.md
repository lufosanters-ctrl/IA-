# Núcleo

**Uma IA de estudo que pesquisa bases de dados públicas da internet e responde
com citações verificáveis.**

O Núcleo não responde de memória. A cada pergunta ele consulta ao vivo oito
bases públicas, ranqueia os trechos recuperados e redige a resposta apoiada
apenas nesse material — com marcadores `[1]`, `[2]` ligados às fontes reais.
Em cima do que você acabou de ler, ele gera flashcards, quizzes e um plano de
estudo, e agenda as revisões com repetição espaçada.

Feito em **Python** (FastAPI, `asyncio`) com interface web sem etapa de build.

---

## Como rodar

```bash
git clone https://github.com/lufosanters-ctrl/IA-.git
cd IA-
./iniciar.sh
```

Abra <http://127.0.0.1:8000>. O script cria o ambiente virtual, instala as
dependências e sobe o servidor na primeira execução.

Passo a passo manual, se preferir:

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python -m app
```

### Os dois modos de operação

| | Sem chave de API | Com `ANTHROPIC_API_KEY` |
|---|---|---|
| Busca nas bases | completa | completa |
| Resposta | trechos reais selecionados e ordenados | texto redigido e explicado |
| Flashcards / quiz | extraídos por regra do material | escritos a partir do material |
| Plano de estudo | sequenciado pelas fontes | sequenciado pedagogicamente |

A plataforma funciona inteira sem chave nenhuma. Nesse **modo extrativo** ela
nunca inventa uma frase: tudo o que aparece na tela veio literalmente de uma
fonte citada. Para ligar a síntese neural, coloque a chave no `.env`:

```bash
ANTHROPIC_API_KEY=sk-ant-...
NUCLEO_MODELO=claude-sonnet-5
```

---

## As oito bases consultadas

Todas públicas e sem chave de API.

| Base | O que traz | Boa para |
|---|---|---|
| **Wikipedia** | verbetes em português ou inglês | visão geral, definições |
| **OpenAlex** | 250M+ trabalhos acadêmicos com resumo | qualquer área científica |
| **arXiv** | pré-prints de exatas e computação | pesquisa recente, IA |
| **PubMed / Europe PMC** | literatura biomédica com resumo completo | medicina, biologia |
| **Semantic Scholar** | busca acadêmica com citações influentes | achar o artigo seminal |
| **Crossref** | registro oficial de DOIs | citar corretamente |
| **Open Library** | catálogo de livros | bibliografia de um tema |
| **Stack Exchange** | perguntas respondidas pela comunidade | programação, prática |

**Roteamento automático.** O Núcleo lê a pergunta e escolhe as bases. "Sintomas
do diabetes tipo 2" vai para PubMed primeiro; "como funciona um decorator em
Python" vai para Stack Exchange e arXiv. Você pode sobrescrever a escolha
marcando as bases na própria busca.

---

## Como a resposta é construída

```
pergunta
  │
  ├─ 1. roteamento por área do conhecimento
  ├─ 2. consulta paralela às bases (asyncio.gather, cache de 6h)
  ├─ 3. normalização: HTML limpo, resumos remontados, campos unificados
  ├─ 4. fragmentação em trechos de ~900 caracteres nos limites de frase
  ├─ 5. ranqueamento BM25 + peso de credibilidade da fonte + bônus de título
  ├─ 6. seleção diversa (MMR): corta redundância, limita 2 trechos por documento
  └─ 7. síntese com citação numerada obrigatória
```

Decisões que valem explicar:

- **BM25 em Python puro**, sem embeddings. Roda em milissegundos, não baixa
  modelo nenhum e funciona offline. Para o tamanho do corpus recuperado por
  pergunta (dezenas de trechos), a qualidade é equivalente.
- **Peso por fonte.** Um artigo revisado por pares pesa mais que um post de
  fórum na mesma pontuação bruta. Os pesos estão em `app/ranking.py`.
- **MMR na seleção final.** Sem isso, o contexto vira cinco paráfrases do mesmo
  parágrafo e a resposta fica pobre.
- **Uma base fora do ar não derruba a busca.** Cada conector captura suas
  próprias falhas e o painel "Bases consultadas" mostra o que respondeu, o que
  falhou e o que veio do cache.

---

## As ferramentas de estudo

**Flashcards.** Gerados sobre o material que você acabou de ler, cada um com a
citação de origem. Salve num baralho e eles entram na fila de revisão.

**Quiz.** Múltipla escolha com explicação e referência. No modo extrativo as
questões são de completar lacunas, montadas com frases reais das fontes.

**Explicação em níveis.** O mesmo conceito reescrito para iniciante, graduação
ou pós-graduação, sempre com as mesmas fontes por trás.

**Plano de estudo.** Informe o tema, quantas semanas e quantas horas por
semana. Sai uma sequência de sessões com objetivo verificável e atividade
prática em cada uma.

**Revisão espaçada (SM-2).** O mesmo algoritmo do Anki e do SuperMemo. Você nota
de 0 a 5 o quanto lembrou e o Núcleo calcula o próximo intervalo:

```
nota < 3  → volta para 1 dia, fator de facilidade cai 0,20
1ª acerto → 1 dia     2º acerto → 6 dias     depois → intervalo × facilidade
```

A implementação está em `banco.calcular_sm2()`, com testes cobrindo cada ramo.

---

## Estrutura

```
app/
  main.py            API FastAPI: 26 rotas
  config.py          configuração por ambiente / .env
  schemas.py         validação de entrada e saída (Pydantic)
  texto.py           limpeza, tokenização, frases, fragmentação
  ranking.py         BM25 + MMR + pesos de credibilidade
  cache.py           cache LRU com expiração
  banco.py           SQLite: histórico, baralhos, cartões, SM-2
  sources/           um módulo por base de dados + roteador por área
  ai/
    llm.py           cliente do modelo, com streaming e extração de JSON
    pesquisa.py      o pipeline de pesquisa (normal e em fluxo/SSE)
    estudo.py        flashcards, quiz, plano, explicação em níveis
web/
  index.html         interface
  assets/estilo.css  tema claro e escuro
  assets/app.js      aplicação
  assets/api.js      camada de acesso à API
  assets/markdown.js renderizador de markdown com pílulas de citação
tests/               68 testes, sem tocar a internet
```

Seus dados ficam em `data/nucleo.db`, na sua máquina. Nada é enviado para
lugar nenhum, exceto as consultas às bases públicas (e ao modelo, se você
configurar a chave).

---

## API

A documentação interativa fica em <http://127.0.0.1:8000/docs>.

```bash
# pesquisa com citações
curl -X POST localhost:8000/api/pesquisar \
  -H 'Content-Type: application/json' \
  -d '{"pergunta": "como funciona a fotossíntese", "profundidade": "media"}'

# pesquisa transmitida em tempo real (SSE)
curl -N 'localhost:8000/api/pesquisar/fluxo?pergunta=fotossíntese'

# flashcards sobre o mesmo material
curl -X POST localhost:8000/api/flashcards \
  -H 'Content-Type: application/json' \
  -d '{"pergunta": "como funciona a fotossíntese", "quantidade": 8}'

# o que revisar hoje
curl localhost:8000/api/revisao
```

Rotas principais: `/api/pesquisar`, `/api/pesquisar/fluxo`, `/api/flashcards`,
`/api/quiz`, `/api/plano`, `/api/explicar`, `/api/historico`, `/api/baralhos`,
`/api/revisao`, `/api/estatisticas`, `/api/fontes`, `/api/saude`.

---

## Testes

```bash
python -m pytest        # 68 testes, ~1 segundo
```

Os testes simulam as respostas das oito APIs com `httpx.MockTransport`, então
rodam offline e de forma determinística. Cobrem: limpeza e fragmentação de
texto, ranqueamento, cada conector (incluindo queda de rede, HTTP 429 e
resposta malformada), o pipeline completo, o cache, o algoritmo SM-2 e todos
os endpoints HTTP.

---

## Atalhos

`Ctrl/Cmd + K` foca a busca · clique num `[n]` para pular à referência ·
clique num flashcard para virar · o botão no rodapé alterna tema claro e escuro.

---

## Limites que você deve conhecer

- A qualidade da resposta é limitada pela qualidade do que as bases devolvem.
  Se a pergunta for vaga, os trechos recuperados serão vagos.
- Resumos de artigos são resumos, não o texto completo. Para citar num
  trabalho, abra a referência e leia a fonte.
- No modo extrativo a resposta é uma seleção de trechos, não uma explicação
  didática. Para aprender um conceito novo do zero, a síntese neural ajuda
  bastante.
- As APIs públicas têm limites de requisição. O cache de 6 horas existe
  justamente para não abusar delas.
