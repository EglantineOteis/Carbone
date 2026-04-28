"""
ParseurDossier — lit les dossiers clients et extrait les données projet.

Formats supportés :
  - JSON  : données déjà structurées
  - Texte : extraction par mots-clés
  - PDF   : extraction via pdfplumber (si installé)
  - Auto  : détection par extension
"""

import json
import re
from pathlib import Path
from typing import Any
from datetime import datetime


class ParseurDossier:
    """Parse un dossier client et retourne un dict structuré."""

    # Valeurs par défaut si non trouvées dans le dossier
    DEFAULTS = {
        "nom_projet": "Projet sans nom",
        "maitre_ouvrage": "",
        "localisation": "",
        "type_batiment": "bureaux",
        "surface_plancher": 0,
        "nb_niveaux": 1,
        "zone_climatique": "H1",
        "annee_livraison": datetime.now().year + 2,
        "systeme_cvc": {
            "chauffage": "PAC air/eau",
            "climatisation": "PAC reversible",
            "ventilation": "double flux",
            "ecs": "PAC thermodynamique"
        },
        "enr": [],
        "isolation": {
            "murs": {"epaisseur_cm": 20, "materiau": "laine de roche"},
            "toiture": {"epaisseur_cm": 30, "materiau": "laine de roche"},
            "plancher_bas": {"epaisseur_cm": 16, "materiau": "polystyrene"}
        },
        "menuiseries": {
            "vitrage": "triple vitrage",
            "uw": 1.0,
            "sw": 0.35
        },
        "surface_vitre_pct": 30,
        "notes": ""
    }

    def lire(self, chemin: str, format: str = "auto") -> dict[str, Any]:
        """
        Lit un fichier ou dossier client et retourne les données structurées.

        Args:
            chemin: chemin vers le fichier ou dossier
            format: 'json', 'texte', 'pdf', ou 'auto'

        Returns:
            dict avec toutes les données projet + métadonnées de parsing
        """
        path = Path(chemin)

        if not path.exists():
            # Mode démonstration : retourne un projet exemple
            return self._projet_demo(chemin)

        # Détection automatique du format
        if format == "auto":
            format = self._detecter_format(path)

        # Lecture selon le format
        if format == "json":
            donnees = self._lire_json(path)
        elif format == "pdf":
            donnees = self._lire_pdf(path)
        else:
            donnees = self._lire_texte(path)

        # Compléter avec les valeurs par défaut
        donnees_completes = {**self.DEFAULTS, **donnees}

        # Ajouter métadonnées de parsing
        donnees_completes["_meta"] = {
            "source": str(path),
            "format_detecte": format,
            "date_lecture": datetime.now().isoformat(),
            "completude_pct": self._calculer_completude(donnees_completes)
        }

        return donnees_completes

    def _detecter_format(self, path: Path) -> str:
        suffix = path.suffix.lower()
        if suffix == ".json":
            return "json"
        elif suffix == ".pdf":
            return "pdf"
        elif path.is_dir():
            return "dossier"
        else:
            return "texte"

    def _lire_json(self, path: Path) -> dict:
        with open(path, encoding="utf-8") as f:
            return json.load(f)

    def _lire_texte(self, path: Path) -> dict:
        """Extraction par mots-clés dans un fichier texte."""
        texte = path.read_text(encoding="utf-8", errors="ignore")
        return self._extraire_donnees_texte(texte)

    def _lire_pdf(self, path: Path) -> dict:
        """Extraction depuis un PDF (nécessite pdfplumber)."""
        try:
            import pdfplumber
            texte = ""
            with pdfplumber.open(path) as pdf:
                for page in pdf.pages:
                    texte += page.extract_text() or ""
            return self._extraire_donnees_texte(texte)
        except ImportError:
            return {
                "notes": f"PDF non parsé (pdfplumber non installé) : {path.name}",
                "nom_projet": path.stem
            }

    def _extraire_donnees_texte(self, texte: str) -> dict:
        """Extraction par regex depuis du texte libre."""
        d = {}
        t = texte.lower()

        # Surface
        m = re.search(r"surface\s+(?:plancher|shon|utile)?\s*[:\-]?\s*([\d\s]+)\s*m[²2]", t)
        if m:
            d["surface_plancher"] = int(re.sub(r"\s", "", m.group(1)))

        # Localisation
        for ville in ["paris", "lyon", "marseille", "bordeaux", "nantes", "toulouse",
                      "lille", "strasbourg", "rennes", "nice", "grenoble", "rouen"]:
            if ville in t:
                d["localisation"] = ville.capitalize()
                break

        # Type de bâtiment
        for type_bat in ["bureaux", "logement", "ehpad", "scolaire", "commercial",
                         "industriel", "santé", "hôtel", "sport"]:
            if type_bat in t:
                d["type_batiment"] = type_bat
                break

        # Systèmes CVC
        cvc = {}
        if "pompe à chaleur" in t or "pac" in t:
            cvc["chauffage"] = "PAC air/eau"
        if "chaudière gaz" in t:
            cvc["chauffage"] = "Chaudière gaz"
        if "double flux" in t:
            cvc["ventilation"] = "double flux"
        if cvc:
            d["systeme_cvc"] = {**self.DEFAULTS["systeme_cvc"], **cvc}

        # ENR
        enr = []
        if "photovoltaïque" in t or "pv" in t:
            enr.append("photovoltaïque")
        if "solaire thermique" in t:
            enr.append("solaire thermique")
        if enr:
            d["enr"] = enr

        # Nom projet (première ligne souvent)
        premiere_ligne = texte.strip().split("\n")[0][:80]
        if premiere_ligne:
            d["nom_projet"] = premiere_ligne.strip()

        return d

    def _calculer_completude(self, d: dict) -> int:
        """Retourne le % de champs renseignés (hors _meta)."""
        champs_cles = ["nom_projet", "localisation", "surface_plancher",
                       "type_batiment", "systeme_cvc", "isolation"]
        renseignes = sum(
            1 for c in champs_cles
            if d.get(c) and d[c] != self.DEFAULTS.get(c)
        )
        return round(renseignes / len(champs_cles) * 100)

    def _projet_demo(self, nom: str) -> dict:
        """Retourne un projet de démonstration."""
        return {
            **self.DEFAULTS,
            "nom_projet": f"Démo — {Path(nom).stem}",
            "maitre_ouvrage": "OTEIS Group",
            "localisation": "Paris (75)",
            "type_batiment": "bureaux",
            "surface_plancher": 2500,
            "nb_niveaux": 5,
            "zone_climatique": "H1",
            "systeme_cvc": {
                "chauffage": "PAC air/eau",
                "climatisation": "PAC réversible",
                "ventilation": "double flux",
                "ecs": "PAC thermodynamique"
            },
            "enr": ["photovoltaïque"],
            "isolation": {
                "murs": {"epaisseur_cm": 20, "materiau": "laine de roche"},
                "toiture": {"epaisseur_cm": 30, "materiau": "laine de roche"},
                "plancher_bas": {"epaisseur_cm": 16, "materiau": "polystyrène"}
            },
            "menuiseries": {
                "vitrage": "triple vitrage",
                "uw": 0.9,
                "sw": 0.32
            },
            "surface_vitre_pct": 35,
            "notes": "Projet de démonstration généré automatiquement",
            "_meta": {
                "source": "demo",
                "format_detecte": "demo",
                "date_lecture": datetime.now().isoformat(),
                "completude_pct": 100
            }
        }
