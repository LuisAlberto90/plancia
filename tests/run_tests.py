"""python tests/run_tests.py  — lancia tutti i test (sola libreria standard; test_piano_modello salta la parte YAML se manca PyYAML)."""
import subprocess, sys
from pathlib import Path
Q = Path(__file__).resolve().parent; rc = 0
for t in ("test_piano_modello.py", "test_ciclo.py", "test_guardie_mcp.py", "test_panoramica.py", "test_vscode.py", "test_pannello_browser.py"):
    print("==", t); r = subprocess.run([sys.executable, str(Q / t)]); rc |= r.returncode
print("\nTUTTO OK" if rc == 0 else "\nCI SONO KO"); sys.exit(rc)
