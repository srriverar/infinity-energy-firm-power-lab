"""Prueba de humo: ejecuta cada página con streamlit.testing (sin navegador).

Uso:  python -m tests.smoke_app
"""
import sys
from pathlib import Path

from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parent.parent
PAGES = ["home", "contexto", "demo", "fisica", "ucf_page", "firmeza", "validacion", "roadmap", "tecnoeconomia", "eoi"]


def main() -> int:
    failures = 0
    for name in PAGES:
        at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=180)
        at.run()
        at.switch_page(f"views/{name}.py")
        at.run()
        n_exc = len(at.exception)
        print(f"{name:15s} excepciones={n_exc}")
        if n_exc:
            failures += 1
            for e in at.exception:
                print("   ", e.message)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
