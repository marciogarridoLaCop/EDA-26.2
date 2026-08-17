// Revela o ponto c trocando só os pedaços que mudam, sem recarregar a página.
//
// O botão continua sendo um link de verdade para /solucao: sem JavaScript, ou
// se a requisição falhar, a navegação normal acontece e nada se perde.

(() => {
  "use strict";

  const enderecoDaApi = (href) => {
    const url = new URL(href, location.href);
    url.pathname = "/api/solucao";
    return url.toString();
  };

  // guarda a resposta buscada na passagem do mouse, para o clique ser instantâneo
  const cache = new Map();

  const buscar = (href) => {
    const chave = enderecoDaApi(href);
    if (!cache.has(chave)) {
      cache.set(
        chave,
        fetch(chave, { headers: { Accept: "application/json" } }).then((r) => {
          if (!r.ok) throw new Error(`resposta ${r.status}`);
          return r.json();
        })
      );
    }
    return cache.get(chave);
  };

  // a trilha vem como <nav>…</nav>; aqui só interessa o que está dentro dela
  const extrairMiolo = (html) => {
    const molde = document.createElement("div");
    molde.innerHTML = html.trim();
    return molde.firstElementChild ? molde.firstElementChild.innerHTML : html;
  };

  const trocar = (seletor, marcacao) => {
    const alvo = document.querySelector(seletor);
    if (alvo && typeof marcacao === "string") alvo.innerHTML = marcacao;
  };

  document.addEventListener("mouseenter", (evento) => {
    const gatilho = evento.target.closest?.("[data-revelar]");
    if (gatilho) buscar(gatilho.href).catch(() => {});
  }, true);

  document.addEventListener("click", async (evento) => {
    const gatilho = evento.target.closest("[data-revelar]");
    if (!gatilho) return;
    // deixa passar o que o navegador faz melhor: nova aba, nova janela, download
    if (evento.button !== 0 || evento.metaKey || evento.ctrlKey || evento.shiftKey || evento.altKey) {
      return;
    }

    evento.preventDefault();
    const prancha = document.querySelector(".prancha");
    gatilho.setAttribute("aria-busy", "true");
    prancha?.classList.add("calculando");

    try {
      const dados = await buscar(gatilho.href);

      trocar(".cabecalho-pagina", dados.cabecalho);
      trocar(".prancha", dados.figura);
      trocar(".ficha", dados.ficha);
      trocar(".trilha", dados.trilha ? extrairMiolo(dados.trilha) : null);
      if (dados.titulo) document.title = dados.titulo;
      if (dados.url) history.pushState({ revelado: true }, "", dados.url);
    } catch (erro) {
      location.href = gatilho.href; // qualquer tropeço vira navegação normal
      return;
    } finally {
      gatilho.removeAttribute("aria-busy");
      prancha?.classList.remove("calculando");
    }
  });

  // voltar pelo navegador precisa devolver a página do sorteio de verdade
  addEventListener("popstate", () => location.reload());
})();
