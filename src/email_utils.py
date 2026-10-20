"""
Local implementations for email extraction utilities.
Replaces outreach_saas dependencies for self-contained operation.
"""

import re
import html
import urllib.parse
from typing import List, Dict, Any, Optional, Set
import logging
import requests

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants (previously from outreach_saas.config.definitions)
# ---------------------------------------------------------------------------

# ============================================================================
# EMAIL CLEANING CONSTANTS - 9 Categories of "dirt"
# ============================================================================

# Category 2: Asset grafici (@2x, @3x, etc.) - estensioni di file
IMAGE_EXTENSIONS = {
    'jpg', 'jpeg', 'png', 'gif', 'webp', 'svg', 'bmp', 'tiff', 'ico',
    'pdf', 'doc', 'docx', 'xls', 'xlsx', 'ppt', 'pptx', 'txt',
    'html', 'htm', 'css', 'js', 'json', 'xml', 'csv',
    'zip', 'rar', 'tar', 'gz', '7z', 'mp3', 'mp4', 'avi', 'mov',
}

# Category 2: Pattern per asset grafici con @nx
ASSET_PATTERNS = [
    re.compile(r'@\d+x\.'),  # @2x., @3x., etc.
    re.compile(r'@\d+x$'),   # @2x, @3x alla fine
    re.compile(r'@\d+\.'),  # @2., @3.
]

# Category 3: Tracking domains (Sentry, Wix, Error Tracker)
TRACKING_DOMAINS = {
    'sentry.io', 'sentry.wixpress.com', 'sentry-next.wixpress.com',
    'errors.dkd.de', 'ingest.sentry.io', 'o4508817376804864.ingest.de.sentry.io',
    'sentry.userreporting.com', 'sentry.prod',
}

# Category 3: Pattern per DSN di tracking
TRACKING_PATTERNS = [
    re.compile(r'[a-f0-9]{32,}@'),  # Hash esadecimale @
    re.compile(r'[a-f0-9]{20,}@'),  # Hash più corto
]

# Category 4: Placeholder/fake email domains
# NOTE: test.com, domain.com, example.com sono domini reali, ma anche usati come placeholder
# Li teniamo per ora, ma possiamo disabilitare il filtro con include_existing_filters=False
# o aggiungere logica più intelligente in futuro
FAKE_EMAIL_DOMAINS = {
    'esempio.it', 'esempio.com',
    'dominio.com', 'dominio.it', 'dominio.net',
    'yourdomain.com', 'your-domain.com', 'ilmiosito.com', 'miosito.com',
    'demo.com', 'demo.it',
    'placeholder.com', 'fake.com', 'dummy.com', 'lorem.com',
    'abc.com', 'xyz.com', '123.com',
}

# Category 4: Placeholder local parts
FAKE_LOCAL_PARTS = {
    'contatto', 'email', 'utente', 'user', 'nome', 'name', 'test',
    'john', 'johndoe', 'johnsmith', 'mario', 'mariorossi',
    'needhelp', 'yourname', 'you', 'your', 'myemail',
    'mail_to_define', 'bcc_email', 'cc_email', 'xxxx',
    'tua', 'tuaemail', 'esempio', 'example',
}

# Category 5: URL encoding patterns to clean
# NOTE: NON includere '20' come pattern! '20' è un numero valido nella local part
# Solo codifiche URL e Unicode escape sequenze
URL_ENCODING_PATTERNS = {
    '%20': ' ',     # Spazio URL-encoded
    'u0020': ' ',    # Unicode space
    'u003e': '>',    # Unicode >
    'u0022': '"',    # Unicode "
    'u0027': "'",    # Unicode '
    'u002f': '/',    # Unicode /
    'u003f': '?',    # Unicode ?
    'u0026': '&',    # Unicode &
}

# Category 6: Third-party vendor domains to filter
THIRD_PARTY_DOMAINS = {
    # Piattaforme/Hosting
    'webador.it', 'opencart.com', 'prestashop.com', 'godaddy.com',
    'wordpress.com', 'wix.com', 'weebly.com', 'squarespace.com',
    'shopify.com', 'bigcommerce.com', 'magneto.com',
    
    # Font & Icone
    'latofonts.com', 'fontawesome.com', 'fonts.google.com',
    
    # Privacy/DPO
    'google.com', 'osmfoundation.org', 'defiant.com', 'wordfence.com',
    
    # Temi WordPress
    'qodeinteractive.com', 'bold-themes.com', 'elegantthemes.com',
    'avada.theme-fusion.com', 'divi.com',
    
    # Web Agency (esempi generici - attentio a non filtrare troppo!)
    'lynx2000.it', 'proximaspa.it', 'sitebysite.it',
    
    # Altro
    'paypal.com', 'stripe.com', 'amazonaws.com',
}

