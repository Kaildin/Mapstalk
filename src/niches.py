"""
Nicchie per Google Maps, lette dal database ufficiale delle categorie GMB:
    data/gmb-categories-it.json
    data/gmb-categories-en.json

Ogni entry di NICHES: (label_ui, [keyword_1, ...]).
La label e' il nome ufficiale della categoria e la keyword usata su Maps e' la label stessa.
"""

import logging
from pathlib import Path
from typing import List, Tuple

from .category_manager import CategoryManager

logger = logging.getLogger(__name__)

LANGS = ("it", "en")

_DATA_DIR = Path(__file__).resolve().parent.parent / "data"
_manager = CategoryManager(data_dir=str(_DATA_DIR))


def get_niches(lang: str = None) -> List[Tuple[str, List[str]]]:
    """Ritorna [(label, [keyword])] dalle categorie JSON.

    lang: "it" o "en" per una sola lingua; None per IT + EN uniti.
    """
    langs = (lang,) if lang in LANGS else LANGS
    seen = set()
    result: List[Tuple[str, List[str]]] = []
    for code in langs:
        names = sorted(_manager.get_all(code).values(), key=str.casefold)
        for name in names:
            key = name.casefold()
            if not name or key in seen:
                continue
            seen.add(key)
            result.append((name, [name]))
    return result


NICHES = get_niches()

if not NICHES:
    raise RuntimeError(
        f"Nessuna categoria caricata da {_DATA_DIR}. "
        "Controlla che data/gmb-categories-it.json e data/gmb-categories-en.json esistano "
        "e abbiano elementi con i campi 'id' e 'it'/'en'."
    )

logger.info(f"[Niches] Caricate {len(NICHES)} nicchie dai JSON GMB.")


def search_niches(query: str, limit: int = 10) -> List[str]:
    """Cerca label per sottostringa (case-insensitive), le piu' corte per prime."""
    q = query.strip().casefold()
    if not q:
        return []
    matches = [label for label, _kw in NICHES if q in label.casefold()]
    return sorted(matches, key=len)[:limit]
