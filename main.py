"""Teorema do Valor Intermediário — sorteio de a, b e d, e localização de c.

O programa segue três passos:
    1. sorteia a, b e o valor d, e abre o gráfico com esses pontos;
    2. quando você fecha a janela, roda o cálculo;
    3. abre o gráfico de novo, agora com a seta apontando para o ponto c.

Uso rápido:
    python3 main.py                                  # pergunta a função
    python3 main.py -f "x^3 - 3*x + 1" --semente 7   # reprodutível
    python3 main.py -f "1/(1+x^2)" -d -3 3 --tabela
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np

from bissecao import SemTrocaDeSinal, bissecao, formatar_tabela
from funcao import ExpressaoInvalida, Funcao
from grafico import backend_interativo, mostrar_solucao, mostrar_sorteio
from sorteio import Cenario, SorteioImpossivel, sortear_cenario

RESIDUO_ACEITAVEL = 1e-6
MAX_SORTEIOS = 20
LARGURA = 64


def analisar_argumentos(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Sorteia a, b e d e encontra o ponto c com f(c) = d (TVI).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("-f", "--funcao", help="expressão em x, ex: 'x^3 - 3*x + 1'")
    parser.add_argument(
        "-d", "--dominio", nargs=2, type=float, metavar=("INICIO", "FIM"),
        default=[-2.0, 4.0], help="faixa de onde a e b são sorteados (padrão: -2 4)",
    )
    parser.add_argument("-s", "--semente", type=int, help="semente aleatória (torna o sorteio reprodutível)")
    parser.add_argument("-t", "--tolerancia", type=float, default=1e-12, help="erro máximo em c (padrão: 1e-12)")
    parser.add_argument("--tabela", action="store_true", help="mostra a tabela de convergência")
    parser.add_argument(
        "--salvar", metavar="PREFIXO", nargs="?", const="tvi",
        help="também salva as figuras como PREFIXO_sorteio.png e PREFIXO_solucao.png",
    )
    parser.add_argument("--sem-grafico", action="store_true", help="só imprime o resultado no terminal")
    return parser.parse_args(argv)


def _regua(titulo: str = "") -> None:
    print("─" * LARGURA if not titulo else titulo.center(LARGURA))


def imprimir_sorteio(f: Funcao, cenario: Cenario) -> None:
    print()
    print("─" * LARGURA)
    _regua("TEOREMA DO VALOR INTERMEDIÁRIO")
    print("─" * LARGURA)
    print(f"  {f}")
    print()
    print("  Pontos sorteados:")
    print(f"    a = {cenario.a:>13.6f}     f(a) = {cenario.fa:>13.6f}")
    print(f"    b = {cenario.b:>13.6f}     f(b) = {cenario.fb:>13.6f}")
    print(f"    d = {cenario.d:>13.6f}     (entre f(a) e f(b))")
    print()
    print("  Como f é contínua em [a, b] e d está entre f(a) e f(b), o TVI")
    print("  garante que existe c em (a, b) com f(c) = d.")
    print()


def imprimir_resultado(f: Funcao, cenario: Cenario, c: float, resultado, mostrar_tabela: bool) -> None:
    if mostrar_tabela:
        print("  Convergência em g(x) = f(x) - d:")
        print(formatar_tabela(resultado.historico, ultimas=12))
        print()

    print(f"  Resultado após {resultado.iteracoes} iterações:")
    print()
    print(f"    ► c = ({c:.6f}, {cenario.d:.6f})")
    print()
    print(f"    f(c) = {f(c):.6f}")
    print(f"    resíduo |f(c) - d| = {abs(f(c) - cenario.d):.2e}")
    print(f"    erro máximo em c   = {resultado.erro:.2e}")
    if not resultado.convergiu:
        print("    (atenção: parou no limite de iterações ou na precisão da máquina)")
    print("─" * LARGURA)
    print()


def main(argv: list[str] | None = None) -> int:
    args = analisar_argumentos(argv)

    texto = args.funcao
    if texto is None:
        try:
            texto = input("Digite uma função de x (ex: x^3 - 3*x + 1): ")
        except (EOFError, KeyboardInterrupt):
            print()
            return 1

    try:
        f = Funcao(texto)
    except ExpressaoInvalida as erro:
        print(f"Erro: {erro}", file=sys.stderr)
        return 1

    rng = np.random.default_rng(args.semente)
    dominio = (args.dominio[0], args.dominio[1])

    desenhar = not args.sem_grafico
    prefixo = args.salvar
    if desenhar and prefixo is None and not backend_interativo():
        prefixo = "tvi"
        print(
            "Aviso: nenhum backend gráfico interativo disponível; "
            "as figuras serão salvas em arquivo.",
            file=sys.stderr,
        )

    for _ in range(MAX_SORTEIOS):
        try:
            cenario = sortear_cenario(f, dominio, rng)
        except (SorteioImpossivel, ValueError) as erro:
            print(f"Erro: {erro}", file=sys.stderr)
            return 1

        # ── passo 1: mostra o problema, sem a resposta ──────────────────────
        imprimir_sorteio(f, cenario)
        if desenhar:
            print("  Abrindo o gráfico — feche a janela para calcular o ponto c.")
            print()
            mostrar_sorteio(
                f, cenario, dominio,
                saida=Path(f"{prefixo}_sorteio.png") if prefixo else None,
            )

        # ── passo 2: agora sim, a bisseção ──────────────────────────────────
        try:
            resultado = bissecao(
                lambda x: f(x) - cenario.d, cenario.a, cenario.b, tolerancia=args.tolerancia
            )
        except SemTrocaDeSinal as erro:  # pragma: no cover - o sorteio garante a troca
            print(f"  Cenário descartado ({erro}). Sorteando de novo...\n")
            continue

        c = resultado.raiz
        if abs(f(c) - cenario.d) > RESIDUO_ACEITAVEL:
            # a bisseção convergiu para um salto da função, não para um c legítimo
            print("  O cálculo caiu numa descontinuidade. Sorteando outro cenário...\n")
            continue

        # ── passo 3: a resposta ─────────────────────────────────────────────
        imprimir_resultado(f, cenario, c, resultado, args.tabela)
        if desenhar:
            caminho = mostrar_solucao(
                f, cenario, c, dominio,
                saida=Path(f"{prefixo}_solucao.png") if prefixo else None,
            )
            if caminho is not None:
                print(f"  Figuras salvas em: {caminho.parent.resolve()}")
                print()
        return 0

    print(
        f"Erro: não consegui localizar um c confiável após {MAX_SORTEIOS} sorteios. "
        "A função provavelmente é descontínua nesse domínio — tente outro --dominio.",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
