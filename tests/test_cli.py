"""Testes da linha de comando.

Continuam sem tocar a internet: o `respx` responde pelas fixtures reais. O que se
verifica aqui é o que o usuário vê na tela e o código de saída — o contrato de um
programa de terminal com quem o chama.
"""

import json
from pathlib import Path

import httpx
import pytest
import respx

from nextup.cli import main
from nextup.clients.themeparks import ThemeParksClient
from nextup.config import DEFAULT_PARK_ID, THEMEPARKS_BASE_URL

FIXTURES = Path(__file__).parent / "fixtures"

URL_DESTINOS = f"{THEMEPARKS_BASE_URL}/destinations"
URL_CATALOGO = f"{THEMEPARKS_BASE_URL}/entity/{DEFAULT_PARK_ID}/children"
URL_LIVE = f"{THEMEPARKS_BASE_URL}/entity/{DEFAULT_PARK_ID}/live"


def carregar(nome: str) -> dict:
    return json.loads((FIXTURES / nome).read_text(encoding="utf-8"))


@pytest.fixture
def api_no_ar(monkeypatch, conexao):
    """Deixa a API respondendo as fixtures reais e reaproveita a conexão da suíte.

    O `monkeypatch` troca o `ThemeParksClient` que o CLI usa por uma versão que
    recebe a conexão compartilhada — sem isso, cada teste montaria um contexto
    SSL novo e custaria quase um segundo.
    """

    def fabrica(**kwargs):
        return ThemeParksClient(http_client=conexao, **kwargs)

    monkeypatch.setattr("nextup.cli.ThemeParksClient", fabrica)

    with respx.mock:
        yield {
            "catalogo": respx.get(URL_CATALOGO).mock(
                return_value=httpx.Response(200, json=carregar("children_magic_kingdom.json"))
            ),
            "live": respx.get(URL_LIVE).mock(
                return_value=httpx.Response(200, json=carregar("live_magic_kingdom.json"))
            ),
            "destinos": respx.get(URL_DESTINOS).mock(
                return_value=httpx.Response(200, json=carregar("destinations.json"))
            ),
        }


class TestListagemDeFilas:
    def test_sai_com_sucesso(self, api_no_ar, capsys):
        assert main([]) == 0
        assert "Magic Kingdom Park" in capsys.readouterr().out

    def test_filas_saem_em_ordem_crescente(self, api_no_ar, capsys):
        """O ponto do comando: a menor fila primeiro."""
        main(["--limit", "0"])
        saida = capsys.readouterr().out

        minutos = [
            int(linha.split("min")[0].split(".")[-1])
            for linha in saida.splitlines()
            if " min   " in linha
        ]

        assert minutos == sorted(minutos)

    def test_limit_controla_quantas_aparecem(self, api_no_ar, capsys):
        main(["--limit", "3"])
        saida = capsys.readouterr().out

        assert len([ln for ln in saida.splitlines() if " min   " in ln]) == 3
        assert "e mais" in saida

    def test_limit_zero_mostra_todas(self, api_no_ar, capsys):
        """Na fixture, 26 atrações estavam ranqueáveis."""
        main(["--limit", "0"])
        saida = capsys.readouterr().out

        assert len([ln for ln in saida.splitlines() if " min   " in ln]) == 26
        assert "e mais" not in saida

    def test_mostra_quantas_de_quantas_tem_fila(self, api_no_ar, capsys):
        main([])

        assert "26 de 35" in capsys.readouterr().out

    def test_shows_e_restaurantes_ficam_de_fora(self, api_no_ar, capsys):
        """Só atrações entram — o cruzamento com o catálogo garante isso."""
        main(["--limit", "0"])
        saida = capsys.readouterr().out

        assert "Cinderella Castle" not in saida  # atração sem fila
        assert "Casey's Corner" not in saida  # restaurante

    def test_informa_quando_o_dado_foi_atualizado(self, api_no_ar, capsys):
        main([])

        assert "Dado da API de" in capsys.readouterr().out


class TestListagemDeParques:
    def test_parks_lista_ids_e_nomes(self, api_no_ar, capsys):
        assert main(["--parks"]) == 0
        saida = capsys.readouterr().out

        assert DEFAULT_PARK_ID in saida
        assert "Magic Kingdom Park" in saida
        assert "Walt Disney World® Resort" in saida

    def test_parks_nao_busca_filas(self, api_no_ar, capsys):
        """Listar parques não deve gastar requisição de dado ao vivo."""
        main(["--parks"])

        assert api_no_ar["destinos"].call_count == 1
        assert api_no_ar["live"].call_count == 0
        assert api_no_ar["catalogo"].call_count == 0