# Category 7: Typo patterns (common mistakes)
TYPO_PATTERNS = [
    re.compile(r'\.itm$'),      # .itm invece di .it
    re.compile(r'\.itt$'),      # .itt invece di .it
    re.compile(r'\.com\.com$'), # .com.com
    re.compile(r'\.net\.net$'), # .net.net
    re.compile(r'^www\.$'),     # www. alla fine
    re.compile(r'^\.$'),        # . all'inizio del dominio
    re.compile(r'@\.$'),        # @. nel dominio
]

# Category 8: Deduplication
MAX_EMAILS_PER_FIELD = 20  # Limite massimo di email per singolo campo

# Big company keywords - used to skip large enterprises
BIG_COMPANY_KEYWORDS = [
    "enel", "eni", "edison", "acea", "a2a", "hera", "snam", "terna",
    "telecom", "tim", "vodafone", "wind", "fastweb", "poste italiane",
    "intesa sanpaolo", "unicredit", "banca intesa", "bnp paribas",
    "generali", "allianz", "axa", "zurich", "unipol", "cattolica",
    "ferrovie dello stato", "trenitalia", "italo", "autostrade",
    "fincantieri", "leonardo", "finmeccanica", "prysmian", "pirelli",
    "luxottica", "ferrari", "fiat", "stellantis", "lamborghini",
    "amazon", "google", "microsoft", "apple", "facebook", "meta",
    "tesla", "spacex", "boeing", "lockheed martin", "northrop grumman",
    "walmart", "costco", "target", "home depot", "lowes",
    "bank of america", "jpmorgan", "chase", "wells fargo", "citibank",
    "goldman sachs", "morgan stanley", "blackrock", "fidelity",
    "verizon", "att", "t-mobile", "comcast", "charter",
    "exxon", "chevron", "shell", "bp", "total", "conoco",
    "ford", "gm", "general motors", "toyota", "honda", "nissan",
    "mercedes", "bmw", "volkswagen", "hyundai", "kia",
    "coca cola", "pepsi", "pepsico", "nestle", "unilever",
    "procter & gamble", "johnson & johnson", "pfizer", "merck",
    "roche", "novartis", "gsk", "astrazeneca", "moderna",
    "intel", "amd", "nvidia", "qualcomm", "ibm", "oracle",
    "sap", "salesforce", "adobe", "autodesk", "cisco",
    "dell", "hp", "lenovo", "acer", "asus", "msi",
    "samsung", "lg", "sony", "panasonic", "sharp",
    "ikea", "leroy merlin", "obi", "bauhaus", "castorama",
    "decathlon", "nike", "adidas", "puma", "under armour",
    "zara", "h&m", "mango", "bershka", "pull&bear",
    "gucci", "prada", "armani", "dolce & gabbana", "valentino",
    "mcdonalds", "burger king", "kfc", "subway", "starbucks",
    "marriott", "hilton", "accor", "ihg", "wyndham",
    "ryanair", "easyjet", "lufthansa", "air france", "klm",
    "delta", "united", "american airlines", "southwest", "jetblue",
    "fedex", "ups", "dhl", "tnt", "gls",
    "maersk", "mediterranean shipping", "cma cgm", "cosco", "evergreen",
]

# Ignored email domains
IGNORED_EMAIL_DOMAINS = {
    "googlemail.com", "yahoo.com", "ymail.com", "rocketmail.com",
    "outlook.com", "hotmail.com", "live.com", "msn.com", "passport.com",
    "icloud.com", "me.com", "mac.com",
    "aol.com", "aim.com", "mail.com", "protonmail.com", "proton.me",
    "zoho.com", "yandex.com", "gmail.co.uk", "gmail.fr", "gmail.de",
    "hotmail.co.uk", "hotmail.fr", "hotmail.de", "outlook.co.uk",
    "outlook.fr", "outlook.de", "yahoo.co.uk", "yahoo.fr", "yahoo.de",
    "fastmail.com", "hushmail.com", "gmx.com", "gmx.us", "gmx.de",
    "gmx.fr", "gmx.co.uk", "mailinator.com", "tempmail.com", "guerrillamail.com",
    "10minutemail.com", "throwawaymail.com", "fakeinbox.com", "temp-mail.org",
    "trashmail.com", "maildrop.cc", "yopmail.com", "getnada.com",
    "tempinbox.com", "10minutemail.net", "20minutemail.com",
    "33mail.com", "emailondeck.com", "mohmal.com", "jetable.org",
    "mailexpire.com", "tempmail.net", "tempmail.pro", "temp-mail.io",
}

