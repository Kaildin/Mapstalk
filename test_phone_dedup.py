from src.dedup_utils import phone_key

ICON = chr(0xE0B0)


def check(raw, lang, expected):
    got = phone_key(raw, lang)
    assert got == expected, f"{raw!r} ({lang}) -> {got!r}, atteso {expected!r}"


def main():
    check(ICON + " +39 342 809 7473", "it", "3428097473")
    check(" +39 342 809 7473", "it", "3428097473")
    check("342 809 7473", "it", "3428097473")
    check("0039 342 809 7473", "it", "3428097473")
    check("+39 06 1234567", "it", "061234567")
    check("06 1234567", "it", "061234567")
    check("391 234 5678", "it", "3912345678")
    check("(512) 555-0147", "en", "5125550147")
    check("+1 512-555-0147", "en", "5125550147")
    check("1-512-555-0147", "en", "5125550147")
    check("", "en", "")
    check("12345", "en", "")
    print("OK: tutti i test phone_key passati")


if __name__ == "__main__":
    main()
