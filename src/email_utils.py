"""
Local implementations for email extraction utilities.
Replaces outreach_saas dependencies for self-contained operation.
"""

import re
from typing import List, Dict, Any, Optional
import logging
import requests

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants (previously from outreach_saas.config.definitions)
# ---------------------------------------------------------------------------

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


def extract_emails_from_text(text: str) -> List[str]:
    """Extract emails from text using regex patterns."""
    emails = []
    if not text:
        return emails
    
    # Pattern migliorato che cattura anche mailto:
    patterns = [
        r'mailto:[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}\b',
        r'\b[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}\b',
    ]
    
    for pattern in patterns:
        try:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for match in matches:
                # Rimuovi mailto:
                email = re.sub(r'^mailto:', '', match, flags=re.IGNORECASE).strip().lower()
                if email and '@' in email and email not in emails:
                    # Filtro rapido: escludi TLD di file
                    domain = email.split('@')[1]
                    tld = domain.split('.')[-1]
                    if tld not in ['jpg', 'jpeg', 'png', 'gif', 'webp', 'svg', 'pdf', 'doc', 'xls']:
                        emails.append(email)
        except Exception as e:
            logger.debug(f"Error extracting emails with pattern {pattern}: {e}")
    
    return emails


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