# Local part patterns to ignore
LOCAL_PART_IGNORE_PATTERNS = [
    re.compile(r"^info$"),
    re.compile(r"^contact$"),
    re.compile(r"^hello$"),
    re.compile(r"^hi$"),
    re.compile(r"^support$"),
    re.compile(r"^sales$"),
    re.compile(r"^admin$"),
    re.compile(r"^webmaster$"),
    re.compile(r"^postmaster$"),
    re.compile(r"^abuse$"),
    re.compile(r"^noreply$"),
    re.compile(r"^no[-_]?reply$"),
    re.compile(r"^feedback$"),
    re.compile(r"^help$"),
    re.compile(r"^assistance$"),
    re.compile(r"^service$"),
    re.compile(r"^customer[-_]?service$"),
    re.compile(r"^general$"),
    re.compile(r"^office$"),
    re.compile(r"^marketing$"),
    re.compile(r"^press$"),
    re.compile(r"^media$"),
    re.compile(r"^pr$"),
    re.compile(r"^hr$"),
    re.compile(r"^human[-_]?resources$"),
    re.compile(r"^careers$"),
    re.compile(r"^jobs$"),
    re.compile(r"^recruiting$"),
    re.compile(r"^newsletter$"),
    re.compile(r"^subscribe$"),
    re.compile(r"^unsubscribe$"),
    re.compile(r"^news$"),
    re.compile(r"^updates$"),
    re.compile(r"^alerts$"),
    re.compile(r"^web$"),
    re.compile(r"^www$"),
    re.compile(r"^hostmaster$"),
    re.compile(r"^usenet$"),
    re.compile(r"^uucp$"),
    re.compile(r"^news$"),
    re.compile(r"^list$"),
    re.compile(r"^listserv$"),
    re.compile(r"^majordomo$"),
]


# ---------------------------------------------------------------------------
# Email extraction functions
# ---------------------------------------------------------------------------

EMAIL_PATTERNS = [
    r'\b[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}\b',
    r'mailto:\b[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}\b'
]


def extract_emails_from_text(text: str, include_existing_filters: bool = True) -> List[str]:
    """
    Extract emails from text using regex patterns and clean them.
    Now uses the advanced cleaning logic for all 9 categories.
    
    Args:
        text: The text to extract emails from
        include_existing_filters: If True, also apply IGNORED_EMAIL_DOMAINS and LOCAL_PART_IGNORE_PATTERNS
    """
    if not text:
        return []
    
    # Pattern che cattura email e mailto:
    patterns = [
        r'mailto:[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}\b',
        r'\b[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}\b',
    ]
    
    raw_emails = []
    for pattern in patterns:
        try:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for match in matches:
                # Rimuovi mailto:
                email = re.sub(r'^mailto:', '', match, flags=re.IGNORECASE).strip()
                if email and '@' in email and email not in raw_emails:
                    raw_emails.append(email)
        except Exception as e:
            logger.debug(f"Error extracting emails with pattern {pattern}: {e}")
    
    # Now clean all extracted emails using the advanced cleaner
    if not raw_emails:
        return []
    
    # Use clean_email_list to handle all 9 categories
    return clean_email_list(raw_emails, include_existing_filters=include_existing_filters)


def extract_emails_from_website(url: str, timeout: int = 10) -> List[str]:
    """Extract emails from a website via HTTP request."""
    if not url:
        return []
    
    if not url.startswith(('http://', 'https://')):
        url = 'https://' + url
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'it-IT,it;q=0.9,en-US;q=0.8,en;q=0.7',
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=timeout)
        if response.status_code == 200:
            text = response.text
            return extract_emails_from_text(text)
    except Exception as e:
        logger.debug(f"Error downloading site {url}: {e}")
    
    return []


