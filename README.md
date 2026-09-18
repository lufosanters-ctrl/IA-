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

Para gramática, o mesmo princípio: crase, regência, colocação pronominal e
concordância são analisadas por **regras codificadas**, não por opinião de
modelo. E há um **modo tutor** que não entrega a resposta — a ajuda sobe um
degrau de cada vez, e recua quando você está quase lá.

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

## Modo tutor: a escada de ajuda

O princípio é o da **mínima ajuda necessária**. Entregar a resolução destrói o
exercício; negar ajuda a quem está travado de verdade produz frustração. A
escada existe para que a ajuda cresça um degrau por vez, e só quando o anterior
não bastou.

| Degrau | O que aparece |
|---|---|
| 0 · Orientação | qual é o assunto e o que a questão pede |
| 1 · Pergunta guia | uma pergunta que obriga a pensar no ponto certo |
| 2 · Pista conceitual | a propriedade que resolve, sem aplicá-la |
| 3 · Pista operacional | o próximo passo concreto, sem executá-lo |
| 4 · Primeiro passo | a primeira transformação, e o problema volta pra você |
| 5 · Resolução parcial | tudo até antes da etapa decisiva |
| 6 · Resolução completa | só a pedido, com ideia, desenvolvimento e verificação |

Três comportamentos importam mais que a escada em si:

- **Acerto parcial faz a ajuda RECUAR.** Quem está quase lá não precisa de mais
  andaime, precisa de menos. É a mesma lógica do *fading*: quem já mostra
  domínio de um assunto começa a escada mais alto da próxima vez.
- **"Não me dê a resposta" é comando forte.** Com esse pedido, a escada nunca
  passa do degrau 5, por mais vezes que você peça ajuda.
- **O tutor aponta o PRIMEIRO erro, não todos.** Erros posteriores costumam ser
  consequência do primeiro, e listar tudo de uma vez confunde em vez de ensinar.
  A resposta segue sempre a mesma forma: até onde o raciocínio se sustenta, onde
  ele sai do rumo, por que aquele passo não funciona, e a pergunta que faz você
  corrigir sozinho.

**Padrões de erro.** Cada tentativa é classificada (conceitual, interpretação,
algébrico, sinal, distração, fora das condições, confusão entre regras,
incompleto). Quando um tipo se repete, o tutor para de corrigir o deslize e
passa a ensinar a rotina que o previne.

**Questão fotografada.** Você manda a foto, o tutor transcreve e **pede sua
confirmação antes de resolver** — enunciado, alternativas, o que você escreveu
à mão e os trechos que ficaram ilegíveis. Erro de leitura produz resolução
perfeita da questão errada, e é o tipo de erro que passa despercebido porque a
conta fecha.

## Gramática verificada

Crase e colocação pronominal são os tópicos de português que mais se parecem
com matemática, e por isso dão para verificar de verdade:

```
crase = o termo anterior exige a preposição "a"
      + o termo seguinte admite o artigo "a"
```

O motor testa as duas condições separadamente e na ordem certa. As
**proibições** vêm primeiro, porque são absolutas: antes de verbo, de palavra
masculina, de pronome pessoal, de plural com "a" no singular, ou depois de
outra preposição, acabou — nem precisa olhar a regência. Depois vêm as
**locuções consagradas**, os casos **facultativos** (marcados como tais, sem
fingir resposta única) e, por fim, a **regência**.

Na regência está a decisão mais importante do motor: quando o verbo é
transitivo indireto puro e exige "a" em todos os sentidos registrados, ele
conclui; quando o verbo muda de regência conforme o sentido — "assistir",
"visar", "aspirar", "implicar" — ele **devolve a pergunta** em vez de chutar,
porque quem decide o sentido é você. Verbo bitransitivo também não conclui:
em "convidei a aluna", o termo colado ao verbo é o objeto direto, e tratá-lo
como indireto acusaria de erro uma frase correta.

Além de consultar o que o verbo pede, o motor confere o que a frase fez. O
conferidor compara a preposição efetivamente usada com a registrada e acusa os
desvios clássicos — "prefiro café **do que** chá", "obedeço **as** regras",
"cheguei **em** casa", "namorei **com** a Ana". Ele só opina sobre verbo de
sentido único no dicionário: onde há polissemia, quem escolhe o sentido é
você, e o motor se cala.

Também estão codificados:

- **colocação pronominal**, por um algoritmo quase fechado: há palavra atrativa
  antes do verbo? próclise. Não há e o verbo está no futuro? mesóclise. Senão,
  ênclise;
- **concordância**, nas armadilhas clássicas: "haver" impessoal, "fazer"
  temporal, partícula "se" apassivadora × índice de indeterminação, "um dos que";
- **regência verbal e nominal**, com todos os sentidos de cada verbo e um
  exemplo para cada, mais a conferência da preposição usada na frase;
