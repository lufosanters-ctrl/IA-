# Núcleo

**Uma IA de estudo que pesquisa bases de dados públicas da internet e responde
com citações verificáveis.**

O Núcleo não responde de memória. A cada pergunta ele consulta ao vivo oito
bases públicas **mais os seus próprios livros didáticos**, ranqueia os trechos
recuperados e redige a resposta apoiada apenas nesse material — com marcadores
`[1]`, `[2]` ligados às fontes reais. Depois **confere, afirmação por
afirmação, se a fonte citada sustenta o que foi dito**. Em cima do que você
acabou de ler, ele gera flashcards, quizzes e um plano de estudo, e agenda as
revisões com repetição espaçada.

Para matemática há um motor separado, no padrão ITA/IME: ele **resolve com
álgebra computacional**, verifica o resultado por um caminho independente e
**critica a própria solução** antes de entregá-la.

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

### Adicionando seus livros

Jogue os arquivos na pasta `biblioteca/` e rode:

```bash
python -m app.ingerir                 # indexa tudo que estiver em biblioteca/
python -m app.ingerir livro.pdf       # ou um arquivo específico
python -m app.ingerir --catalogo      # baixa livros didáticos abertos
```

Também dá para arrastar os arquivos direto na aba **Biblioteca** da interface.
Formatos aceitos: PDF, EPUB, TXT, Markdown e HTML.

Se você não tem os livros à mão, o catálogo aberto baixa material didático de
licença livre da Wikilivros e do Project Gutenberg — matemática, física,
química, biologia, programação, história e português:

```bash
python -m app.ingerir --catalogo-disponivel   # ver o que tem
python -m app.ingerir --livro calculo         # baixar um só
python -m app.ingerir --catalogo --area biologia
```

O que entra na biblioteca vira fonte de primeira classe: para dúvidas de
conceito, um livro didático costuma explicar melhor que um artigo de pesquisa,
e o Núcleo pesa isso na hora de escolher o que citar.

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
| **Sua biblioteca** | os livros que você indexou, por capítulo | fundamentos, estudo dirigido |
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

## Motor matemático

Um modelo de linguagem escreve matemática convincente e, às vezes, errada. O
que torna a resolução confiável não é o texto prometer que verificou — é um
verificador independente conferir. O Núcleo usa o SymPy, um sistema de álgebra
computacional, como fonte de verdade.

```
enunciado
  │
  ├─ 1. diagnóstico: assunto, dificuldade (1 a 4) e o que isso muda
  ├─ 2. leitura simbólica: extrai as equações da prosa e resolve o que dá
  ├─ 3. exploração de estratégias    (só nos níveis 3 e 4)
  ├─ 4. resolução, com as estratégias e o protocolo daquele assunto
  ├─ 5. confronto: a álgebra resolve por conta própria e compara
  ├─ 6. crítica interna: caça salto lógico, caso perdido, divisão por zero
  └─ 7. correção, se a crítica encontrou algo que importa
```

**A profundidade é adaptativa.** "Calcule a derivada de x²" sai em uma passada.
"Determine todos os valores de m para que a equação tenha duas raízes distintas
e positivas" passa por escolha de estratégia, verificação independente e
crítica. Gastar três passes numa equação do segundo grau é desperdício;
resolver um problema de ITA com uma única passada é imprudência.

**O que a verificação simbólica realmente checa:**

| Teste | O que pega |
|---|---|
| substituição | raiz que não zera a equação original |
| domínio | raiz estranha: anula denominador, radicando negativo, log de zero |
| sistema | solução que satisfaz uma equação e viola outra |
| identidade | igualdade falsa, testada em 12 pontos aleatórios |
| intervalo | probabilidade fora de [0, 1] |
| confronto | a resposta afirmada não contém todas as raízes |

**Funciona sem chave de API.** Nesse modo, o SymPy resolve e verifica sozinho:
você não recebe a explicação didática, mas recebe matemática correta e
conferida, o que é bem mais útil do que um texto plausível sem conferência.

**Modo socrático.** Em vez da resolução, você pede pistas. São quatro níveis:
a primeira aponta só onde olhar, a última desenvolve quase tudo e deixa o
fecho para você. A resposta final nunca aparece nesse modo.

**Gerador de questões.** Cada distrator corresponde a um erro real e conhecido
— sinal trocado, caso esquecido, raiz estranha aceita, fórmula aplicada fora da
hipótese — e o erro é mostrado depois que você responde. Nas questões de molde
o gabarito é **calculado pelo SymPy**, não escrito à mão, então é correto por
construção. Nas criadas pelo modelo, o gabarito passa por conferência antes de
ser entregue.