def filter_valid_emails(emails: List[str]) -> List[str]:
    """Filter valid emails excluding ignored domains and unwanted patterns."""
    valid_emails = []
    
    for email in emails:
        if not email or '@' not in email:
            continue
        
        try:
            domain = email.split('@')[1].lower()
            local_part = email.split('@')[0].lower()
            
            # Check ignored domains
            if domain in IGNORED_EMAIL_DOMAINS:
                logger.debug(f"Email skipped - ignored domain: {email}")
                continue
            
            # Check local part patterns
            if any(pattern.match(local_part) for pattern in LOCAL_PART_IGNORE_PATTERNS):
                logger.debug(f"Email skipped - local part pattern: {email}")
                continue
            
            # Check for disposable email domains
            disposable_domains = ['mailinator.com', 'tempmail.com', 'guerrillamail.com',
                                  '10minutemail.com', 'throwawaymail.com', 'fakeinbox.com']
            if domain in disposable_domains:
                logger.debug(f"Email skipped - disposable domain: {email}")
                continue
            
            valid_emails.append(email)
        except Exception:
            continue
    
    return valid_emails


# ---------------------------------------------------------------------------
# Advanced email cleaning - Handles all 9 categories of "dirt"
# ---------------------------------------------------------------------------

def clean_email_field(email_field: str, include_existing_filters: bool = True) -> List[str]:
    """
    Clean a single email field handling all 9 categories of dirt:
    1. mailto: prefix
    2. Asset grafici (@2x, @3x, ecc.)
    3. Log/DSN tracking (Sentry, Wix, ecc.)
    4. Indirizzi fittizi/placeholder
    5. Corruzione da codifica URL/Unicode
    6. Contatti fornitori terzi
    7. Errori di battitura (typos)
    8. Duplicazioni sistematiche
    9. Dump massivi
    
    Args:
        email_field: The raw email field string
        include_existing_filters: If True, also apply IGNORED_EMAIL_DOMAINS and LOCAL_PART_IGNORE_PATTERNS
    
    Returns a list of cleaned, unique, valid emails.
    """
    if not email_field or not email_field.strip():
        return []
    
    # Step 0: Normalizza il campo
    email_field = email_field.strip()
    
    # Step 1: Applica URL decoding e Unicode unescape
    cleaned_field = _decode_url_encoded(email_field)
    
    # Step 2: Splitta per separatori (virgola, spazio, punto e virgola)
    parts = re.split(r'[,\s;]+', cleaned_field)
    
    # Step 3: Processa ogni parte individualmente
    cleaned_emails = []
    for part in parts:
        part = part.strip()
        if not part or '@' not in part:
            continue
        
        # Step 3a: Pulizia specifica per singola parte (Category 5)
        part = _clean_single_email_part(part)
        
        # Step 3b: Rimuovi prefisso mailto: (Category 1)
        if part.lower().startswith('mailto:'):
            part = part[7:].strip()
        
        # Step 3b: Filtra asset grafici (Category 2)
        if _is_image_asset(part):
            logger.debug(f"Email skipped - image asset: {part}")
            continue
        
        # Step 3c: Filtra tracking IDs (Category 3)
        if _is_tracking_id(part):
            logger.debug(f"Email skipped - tracking ID: {part}")
            continue
        
        # Step 3d: Filtra placeholder/fake emails (Category 4)
        if _is_fake_email(part):
            logger.debug(f"Email skipped - fake/placeholder: {part}")
            continue
        
        # Step 3e: Filtra third-party vendors (Category 6)
        if _is_third_party_email(part):
            logger.debug(f"Email skipped - third party vendor: {part}")
            continue
        
        # Step 3f: Controlla per typos (Category 7)
        if _has_typo(part):
            logger.debug(f"Email skipped - typo detected: {part}")
            continue
        
        # Step 3g: Validazione finale dell'email
        if not _is_valid_email_format(part):
            logger.debug(f"Email skipped - invalid format: {part}")
            continue
        
        # Step 3h: Applica filtri esistenti se richiesto
        if include_existing_filters:
            if not _passes_existing_filters(part):
                logger.debug(f"Email skipped - existing filter: {part}")
                continue
        
        # Normalizza a lowercase
        cleaned_emails.append(part.lower())
    
    # Step 4: Deduplica (Category 8)
    cleaned_emails = list(dict.fromkeys(cleaned_emails))  # Preserva ordine
    
    # Step 5: Limita il numero massimo (Category 9 - Dump massivi)
    if len(cleaned_emails) > MAX_EMAILS_PER_FIELD:
        logger.debug(f"Email field truncated from {len(cleaned_emails)} to {MAX_EMAILS_PER_FIELD}")
        cleaned_emails = cleaned_emails[:MAX_EMAILS_PER_FIELD]
    
    return cleaned_emails


