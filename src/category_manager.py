"""
Gestione centralizzata delle categorie GMB da file JSON.
Permette di caricare, cercare e validare le categorie da gmb-categories-it.json e gmb-categories-en.json.
"""

import json
import logging
from pathlib import Path
from typing import Dict, Optional, List, Tuple

logger = logging.getLogger(__name__)


class CategoryManager:
    """
    Gestisce il caricamento e la ricerca delle categorie GMB da JSON.
    Supporta sia italiano che inglese.
    """

    def __init__(self, data_dir: str = "data"):
        """
        Inizializza il CategoryManager.
        
        Args:
            data_dir: Cartella dove si trovano i file JSON (default: "data")
        """
        self.data_dir = Path(data_dir)
        self._categories: Dict[str, Dict[int, str]] = {}  # {"it": {id: nome}, "en": {id: nome}}
        self._reverse: Dict[str, Dict[str, int]] = {}    # {"it": {nome_lower: id}, "en": {nome_lower: id}}
        self._loaded = False
        self._load_all()

    def _load_all(self):
        """Carica tutti i file JSON delle categorie."""
        if self._loaded:
            return
        
        for lang in ["it", "en"]:
            file_path = self.data_dir / f"gmb-categories-{lang}.json"
            if file_path.exists():
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    
                    # Crea mapping id -> nome
                    self._categories[lang] = {}
                    for item in data:
                        if "id" in item and lang in item:
                            cat_id = int(item["id"])
                            cat_name = item[lang].strip()
                            self._categories[lang][cat_id] = cat_name
                    
                    # Crea reverse mapping nome -> id (case-insensitive)
                    self._reverse[lang] = {}
                    for cat_id, name in self._categories[lang].items():
                        self._reverse[lang][name.lower()] = cat_id
                    
                    logger.info(f"✅ Caricate {len(self._categories[lang])} categorie ({lang})")
                except Exception as e:
                    logger.error(f"❌ Errore caricamento {file_path}: {e}")
        
        self._loaded = True

    def get_by_id(self, cat_id: int, lang: str = "it") -> Optional[str]:
        """
        Ottieni il nome della categoria da ID.
        
        Args:
            cat_id: ID della categoria
            lang: Lingua ("it" o "en")
        
        Returns:
            Nome della categoria o None se non trovato
        """
        return self._categories.get(lang, {}).get(cat_id)

    def get_id_by_name(self, name: str, lang: str = "it") -> Optional[int]:
        """
        Ottieni l'ID della categoria da nome (case-insensitive).
        
        Args:
            name: Nome della categoria
            lang: Lingua ("it" o "en")
        
        Returns:
            ID della categoria o None se non trovato
        """
        return self._reverse.get(lang, {}).get(name.strip().lower())

    def search(self, query: str, lang: str = "it", top_n: int = 10) -> List[Tuple[int, str]]:
        """
        Cerca categorie per nome parziale.
        
        Args:
            query: Testo da cercare
            lang: Lingua ("it" o "en")
            top_n: Numero massimo di risultati
        
        Returns:
            Lista di tuple (id, nome) ordinate per similarità
        """
        query_lower = query.strip().lower()
        categories = self._categories.get(lang, {})
        results = []
        
        for cat_id, name in categories.items():
            if query_lower in name.lower():
                results.append((cat_id, name))
        
        # Ordina per lunghezza della stringa (più corto = più specifico)
        return sorted(results, key=lambda x: len(x[1]))[:top_n]

    def validate(self, name: str, lang: str = "it") -> Tuple[bool, Optional[int]]:
        """
        Verifica se una categoria esiste e restituisce l'ID.
        
        Args:
            name: Nome della categoria da validare
            lang: Lingua ("it" o "en")
        
        Returns:
            Tuple di (esiste: bool, id: Optional[int])
        """
        cat_id = self.get_id_by_name(name, lang)
        return (cat_id is not None, cat_id)

    def get_all(self, lang: str = "it") -> Dict[int, str]:
        """
        Ottieni tutte le categorie per una lingua.
        
        Args:
            lang: Lingua ("it" o "en")
        
        Returns:
            Dizionario {id: nome}
        """
        return self._categories.get(lang, {}).copy()


# Istanza globale (singleton)
category_manager = CategoryManager()
