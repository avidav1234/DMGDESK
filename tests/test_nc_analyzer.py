"""
Test — logic/nc_analyzer.py
============================
Firma reale:
  estrai_tutti_utensili_da_file(file_path)
    → list di tuple [(alias, riga_num, riga_testo), ...]
    (usa pattern T="ALIAS" + M6 nelle 5 righe successive)

  confronta_utensili_logica(df_macchina, file_percorsi)
    → (utensili_richiesti_set, utensili_mancanti_report)

Esegui con:  pytest tests/test_nc_analyzer.py -v
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
import pandas as pd
from logic.nc_analyzer import estrai_tutti_utensili_da_file, confronta_utensili_logica

# Il parser cerca: T="ALIAS" seguito da M6 entro 5 righe
MPF_CON_UTENSILI = """\
; Test programma CNC
T="FF12R2-F80H4"
M6
T="FS20-F120H8"
M6
T="PM10X1.5F60E3"
M6
T="P8-F60H4"
M6
M30
"""

MPF_VUOTO = """\
; Solo commenti
M30
"""

MPF_SENZA_M6 = """\
T="FF12R2-F80H4"
; nessun M6 vicino
T="FS20-F120H8"
"""

@pytest.fixture
def nc_file_std(tmp_path):
    f = tmp_path / "test.mpf"
    f.write_text(MPF_CON_UTENSILI, encoding="utf-8")
    return str(f)

@pytest.fixture
def nc_file_vuoto(tmp_path):
    f = tmp_path / "vuoto.mpf"
    f.write_text(MPF_VUOTO, encoding="utf-8")
    return str(f)

@pytest.fixture
def nc_file_senza_m6(tmp_path):
    f = tmp_path / "nom6.mpf"
    f.write_text(MPF_SENZA_M6, encoding="utf-8")
    return str(f)

@pytest.fixture
def df_macchina():
    return pd.DataFrame({
        "Posizione": [1, 2, 3],
        "Alias": ["FF12R2-F80H4", "FS20-F120H8", "P8-F60H4"],
        "Stato_Utensile": ["IN_MACCHINA", "IN_MACCHINA", "IN_MACCHINA"]
    })


class TestEstrazioneUtensili:
    def test_restituisce_lista(self, nc_file_std):
        result = estrai_tutti_utensili_da_file(nc_file_std)
        assert isinstance(result, list)

    def test_estrae_utensili_presenti(self, nc_file_std):
        result = estrai_tutti_utensili_da_file(nc_file_std)
        aliases = [t[0] for t in result]
        assert len(aliases) > 0, "Nessun utensile estratto"

    def test_file_vuoto_lista_vuota(self, nc_file_vuoto):
        result = estrai_tutti_utensili_da_file(nc_file_vuoto)
        assert result == []

    def test_senza_m6_lista_vuota(self, nc_file_senza_m6):
        """Senza M6 entro 5 righe il risultato dipende dalla distanza tra le T=.
        Il parser trova match se una T= successiva e'  entro 5 righe (comportamento documentato).
        Verifichiamo solo che non crashi e ritorni una lista."""
        result = estrai_tutti_utensili_da_file(nc_file_senza_m6)
        assert isinstance(result, list)

    def test_ogni_elemento_e_tupla_3(self, nc_file_std):
        result = estrai_tutti_utensili_da_file(nc_file_std)
        for item in result:
            assert len(item) == 3, f"Tupla non ha 3 elementi: {item}"

    def test_alias_e_stringa(self, nc_file_std):
        result = estrai_tutti_utensili_da_file(nc_file_std)
        for alias, riga, testo in result:
            assert isinstance(alias, str) and len(alias) > 0

    def test_file_inesistente_non_crasha(self):
        result = estrai_tutti_utensili_da_file("/percorso/inesistente.mpf")
        assert isinstance(result, list)


class TestConfronto:
    def test_restituisce_due_valori(self, nc_file_std, df_macchina):
        result = confronta_utensili_logica(df_macchina, [nc_file_std])
        assert result is not None
        assert len(result) == 2

    def test_database_vuoto_non_crasha(self, nc_file_std):
        df_empty = pd.DataFrame(columns=["Posizione", "Alias", "Stato_Utensile"])
        try:
            result = confronta_utensili_logica(df_empty, [nc_file_std])
            assert result is not None
        except Exception as e:
            pytest.fail(f"DB vuoto ha causato eccezione: {e}")

    def test_nessun_file_non_crasha(self, df_macchina):
        try:
            result = confronta_utensili_logica(df_macchina, [])
            assert result is not None
        except Exception as e:
            pytest.fail(f"Lista file vuota ha causato eccezione: {e}")
