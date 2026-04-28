import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent))

from core.moteur_calcul import MoteurCalcul
from core.parseur_dossier import ParseurDossier

parseur = ParseurDossier()
moteur = MoteurCalcul(Path("data/bases"))

def analyser_projet(chemin):
    data = parseur.lire(chemin)
    bilan = moteur.calculer(data)
    return data, bilan
