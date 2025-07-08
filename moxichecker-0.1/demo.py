"""
MoXIchecker Demo-Script
========================
Dependencies:
- Python >= 3.10
- pysmt==0.9.6 (Installation: pip install pysmt==0.9.6)
- Z3 SMT-Solver (Installation: pysmt-install --z3)

Verwendung:
$ python demo.py

Beispiel:
"examples/QF_LIA/FibonacciSequence_unreach.moxi.json" -> safe
"examples/QF_LIA/IntIncrement_reach.moxi.json" -> unsafe
"""

from moxichecker.main import main

# --------------------------
# Einstellungen anpassen
# --------------------------

# Pfad zur MoXI-Datei
MOXI_PATH1 = "examples/QF_LIA/FibonacciSequence_unreach.moxi.json"
MOXI_PATH2 = "examples/QF_LIA/IntIncrement_reach.moxi.json"

# Konfiguration: Solver und Algorithmus
args = [
    "--solver", "z3",         # oder msat
    "--mc-alg", "kind",       # kind, bmc, ic3
    MOXI_PATH1
]

# --------------------------
# Aufruf von MoXIchecker
# --------------------------

if __name__ == "__main__":
    print(f"🔍 Starte MoXIchecker mit Datei: {MOXI_PATH1}")
    print(f"⚙️  Konfiguration: Solver=z3, Algorithmus=k-induktion\n")
    main(args)