class TestErros:
    def test_parque_inexistente_sai_com_codigo_1(self, monkeypatch, conexao, capsys):
        def fabrica(**kwargs):
            return ThemeParksClient(http_client=conexao, **kwargs)

        monkeypatch.setattr("nextup.cli.ThemeParksClient", fabrica)

        with respx.mock:
            respx.get(f"{THEMEPARKS_BASE_URL}/entity/fantasma/children").mock(
                return_value=httpx.Response(404)
            )
            respx.get(f"{THEMEPARKS_BASE_URL}/entity/fantasma/live").mock(
                return_value=httpx.Response(404)
            )

            codigo = main(["--park", "fantasma"])

        assert codigo == 1
        assert "Erro ao consultar a API" in capsys.readouterr().err

    def test_parque_sem_nenhuma_fila_avisa_em_vez_de_quebrar(self, monkeypatch, conexao, capsys):
        """Parque fechado de madrugada: lista vazia é situação normal."""

        def fabrica(**kwargs):
            return ThemeParksClient(http_client=conexao, **kwargs)

        monkeypatch.setattr("nextup.cli.ThemeParksClient", fabrica)

        live_fechado = carregar("live_magic_kingdom.json")
        for item in live_fechado["liveData"]:
            item["status"] = "CLOSED"

        with respx.mock:
            respx.get(URL_CATALOGO).mock(
                return_value=httpx.Response(200, json=carregar("children_magic_kingdom.json"))
            )
            respx.get(URL_LIVE).mock(return_value=httpx.Response(200, json=live_fechado))

            codigo = main([])

        saida = capsys.readouterr().out
        assert codigo == 0
        assert "Nenhuma atração com fila informada" in saida
        assert "pode estar fechado" in saida


class TestRecomendacao:
    """Modo `--lat/--lon`: a entrega da Fase 2."""

    def test_com_posicao_ranqueia_por_custo_total(self, api_no_ar, capsys):
        assert main(["--lat", "28.42037", "--lon", "-81.58031"]) == 0
        saida = capsys.readouterr().out

        assert "para onde ir agora" in saida
        assert "de caminhada +" in saida
        assert "de fila =" in saida

    def test_sem_posicao_mostra_so_as_filas(self, api_no_ar, capsys):
        main([])
        saida = capsys.readouterr().out

        assert "filas agora" in saida
        assert "de caminhada" not in saida

    def test_ranking_sai_em_ordem_crescente_de_custo(self, api_no_ar, capsys):
        main(["--lat", "28.42037", "--lon", "-81.58031", "--limit", "0"])
        saida = capsys.readouterr().out

        totais = [
            int(linha.split("= ")[1].split(" min")[0])
            for linha in saida.splitlines()
            if " min de fila = " in linha
        ]

        assert len(totais) == 26
        assert totais == sorted(totais)

    def test_posicoes_diferentes_dao_respostas_diferentes(self, api_no_ar, capsys):
        """A prova de que a distância entra na conta."""
        main(["--lat", "28.4210", "--lon", "-81.5810", "--limit", "1"])
        norte = capsys.readouterr().out

        main(["--lat", "28.4180", "--lon", "-81.5825", "--limit", "1"])
        sul = capsys.readouterr().out

        assert norte != sul

    def test_contagem_nao_se_confunde_com_o_limite(self, api_no_ar, capsys):
        """Bug corrigido: `--limit 6` dizia "6 de 35" em vez de "26 de 35"."""
        main(["--lat", "28.42037", "--lon", "-81.58031", "--limit", "6"])
        saida = capsys.readouterr().out

        assert "26 de 35" in saida
        assert "e mais 20" in saida

    def test_lat_sem_lon_e_erro_de_uso(self, capsys):
        assert main(["--lat", "28.42"]) == 2
        assert "precisam ser usados juntos" in capsys.readouterr().err

    def test_lon_sem_lat_e_erro_de_uso(self, capsys):
        assert main(["--lon", "-81.58"]) == 2
        assert "precisam ser usados juntos" in capsys.readouterr().err

    def test_coordenada_fora_do_planeta_e_recusada(self, capsys):
        assert main(["--lat", "91", "--lon", "0"]) == 2
        assert "Coordenada inválida" in capsys.readouterr().err


class TestArgumentos:
    def test_help_nao_quebra(self, capsys):
        with pytest.raises(SystemExit) as info:
            main(["--help"])

        assert info.value.code == 0
        assert "nextup" in capsys.readouterr().out
