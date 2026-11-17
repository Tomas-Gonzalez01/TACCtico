import csv
import sys
from pathlib import Path
from unittest.mock import patch

from streamlit.testing.v1 import AppTest


ROOT = Path(__file__).resolve().parents[1]


@patch.object(sys, "path", [str(ROOT / "app"), *sys.path])
def main():
    from purchase_data import market_csv

    with market_csv(ROOT).open(encoding="utf-8", newline="") as file:
        rows = list(csv.DictReader(file))
    app = AppTest.from_file(str(ROOT / "app" / "streamlit_app.py"), default_timeout=20).run()
    assert not app.exception and not app.error
    assert int(app.metric[0].value) == len(rows)
    assert set(app.dataframe[0].value["id_publicacion"]) == {row["id_publicacion"] for row in rows}

    app.text_input(key="titulo_real").set_value(rows[0]["titulo"]).run()
    assert not app.exception and not app.error
    assert app.dataframe[0].value["id_publicacion"].eq(rows[0]["id_publicacion"]).any()

    app.text_input(key="titulo_real").set_value("sin-coincidencias-tacctico").run()
    assert not app.exception and app.metric[0].value == "0" and app.info
    print(f"Catálogo validado con {len(rows)} publicaciones reales.")


if __name__ == "__main__":
    main()
