"""Configuration pytest pour les tests du projet scoring."""
import sys
from pathlib import Path

# Ajouter le répertoire racine du projet au path pour importer shap_calculator
sys.path.insert(0, str(Path(__file__).parent.parent))
