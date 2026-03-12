"""
Test — logic/calibra_only_logic.py
====================================
Copre le 5 modalità CALIBRA ONLY.

Esegui con:  pytest tests/test_calibra_only.py -v
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
import json
import tempfile
from unittest.mock import patch
from logic.calibra_only_logic import CalibraOnlyLogic, get_calibra_logic


@pytest.fixture
def logic():
    """Istanza fresca con settings mockati via patch."""
    return CalibraOnlyLogic()


@pytest.fixture
def settings_file(tmp_path):
    """Crea un file settings temporaneo e lo patcha nel logic."""
    f = tmp_path / "calibra_only_settings.json"
    return f


def make_logic_with_mode(mode, x_fin=3, x_qual=3):
    """Helper: crea un CalibraOnlyLogic con modalità specifica."""
    inst = CalibraOnlyLogic()
    settings = {"mode": mode, "x_finitura": x_fin, "x_qualsiasi": x_qual}
    with patch.object(inst, "_load_settings", return_value=settings):
        yield inst


# ─── Test classificazione utensili ──────────────────────────

class TestClassificazione:
    def test_ff_e_finitura(self, logic):
        assert logic.is_finitura("FF12R2-F80H4") is True

    def test_ff_case_insensitive(self, logic):
        assert logic.is_finitura("ff12R2-F80H4") is True

    def test_fs_non_e_finitura(self, logic):
        assert logic.is_finitura("FS20-F120H8") is False

    def test_punta_non_e_finitura(self, logic):
        assert logic.is_finitura("P8-F60H4") is False

    def test_vuoto_non_e_finitura(self, logic):
        assert logic.is_finitura("") is False

    def test_none_non_e_finitura(self, logic):
        assert logic.is_finitura(None) is False


# ─── Test modalità ──────────────────────────────────────────

class TestModalitaMai:
    def test_mai_finitura(self, logic):
        with patch.object(logic, "_load_settings", return_value={"mode": "mai", "x_finitura": 3, "x_qualsiasi": 3}):
            logic.reset_call_count()
            assert logic.needs_calibra_only("FF12R2-F80H4", 0, 10) is False

    def test_mai_sgrossatura(self, logic):
        with patch.object(logic, "_load_settings", return_value={"mode": "mai", "x_finitura": 3, "x_qualsiasi": 3}):
            logic.reset_call_count()
            assert logic.needs_calibra_only("FS20-F120H8", 0, 10) is False


class TestModalitaInizio:
    def test_inizio_primo_utensile(self, logic):
        with patch.object(logic, "_load_settings", return_value={"mode": "inizio", "x_finitura": 3, "x_qualsiasi": 3}):
            logic.reset_call_count()
            assert logic.needs_calibra_only("FS20-F120H8", 0, 10) is True

    def test_inizio_non_primo(self, logic):
        with patch.object(logic, "_load_settings", return_value={"mode": "inizio", "x_finitura": 3, "x_qualsiasi": 3}):
            logic.reset_call_count()
            assert logic.needs_calibra_only("FS20-F120H8", 3, 10) is False


class TestModalitaFInituraUnico:
    def test_finitura_unico_ff_riceve_calibra(self, logic):
        with patch.object(logic, "_load_settings", return_value={"mode": "finitura_unico", "x_finitura": 3, "x_qualsiasi": 3}):
            logic.reset_call_count()
            assert logic.needs_calibra_only("FF12R2-F80H4", 1, 10) is True

    def test_finitura_unico_sgrossatura_no_calibra(self, logic):
        with patch.object(logic, "_load_settings", return_value={"mode": "finitura_unico", "x_finitura": 3, "x_qualsiasi": 3}):
            logic.reset_call_count()
            assert logic.needs_calibra_only("FS20-F120H8", 1, 10) is False


class TestModalitaFInituraX:
    def test_finitura_x_dopo_x_richiami(self, logic):
        with patch.object(logic, "_load_settings", return_value={"mode": "finitura_x", "x_finitura": 2, "x_qualsiasi": 3}):
            logic.reset_call_count()
            logic.needs_calibra_only("FF12R2-F80H4", 0, 10)  # 1° richiamo
            result = logic.needs_calibra_only("FF12R2-F80H4", 1, 10)  # 2° → calibra
            assert result is True

    def test_finitura_x_primo_calibra_sempre(self, logic):
        """In finitura_x il primo richiamo FF calibra sempre (by design)."""
        with patch.object(logic, "_load_settings", return_value={"mode": "finitura_x", "x_finitura": 3, "x_qualsiasi": 3}):
            logic.reset_call_count()
            result = logic.needs_calibra_only("FF12R2-F80H4", 0, 10)
            assert result is True

    def test_finitura_x_secondo_no_calibra(self, logic):
        """In finitura_x il 2° richiamo su x=3 non calibra."""
        with patch.object(logic, "_load_settings", return_value={"mode": "finitura_x", "x_finitura": 3, "x_qualsiasi": 3}):
            logic.reset_call_count()
            logic.needs_calibra_only("FF12R2-F80H4", 0, 10)
            result = logic.needs_calibra_only("FF12R2-F80H4", 1, 10)
            assert result is False


class TestModalitaOgniX:
    def test_ogni_x_al_terzo(self, logic):
        with patch.object(logic, "_load_settings", return_value={"mode": "ogni_x", "x_finitura": 3, "x_qualsiasi": 3}):
            logic.reset_call_count()
            logic.needs_calibra_only("FS20-F120H8", 0, 10)  # 1
            logic.needs_calibra_only("FS20-F120H8", 1, 10)  # 2
            result = logic.needs_calibra_only("FS20-F120H8", 2, 10)  # 3 → calibra
            assert result is True

    def test_ogni_x_valido_anche_per_finitura(self, logic):
        with patch.object(logic, "_load_settings", return_value={"mode": "ogni_x", "x_finitura": 3, "x_qualsiasi": 2}):
            logic.reset_call_count()
            logic.needs_calibra_only("FF12R2-F80H4", 0, 10)  # 1
            result = logic.needs_calibra_only("FF12R2-F80H4", 1, 10)  # 2 → calibra
            assert result is True


# ─── Test reset e comandi ────────────────────────────────────

class TestUtility:
    def test_reset_azzera_contatori(self, logic):
        with patch.object(logic, "_load_settings", return_value={"mode": "ogni_x", "x_finitura": 3, "x_qualsiasi": 2}):
            logic.needs_calibra_only("FS20", 0, 5)
            logic.reset_call_count()
            assert logic.tool_call_count == {}

    def test_get_calibra_command_restituisce_stringa(self, logic):
        cmd = logic.get_calibra_command()
        assert isinstance(cmd, str) and len(cmd) > 0

    def test_get_calibra_command_e_calibra_only(self, logic):
        assert logic.get_calibra_command() == "CALIBRA_ONLY"

    def test_get_mode_description_restituisce_stringa(self, logic):
        with patch.object(logic, "_load_settings", return_value={"mode": "mai", "x_finitura": 3, "x_qualsiasi": 3}):
            desc = logic.get_mode_description()
            assert isinstance(desc, str) and len(desc) > 0

    def test_get_statistics_restituisce_dict(self, logic):
        with patch.object(logic, "_load_settings", return_value={"mode": "finitura_unico", "x_finitura": 3, "x_qualsiasi": 3}):
            aliases = ["FF12R2-F80H4", "FS20-F120H8", "FF8R1-F50E2"]
            stats = logic.get_statistics(aliases)
            assert "total" in stats and "with_calibra" in stats and "percentage" in stats

    def test_get_statistics_totale_corretto(self, logic):
        with patch.object(logic, "_load_settings", return_value={"mode": "finitura_unico", "x_finitura": 3, "x_qualsiasi": 3}):
            aliases = ["FF12R2", "FS20", "FF8R1", "P8"]
            stats = logic.get_statistics(aliases)
            assert stats["total"] == 4

    def test_get_statistics_percentuale_range(self, logic):
        with patch.object(logic, "_load_settings", return_value={"mode": "finitura_unico", "x_finitura": 3, "x_qualsiasi": 3}):
            aliases = ["FF12R2", "FS20", "FF8R1"]
            stats = logic.get_statistics(aliases)
            assert 0 <= stats["percentage"] <= 100

    def test_singleton_get_calibra_logic(self):
        inst1 = get_calibra_logic()
        inst2 = get_calibra_logic()
        assert inst1 is inst2
