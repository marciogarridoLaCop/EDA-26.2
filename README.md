# TVI — Teorema do Valor Intermediário

Você digita uma função e o programa funciona em três passos:

1. **sorteia** `a`, `b` e o valor `d`, e mostra o gráfico com esses pontos — sem a
   resposta, só o problema;
2. quando você **avança**, roda a bisseção para achar o `c`;
3. mostra o gráfico de novo, agora com a **seta apontando para `c`** e a
   coordenada em números.

As duas telas usam exatamente o mesmo enquadramento, então a segunda é a
primeira com a resposta desenhada por cima — nada muda de lugar entre elas.

O projeto tem **duas frentes** sobre o mesmo núcleo de cálculo:

| | Como se avança | Arquivo de entrada |
|---|---|---|
| **Terminal** | fechando a janela do matplotlib | [main.py](main.py) |
| **Web** | clicando em "Revelar o ponto c" | [app.py](app.py) |

> **TVI** — Se `f` é contínua em `[a, b]` e `d` está entre `f(a)` e `f(b)`, então
> existe pelo menos um `c` em `(a, b)` tal que `f(c) = d`.
>
> O sorteio, por construção, nunca gera um problema sem solução: `d` é escolhido
> *entre* `f(a)` e `f(b)`, então o teorema garante que o `c` existe. A bisseção
> só precisa localizá-lo.

## Como executar — web

```bash
pip install -r requirements.txt
python3 app.py                     # servidor de desenvolvimento em :5000
```

Ou como roda em produção:

```bash
MPLBACKEND=Agg gunicorn app:app --bind 0.0.0.0:8000 --workers 1 --threads 4
```

As três páginas são `/` (a função), `/sorteio` (os pontos) e `/solucao` (o ponto
`c`). O estado inteiro vai na URL — função, domínio, `a`, `b`, `d` — então **não
há sessão nem banco de dados**: cada tela é um link que pode ser mandado para
alguém e reaberto igual, e o servidor pode reiniciar sem perder nada.

## Como executar — terminal

```bash
python3 main.py                                        # pergunta a função
python3 main.py -f "x^3 - 3*x + 1" --semente 7         # reprodutível
python3 main.py -f "cos(x)*exp(-x/3)" -d -4 4 --tabela # mostra a convergência
python3 main.py -f "1/(1+x^2)" --salvar aula           # também grava os PNGs
```

Dependências: `numpy`, `sympy`, `matplotlib`.

### Opções

| Opção | O que faz |
|---|---|
| `-f`, `--funcao` | expressão em `x`; aceita `^` e até o `@(x)` do MATLAB |
| `-d`, `--dominio` | faixa de onde `a` e `b` são sorteados (padrão `-2 4`) |
| `-s`, `--semente` | fixa o sorteio, para repetir o mesmo resultado |
| `-t`, `--tolerancia` | erro máximo admitido em `c` (padrão `1e-12`) |
| `--tabela` | imprime a tabela de convergência da bisseção |
| `--salvar PREFIXO` | grava `PREFIXO_sorteio.png` e `PREFIXO_solucao.png` |
| `--sem-grafico` | só o relatório no terminal, sem abrir janela |

Sem `--salvar`, nada é gravado em disco: as figuras só aparecem nas janelas. Se
não houver backend gráfico interativo disponível, o programa avisa e salva os
PNGs automaticamente.

## Estrutura

| Arquivo | Responsabilidade |
|---|---|
| [funcao.py](funcao.py) | interpreta o texto digitado com lista branca e o compila para NumPy |
| [bissecao.py](bissecao.py) | o método da bisseção e a tabela de convergência |
| [sorteio.py](sorteio.py) | sorteia `a`, `b`, `d` e rejeita intervalos inutilizáveis |
| [grafico.py](grafico.py) | desenha a curva, a construção do TVI e a seta |
| [main.py](main.py) | linha de comando e relatório |
| [app.py](app.py) | as rotas da web |
| [templates/](templates/) | as páginas |

O núcleo (`funcao`, `bissecao`, `sorteio`, `grafico`) não sabe se está sendo
usado pelo terminal ou pela web — quem escolhe é `main.py` ou `app.py`.

