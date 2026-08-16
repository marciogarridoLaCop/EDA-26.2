"""Versão web do TVI — o mesmo fluxo de dois passos, agora em duas páginas.

    /            formulário: a função e o domínio
    /sorteio     os pontos a, b e d, e a reta y = d sem tocar em nada
    /solucao     a bisseção rodou: o ponto c, a seta e os números

O estado vai todo na URL (função, a, b, d), então não há sessão nem banco: cada
página é reproduzível por link, e o servidor pode reiniciar sem perder nada.
Nada que vem da URL é aceito sem conferência — inclusive a, b e d, que são
revalidados contra a função antes de qualquer conta.
"""

from __future__ import annotations

import html
import os
import re

import numpy as np
import sympy as sp
from flask import Flask, redirect, render_template, request, url_for
from markupsafe import Markup

from bissecao import SemTrocaDeSinal, bissecao
from funcao import ExpressaoInvalida, Funcao
from grafico import svg
from sorteio import SorteioImpossivel, Cenario, sortear_cenario

app = Flask(__name__)

FUNCAO_PADRAO = "x^3 - 3*x + 1"
DOMINIO_PADRAO = (-2.0, 4.0)
LIMITE_DOMINIO = 1e6
LARGURA_MAXIMA = 1e5
RESIDUO_ACEITAVEL = 1e-6
TOLERANCIA = 1e-12

EXEMPLOS = [
    ("x^3 - 3*x + 1", "-2 4"),
    ("cos(x)*exp(-x/3)", "-4 4"),
    ("x^2 - 4", "-3 3"),
    ("sin(x) + x/2", "-6 6"),
    ("1/(1+x^2)", "-4 4"),
    ("sqrt(x+5) - 1", "-4 6"),
]


# ──────────────────────────── entrada da URL ─────────────────────────────

class EntradaInvalida(ValueError):
    """Algum parâmetro da URL não serve."""


def _float(nome: str, valor: str | None, padrao: float | None = None) -> float:
    if valor is None or valor == "":
        if padrao is None:
            raise EntradaInvalida(f"Faltou o parâmetro '{nome}'.")
        return padrao
    try:
        numero = float(valor)
    except (TypeError, ValueError):
        raise EntradaInvalida(f"'{nome}' precisa ser um número.") from None
    if not np.isfinite(numero) or abs(numero) > LIMITE_DOMINIO:
        raise EntradaInvalida(f"'{nome}' está fora da faixa permitida.")
    return numero


def _ler_dominio(args) -> tuple[float, float]:
    inicio = _float("x0", args.get("x0"), DOMINIO_PADRAO[0])
    fim = _float("x1", args.get("x1"), DOMINIO_PADRAO[1])
    if fim <= inicio:
        raise EntradaInvalida("O fim do domínio precisa ser maior que o início.")
    if fim - inicio > LARGURA_MAXIMA:
        raise EntradaInvalida("O domínio é largo demais.")
    return inicio, fim


def _ler_funcao(args) -> Funcao:
    return Funcao(args.get("f") or FUNCAO_PADRAO)


def _ler_semente(args) -> int | None:
    bruto = args.get("semente")
    if not bruto:
        return None
    try:
        return int(bruto) % (2**32)
    except (TypeError, ValueError):
        return None


# ──────────────────────────── apresentação ───────────────────────────────

_EXPOENTE = re.compile(r"\*\*\(?(-?[\w./]+)\)?")


def expressao_html(expr) -> Markup:
    """Uma versão legível da expressão para o cabeçalho: x**3 vira x³ de verdade."""
    texto = html.escape(sp.sstr(expr))
    texto = _EXPOENTE.sub(r"<sup>\1</sup>", texto)
    texto = texto.replace("*", "·")
    return Markup(texto)


def _parametros(funcao: Funcao, dominio: tuple[float, float], **extras) -> dict:
    base = {"f": funcao.texto, "x0": repr(dominio[0]), "x1": repr(dominio[1])}
    base.update({chave: repr(valor) for chave, valor in extras.items()})
    return base