**Segurança da entrada.** O enunciado do usuário nunca chega a um `eval` livre.
Há um filtro de caracteres, uma lista de termos proibidos, um espaço de nomes
sem `builtins` e limites contra fatorial gigante e torre de potências. Há teste
para cada uma dessas portas.

## Como a resposta é construída

```
pergunta
  │
  ├─ 1. classificação da intenção (definição? como fazer? estado da arte?)
  ├─ 2. roteamento por área do conhecimento
  ├─ 3. ponte bilíngue: a versão em inglês vai para as bases acadêmicas
  ├─ 4. consulta paralela às bases + biblioteca local (cache de 6h)
  ├─ 5. normalização: HTML limpo, resumos remontados, campos unificados
  ├─ 6. fragmentação em trechos de ~900 caracteres nos limites de frase
  ├─ 7. BM25 + credibilidade da fonte, com pesos ajustados pela intenção
  ├─ 8. (modo profundo) 2ª rodada com os termos aprendidos na 1ª
  ├─ 9. seleção diversa (MMR), equilibrada entre fontes
  ├─ 10. síntese com citação numerada obrigatória
  └─ 11. checagem: cada afirmação confere com a fonte que ela cita?
```

Decisões que valem explicar:

- **Intenção antes de busca.** "O que é entropia?" e "quais os avanços recentes
  em entropia?" pedem material diferente. A intenção detectada muda o peso de
  cada base — livro didático sobe numa pergunta de definição, pré-print sobe
  numa de estado da arte — e muda o formato pedido ao modelo. Está em
  `app/consulta.py`.
- **Ponte bilíngue.** Boa parte da literatura está em inglês. Perguntar
  "mecanismo de atenção" ao arXiv devolve quase nada; "attention mechanism"
  devolve o campo inteiro. A tradução usa os *langlinks* da Wikipedia (o mesmo
  conceito ligado entre idiomas, o que acerta o termo consagrado) e cai num
  glossário acadêmico embutido quando a rede falha. As bases em português
  continuam recebendo a pergunta original.
- **BM25 em Python puro**, sem embeddings. Roda em milissegundos, não baixa
  modelo nenhum e funciona offline. Para o tamanho do corpus recuperado por
  pergunta (dezenas de trechos), a qualidade é equivalente.
- **Realimentação de relevância (Rocchio).** No modo profundo, os melhores
  trechos da primeira rodada revelam o vocabulário real do assunto, e esses
  termos alimentam uma segunda busca. É aprender o jargão lendo a primeira
  página antes de procurar direito.
- **MMR na seleção final,** com teto por fonte. Sem isso, o contexto vira cinco
  paráfrases do mesmo parágrafo, ou uma única base ocupa tudo e a resposta
  perde o contraste entre pontos de vista.
- **Uma base fora do ar não derruba a busca.** Cada conector captura suas
  próprias falhas e o painel "Bases consultadas" mostra o que respondeu, o que
  falhou e o que veio do cache.

## A checagem de fundamentação

Citar `[3]` no fim da frase não prova nada: o modelo pode citar a fonte errada
ou afirmar um número que não está lá. Depois de redigir, o Núcleo confere cada
afirmação contra o texto que ela cita e mostra dois números ao lado da resposta:

| Medida | O que significa |
|---|---|
| **com citação** | quantas afirmações factuais trazem alguma referência |
| **sustentadas** | quantas dessas realmente batem com o texto citado |

A checagem é lexical, não semântica: mede sobreposição de palavras de conteúdo
e confere se os números citados aparecem na fonte. Isso não pega paráfrase
distante, mas pega com segurança os dois erros que mais importam — citar a
fonte errada e inventar número. Afirmações frágeis ficam sublinhadas no próprio
texto da resposta.

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
  main.py            API FastAPI: 32 rotas
  config.py          configuração por ambiente / .env
  schemas.py         validação de entrada e saída (Pydantic)
  texto.py           limpeza, tokenização, frases, fragmentação
  consulta.py        intenção, ponte bilíngue, realimentação de relevância
  ranking.py         BM25 + MMR + pesos de credibilidade e de intenção
  cache.py           cache LRU com expiração
  matematica/
    classificacao.py assunto, dificuldade e profundidade adaptativa
    simbolico.py     álgebra computacional: leitura segura, solução, verificação
    prompts.py       resolvedor, crítico, socrático e criador de questões
    resolucao.py     orquestração das fases e do ciclo crítica → correção
    criacao.py       geradores paramétricos com gabarito calculado
  banco.py           SQLite: histórico, baralhos, cartões, SM-2
  livros.py          extração de texto de PDF, EPUB, TXT, Markdown e HTML
  biblioteca.py      índice FTS5 dos seus livros
  catalogo.py        livros didáticos abertos que a IA baixa sozinha
  ingerir.py         linha de comando da biblioteca
  sources/           um módulo por base de dados + roteador por área
  ai/
    llm.py           cliente do modelo, com streaming e extração de JSON
    pesquisa.py      o pipeline de pesquisa (normal e em fluxo/SSE)
    estudo.py        flashcards, quiz, plano, explicação em níveis
    verificacao.py   checagem de fundamentação das afirmações
