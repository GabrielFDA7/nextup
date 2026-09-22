/* O que o visitante marcou: o que já fez e o que veio fazer.
 *
 * Tudo mora no navegador, por decisão registrada na seção 7 do docs/PROJETO.md:
 * o app é usado dentro do parque, no celular, por algumas horas — e exigir
 * cadastro antes de responder "para onde vou agora" mataria o produto.
 *
 * As duas marcações parecem iguais e têm regras opostas:
 *
 *   VISITADAS  valem por DIA.   Amanhã o parque está inteiro de novo.
 *   ALVOS      valem até mudar. São desejo, não acontecimento.
 *
 * Por isso a visitada carrega carimbo de data e o alvo não. Uma lista de desejos
 * que se apaga sozinha à meia-noite seria um app que esquece o que você quer.
 */

"use strict";

/* A base que as duas marcações compartilham.
 *
 * Existe para o tratamento de erro do `localStorage` ficar num lugar só. Ele não
 * é uma garantia: em aba anônima, com cookies bloqueados ou com a cota estourada,
 * ele **lança** em vez de devolver vazio. Duplicar esse cuidado em dois arquivos
 * seria pedir para um deles esquecê-lo.
 */
const ARMAZENAMENTO = (() => {
  function ler(chave) {
    try {
      return JSON.parse(localStorage.getItem(chave)) || {};
    } catch {
      return {};
    }
  }

  function escrever(chave, dados) {
    try {
      localStorage.setItem(chave, JSON.stringify(dados));
      return true;
    } catch {
      // Sem armazenamento o app continua funcionando — só não lembra.
      return false;
    }
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

  /* O dia corrente no fuso do parque, como "2026-09-20".
   *
   * `en-CA` não é escolha exótica: é o locale cujo formato de data já é
   * ano-mês-dia com zeros à esquerda, que ordena como texto e compara com `===`.
   * Montar isso à mão com getFullYear/getMonth daria o dia do **navegador** — e
   * quem está em Orlando às 23h ainda está no mesmo dia de visita, mesmo que no
   * Brasil já seja amanhã.
   */
  function diaDoParque(timezone) {
    try {
      return new Intl.DateTimeFormat("en-CA", { timeZone: timezone }).format(new Date());
    } catch {
      // Fuso desconhecido ou ausente: cai no dia local, que é melhor que nada.
      return new Intl.DateTimeFormat("en-CA").format(new Date());
    }
  }

  return { ler, escrever, disponivel, diaDoParque };
})();

/* As atrações que o visitante já fez HOJE.
 *
 * Marcar tira do ranking — é o que o consultor de parque faz: ele não manda você
 * de volta para onde acabou de ir.
 */
const VISITADAS = (() => {
  const CHAVE = "nextup:visitadas";

  function doParque(parqueId, timezone) {
    const registro = ARMAZENAMENTO.ler(CHAVE)[parqueId];
    if (!registro || registro.dia !== ARMAZENAMENTO.diaDoParque(timezone)) return new Set();
    return new Set(registro.visitadas || []);
  }

  function alternar(parqueId, timezone, attractionId) {
    const dados = ARMAZENAMENTO.ler(CHAVE);
    const hoje = ARMAZENAMENTO.diaDoParque(timezone);
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
    ARMAZENAMENTO.escrever(CHAVE, _semDiasVelhos(dados, hoje));

    return atuais;
  }

  function limpar(parqueId) {
    const dados = ARMAZENAMENTO.ler(CHAVE);
    delete dados[parqueId];
    ARMAZENAMENTO.escrever(CHAVE, dados);
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

  return { doParque, alternar, limpar };
})();

/* Os limites que o visitante impõe às sugestões.
 *
 * Existem porque o `custo_total` **soma as parcelas**, e para quem está no parque
 * elas não são intercambiáveis: cinco minutos de caminhada mais trinta e cinco de
 * fila dá o mesmo total que vinte mais vinte, e são experiências opostas para
 * quem empurra um carrinho ou está com uma criança no colo.
 *
 * O ranking continua ordenando por custo total — o filtro **corta**, não
 * reordena. Quem quiser mudar o critério de ordenação estaria mudando a tese do
 * projeto, e isso não é um filtro.
 *
 * Guardados **sem** o parque na chave, ao contrário de visitadas e alvos: "não
 * quero andar muito" é sobre a pessoa, não sobre o Magic Kingdom.
 */
const FILTROS = (() => {
  const CHAVE = "nextup:filtros";

  //: O maior valor do controle significa "sem limite". Ter um número no lugar de
  //: `null` mantém o `<input type="range">` simples — ele não sabe dizer "nenhum".
  const SEM_LIMITE = 125;

  //: As faixas de popularidade, na ordem em que aparecem na tela. `UNKNOWN` é uma
  //: faixa de verdade, e não a ausência de uma: histórico curto demais para
  //: afirmar é diferente de fila curta. Ver `core/popularity.py`.
  const FAIXAS = ["HEADLINER", "MODERATE", "QUIET", "UNKNOWN"];

  function ler() {
    const dados = ARMAZENAMENTO.ler(CHAVE);

    // Faixa desconhecida é descartada: uma versão futura pode renomeá-las, e um
    // valor órfão guardado no navegador esconderia atrações para sempre, sem que
    // o visitante tivesse como descobrir por quê.
    const guardadas = Array.isArray(dados.faixas)
      ? dados.faixas.filter((f) => FAIXAS.includes(f))
      : null;

    return {
      filaMax: Number(dados.filaMax) || SEM_LIMITE,
      caminhadaMax: Number(dados.caminhadaMax) || SEM_LIMITE,
      // O padrão é mostrar tudo. Um app que abre escondendo atrações precisaria
      // explicar por quê antes mesmo de o visitante pedir alguma coisa.
      faixas: guardadas && guardadas.length > 0 ? guardadas : [...FAIXAS],
    };
  }

  function salvar(filtros) {
    ARMAZENAMENTO.escrever(CHAVE, filtros);
    return filtros;
  }

  function limpar() {
    ARMAZENAMENTO.escrever(CHAVE, {});
    return { filaMax: SEM_LIMITE, caminhadaMax: SEM_LIMITE, faixas: [...FAIXAS] };
  }

  /** Se algum limite está valendo. A tela usa para avisar, e o aviso é essencial. */
  function ativos(filtros) {
    return (
      filtros.filaMax < SEM_LIMITE ||
      filtros.caminhadaMax < SEM_LIMITE ||
      filtros.faixas.length < FAIXAS.length
    );
  }

  return { ler, salvar, limpar, ativos, SEM_LIMITE, FAIXAS };
})();

/* As atrações que o visitante VEIO FAZER.
 *
 * **Sem carimbo de data**, ao contrário das visitadas. Um alvo é desejo, não
 * acontecimento: quem marcou o Space Mountain como imperdível continua querendo
 * ir nele no mês que vem. Uma lista de desejos que se apaga à meia-noite seria um
 * app que esquece o que você quer.
 *
 * Por parque, porque a lista de desejos do Magic Kingdom não diz nada sobre o
 * EPCOT.
 */
const ALVOS = (() => {
  const CHAVE = "nextup:alvos";

  function doParque(parqueId) {
    return new Set(ARMAZENAMENTO.ler(CHAVE)[parqueId] || []);
  }

  function alternar(parqueId, attractionId) {
    const dados = ARMAZENAMENTO.ler(CHAVE);
    const atuais = new Set(dados[parqueId] || []);

    if (atuais.has(attractionId)) {
      atuais.delete(attractionId);
    } else {
      atuais.add(attractionId);
    }

    // Parque sem alvo nenhum sai do armazenamento, em vez de virar uma lista
    // vazia guardada para sempre.
    if (atuais.size === 0) {
      delete dados[parqueId];
    } else {
      dados[parqueId] = [...atuais];
    }

    ARMAZENAMENTO.escrever(CHAVE, dados);
    return atuais;
  }

  function limpar(parqueId) {
    const dados = ARMAZENAMENTO.ler(CHAVE);
    delete dados[parqueId];
    ARMAZENAMENTO.escrever(CHAVE, dados);
  }

  return { doParque, alternar, limpar };
})();
