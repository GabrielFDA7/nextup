"""Testes da faixa de popularidade.

O que esta suíte protege não é a aritmética — é o **conjunto de decisões** que
saiu da medição sobre 1257 snapshots reais e está registrado no cabeçalho de
`core/popularity.py`. Cada uma delas é uma escolha que alguém poderia desfazer
sem perceber o que quebrou:

- faixa **relativa ao parque**, nunca limiar absoluto de minutos;
- razão contra a **mediana**, nunca tercil por posição;
- `UNKNOWN` é diferente de `QUIET`;
- a popularidade **não reordena** o ranking.
"""

import pytest

from nextup.core.popularity import AttractionPopularity, Popularity, classify

#: Um parque plausível: duas campeãs, um miolo e uma cauda tranquila. Todas com
#: medições de sobra, para que só a média decida a faixa.
PARQUE = {
    "tron": (52.6, 35),
    "dwarfs": (48.2, 33),
    "peter-pan": (35.7, 27),
    "space-mountain": (30.6, 62),
    "haunted": (23.1, 60),
    "pirates": (19.5, 61),
    "small-world": (14.9, 69),
    "peoplemover": (10.4, 42),
    "carpets": (7.5, 44),
}


class TestFaixas:
    def test_as_campeas_sao_principais(self):
        faixas = classify(PARQUE)

        assert faixas["tron"].tier is Popularity.HEADLINER
        assert faixas["dwarfs"].tier is Popularity.HEADLINER

    def test_as_de_fila_curta_sao_tranquilas(self):
        faixas = classify(PARQUE)

        assert faixas["carpets"].tier is Popularity.QUIET
        assert faixas["peoplemover"].tier is Popularity.QUIET

    def test_a_do_meio_e_moderada(self):
        # Mediana de PARQUE é 23,1 (Haunted Mansion). Ela não pode cair em
        # nenhum dos extremos, por construção.
        assert classify(PARQUE)["haunted"].tier is Popularity.MODERATE

    def test_devolve_todas_as_atracoes_recebidas(self):
        """Inclusive as inelegíveis: quem chama precisa distinguir 'não sabemos'
        de 'não está no parque', e omitir apagaria essa diferença."""
        faixas = classify({**PARQUE, "recem-aberta": (40.0, 2)})

        assert set(faixas) == set(PARQUE) | {"recem-aberta"}


class TestRelatividadeAoParque:
    """A faixa descreve a atração **dentro do parque dela**.

    É o que permite a mesma régua servir ao Magic Kingdom e a um parque pequeno
    onde 20 minutos já é fila de campeã. Um limiar absoluto em minutos chamaria
    o parque pequeno inteiro de tranquilo.
    """

    def test_o_mesmo_numero_muda_de_faixa_conforme_o_parque(self):
        grande = classify({"a": (60.0, 30), "b": (30.0, 30), "c": (20.0, 30)})
        pequeno = classify({"a": (30.0, 30), "b": (10.0, 30), "c": (7.0, 30)})

        # 30 minutos: miolo no parque grande, campeã no pequeno.
        assert grande["b"].tier is Popularity.MODERATE
        assert pequeno["a"].tier is Popularity.HEADLINER

    def test_nao_forca_um_terco_em_cada_faixa(self):
        """O tercil por posição foi medido e perdeu (74% contra 83% de
        estabilidade) — mas erra de um jeito pior, que é este: num parque com uma
        campeã e muitas medianas, ele promoveria um terço delas só para encher a
        cota."""
        parque = {"campea": (60.0, 30)} | {f"mediana-{i}": (20.0, 30) for i in range(9)}

        faixas = classify(parque)
        principais = [a for a, p in faixas.items() if p.tier is Popularity.HEADLINER]

        assert principais == ["campea"]


