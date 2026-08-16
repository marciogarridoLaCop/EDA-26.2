"""O desenho do TVI, em duas etapas: o sorteio e a solução.

Este módulo **não** importa `pyplot` no topo de propósito. O `pyplot` guarda
estado global (a lista de janelas abertas) e não é seguro num servidor web com
várias requisições ao mesmo tempo. As figuras são criadas com `Figure` direto,
e o `pyplot` só aparece — importado lá dentro — nas funções de janela do
programa de terminal.

    montar()            desenha numa figura já existente
    svg()               devolve a figura como SVG, para a web
    mostrar_sorteio()   abre a janela 1 (terminal)
    mostrar_solucao()   abre a janela 2 (terminal)
"""

from __future__ import annotations

import io
import re
from pathlib import Path

import numpy as np
import sympy as sp
from matplotlib.figure import Figure

from funcao import Funcao
from sorteio import Cenario

# Paleta validada (modo claro): curva no azul da série 1, construção no vermelho
# da série 8. Textos usam tinta neutra, nunca a cor da série.
SUPERFICIE = "#fcfcfb"
TINTA_FORTE = "#0b0b0b"
TINTA_FRACA = "#52514e"
CURVA = "#2a78d6"
DESTAQUE = "#e34948"
GRADE = "#e3e3e0"

TAMANHO = (10.0, 6.5)


def _limites_y(ys_intervalo: np.ndarray, obrigatorios: list[float]) -> tuple[float, float]:
    """Enquadra pelo trecho [a, b] da curva, não pelo domínio inteiro.

    Fora de [a, b] a função pode crescer sem limite (um polinômio de grau alto,
    por exemplo) e achatar justamente a região onde a construção acontece.
    """
    finitos = ys_intervalo[np.isfinite(ys_intervalo)]
    candidatos = [*obrigatorios]
    if finitos.size:
        candidatos += [float(finitos.min()), float(finitos.max())]

    base, topo = min(candidatos), max(candidatos)
    folga = 0.18 * (topo - base) if topo > base else 1.0
    return base - folga, topo + folga


def _cabecalho(fig: Figure, funcao: Funcao) -> None:
    """Usa a notação matemática do SymPy, caindo para o texto puro se não renderizar."""
    try:
        fig.suptitle(
            f"$f(x) = {funcao.latex}$", color=TINTA_FORTE, fontsize=15, y=0.97, va="top"
        )
        fig.draw_without_rendering()
    except Exception:
        fig.suptitle(
            f"f(x) = {funcao.texto}", color=TINTA_FORTE, fontsize=15, y=0.97, va="top"
        )


def _fracao_na_figura(ax, x: float, y: float) -> dict[str, float]:
    """Converte um ponto dos eixos em fração da figura (0–1).

    É o que permite ao HTML posicionar um marcador em cima do SVG, já que a
    página não sabe nada sobre as coordenadas do gráfico.
    """
    caixa = ax.get_position()
    x0, x1 = ax.get_xlim()
    y0, y1 = ax.get_ylim()
    return {
        "x": caixa.x0 + (x - x0) / (x1 - x0) * caixa.width,
        "y": 1.0 - (caixa.y0 + (y - y0) / (y1 - y0) * caixa.height),  # CSS conta de cima
    }