def _passes_existing_filters(email: str) -> bool:
    """Apply existing IGNORED_EMAIL_DOMAINS and LOCAL_PART_IGNORE_PATTERNS filters."""
    if not email or '@' not in email:
        return False
    
    try:
        domain = email.split('@')[1].lower()
        local_part = email.split('@')[0].lower()
        
        # Check ignored domains
        if domain in IGNORED_EMAIL_DOMAINS:
            return False
        
        # Check local part patterns
        if any(pattern.match(local_part) for pattern in LOCAL_PART_IGNORE_PATTERNS):
            return False
        
        # Check for disposable email domains
        disposable_domains = ['mailinator.com', 'tempmail.com', 'guerrillamail.com',
                              '10minutemail.com', 'throwawaymail.com', 'fakeinbox.com']
        if domain in disposable_domains:
            return False
        
        return True
    except Exception:
        return False


def clean_email_list(email_list: List[str], include_existing_filters: bool = True) -> List[str]:
    """
    Clean a list of email strings (from CSV email field).
    Each string can contain multiple emails separated by commas/spaces.
    
    Args:
        email_list: List of raw email field strings
        include_existing_filters: If True, also apply IGNORED_EMAIL_DOMAINS and LOCAL_PART_IGNORE_PATTERNS
    """
    if not email_list:
        return []
    
    all_emails = []
    for email_field in email_list:
        cleaned = clean_email_field(email_field, include_existing_filters=include_existing_filters)
        all_emails.extend(cleaned)
    
    # Final deduplication across all fields
    return list(dict.fromkeys(all_emails))


# ============================================================================
# Helper functions for email cleaning
# ============================================================================


def _decode_url_encoded(text: str) -> str:
    """
    Decode URL-encoded and Unicode-escaped characters (Category 5).
    
    GESTISCE:
    - %20 -> spazio (URL encoding)
    - \u003e -> > (Unicode escape)
    
    NON modifica numeri validi nella local part (es. 20info@ è valido!)
    La pulizia specifica per "20 info@" viene fatta a livello di singola email.
    """
    # HTML unescape prima (es. &amp; -> &)
    text = html.unescape(text)
    
    # URL decode (es. %20 -> spazio)
    try:
        text = urllib.parse.unquote(text)
    except Exception:
        pass
    
    # Unicode escape sequences (es. \u003e -> >)
    for encoded, decoded in URL_ENCODING_PATTERNS.items():
        text = text.replace(encoded, decoded)
    
    return text


def _clean_single_email_part(part: str) -> str:
    """
    Pulisce una singola parte di email (dopo decode e split).
    Gestisce specificamente Category 5: codifica URL/Unicode.
    """
    # Rimuovi spazi prima di @
    part = re.sub(r'\s+@', '@', part)
    
    # Gestione specifica per "20 info@" -> "info@"
    # Questo si verifica quando lo scraper ha catturato "mailto: 20info@..." o "%20info@..."
    # Dopo decode, diventa "20 info@..."
    # Vogliamo rimuovere il "20 " (con spazio) prima di @
    # Ma NON rimuovere "20" senza spazio (es. "20info@" è valido!)
    
    # Pattern: numero + spazio + lettera + @ -> rimuovi numero e spazio
    part = re.sub(r'(\d+)\s+([a-zA-Z]+@)', r'\2', part)
    
    # Strip
    return part.strip()


def _is_image_asset(email: str) -> bool:
    """Check if email is actually an image asset (Category 2)."""
    # Controlla estensioni di file
    domain = email.split('@')[1].lower() if '@' in email else email.lower()
    tld = domain.split('.')[-1]
    
    if tld in IMAGE_EXTENSIONS:
        return True
    
    # Controlla pattern @nx
    for pattern in ASSET_PATTERNS:
        if pattern.search(email):
            return True
    
    # Controlla nomi di file comuni
    if any(ext in domain.lower() for ext in ['.png', '.jpg', '.jpeg', '.gif', '.webp', '.svg']):
        return True
    
    return False


