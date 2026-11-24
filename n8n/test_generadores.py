"""Las plantillas deben reproducirse desde un clon público, sin datos privados."""

import json
from pathlib import Path
import shutil
import subprocess
import sys
import textwrap
from tempfile import TemporaryDirectory
import unittest


ROOT = Path(__file__).resolve().parent
GENERATORS = ("generar_flujo.py", "generar_flujo_drive.py", "generar_publicacion.py")


class GeneratorTests(unittest.TestCase):
    def clone_generators(self, folder):
        for name in GENERATORS:
            shutil.copyfile(ROOT / name, folder / name)

    def run_python(self, *args):
        return subprocess.run(
            [sys.executable, "-B", *map(str, args)],
            capture_output=True,
            text=True,
            check=True,
        )

    def test_importing_generators_does_not_create_or_modify_files(self):
        with TemporaryDirectory() as temp:
            folder = Path(temp)
            self.clone_generators(folder)
            before = {p.name: p.read_bytes() for p in folder.iterdir()}
            self.run_python(
                "-c",
                "import sys; sys.path.insert(0, sys.argv[1]); "
                "import generar_flujo, generar_flujo_drive, generar_publicacion",
                folder,
            )
            self.assertEqual({p.name: p.read_bytes() for p in folder.iterdir()}, before)

    def test_public_templates_are_reproducible_without_backups_or_credentials(self):
        with TemporaryDirectory() as temp:
            folder = Path(temp)
            self.clone_generators(folder)
            output = folder / "plantillas"
            self.run_python(folder / "generar_flujo.py", "--output-dir", output)
            self.run_python(folder / "generar_publicacion.py", "--output-dir", output)
            names = (
                "flujo_dataset_limpio.json",
                "flujo_drive_plantilla.json",
                "flujo_publicador_plantilla.json",
            )
            for name in names:
                flow = json.loads((output / name).read_text(encoding="utf-8"))
                expected = json.loads((ROOT / name).read_text(encoding="utf-8"))
                self.assertEqual(flow, expected)
                self.assertFalse(flow["active"])
                self.assertFalse(flow["pinData"])
                self.assertFalse(any(node.get("credentials") for node in flow["nodes"]))
                self.assertFalse(any("habilitar solo lectura" in node["name"] for node in flow["nodes"]))
                node_names = {node["name"] for node in flow["nodes"]}
                for node in flow["nodes"]:
                    code = node.get("parameters", {}).get("pythonCode")
                    if code:
                        compile("def execute(_items):\n" + textwrap.indent(code, "    "), name, "exec")
                for source, connections in flow["connections"].items():
                    self.assertIn(source, node_names)
                    for branch in connections["main"]:
                        for target in branch:
                            self.assertIn(target["node"], node_names)
            first = {p.name: p.read_bytes() for p in output.iterdir()}
            self.run_python(folder / "generar_publicacion.py", "--output-dir", output)
            self.assertEqual({p.name: p.read_bytes() for p in output.iterdir()}, first)
            self.assertFalse((folder / "backups").exists())

    def test_private_configuration_is_explicit_and_kept_out_of_public_templates(self):
        with TemporaryDirectory() as temp:
            folder = Path(temp)
            self.clone_generators(folder)
            output = folder / "publico"
            private = folder / "privado"
            private.mkdir()
            config_path = private / "destinos.json"
            config_path.write_text(
                json.dumps(
                    {
                        "workflow_id": "flujo-prueba",
                        "archivo_crudo": "crudo-prueba",
                        "carpeta_salida": "salida-prueba",
                    }
                ),
                encoding="utf-8",
            )
            export_path = private / "conexion.json"
            credentials = {"googleDriveOAuth2Api": {"id": "conexion-prueba", "name": "Prueba"}}
            export_path.write_text(json.dumps([{"nodes": [{"credentials": credentials}]}]), encoding="utf-8")
            args = (
                folder / "generar_publicacion.py",
                "--output-dir",
                output,
                "--config",
                config_path,
                "--credentials-from",
                export_path,
            )
            self.run_python(*args)
            config = json.loads(config_path.read_text(encoding="utf-8"))
            flows = json.loads((private / "flujos_publicacion.json").read_text(encoding="utf-8"))
            self.assertEqual({flow["id"] for flow in flows}, {"flujo-prueba", config["publicador_id"]})
            for flow in flows:
                drive_nodes = [node for node in flow["nodes"] if node["type"] == "n8n-nodes-base.googleDrive"]
                self.assertTrue(drive_nodes)
                self.assertTrue(all(node["credentials"] == credentials for node in drive_nodes))
            for path in output.iterdir():
                public = path.read_text(encoding="utf-8")
                self.assertNotIn("crudo-prueba", public)
                self.assertNotIn("salida-prueba", public)
                self.assertNotIn("conexion-prueba", public)
            self.run_python(*args)
            self.assertEqual(
                json.loads(config_path.read_text(encoding="utf-8"))["publicador_id"], config["publicador_id"]
            )


if __name__ == "__main__":
    unittest.main()