def montar(
    fig: Figure,
    funcao: Funcao,
    cenario: Cenario,
    dominio: tuple[float, float],
    c: float | None = None,
    legenda: str | None = None,
    titulo: bool = True,
) -> dict[str, float] | None:
    """Desenha o gráfico na figura dada.

    Sem `c`, sai o sorteio: os pontos e a reta y = d tracejada, sem resposta.
    Com `c`, sai a solução: a reta para no ponto e a seta o aponta.

    `titulo=False` omite o "f(x) = ..." — na web quem escreve isso é a página,
    em tipografia melhor que a do matplotlib.

    Devolve a posição de `c` em fração da figura, ou None no caso do sorteio.
    """
    inicio, fim = dominio
    folga_x = 0.05 * (fim - inicio)
    xs = np.linspace(inicio - folga_x, fim + folga_x, 2000)
    ys = funcao.avaliar(xs)

    fig.set_facecolor(SUPERFICIE)
    ax = fig.subplots()
    ax.set_facecolor(SUPERFICIE)

    ys_intervalo = funcao.avaliar(np.linspace(cenario.a, cenario.b, 400))
    base_y, topo_y = _limites_y(ys_intervalo, [cenario.fa, cenario.fb, cenario.d])
    ax.set_xlim(xs[0], xs[-1])
    ax.set_ylim(base_y, topo_y)

    ax.grid(True, color=GRADE, linewidth=0.8, zorder=0)
    ax.set_axisbelow(True)
    for lado in ("top", "right"):
        ax.spines[lado].set_visible(False)
    for lado in ("left", "bottom"):
        ax.spines[lado].set_color(GRADE)
    ax.tick_params(colors=TINTA_FRACA, labelsize=10)
    ax.set_xlabel("x", color=TINTA_FRACA, fontsize=11)
    ax.set_ylabel("y", color=TINTA_FRACA, fontsize=11)

    if base_y < 0 < topo_y:
        ax.axhline(0, color=GRADE, linewidth=1.2, zorder=1)
    if xs[0] < 0 < xs[-1]:
        ax.axvline(0, color=GRADE, linewidth=1.2, zorder=1)

    ax.plot(xs, ys, color=CURVA, linewidth=2, zorder=3)

    # a faixa entre f(a) e f(b): onde o TVI garante solução
    menor, maior = sorted((cenario.fa, cenario.fb))
    ax.axhspan(menor, maior, color=CURVA, alpha=0.06, zorder=1)
    for altura, rotulo in ((cenario.fa, "f(a)"), (cenario.fb, "f(b)")):
        ax.axhline(altura, color=TINTA_FRACA, linewidth=1, linestyle=":", alpha=0.55, zorder=2)
        ax.annotate(
            f"{rotulo} = {altura:.4f}", xy=(xs[0], altura), xytext=(4, 5),
            textcoords="offset points", color=TINTA_FRACA, fontsize=9,
        )

    # os extremos sorteados — rótulos apontados para fora, longe do miolo
    for x_ponto, y_ponto, rotulo, lado in (
        (cenario.a, cenario.fa, "a", -1),
        (cenario.b, cenario.fb, "b", +1),
    ):
        ax.plot(
            x_ponto, y_ponto, "o", markersize=9, color=TINTA_FORTE,
            markeredgecolor=SUPERFICIE, markeredgewidth=2, zorder=5,
        )
        ax.annotate(
            f"{rotulo} = {x_ponto:.4f}",
            xy=(x_ponto, y_ponto), xytext=(12 * lado, -16),
            textcoords="offset points",
            ha="left" if lado > 0 else "right",
            color=TINTA_FORTE, fontsize=10, fontweight="bold",
        )

    if c is None:
        # ── o problema: a reta y = d atravessa tudo, sem tocar em nada ──
        ax.axhline(cenario.d, color=DESTAQUE, linewidth=2, linestyle="--", zorder=4)
        ax.annotate(
            f"d = {cenario.d:.4f}", xy=(xs[-1], cenario.d), xytext=(-6, 8),
            textcoords="offset points", ha="right",
            color=DESTAQUE, fontsize=11, fontweight="bold",
        )
    else:
        # ── a resposta: a reta para em c e desce até o eixo ──
        ax.plot([xs[0], c], [cenario.d, cenario.d], color=DESTAQUE, linewidth=2, zorder=4)
        ax.plot([c, c], [base_y, cenario.d], color=DESTAQUE, linewidth=2, zorder=4)
        ax.annotate(
            f"d = {cenario.d:.4f}", xy=(xs[0], cenario.d), xytext=(6, 8),
            textcoords="offset points", color=DESTAQUE, fontsize=11, fontweight="bold",
        )
        ax.plot(
            c, cenario.d, "o", markersize=11, color=DESTAQUE,
            markeredgecolor=SUPERFICIE, markeredgewidth=2, zorder=6,
        )

        para_esquerda = c > (xs[0] + xs[-1]) / 2
        ax.annotate(
            f"c = ({c:.6f},  {cenario.d:.6f})",
            xy=(c, cenario.d),
            xytext=(-75, 55) if para_esquerda else (75, 55),
            textcoords="offset points",
            ha="right" if para_esquerda else "left",
            va="center",
            fontsize=11.5,
            color=TINTA_FORTE,
            bbox=dict(boxstyle="round,pad=0.5", facecolor=SUPERFICIE, edgecolor=DESTAQUE, alpha=0.95),
            arrowprops=dict(
                arrowstyle="-|>", color=DESTAQUE, linewidth=1.8, shrinkA=2, shrinkB=9,
                connectionstyle=f"arc3,rad={0.25 if para_esquerda else -0.25}",
            ),
            zorder=7,
        )

    if titulo:
        _cabecalho(fig, funcao)

    base_rodape = 0.04 if legenda else 0.0
    topo = 0.93 if titulo else 0.98
    if legenda:
        fig.text(
            0.5, 0.015, legenda, ha="center", color=TINTA_FRACA, fontsize=10.5, style="italic"
        )
    fig.tight_layout(rect=(0, base_rodape, 1, topo))

    return None if c is None else _fracao_na_figura(ax, c, cenario.d)


