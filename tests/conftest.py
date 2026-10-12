"""Configuration pytest pour les tests du projet scoring."""
import sys
from pathlib import Path

# Racine du projet
root = Path(__file__).parent.parent
sys.path.insert(0, str(root))

# Dossier api/ (contient shap_calculator, oracle_connector, auth, etc.)
sys.path.insert(0, str(root / "api"))