def _is_tracking_id(email: str) -> bool:
    """Check if email is a tracking DSN (Category 3)."""
    domain = email.split('@')[1].lower() if '@' in email else ""
    
    # Controlla domini di tracking noti
    if domain in TRACKING_DOMAINS:
        return True
    
    # Controlla se il dominio contiene tracking keywords
    if any(tracking in domain for tracking in ['sentry', 'wixpress', 'ingest', 'errors']):
        return True
    
    # Controlla pattern hash@
    for pattern in TRACKING_PATTERNS:
        if pattern.search(email):
            return True
    
    return False


def _is_fake_email(email: str) -> bool:
    """Check if email is a placeholder/fake (Category 4)."""
    if not email or '@' not in email:
        return False
    
    domain = email.split('@')[1].lower()
    local_part = email.split('@')[0].lower()
    
    # Controlla domini fake
    if domain in FAKE_EMAIL_DOMAINS:
        return True
    
    # Controlla local part fake
    if local_part in FAKE_LOCAL_PARTS:
        return True
    
    # Controlla pattern generici
    if re.match(r'^(test|demo|fake|placeholder|dummy|example|lorem)$', local_part):
        return True
    
    return False


def _is_third_party_email(email: str) -> bool:
    """Check if email belongs to third-party vendor (Category 6)."""
    if not email or '@' not in email:
        return False
    
    domain = email.split('@')[1].lower()
    
    if domain in THIRD_PARTY_DOMAINS:
        return True
    
    return False


def _has_typo(email: str) -> bool:
    """Check for common typo patterns (Category 7)."""
    if not email or '@' not in email:
        return False
    
    domain = email.split('@')[1].lower()
    
    # Controlla TLD errati comuni
    for pattern in TYPO_PATTERNS:
        if pattern.search(email.lower()):
            return True
    
    # Controlla se il dominio inizia con punto
    if domain.startswith('.'):
        return True
    
    # Controlla se la local part è solo numeri (es. 123@dominio.it)
    local_part = email.split('@')[0]
    if re.match(r'^\d+$', local_part):
        return True
    
    return False


def _is_valid_email_format(email: str) -> bool:
    """Validate email format with strict rules."""
    if not email or '@' not in email:
        return False
    
    try:
        local_part, domain = email.split('@')
        
        # Local part non può essere vuota
        if not local_part:
            return False
        
        # Domain non può essere vuoto
        if not domain:
            return False
        
        # Local part regex
        if not re.match(r'^[a-zA-Z0-9._%+-]+$', local_part):
            return False
        
        # Domain regex (almeno un punto, TLD di almeno 2 caratteri)
        if not re.match(r'^[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', domain):
            return False
        
        # TLD non può essere un'estensione di file
        tld = domain.split('.')[-1].lower()
        if tld in IMAGE_EXTENSIONS:
            return False
        
        # Domain non può iniziare o finire con punto
        if domain.startswith('.') or domain.endswith('.'):
            return False
        
        # Non può avere due punti consecutivi
        if '..' in domain:
            return False
        
        return True
        
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Company filtering
# ---------------------------------------------------------------------------

def is_big_company(name: str) -> bool:
    """Check if company name contains big company keywords."""
    if not name:
        return False
    name_lower = name.lower()
    return any(kw in name_lower for kw in BIG_COMPANY_KEYWORDS)


# ---------------------------------------------------------------------------
# Website Relevance Analyzer (simplified local version)
# ---------------------------------------------------------------------------

