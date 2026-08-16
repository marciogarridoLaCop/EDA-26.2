"""Método da bisseção (Bolzano).

Aqui ele é usado como motor do Teorema do Valor Intermediário: para achar o
ponto c com f(c) = d, aplicamos a bisseção em g(x) = f(x) - d, cuja raiz é
exatamente esse c.

Detalhes que importam:
  * o critério de parada é a largura do intervalo (erro no eixo x), não a
    diferença entre os valores da função (erro no eixo y);
  * g(meio) == 0 encerra o laço, em vez de travá-lo;
  * cada iteração faz uma única avaliação de g.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Callable


@dataclass
class Passo:
    """Uma linha da tabela de convergência."""

    iteracao: int
    esquerda: float
    direita: float
    meio: float
    valor: float


@dataclass
class Resultado:
    raiz: float
    valor: float
    iteracoes: int
    erro: float
    convergiu: bool
    historico: list[Passo] = field(default_factory=list)


class SemTrocaDeSinal(ValueError):
    """O intervalo não satisfaz a hipótese de Bolzano."""


def bissecao(
    g: Callable[[float], float],
    a: float,
    b: float,
    tolerancia: float = 1e-12,
    max_iter: int = 200,
) -> Resultado:
    """Localiza uma raiz de `g` em [a, b], supondo troca de sinal nos extremos."""
    if a > b:
        a, b = b, a

    ga, gb = g(a), g(b)
    if not (math.isfinite(ga) and math.isfinite(gb)):
        raise SemTrocaDeSinal("A função não está definida em um dos extremos do intervalo.")
    if ga == 0.0:
        return Resultado(a, 0.0, 0, 0.0, True)
    if gb == 0.0:
        return Resultado(b, 0.0, 0, 0.0, True)
    if ga * gb > 0.0:
        raise SemTrocaDeSinal(
            "Não há troca de sinal em [a, b]: a bisseção não se aplica nesse intervalo."
        )

    esquerda, direita = a, b
    meio = (esquerda + direita) / 2
    valor = g(meio)
    historico: list[Passo] = []
    iteracao = 0

    while (direita - esquerda) / 2 > tolerancia and iteracao < max_iter:
        iteracao += 1
        meio = (esquerda + direita) / 2
        valor = g(meio)
        historico.append(Passo(iteracao, esquerda, direita, meio, valor))

        if valor == 0.0:  # raiz exata
            esquerda = direita = meio
            break

        if meio == esquerda or meio == direita:  # limite da precisão da máquina
            break

        if ga * valor < 0.0:  # a troca de sinal está em [esquerda, meio]
            direita = meio
        else:  # a troca de sinal está em [meio, direita]
            esquerda = meio
            ga = valor

    erro = (direita - esquerda) / 2
    return Resultado(meio, valor, iteracao, erro, erro <= tolerancia, historico)


def formatar_tabela(historico: list[Passo], ultimas: int | None = None) -> str:
    """Monta a tabela de convergência para exibir no terminal."""
    if not historico:
        return "  (a raiz coincidiu com um dos extremos; nenhuma iteração foi necessária)"

    linhas = historico if ultimas is None else historico[-ultimas:]
    cabecalho = f"  {'iter':>4} {'a':>14} {'b':>14} {'c':>14} {'g(c)':>13}"
    corpo = [
        f"  {p.iteracao:>4} {p.esquerda:>14.9f} {p.direita:>14.9f} "
        f"{p.meio:>14.9f} {p.valor:>13.2e}"
        for p in linhas
    ]
    if ultimas is not None and len(historico) > ultimas:
        corpo.insert(0, f"  {'...':>4} ({len(historico) - ultimas} iterações omitidas)")
    return "\n".join([cabecalho, *corpo])