Um detalhe do `grafico.py`: ele **não importa `pyplot` no topo**. O `pyplot`
guarda estado global (a lista de janelas abertas) e não serve para um servidor
atendendo vários pedidos ao mesmo tempo; as figuras são criadas com `Figure`
direto, e o `pyplot` só aparece dentro das funções de janela do terminal.

## Como o `c` é encontrado

Achar `c` com `f(c) = d` é o mesmo que achar a **raiz** de

```
g(x) = f(x) − d
```

e é aí que a bisseção entra: como `d` está entre `f(a)` e `f(b)`, temos
`g(a)·g(b) < 0` — exatamente a hipótese de Bolzano. A cada iteração o intervalo
é cortado ao meio e ficamos com a metade onde o sinal troca, então o erro após
`n` iterações é no máximo `(b − a) / 2ⁿ`.

Três detalhes da implementação em [bissecao.py](bissecao.py):

1. **O critério de parada é a largura do intervalo**, `(b − a)/2 > tolerância`, e
   não `|g(a) − g(b)| > tolerância`. O segundo mede erro no eixo *y* e depende da
   inclinação da função — numa função achatada ele para cedo demais, numa
   inclinada tarde demais. A largura do intervalo é o que o teorema realmente
   limita.
2. **`g(meio) == 0` encerra o laço.** Sem esse caso, quando o meio cai exatamente
   na raiz nenhum dos lados é atualizado e o laço roda para sempre.
3. **Uma única avaliação de `g` por iteração**, com os valores dos extremos
   guardados entre as iterações.

## Robustez

- Intervalos com polos ou onde a função não é real (`1/x` em torno de zero,
  `sqrt(x)` em `x < 0`) são **rejeitados no sorteio** — o TVI exige continuidade.
- Depois de localizar `c`, o resíduo `|f(c) − d|` é conferido: se a bisseção
  tiver convergido para uma descontinuidade que escapou da amostragem, o cenário
  é descartado e um novo é sorteado.
- Funções constantes não têm valor intermediário para sortear e o programa avisa
  isso explicitamente.
- Na web, `a`, `b` e `d` chegam pela URL e por isso **não são confiáveis**: antes
  de qualquer conta eles são revalidados contra a função (`d` precisa mesmo estar
  entre `f(a)` e `f(b)`), senão o pedido volta para o sorteio.

## Segurança do campo de expressão

Isto importa porque na web qualquer pessoa pode digitar ali. O `sympify` do
SymPy usa `eval` por baixo dos panos e **não** é seguro em entrada de
desconhecidos, então [funcao.py](funcao.py) filtra antes de chegar ao parser:

1. no máximo 120 caracteres e nenhum `_` — o que já derruba `__import__`,
   `__class__` e companhia;
2. lista branca de caracteres e de nomes: só passam `x`, as constantes `pi`/`e`
   e funções conhecidas (`sin`, `cos`, `exp`, `log`, `sqrt`, `abs`…);
3. `parse_expr` com escopo global reduzido aos construtores que o próprio parser
   emite, em vez do namespace inteiro do SymPy;
4. limite de complexidade na árvore resultante e expoentes até 50, para barrar
   `x**999999999` e afins.

## Publicar no Render

O [render.yaml](render.yaml) está na raiz do repositório, então o caminho é
direto: no painel do Render, **New → Blueprint**, escolher este repositório e
confirmar. Ele já traz build, start, health check e as variáveis de ambiente.

Se preferir criar à mão (New → Web Service), os valores são:

| Campo | Valor |
|---|---|
| Build Command | `pip install -r requirements.txt` |
| Start Command | `gunicorn app:app --bind 0.0.0.0:$PORT --workers 1 --threads 4 --timeout 60` |
| Health Check Path | `/saude` |

E duas variáveis de ambiente, ambas por causa do matplotlib num servidor sem
tela:

| Variável | Valor | Por quê |
|---|---|---|
| `MPLBACKEND` | `Agg` | não existe janela para abrir no contêiner |
| `MPLCONFIGDIR` | `/tmp/matplotlib` | o `HOME` do contêiner é somente leitura e o cache de fontes precisa de um lugar para morar |

Repositório privado funciona igual — o Render acessa via app do GitHub.

No plano gratuito o serviço hiberna depois de ~15 minutos parado, e a primeira
visita depois disso demora um pouco: importar matplotlib, numpy e sympy não é
barato.