web/
  index.html         interface
  assets/estilo.css  tema claro e escuro
  assets/app.js      aplicação
  assets/api.js      camada de acesso à API
  assets/markdown.js renderizador de markdown com pílulas de citação
tests/               68 testes, sem tocar a internet
```

Seus dados ficam em `data/nucleo.db` e seus livros em `biblioteca/` com o
índice em `data/biblioteca.db`, tudo na sua máquina. Nenhum livro é enviado
para lugar nenhum: a busca neles é local. Só as consultas vão para as bases
públicas (e para o modelo, se você configurar a chave).

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

```bash
# estado da biblioteca e catálogo disponível
curl localhost:8000/api/biblioteca

# baixar um livro didático aberto
curl -X POST localhost:8000/api/biblioteca/catalogo \
  -H 'Content-Type: application/json' -d '{"chaves": ["calculo"]}'
```

```bash
# resolver com verificação simbólica
curl -X POST localhost:8000/api/matematica/resolver \
  -H 'Content-Type: application/json' \
  -d '{"enunciado": "Resolva a equação x^2 - 5x + 6 = 0."}'

# pedir uma pista em vez da resposta
curl -X POST localhost:8000/api/matematica/pista \
  -H 'Content-Type: application/json' \
  -d '{"enunciado": "Resolva x^2 - 5x + 6 = 0.", "nivel": 1}'

# conferir a sua resposta contra a álgebra
curl -X POST localhost:8000/api/matematica/conferir \
  -H 'Content-Type: application/json' \
  -d '{"enunciado": "Resolva x^2 - 5x + 6 = 0.", "resposta": "x = 2"}'
```

Rotas principais: `/api/pesquisar`, `/api/pesquisar/fluxo`, `/api/flashcards`,
`/api/quiz`, `/api/plano`, `/api/explicar`, `/api/historico`, `/api/baralhos`,
`/api/revisao`, `/api/estatisticas`, `/api/fontes`, `/api/biblioteca`,
`/api/matematica/resolver`, `/api/matematica/pista`, `/api/matematica/conferir`,
`/api/matematica/criar`, `/api/saude`.

---

## Testes

```bash
python -m pytest        # 258 testes, ~7 segundos
```

Os testes simulam as respostas de todas as APIs com `httpx.MockTransport`,
então rodam offline e de forma determinística. Cobrem: limpeza e fragmentação
de texto, ranqueamento, cada conector (incluindo queda de rede, HTTP 429 e
resposta malformada), extração de PDF/EPUB/Markdown, o índice da biblioteca
(inclusive tentativas de injeção na sintaxe do FTS5), classificação de
intenção, tradução, realimentação de relevância, checagem de fundamentação, o
pipeline completo, o cache, o algoritmo SM-2, a leitura segura de expressões
matemáticas (incluindo tentativas de injeção de código), a resolução simbólica,
o diagnóstico de dificuldade, os geradores de questão e todos os endpoints HTTP.

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
- PDF digitalizado (foto de página, sem camada de texto) não é indexável. O
  Núcleo avisa em vez de indexar lixo; passe o arquivo por um OCR antes.
- A checagem de fundamentação é lexical. Ela confirma que a fonte fala do
  mesmo assunto e que os números batem, não que o raciocínio esteja correto.
- Indexe apenas livros que você tem o direito de usar. O catálogo aberto só
  traz material de licença livre ou em domínio público, com a licença
  registrada junto de cada livro.
- A verificação simbólica só alcança o que consegue ler como equação. Em
  problema de geometria, contagem ou demonstração, ela não se aplica — e o
  Núcleo diz isso em vez de fingir que conferiu.
- Verificação não é demonstração. O motor confirmar uma identidade em doze
  pontos aleatórios é evidência forte, não prova. Quando o enunciado pede
  demonstração, o que vale é o argumento escrito.
- O gerador de questões cobre seis assuntos em modo paramétrico. Fora deles,
  a questão depende do modelo e a conferência é apenas estrutural.
- As APIs públicas têm limites de requisição. O cache de 6 horas existe
  justamente para não abusar delas.
