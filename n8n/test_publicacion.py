"""Controles de publicación y coherencia: nunca mezclar lotes ni publicar entradas crudas."""
import hashlib
import io
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "n8n/python"), str(ROOT / "app"), str(ROOT / "n8n")]
from tacctico_etl import procesar, guardar_lote, confirmar_publicacion
from data_release import unpack, verify_folder, load_remote
from test_pipeline import publication


class PublicationTests(unittest.TestCase):
    def setUp(self):
        self.result = procesar([publication()])
        self.batch = self.result["resumen"]["lote"]

    def test_metrics_use_the_same_capture_and_real_arithmetic(self):
        metrics = json.loads(self.result["archivos"]["metricas.json"])
        row = metrics["por_insumo"][0]
        self.assertEqual(metrics["lote"], self.batch)
        self.assertEqual(row["mediana_kg"], 10000)
        self.assertEqual(row["mejor_accesible_kg"], 10000)
        self.assertEqual(row["brecha_mejor_vs_mediana"], 0)
        self.assertEqual(metrics["base_sin_atipicos"], 1)
        document = self.result["archivos"]["dashboard.html"]
        self.assertIn(self.batch, document)
        self.assertNotIn("__TACCTICO_", document)
        self.assertNotIn("a precios de hoy", document)

    def test_no_accessible_offer_is_missing_instead_of_zero(self):
        result = procesar([publication(articuloTitulo="Premezcla para pan 25kg")])
        row = json.loads(result["archivos"]["metricas.json"])["por_insumo"][0]
        self.assertIsNone(row["mejor_accesible_kg"])
        self.assertIsNone(row["brecha_mejor_vs_mediana"])

    def test_bundle_is_allowlisted_and_verifiable(self):
        data = self.result["archivos"]["paquete.zip"]
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            self.assertEqual(set(archive.namelist()), {
                "mercadolibre_validado.csv", "metricas.json", "dashboard.html", "calidad.json", "manifest.json"})
        with TemporaryDirectory() as temp:
            release = unpack(data, Path(temp))
            self.assertEqual(release["lote"], self.batch)
            (Path(temp) / "metricas.json").write_text("corrupto")
            with self.assertRaisesRegex(ValueError, "no coincide"):
                verify_folder(Path(temp))

    def test_unexpected_zip_paths_are_rejected(self):
        stream = io.BytesIO()
        with zipfile.ZipFile(stream, "w") as archive:
            archive.writestr("../fuera.txt", "no")
        with TemporaryDirectory() as temp, self.assertRaises(ValueError):
            unpack(stream.getvalue(), Path(temp) / "lote")

    def pointer(self):
        return {"schema_version": 1, "lote": self.batch, "publicaciones": 1,
            "archivos": {kind: {"drive_id": "archivo_drive_prueba", "sha256": hashlib.sha256(
                self.result["archivos"][name].encode() if isinstance(self.result["archivos"][name], str)
                else self.result["archivos"][name]).hexdigest()}
            for kind, name in (("csv", "mercadolibre_validado.csv"), ("paquete", "paquete.zip"))}}

    def test_staging_does_not_advance_until_remote_confirmation(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            guardar_lote(self.result, root, publicar=False)
            self.assertFalse((root / "vigente.json").exists())
            pointer = self.pointer()
            pointer["archivos"]["paquete"]["sha256"] = "0" * 64
            with self.assertRaises(ValueError):
                confirmar_publicacion(pointer, root)
            self.assertFalse((root / "vigente.json").exists())
            confirmar_publicacion(self.pointer(), root)
            original = (root / "publicado.json").read_bytes()
            confirmar_publicacion(self.pointer(), root)
            self.assertEqual(original, (root / "publicado.json").read_bytes())

    def test_corrupt_remote_bundle_cannot_replace_current(self):
        pointer = self.pointer()
        pointer["archivos"]["paquete"].update(bytes=3)
        with patch("data_release.download_google", side_effect=[json.dumps(pointer).encode(), b"bad"]):
            with self.assertRaisesRegex(ValueError, "integridad"):
                load_remote("puntero_prueba_12345")


if __name__ == "__main__":
    unittest.main()
