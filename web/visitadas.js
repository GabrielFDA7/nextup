/* O que o visitante já fez hoje.
 *
 * Primeiro pedaço de estado que o NextUp guarda por pessoa. Mora no navegador,
 * por decisão registrada na seção 7 do docs/PROJETO.md: o app é usado dentro do
 * parque, no celular, por algumas horas — o cenário em que trocar de aparelho não
 * acontece. Exigir cadastro antes de responder "para onde vou agora" mataria o
 * produto.
 *
 * Duas coisas aqui não são óbvias e são o motivo deste arquivo existir separado:
 *
 * 1. **A marcação vale para HOJE.** Sem carimbo de data, o visitante voltaria ao
 *    parque na semana seguinte com metade das atrações escondidas e nenhuma pista
 *    do porquê.
 *
 * 2. **"Hoje" é o dia DO PARQUE, não o do celular.** Quem está em Orlando às 23h
 *    ainda está no mesmo dia de visita, mesmo que no fuso do aparelho já seja
 *    outro — e no Brasil, às 23h de Orlando, já é o dia seguinte.
 */

"use strict";

const VISITADAS = (() => {
  const CHAVE = "nextup:visitadas";

  /* Toda leitura e escrita passa por try/catch.
   *
   * `localStorage` não é uma garantia: em aba anônima, com cookies bloqueados ou
   * com a cota estourada, ele lança em vez de devolver vazio. Um app que quebra
   * porque não conseguiu lembrar de uma preferência é pior que um app sem
   * preferência nenhuma.
   */
  function ler() {
    try {
      return JSON.parse(localStorage.getItem(CHAVE)) || {};
    } catch {
      return {};
    }
  }

  function escrever(dados) {
    try {
      localStorage.setItem(CHAVE, JSON.stringify(dados));
      return true;
    } catch {
      // Sem armazenamento o app continua funcionando — só não lembra.
      return false;
    }
  }

  /* O dia corrente no fuso do parque, como "2026-09-20".
   *
   * `en-CA` não é escolha exótica: é o locale cujo formato de data já é
   * ano-mês-dia com zeros à esquerda, que ordena como texto e compara com `===`.
   * Montar isso à mão com getFullYear/getMonth daria o dia do **navegador**, que
   * é justamente o que não queremos.
   */
  function diaDoParque(timezone) {
    try {
      return new Intl.DateTimeFormat("en-CA", { timeZone: timezone }).format(new Date());
    } catch {
      // Fuso desconhecido ou ausente: cai no dia local, que é melhor que nada.
      return new Intl.DateTimeFormat("en-CA").format(new Date());
    }
  }

  /** As atrações marcadas hoje neste parque. Um `Set`, porque a pergunta é sempre "está aí?". */
  function doParque(parqueId, timezone) {
    const registro = ler()[parqueId];
    if (!registro || registro.dia !== diaDoParque(timezone)) return new Set();
    return new Set(registro.visitadas || []);
  }

  /** Marca ou desmarca, e devolve o conjunto resultante. */
  function alternar(parqueId, timezone, attractionId) {
    const dados = ler();
    const hoje = diaDoParque(timezone);
    const registro = dados[parqueId];

    // Virou o dia? O registro antigo não é apagado por engano — ele deixou de
    // valer, e sobrescrever é o comportamento certo.
    const atuais =
      registro && registro.dia === hoje ? new Set(registro.visitadas || []) : new Set();

    if (atuais.has(attractionId)) {
      atuais.delete(attractionId);
    } else {
      atuais.add(attractionId);
    }

    dados[parqueId] = { dia: hoje, visitadas: [...atuais] };
    escrever(_semDiasVelhos(dados, hoje));

    return atuais;
  }

  /** Esquece tudo o que foi marcado hoje neste parque. */
  function limpar(parqueId) {
    const dados = ler();
    delete dados[parqueId];
    escrever(dados);
  }

  /* Descarta registros de dias anteriores, de qualquer parque.
   *
   * Sem isso, cada dia de uso deixaria uma entrada morta para sempre, e quem
   * visitasse muitos parques acabaria estourando a cota do navegador por causa de
   * dados que já não valem nada.
   */
  function _semDiasVelhos(dados, hoje) {
    const limpo = {};
    for (const [parque, registro] of Object.entries(dados)) {
      if (registro && registro.dia === hoje) limpo[parque] = registro;
    }
    return limpo;
  }

  /** Se o navegador deixa guardar. A tela usa para avisar em vez de falhar calada. */
  function disponivel() {
    try {
      const teste = "nextup:teste";
      localStorage.setItem(teste, "1");
      localStorage.removeItem(teste);
      return true;
    } catch {
      return false;
    }
  }

  return { doParque, alternar, limpar, diaDoParque, disponivel };
})();