class TestHistoricoInsuficiente:
    """`UNKNOWN` não é `QUIET`, e a diferença tem consequência prática."""

    def test_abaixo_do_minimo_a_faixa_e_desconhecida(self):
        faixas = classify({**PARQUE, "nova": (45.0, 3)})

        assert faixas["nova"].tier is Popularity.UNKNOWN

    def test_desconhecida_nao_e_tranquila(self):
        """Chamar de tranquila uma atração que nunca medimos mandaria o visitante
        para uma fila de uma hora com a nossa bênção."""
        faixas = classify({**PARQUE, "nova": (45.0, 3)})

        assert faixas["nova"].tier is not Popularity.QUIET

    def test_a_inelegivel_nao_entra_na_regua(self):
        """A mediana sai só das elegíveis. Sem isso, o ruído de uma atração de
        três medições mexeria na faixa de todas as vizinhas."""
        sozinho = classify(PARQUE)
        com_ruido = classify(PARQUE | {f"ruido-{i}": (200.0, 2) for i in range(20)})

        for aid in PARQUE:
            assert sozinho[aid].tier is com_ruido[aid].tier

    def test_parque_sem_historico_algum_sai_todo_desconhecido(self):
        """Primeiro dia de coleta de um parque novo. É resultado correto, não erro."""
        faixas = classify({"a": (30.0, 1), "b": (10.0, 2)})

        assert all(p.tier is Popularity.UNKNOWN for p in faixas.values())

    def test_media_zero_nao_vira_regua(self):
        """Uma atração que só mediu fila zero não pode puxar a mediana para baixo
        e promover o parque inteiro a principal."""
        faixas = classify({**PARQUE, "sempre-vazia": (0.0, 40)})

        assert faixas["sempre-vazia"].tier is Popularity.UNKNOWN
        assert faixas["haunted"].tier is Popularity.MODERATE


class TestOportunidade:
    """Uma principal com fila abaixo da própria média — a razão de a feature existir."""

    def test_principal_bem_abaixo_da_media_e_oportunidade(self):
        tron = classify(PARQUE)["tron"]

        assert tron.is_opportunity(20)

    def test_principal_na_media_nao_e(self):
        tron = classify(PARQUE)["tron"]

        assert not tron.is_opportunity(50)

    def test_tranquila_abaixo_da_media_nao_e_noticia(self):
        """Uma tranquila com fila baixa é 4 minutos em vez de 7. Anunciar isso
        gastaria a atenção do visitante com o que ele já sabia."""
        carpets = classify(PARQUE)["carpets"]

        assert not carpets.is_opportunity(0)

    def test_faixa_desconhecida_nunca_e_oportunidade(self):
        """Comparar contra uma média de três medições produziria 'oportunidade'
        a cada oscilação."""
        nova = classify({**PARQUE, "nova": (45.0, 3)})["nova"]

        assert not nova.is_opportunity(5)

    def test_sem_fila_medida_nao_da_para_afirmar(self):
        assert not classify(PARQUE)["tron"].is_opportunity(None)

    @pytest.mark.parametrize(
        ("fila", "esperado"),
        [
            (36, True),  # 36 <= 52,6 * 0,7 = 36,8
            (40, False),
        ],
    )
    def test_o_limiar_e_uma_queda_de_trinta_por_cento(self, fila, esperado):
        """Exigir 30% evita disparar a cada oscilação de cinco minutos, que é o
        passo em que a fonte reporta."""
        assert classify(PARQUE)["tron"].is_opportunity(fila) is esperado


class TestNumerosDeApoio:
    def test_guarda_a_media_e_a_contagem(self):
        """Sem elas não há como explicar a classificação — mesma razão pela qual
        `TrendAnalysis` guarda as duas pontas."""
        tron = classify(PARQUE)["tron"]

        assert tron.average_minutes == 52.6
        assert tron.measurements == 35

    def test_arredonda_para_uma_casa(self):
        """A fonte reporta em passos de 5; seis casas decimais sugeririam uma
        precisão que o dado de origem não tem."""
        faixa = classify({**PARQUE, "x": (18.333333, 30)})["x"]

        assert faixa.average_minutes == 18.3

    def test_is_known_separa_o_que_da_para_afirmar(self):
        faixas = classify({**PARQUE, "nova": (45.0, 3)})

        assert faixas["tron"].is_known
        assert not faixas["nova"].is_known


class TestAusenciaDeDado:
    def test_sem_popularidade_o_objeto_ainda_funciona(self):
        """O default precisa ser inofensivo: o ranking funciona desde a Fase 2 sem
        nada disso, e continua funcionando no primeiro dia de um parque novo."""
        vazia = AttractionPopularity(Popularity.UNKNOWN)

        assert vazia.average_minutes is None
        assert vazia.measurements == 0
        assert not vazia.is_opportunity(10)

    def test_entrada_vazia_devolve_saida_vazia(self):
        assert classify({}) == {}