- um **léxico** de gênero e classe de palavra que sustenta os dois motores
  acima. Quando a evidência não basta — "colega", "grama", palavra comum de
  dois gêneros — ele responde "indeterminado" em vez de chutar, porque um
  chute errado ali vira veredito gramatical errado lá na frente.

## Inglês em cinco dimensões

"Está certo?" é pergunta insuficiente. Uma frase pode ser perfeitamente
gramatical e ser algo que nenhum falante diria. O módulo separa:

| Dimensão | Pergunta |
|---|---|
| grammaticality | as regras permitem? |
| meaning | o que comunica exatamente? |
| naturalness | um falante diria assim nesta situação? |
| register | serve para conversa, e-mail de trabalho ou texto acadêmico? |
| frequency | é corrente ou raro o bastante para soar afetado? |

Há detecção determinística dos **erros de transferência do português** — "people
is", "explain me this", "depends of", "married with", "since three years" — cada
um com o motivo estrutural e o exemplo certo. E uma tabela de **contrastes**,
porque a dúvida real nunca é sobre uma construção isolada: é sempre present
perfect **ou** simple past, make **ou** do, for **ou** since. O que destrava é o
critério de decisão, não a definição de cada um.

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
  main.py            API FastAPI: 49 rotas
  afericao.py        casos com gabarito conhecido, por área
  config.py          configuração por ambiente / .env
  schemas.py         validação de entrada e saída (Pydantic)
  texto.py           limpeza, tokenização, frases, fragmentação
  consulta.py        intenção, ponte bilíngue, realimentação de relevância
  ranking.py         BM25 + MMR + pesos de credibilidade e de intenção
  cache.py           cache LRU com expiração
  gramatica/
    lexico.py        gênero, número e classes fechadas
    regencia.py      regência verbal e nominal, sentido a sentido
    crase.py         as duas condições da crase, testadas na ordem certa
    colocacao.py     próclise, mesóclise e ênclise por algoritmo
    concordancia.py  as armadilhas clássicas, com o teste de cada uma
    analise.py       reúne os motores num veredito só
  ingles/
    dimensoes.py     as cinco dimensões e os erros de transferência
    contrastes.py    pares que se confundem, com o critério de decisão
  tutor/
    escada.py        os sete degraus e a política de mínima ajuda
    treino.py        exercícios dirigidos ao erro que mais se repete
    sessao.py        sessões, tentativas, padrões de erro e fading
    tutoria.py       orquestração: verificador → degrau → resposta
    visao.py         leitura de questão fotografada, com confirmação
    prompts.py       prompts do tutor, do diagnóstico e da generalização
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

```bash
# abrir uma sessão de tutoria (começa no degrau 0)
curl -X POST localhost:8000/api/tutor/sessao \
  -H 'Content-Type: application/json' \
  -d '{"enunciado": "A crase está correta em: Vou a praia?"}'

# analisar uma frase pelos motores de gramática
curl -X POST localhost:8000/api/gramatica/analisar \
  -H 'Content-Type: application/json' \
  -d '{"frase": "Não disseram-me que haviam pessoas à espera."}'

# todos os sentidos de um verbo, cada um com sua regência
curl -X POST localhost:8000/api/gramatica/regencia \
  -H 'Content-Type: application/json' -d '{"verbo": "assistir"}'
```

Rotas principais: `/api/pesquisar`, `/api/pesquisar/fluxo`, `/api/flashcards`,
`/api/quiz`, `/api/plano`, `/api/explicar`, `/api/historico`, `/api/baralhos`,
`/api/revisao`, `/api/estatisticas`, `/api/fontes`, `/api/biblioteca`,
`/api/matematica/resolver`, `/api/matematica/pista`, `/api/matematica/conferir`,
`/api/matematica/criar`, `/api/tutor/sessao`, `/api/tutor/imagem`,
`/api/gramatica/analisar`, `/api/ingles/avaliar`, `/api/saude`.

---

## Testes

```bash
python -m pytest        # 403 testes, ~12 segundos
```

Os testes simulam as respostas de todas as APIs com `httpx.MockTransport`,
então rodam offline e de forma determinística. Cobrem: limpeza e fragmentação
de texto, ranqueamento, cada conector (incluindo queda de rede, HTTP 429 e
resposta malformada), extração de PDF/EPUB/Markdown, o índice da biblioteca
(inclusive tentativas de injeção na sintaxe do FTS5), classificação de
intenção, tradução, realimentação de relevância, checagem de fundamentação, o
pipeline completo, o cache, o algoritmo SM-2, a leitura segura de expressões
matemáticas (incluindo tentativas de injeção de código), a resolução simbólica,
o diagnóstico de dificuldade, os geradores de questão, os motores de crase,
regência, colocação e concordância, a avaliação de inglês, a escada de ajuda
(incluindo a garantia de que os degraus 0 a 5 não vazam a resposta), a
conferência de regência, o montador de treino e todos os endpoints HTTP.