# ─────────────────────────── saída para a web ────────────────────────────

_ATRIBUTOS_FIXOS = re.compile(r'(<svg[^>]*?)\s+width="[^"]*"\s+height="[^"]*"')


def svg(
    funcao: Funcao,
    cenario: Cenario,
    dominio: tuple[float, float],
    c: float | None = None,
    tamanho: tuple[float, float] = TAMANHO,
) -> tuple[str, dict[str, float] | None]:
    """Devolve (svg, posição de c). O SVG vem sem width/height, para escalar sozinho."""
    fig = Figure(figsize=tamanho, facecolor=SUPERFICIE)
    posicao = montar(fig, funcao, cenario, dominio, c=c, titulo=False)

    buffer = io.BytesIO()
    fig.savefig(buffer, format="svg", facecolor=SUPERFICIE)
    desenho = buffer.getvalue().decode("utf-8")

    # sem width/height fixos, o SVG obedece ao contêiner via viewBox
    desenho = _ATRIBUTOS_FIXOS.sub(r"\1", desenho, count=1)
    return desenho[desenho.index("<svg") :], posicao


# ──────────────────────── janelas do programa de terminal ────────────────────

def _janela(
    funcao: Funcao,
    cenario: Cenario,
    dominio: tuple[float, float],
    legenda: str,
    c: float | None,
    saida: Path | None,
) -> Path | None:
    import matplotlib
    import matplotlib.pyplot as plt

    fig = plt.figure(figsize=TAMANHO, facecolor=SUPERFICIE)
    montar(fig, funcao, cenario, dominio, c=c, legenda=legenda)

    caminho = None
    if saida is not None:
        caminho = Path(saida)
        caminho.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(caminho, dpi=200, facecolor=SUPERFICIE)

    interativo = matplotlib.get_backend().lower() in {
        nome.lower() for nome in matplotlib.rcsetup.interactive_bk
    }
    if interativo:
        plt.show()  # bloqueia até a janela ser fechada
    plt.close(fig)
    return caminho


def backend_interativo() -> bool:
    """Diz se há uma janela de verdade para abrir (senão, só resta salvar arquivo)."""
    import matplotlib

    atual = matplotlib.get_backend().lower()
    return atual in {nome.lower() for nome in matplotlib.rcsetup.interactive_bk}


def mostrar_sorteio(
    funcao: Funcao, cenario: Cenario, dominio: tuple[float, float], saida: Path | None = None
) -> Path | None:
    """Janela 1: os pontos sorteados e a reta y = d, sem a resposta."""
    return _janela(
        funcao, cenario, dominio,
        "Onde a reta y = d corta a curva?   Feche esta janela para calcular o ponto c.",
        c=None, saida=saida,
    )


def mostrar_solucao(
    funcao: Funcao,
    cenario: Cenario,
    c: float,
    dominio: tuple[float, float],
    saida: Path | None = None,
) -> Path | None:
    """Janela 2: a mesma figura, agora com o ponto c e a seta."""
    return _janela(
        funcao, cenario, dominio,
        f"O TVI garante este ponto:  f({c:.6f}) = {cenario.d:.6f}",
        c=c, saida=saida,
    )
