"""Interpretação segura de expressões matemáticas digitadas pelo usuário.

O `sympify` do SymPy usa `eval` por baixo dos panos, então **não** é seguro em
entrada vinda da internet. Aqui a expressão passa por três filtros antes de
chegar ao parser:

  1. tamanho máximo e nenhum `_` (mata qualquer tentativa de `__import__`);
  2. lista branca de caracteres e de nomes — só `x`, constantes e funções
     matemáticas conhecidas passam;
  3. limite de complexidade da árvore resultante, para não aceitar expressões
     absurdas de avaliar (`x**999999`).

Só depois disso a expressão é compilada para NumPy.
"""

from __future__ import annotations

import re

import numpy as np
import sympy as sp
from sympy.parsing.sympy_parser import (
    convert_xor,
    parse_expr,
    standard_transformations,
)

X = sp.Symbol("x", real=True)

TAMANHO_MAXIMO = 120
OPERACOES_MAXIMAS = 60
EXPOENTE_MAXIMO = 50

# tudo que o usuário pode escrever, e nada mais
NOMES_PERMITIDOS = (
    "x", "pi", "E", "e",
    "sin", "cos", "tan", "cot", "sec", "csc",
    "asin", "acos", "atan",
    "sinh", "cosh", "tanh",
    "exp", "log", "ln", "sqrt", "cbrt", "abs", "Abs", "sign",
    "floor", "ceiling",
)
CARACTERES_VALIDOS = re.compile(r"^[0-9A-Za-z+\-*/^().,\s]+$")
PALAVRAS = re.compile(r"[A-Za-z]+")

_TRANSFORMACOES = standard_transformations + (convert_xor,)

# O parser reescreve "3" como "Integer(3)" e nomes soltos como "Symbol('nome')",
# então esses construtores precisam existir no escopo global do eval interno —
# e nada além deles.
GLOBAIS = {
    "Integer": sp.Integer,
    "Float": sp.Float,
    "Rational": sp.Rational,
    "Symbol": sp.Symbol,
}


def _montar_ambiente() -> dict[str, object]:
    ambiente: dict[str, object] = {"x": X}
    for nome in NOMES_PERMITIDOS:
        if hasattr(sp, nome):
            ambiente[nome] = getattr(sp, nome)
    ambiente["abs"] = sp.Abs
    ambiente["ln"] = sp.log
    ambiente["e"] = sp.E
    return ambiente


AMBIENTE = _montar_ambiente()


class ExpressaoInvalida(ValueError):
    """A expressão digitada não pôde ser interpretada (ou não é permitida)."""


def _normalizar(texto: str) -> str:
    """Limpa a entrada e aceita alguns vícios comuns de digitação."""
    limpo = texto.strip()
    limpo = re.sub(r"^@\s*\(\s*x\s*\)", "", limpo)  # tolera o formato do MATLAB
    limpo = re.sub(r"^\s*(f\s*\(\s*x\s*\)|y)\s*=", "", limpo)  # tolera "f(x) = ..."
    return limpo.strip()


def _validar(texto: str) -> None:
    """Aplica a lista branca. Levanta ExpressaoInvalida em qualquer desvio."""
    if not texto:
        raise ExpressaoInvalida("Nenhuma expressão foi digitada.")
    if len(texto) > TAMANHO_MAXIMO:
        raise ExpressaoInvalida(f"A expressão passa de {TAMANHO_MAXIMO} caracteres.")
    if "_" in texto:
        raise ExpressaoInvalida("O caractere '_' não é permitido.")
    if not CARACTERES_VALIDOS.match(texto):
        raise ExpressaoInvalida("A expressão tem caracteres que não são permitidos.")

    permitidos = set(NOMES_PERMITIDOS)
    for palavra in PALAVRAS.findall(texto):
        if palavra not in permitidos:
            raise ExpressaoInvalida(
                f"'{palavra}' não é uma função conhecida. "
                f"Use apenas x e funções como sin, cos, exp, log, sqrt."
            )


def _conferir_complexidade(expr) -> None:
    """Barra expressões caras demais para avaliar milhares de vezes."""
    if sp.count_ops(expr) > OPERACOES_MAXIMAS:
        raise ExpressaoInvalida("A expressão é complicada demais.")

    for potencia in expr.atoms(sp.Pow):
        expoente = potencia.exp
        if expoente.is_number:
            try:
                if abs(float(expoente)) > EXPOENTE_MAXIMO:
                    raise ExpressaoInvalida(
                        f"Expoentes acima de {EXPOENTE_MAXIMO} não são permitidos."
                    )
            except (TypeError, ValueError):  # expoente complexo ou infinito
                raise ExpressaoInvalida("Expoente inválido.") from None


def _para_real(bruto, forma: tuple[int, ...]) -> np.ndarray:
    """Converte o resultado do SymPy em vetor de floats, com NaN onde não há valor real."""
    valores = np.asarray(bruto)

    if valores.shape != forma:  # a função era constante: o retorno veio como escalar
        valores = np.broadcast_to(valores, forma)

    if np.iscomplexobj(valores):
        valores = np.where(np.abs(valores.imag) < 1e-12, valores.real, np.nan)

    valores = valores.astype(float, copy=True)
    return np.where(np.isfinite(valores), valores, np.nan)


class Funcao:
    """Uma função real de uma variável, construída a partir de texto.

    >>> f = Funcao("x^3 - 3*x + 1")
    >>> round(f(2), 6)
    3.0
    >>> Funcao("__import__('os')")
    Traceback (most recent call last):
        ...
    funcao.ExpressaoInvalida: O caractere '_' não é permitido.
    """

    def __init__(self, texto: str) -> None:
        self.texto = _normalizar(texto)
        _validar(self.texto)

        try:
            self.expr = parse_expr(
                self.texto,
                local_dict=AMBIENTE,
                global_dict=GLOBAIS,
                transformations=_TRANSFORMACOES,
            )
        except ExpressaoInvalida:
            raise
        except Exception as erro:  # o parser do SymPy levanta de tudo
            raise ExpressaoInvalida(f"Não consegui interpretar '{texto}': {erro}") from erro

        if not isinstance(self.expr, sp.Expr):
            raise ExpressaoInvalida("Isso não é uma expressão matemática.")

        desconhecidos = self.expr.free_symbols - {X}
        if desconhecidos:
            nomes = ", ".join(sorted(str(s) for s in desconhecidos))
            raise ExpressaoInvalida(
                f"A expressão só pode depender de x, mas apareceu: {nomes}."
            )

        _conferir_complexidade(self.expr)
        self._numerica = sp.lambdify(X, self.expr, "numpy")

    def __call__(self, valor: float) -> float:
        """Avalia em um ponto. Devolve NaN se a função não estiver definida ali."""
        return float(self.avaliar(np.array([float(valor)]))[0])

    def avaliar(self, xs) -> np.ndarray:
        """Avalia em um vetor, devolvendo NaN onde a função não está definida."""
        xs = np.asarray(xs, dtype=float)
        with np.errstate(all="ignore"):
            bruto = self._numerica(xs)
        return _para_real(bruto, xs.shape)

    def esta_definida(self, valor: float) -> bool:
        return bool(np.isfinite(self(valor)))

    @property
    def latex(self) -> str:
        return sp.latex(self.expr)

    def __str__(self) -> str:
        return f"f(x) = {self.texto}"