Há ainda um arquivo de regressões de robustez: cada teste ali reproduz uma
falha que chegou ao código, com a entrada concreta que a disparava — bomba de
descompressão em EPUB, bloco de trecho que estourava o tamanho pedido, palavra
real confundida com numeração romana, questão extrativa perdida por causa de
um acento.

### Aferição: os motores estão acertando?

Teste de unidade prova que o código faz o que o código diz. Isso é outra
coisa:

```bash
python -m app.afericao              # roda tudo, taxa por área
python -m app.afericao --area crase
python -m app.afericao --falhas     # só o que errou
```

São 157 casos com gabarito conhecido, tirados das regras consagradas e do tipo
de questão que cai em prova, divididos em dez áreas: crase, colocação,
concordância, léxico, regência (dicionário e uso), inglês, assunto de
matemática, álgebra simbólica e roteamento de matéria. O mesmo relatório está
em `GET /api/afericao` e no painel "Bases de dados" da interface.

O banco existe porque uma bateria de testes verdes não respondia à pergunta
que importa. Quando ele foi rodado contra frases reais de prova pela primeira
vez, quinze frases corretas eram acusadas e seis de sete erros clássicos
passavam limpos — com todos os testes de unidade passando. Cada correção
daquela rodada entrou aqui como caso de referência.

---

## Atalhos

`Ctrl/Cmd + K` abre a paleta de comandos · clique num `[n]` para pular à
referência · clique num flashcard para virar · o botão no rodapé alterna tema
claro e escuro.

A interface é navegável só pelo teclado: as abas respondem às setas, Home e
End; a paleta prende o foco enquanto está aberta, fecha com Esc de qualquer
ponto e devolve o foco a quem a abriu; as duas áreas de envio (livros e foto
da questão) são alcançáveis por Tab e acionadas com Enter ou Espaço. Sem o
KaTeX — offline, ou com o CDN bloqueado — as fórmulas viram texto legível com
expoentes e índices Unicode: `x^2` aparece como x² e `r_1` como r₁.

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
- A checagem por substituição confere a raiz na equação que o motor LEU, não
  na pergunta que o enunciado FEZ. Por isso, quando o enunciado traz uma
  condição em prosa que a leitura não aplica — "em graus", "no intervalo
  [0, 4π]", "sabendo que x < 0", "n natural" — o resultado sai como "o que a
  álgebra leu", sem selo de conferido, com a condição que faltou escrita por
  extenso. O mesmo vale quando a pergunta não é pelas raízes: em "calcule
  a² + b²", as raízes não são a resposta.
- "log x" sem base escrita é lido como base 10, a convenção do ensino
  brasileiro, e uma base declarada no enunciado é respeitada. "ln" continua
  logaritmo natural.
- O confronto entre a sua resposta e a da álgebra compara números escritos no
  texto. Diante de raiz simbólica (5π/3, √2) ele não opina, em vez de acusar
  divergência onde não há.
- Verificação não é demonstração. O motor confirmar uma identidade em doze
  pontos aleatórios é evidência forte, não prova. Quando o enunciado pede
  demonstração, o que vale é o argumento escrito.
- O gerador de questões cobre seis assuntos em modo paramétrico. Fora deles,
  a questão depende do modelo e a conferência é apenas estrutural.
- Os motores de gramática cobrem as regras cobradas em prova, não a língua
  inteira. Quando a decisão depende de análise sintática completa — qual termo
  o verbo rege numa frase longa, por exemplo — o motor devolve a pergunta em
  vez de arriscar um veredito.
- O dicionário de regência traz os verbos que caem em prova. Um verbo fora dele
  não é analisado, e o motor diz isso.
- A conferência de regência se restringe a verbo de sentido único. Um desvio
  em verbo polissêmico não é acusado: seria escolher o sentido no lugar de
  quem escreveu.
- O léxico de gênero cobre as exceções que derrubariam a heurística de
  terminação, não o vocabulário inteiro do português. Fora delas ele responde
  "indeterminado", e o motor que depende dele devolve a pergunta.
- O treino dirigido sorteia do banco de aferição e do gerador paramétrico.
  Sem histórico de erro acumulado, ele monta um treino geral em vez de fingir
  que conhece o seu ponto fraco. "Você vem cometendo" exige pelo menos duas
  ocorrências: uma não é padrão.
- Sem chave de API, a tentativa que você escreve no modo matemática é
  comparada com a álgebra, não comentada linha a linha. O Núcleo diz isso em
  vez de aceitar o texto em silêncio.
- O painel de domínio só mostra taxa quando houve tentativa julgada. Onde o
  sistema não conseguiu julgar, ele escreve "sem tentativa julgada" — não
  "0% de acerto", que seria afirmar um fracasso que ninguém mediu.
- A leitura de questão fotografada depende do modelo de visão, então exige
  chave de API. Sem ela, digite o enunciado.
- As APIs públicas têm limites de requisição. O cache de 6 horas existe
  justamente para não abusar delas.
