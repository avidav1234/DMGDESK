"""
Test — logic/code_generator_logic.py
=====================================
Firma reale:
    genera_codici(tipo_utensile, diametro, r2_x='', l='', vd='', fp='',
                  tipo_holder='', diam_holder='', fresa_dedicata=False, speciale=False)
    → tuple: (nome_completo, commento, errore)

tipo_holder = chiave dict PORTA_UTENSILI, es. 'Caletto_BILZ'
diam_holder = valore da lista 'diametri', es. 'D6'

Esegui con:  pytest tests/test_code_generator.py -v
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from logic.code_generator_logic import UTENSILI, PORTA_UTENSILI, genera_codici

# Holder validi da usare nei test
HOLDER_BILZ = "Caletto_BILZ"
DIAM_BILZ   = "D6"
HOLDER_IDR  = "Idraulico"
DIAM_IDR    = "D6"


class TestCatalogo:
    def test_utensili_non_vuoto(self):
        assert len(UTENSILI) > 0

    def test_almeno_20_tipologie(self):
        assert len(UTENSILI) >= 20

    def test_tutte_le_tipologie_hanno_nome_e_commento(self):
        for key, val in UTENSILI.items():
            assert "nome" in val and val["nome"], f"'{key}' manca nome"
            assert "commento" in val and val["commento"], f"'{key}' manca commento"

    def test_fresa_finitura_hsc_presente(self):
        assert "Fresa-FIN-HSC" in UTENSILI

    def test_pettine_m_presente(self):
        assert "Pettine-M" in UTENSILI

    def test_porta_utensili_non_vuoto(self):
        assert len(PORTA_UTENSILI) > 0

    def test_caletto_bilz_presente(self):
        assert HOLDER_BILZ in PORTA_UTENSILI

    def test_idraulico_presente(self):
        assert HOLDER_IDR in PORTA_UTENSILI


class TestGeneraCodiciOk:
    def _std(self, **kw):
        defaults = dict(tipo_utensile="Fresa-FIN-HSC", diametro="12", r2_x="2",
                        l="80", fp="80", tipo_holder=HOLDER_BILZ, diam_holder=DIAM_BILZ)
        defaults.update(kw)
        return genera_codici(**defaults)

    def test_nessun_errore(self):
        _, _, err = self._std()
        assert err is None, f"Errore inatteso: {err}"

    def test_nome_non_vuoto(self):
        nome, _, _ = self._std()
        assert nome and len(nome) > 0

    def test_commento_non_vuoto(self):
        _, commento, _ = self._std()
        assert commento and len(commento) > 0

    def test_diametro_nel_nome(self):
        nome, _, _ = self._std(diametro="12")
        assert "12" in nome, f"Diametro 12 non trovato in: {nome}"

    def test_holder_lettera_nel_nome(self):
        nome, _, _ = self._std()
        # Caletto BILZ ha lettera H
        assert "H" in nome, f"Lettera H non trovata in: {nome}"

    def test_fresa_fin_prefisso_ff(self):
        _, commento, _ = self._std(tipo_utensile="Fresa-FIN-HSC")
        assert commento.startswith("FF"), f"Commento: {commento}"

    def test_fresa_sgr_prefisso_fs(self):
        _, commento, _ = self._std(tipo_utensile="Fresa-SGR-HSC")
        assert commento.startswith("FS"), f"Commento: {commento}"

    def test_pettine_m_pm_nel_commento(self):
        nome, commento, err = genera_codici(
            tipo_utensile="Pettine-M", diametro="10", r2_x="1.5",
            fp="60", tipo_holder=HOLDER_IDR, diam_holder=DIAM_IDR)
        assert err is None, f"Errore: {err}"
        assert "PM" in commento, f"PM non trovato in: {commento}"

    def test_punta_con_vd_ok(self):
        nome, commento, err = genera_codici(
            tipo_utensile="Punta", diametro="8", vd="5.0",
            fp="60", tipo_holder=HOLDER_BILZ, diam_holder=DIAM_BILZ)
        assert err is None, f"Errore: {err}"
        assert nome

    def test_speciale_aggiunge_x(self):
        nome_no, _, _ = self._std(speciale=False)
        nome_si, _, _ = self._std(speciale=True)
        assert "X" in nome_si, f"Flag speciale: X non trovato in '{nome_si}'"
        assert nome_si != nome_no

    def test_nome_senza_spazi(self):
        nome, _, _ = self._std()
        assert " " not in nome, f"Spazi nel nome: '{nome}'"

    def test_diametro_decimale(self):
        nome, _, err = self._std(diametro="12.7")
        assert err is None and nome, f"Errore con decimale: {err}"


class TestValidazione:
    def test_diametro_vuoto(self):
        _, _, err = genera_codici(tipo_utensile="Fresa-FIN-HSC", diametro="",
                                  fp="80", tipo_holder=HOLDER_BILZ, diam_holder=DIAM_BILZ)
        assert err is not None

    def test_tipo_vuoto(self):
        _, _, err = genera_codici(tipo_utensile="", diametro="12",
                                  fp="80", tipo_holder=HOLDER_BILZ, diam_holder=DIAM_BILZ)
        assert err is not None

    def test_fp_vuoto(self):
        _, _, err = genera_codici(tipo_utensile="Fresa-FIN-HSC", diametro="12",
                                  fp="", tipo_holder=HOLDER_BILZ, diam_holder=DIAM_BILZ)
        assert err is not None

    def test_holder_vuoto(self):
        _, _, err = genera_codici(tipo_utensile="Fresa-FIN-HSC", diametro="12",
                                  fp="80", tipo_holder="", diam_holder="")
        assert err is not None

    def test_diametro_non_numerico(self):
        _, _, err = genera_codici(tipo_utensile="Fresa-FIN-HSC", diametro="abc",
                                  fp="80", tipo_holder=HOLDER_BILZ, diam_holder=DIAM_BILZ)
        assert err is not None

    def test_errore_e_stringa(self):
        _, _, err = genera_codici(tipo_utensile="", diametro="",
                                  fp="", tipo_holder="", diam_holder="")
        assert isinstance(err, str) and len(err) > 0


@pytest.mark.parametrize("tipo", list(UTENSILI.keys()))
def test_smoke_tutte_le_tipologie(tipo):
    """Ogni tipologia deve generare senza crashare."""
    try:
        nome, commento, err = genera_codici(
            tipo_utensile=tipo, diametro="10", r2_x="1", l="50",
            vd="3", fp="60", tipo_holder=HOLDER_BILZ, diam_holder=DIAM_BILZ)
        assert nome is not None or err is not None
    except Exception as e:
        pytest.fail(f"Tipologia '{tipo}' ha causato eccezione: {e}")
