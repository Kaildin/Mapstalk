from src.niches import NICHES, get_niches, search_niches


def main():
    it = get_niches("it")
    en = get_niches("en")
    print(f"Totale: {len(NICHES)} | IT: {len(it)} | EN: {len(en)}")
    assert len(it) > 0, "Nessuna categoria IT caricata"
    assert len(en) > 0, "Nessuna categoria EN caricata"

    labels = {label.casefold() for label, _kw in NICHES}
    for probe in ("plumber", "idraulico", "elettricista", "dog groomer", "toelettatore"):
        print(f"  {probe!r}: {'OK' if probe in labels else 'NON TROVATA (esatta)'}")

    for q in ("idraul", "plumb", "toelett", "groom"):
        print(f"  ricerca {q!r}: {search_niches(q, 5)}")

    print("OK: nicchie caricate dai JSON")


if __name__ == "__main__":
    main()
