"""Sorteio aleatório do cenário do Teorema do Valor Intermediário.

Sorteamos dois pontos a < b no domínio e um valor d estritamente entre f(a) e
f(b). O TVI garante que existe pelo menos um c em (a, b) com f(c) = d — ou
seja, o sorteio nunca produz um problema sem solução, desde que f seja
contínua no intervalo.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from funcao import Funcao


@dataclass
class Cenario:
    """Os três valores sorteados, com f já avaliada nos extremos."""

    a: float
    fa: float
    b: float
    fb: float
    d: float

    @property
    def largura(self) -> float:
        return self.b - self.a


class SorteioImpossivel(RuntimeError):
    """Não foi possível sortear um intervalo utilizável nesta função."""


def _intervalo_utilizavel(f: Funcao, a: float, b: float, amostras: int = 201) -> bool:
    """Rejeita intervalos onde a função explode ou não está definida (polos, raízes de negativos)."""
    ys = f.avaliar(np.linspace(a, b, amostras))
    return bool(np.all(np.isfinite(ys)))


def sortear_cenario(
    f: Funcao,
    dominio: tuple[float, float],
    rng: np.random.Generator,
    largura_minima: float = 0.30,
    margem: float = 0.15,
    tentativas: int = 300,
) -> Cenario:
    """Sorteia a, b e d.

    `largura_minima` é a fração do domínio que [a, b] precisa cobrir (evita
    intervalos minúsculos, ruins de visualizar) e `margem` afasta d das pontas
    f(a) e f(b), para que o c encontrado fique visivelmente dentro do intervalo.
    """
    inicio, fim = dominio
    if fim <= inicio:
        raise ValueError("O domínio precisa ter início menor que fim.")

    largura_exigida = largura_minima * (fim - inicio)

    for _ in range(tentativas):
        a, b = np.sort(rng.uniform(inicio, fim, size=2))
        if b - a < largura_exigida:
            continue

        fa, fb = f(a), f(b)
        if not (np.isfinite(fa) and np.isfinite(fb)):
            continue

        menor, maior = sorted((fa, fb))
        altura = maior - menor
        if altura < 1e-9:  # f(a) == f(b): não há valor intermediário para sortear
            continue

        if not _intervalo_utilizavel(f, a, b):
            continue

        d = float(rng.uniform(menor + margem * altura, maior - margem * altura))
        return Cenario(a=float(a), fa=float(fa), b=float(b), fb=float(fb), d=d)

    raise SorteioImpossivel(
        f"Não achei um intervalo utilizável em [{inicio}, {fim}] após {tentativas} tentativas. "
        "A função pode ser constante, descontínua ou indefinida nessa faixa — "
        "tente outro domínio."
    )