class WebsiteRelevanceAnalyzer:
    """
    Simplified website relevance analyzer for local use.
    Analyzes website content to determine if it's relevant to a specific industry.
    """
    
    # Industry keywords mapping
    INDUSTRY_KEYWORDS = {
        "fotovoltaico": [
            "fotovoltaico", "pannelli solari", "solare", "impianto solare", 
            "energia solare", "inverter", "batterie", "accumulo", "impianti fotovoltaici",
            "solar panels", "solar system", "photovoltaic", "renewable energy",
            "solar energy", "solar power", "pv system", "solar inverter",
        ],
        "idraulico": [
            "idraulico", "impianti idraulici", "tubature", "rubinetti", "scarichi",
            "pronto intervento idraulico", "perdite acqua", "caldaie", "riscaldamento",
            "plumber", "plumbing", "water leak", "pipe repair", "drain cleaning",
        ],
        "elettricista": [
            "elettricista", "impianti elettrici", "cablaggio", "quadro elettrico",
            "illuminazione", "pronto intervento elettrico", "cortocircuito",
            "electrician", "electrical installation", "wiring", "electrical panel",
            "lighting", "power outlet", "electrical repair",
        ],
        "edilizia": [
            "edilizia", "costruzioni", "ristrutturazioni", "muratura", "cantiere",
            "impresa edile", "edile", "restauro", "ristrutturazione",
            "construction", "building", "renovation", "masonry", "construction site",
            "general contractor", "home renovation",
        ],
        "giardinaggio": [
            "giardinaggio", "giardiniere", "manutenzione giardino", "potatura",
            "prato", "irrigazione", "piante", "alberi", "siepi",
            "gardening", "garden maintenance", "lawn care", "pruning",
            "irrigation", "plants", "trees", "hedges", "landscape",
        ],
        "pulizie": [
            "pulizie", "impresa di pulizie", "pulizia uffici", "pulizia case",
            "sanificazione", "igienizzazione", "pulizia industriale",
            "cleaning", "cleaning service", "office cleaning", "house cleaning",
            "sanitization", "deep cleaning", "industrial cleaning",
        ],
        "ristorazione": [
            "ristorante", "pizzeria", "trattoria", "bar", "caffe", "pub",
            "ristorazione", "catering", "menu", "cucina", "pranzo", "cena",
            "restaurant", "pizzeria", "trattoria", "bar", "cafe", "pub",
            "catering", "menu", "kitchen", "lunch", "dinner",
        ],
    }
    
    def __init__(self, industry: str = "fotovoltaico"):
        self.industry = industry.lower()
        self.keywords = self.INDUSTRY_KEYWORDS.get(industry, [])
        if not self.keywords:
            logger.warning(f"No keywords defined for industry: {industry}")
    
    def analyze_website_relevance(self, url: str, timeout: int = 10) -> Dict[str, Any]:
        """
        Analyze website content for relevance to the industry.
        Returns dict with is_relevant, category, and confidence.
        """
        if not url:
            return {
                "is_relevant": False,
                "category": "Sconosciuto",
                "confidence": 0.0,
            }
        
        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'it-IT,it;q=0.9,en-US;q=0.8,en;q=0.7',
        }
        
        try:
            response = requests.get(url, headers=headers, timeout=timeout)
            if response.status_code != 200:
                return {
                    "is_relevant": False,
                    "category": "Sconosciuto",
                    "confidence": 0.0,
                }
            
            text = response.text.lower()
            return self._analyze_text(text)
            
        except Exception as e:
            logger.debug(f"Error analyzing website {url}: {e}")
            return {
                "is_relevant": False,
                "category": "Sconosciuto",
                "confidence": 0.0,
            }
    
    def _analyze_text(self, text: str) -> Dict[str, Any]:
        """Analyze text content for industry relevance."""
        if not self.keywords:
            return {
                "is_relevant": False,
                "category": "Sconosciuto",
                "confidence": 0.0,
            }
        
        # Count keyword matches
        matches = 0
        for keyword in self.keywords:
            if keyword in text:
                matches += 1
        
        # Calculate confidence (0-1)
        keyword_count = len(self.keywords)
        confidence = min(matches / max(keyword_count, 1), 1.0)
        
        # Determine relevance
        is_relevant = matches >= max(1, keyword_count * 0.2)  # At least 20% of keywords or 1 match
        
        # Simple category detection
        category = self._detect_category(text)
        
        return {
            "is_relevant": is_relevant,
            "category": category,
            "confidence": round(confidence, 2),
        }
    
    def _detect_category(self, text: str) -> str:
        """Detect category from text content."""
        # Check for specific industry terms
        industry_terms = {
            "fotovoltaico": ["fotovoltaico", "solare", "pannelli solari", "photovoltaic", "solar panels"],
            "idraulico": ["idraulico", "impianti idraulici", "plumber", "plumbing"],
            "elettricista": ["elettricista", "impianti elettrici", "electrician", "electrical"],
            "edilizia": ["edilizia", "costruzioni", "construction", "building"],
            "giardinaggio": ["giardinaggio", "giardiniere", "gardening", "lawn care"],
            "pulizie": ["pulizie", "sanificazione", "cleaning", "cleaning service"],
            "ristorazione": ["ristorante", "pizzeria", "restaurant", "pizzeria"],
        }
        
        for category, terms in industry_terms.items():
            for term in terms:
                if term in text:
                    return category.capitalize()
        
        return "Sconosciuto"
