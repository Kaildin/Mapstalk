"""Utility per la deduplicazione dei lead tramite numero di telefono."""

import csv
import logging
import re
from pathlib import Path
from typing import Set

logger = logging.getLogger(__name__)


def phone_key(phone, lang: str = "en") -> str:
    """Normalizza un numero di telefono in una chiave confrontabile.

    Tiene solo le cifre (ignora icone/simboli, spazi, '+', parentesi, trattini),
    toglie il prefisso internazionale (IT: 39 / 0039, US: 1) e restituisce il
    numero nazionale. Ritorna '' se il numero e' troppo corto per essere affidabile.
    """
    digits = re.sub(r"[^0-9]", "", phone or "")
    if digits.startswith("00"):
        digits = digits[2:]
    if lang == "it":
        if digits.startswith("39") and len(digits) >= 11:
            digits = digits[2:]
    elif digits.startswith("1") and len(digits) == 11:
        digits = digits[1:]
    return digits if len(digits) >= 6 else ""


def load_known_phones(output_csv: str, lang: str = "en") -> Set[str]:
    """Legge il CSV esistente e ritorna l'insieme dei telefoni normalizzati gia' presenti."""
    known: Set[str] = set()
    path = Path(output_csv)
    if not path.exists():
        return known
    try:
        with open(path, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                key = phone_key(row.get("telefono"), lang)
                if key:
                    known.add(key)
        logger.info(f"[Dedup] {len(known)} telefoni gia' presenti nel CSV.")
    except Exception as e:
        logger.warning(f"[Dedup] Errore lettura telefoni dal CSV esistente: {e}")
    return known
