import sys
import unittest
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from ons_carga.ingest import validar_csv


HEADER = "id_subsistema;nom_subsistema;din_instante;val_cargaenergiamwmed\n"
LINHAS = [
    "N;Norte;2026-01-01;7000.25",
    "NE;Nordeste;2026-01-01;12000.5",
    "S;Sul;2026-01-01;11000.75",
    "SE;Sudeste/Centro-Oeste;2026-01-01;40000.0",
]


def csv_bytes(linhas):
    return (HEADER + "\n".join(linhas) + "\n").encode("utf-8")


class TestValidacao(unittest.TestCase):
    def test_quatro_subsistemas_formam_um_dia(self):
        leituras = validar_csv(csv_bytes(LINHAS), 2026)
        self.assertEqual(len(leituras), 4)
        self.assertEqual(leituras[0].dia, date(2026, 1, 1))

    def test_recusa_chave_duplicada(self):
        with self.assertRaisesRegex(ValueError, "duplicada"):
            validar_csv(csv_bytes(LINHAS + [LINHAS[0]]), 2026)

    def test_recusa_dia_incompleto(self):
        with self.assertRaisesRegex(ValueError, "incompleto"):
            validar_csv(csv_bytes(LINHAS[:-1]), 2026)

    def test_recusa_carga_negativa(self):
        linhas = LINHAS.copy()
        linhas[0] = "N;Norte;2026-01-01;-1"
        with self.assertRaisesRegex(ValueError, "positiva"):
            validar_csv(csv_bytes(linhas), 2026)


if __name__ == "__main__":
    unittest.main()