def _voltar_com_erro(erro: object):
    """Devolve ao formulário preservando o que a pessoa já tinha digitado."""
    campos = {chave: valor for chave, valor in request.args.items() if chave != "erro"}
    return redirect(url_for("inicio", erro=str(erro), **campos))


# ──────────────────────────────── rotas ──────────────────────────────────

@app.route("/")
def inicio():
    return render_template(
        "inicio.html",
        funcao=request.args.get("f", FUNCAO_PADRAO),
        x0=request.args.get("x0", DOMINIO_PADRAO[0]),
        x1=request.args.get("x1", DOMINIO_PADRAO[1]),
        exemplos=EXEMPLOS,
        erro=request.args.get("erro"),
    )


@app.route("/sorteio")
def sorteio():
    """Passo 1: sorteia a, b e d, e mostra o problema — sem a resposta."""
    try:
        funcao = _ler_funcao(request.args)
        dominio = _ler_dominio(request.args)
        rng = np.random.default_rng(_ler_semente(request.args))
        cenario = sortear_cenario(funcao, dominio, rng)
    except (ExpressaoInvalida, EntradaInvalida, SorteioImpossivel, ValueError) as erro:
        return _voltar_com_erro(erro)

    desenho, _ = svg(funcao, cenario, dominio)
    return render_template(
        "sorteio.html",
        funcao=funcao,
        expressao=expressao_html(funcao.expr),
        cenario=cenario,
        dominio=dominio,
        desenho=Markup(desenho),
        link_solucao=url_for(
            "solucao", **_parametros(funcao, dominio, a=cenario.a, b=cenario.b, d=cenario.d)
        ),
        link_outro=url_for("sorteio", **_parametros(funcao, dominio)),
    )


@app.route("/solucao")
def solucao():
    """Passo 2: roda a bisseção e mostra o ponto c."""
    try:
        funcao = _ler_funcao(request.args)
        dominio = _ler_dominio(request.args)
        a = _float("a", request.args.get("a"))
        b = _float("b", request.args.get("b"))
        d = _float("d", request.args.get("d"))
    except (ExpressaoInvalida, EntradaInvalida) as erro:
        return _voltar_com_erro(erro)

    # nada que veio da URL é confiável: o cenário é reconferido contra a função
    fa, fb = funcao(a), funcao(b)
    menor, maior = sorted((fa, fb))
    if not (a < b and np.isfinite(fa) and np.isfinite(fb) and menor < d < maior):
        return redirect(url_for("sorteio", **_parametros(funcao, dominio)))

    cenario = Cenario(a=a, fa=fa, b=b, fb=fb, d=d)
    try:
        resultado = bissecao(lambda x: funcao(x) - d, a, b, tolerancia=TOLERANCIA)
    except SemTrocaDeSinal:
        return redirect(url_for("sorteio", **_parametros(funcao, dominio)))

    c = resultado.raiz
    residuo = abs(funcao(c) - d)
    if residuo > RESIDUO_ACEITAVEL:
        # a bisseção convergiu para uma descontinuidade, não para um c legítimo
        return redirect(url_for("sorteio", **_parametros(funcao, dominio)))

    desenho, posicao = svg(funcao, cenario, dominio, c=c)
    return render_template(
        "solucao.html",
        funcao=funcao,
        expressao=expressao_html(funcao.expr),
        cenario=cenario,
        resultado=resultado,
        c=c,
        residuo=residuo,
        desenho=Markup(desenho),
        posicao=posicao,
        link_outro=url_for("sorteio", **_parametros(funcao, dominio)),
    )


@app.route("/saude")
def saude():
    """Endpoint de health check do Render."""
    return {"ok": True}


if __name__ == "__main__":
    app.run(debug=True, port=int(os.environ.get("PORT", 5000)))
