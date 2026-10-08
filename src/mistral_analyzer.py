"""
Mistral API-based Website Relevance Analyzer.

This module provides asynchronous website relevance analysis using Mistral's most
cost-effective model (mistral-tiny) to determine if a website is relevant to a
specific industry/niche.

Features:
- Async HTTP requests for parallel processing
- HTML content extraction and truncation
- Mistral API integration for semantic analysis
- Batch processing for cost efficiency
- Configurable truncation and analysis parameters

Usage:
    from src.mistral_analyzer import MistralWebsiteAnalyzer
    
    analyzer = MistralWebsiteAnalyzer(
        api_key="your-mistral-api-key",
        industry="fotovoltaico"
    )
    
    # Sync usage
    result = analyzer.analyze_website("https://example.com")
    
    # Async usage (recommended for batch processing)
    results = await analyzer.analyze_websites_async([
        "https://site1.com",
        "https://site2.com"
    ])
"""

import asyncio
import logging
import re
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
import aiohttp

logger = logging.getLogger(__name__)


@dataclass
class AnalysisResult:
    """Result of website relevance analysis."""
    url: str
    is_relevant: bool
    category: str
    confidence: float
    analysis_text: Optional[str] = None
    error: Optional[str] = None
    tokens_used: Optional[int] = None


class MistralWebsiteAnalyzer:
    """
    Analyzes website relevance using Mistral API.
    
    Uses the most cost-effective Mistral model (mistral-tiny) to evaluate
    if a website's content is relevant to a specific industry.
    
    Args:
        api_key: Mistral API key (required)
        industry: Target industry/niche for relevance analysis
        model: Mistral model to use (default: "mistral-tiny" - cheapest)
        max_content_length: Max characters to send to API (default: 15000)
        timeout: HTTP timeout in seconds (default: 30)
        max_retries: Max retries for API calls (default: 3)
        rate_limit_delay: Delay between API calls in seconds (default: 0.1)
    """
    
    # Available Mistral models (ordered by cost - cheapest first)
    AVAILABLE_MODELS = [
        "mistral-tiny",      # Cheapest, fastest
        "mistral-small",    # Slightly more expensive, better quality
        "mistral-medium",   # More expensive
        "mistral-large",    # Most expensive
        "open-mistral-7b",  # Open source, good quality
        "open-mixtral-8x7b", # Open source, better quality
    ]
    
    # Default system prompt for relevance analysis (in Italian)
    DEFAULT_SYSTEM_PROMPT_IT = """Sei un esperto analista di mercato. Il tuo compito è valutare 
se il contenuto di un sito web è pertinente a una specifica nicchia di mercato.

Analizza il seguente contenuto HTML e rispondi SOLO in formato JSON con questa struttura:
{
    "is_relevant": true/false,
    "category": "nome della categoria rilevata o 'Sconosciuto'",
    "confidence": 0.0-1.0,
    "reasoning": "spiegazione breve in italiano"
}

Regole:
- "is_relevant" deve essere true solo se il sito tratta esplicitamente della nicchia specificata
- "confidence" deve essere un valore numerico tra 0 e 1
- "category" deve essere una singola parola o frase corta
- Non inventare informazioni non presenti nel contenuto
- Se il contenuto è scarsamente rilevante o generico, imposta is_relevant a false"""

    # Default system prompt for relevance analysis (in English)
    DEFAULT_SYSTEM_PROMPT_EN = """You are a market analysis expert. Your task is to evaluate 
whether a website's content is relevant to a specific market niche.

Analyze the following HTML content and respond ONLY in JSON format with this structure:
{
    "is_relevant": true/false,
    "category": "detected category name or 'Unknown'",
    "confidence": 0.0-1.0,
    "reasoning": "brief explanation in English"
}

Rules:
- "is_relevant" should be true only if the site explicitly deals with the specified niche
- "confidence" must be a numeric value between 0 and 1
- "category" should be a single word or short phrase
- Do not invent information not present in the content
- If content is barely relevant or generic, set is_relevant to false"""
    
    # HTML tags to remove for cleaner analysis
    HTML_TAGS_TO_REMOVE = [
        r'<script[^>]*>.*?</script>',
        r'<style[^>]*>.*?</style>',
        r'<noscript[^>]*>.*?</noscript>',
        r'<meta[^>]*>',
        r'<link[^>]*>',
        r'<img[^>]*>',
        r'<svg[^>]*>.*?</svg>',
        r'<iframe[^>]*>.*?</iframe>',
        r'<!--.*?-->',
        r'<[^>]+>',
    ]
    
    # Industry descriptions for better context (Italian)
    INDUSTRY_DESCRIPTIONS_IT = {
        "fotovoltaico": "Installazione, manutenzione e vendita di impianti fotovoltaici, pannelli solari, sistemi di accumulo, inverter",
        "idraulico": "Servizi idraulici, riparazione perdite, installazione impianti idraulici, manutenzione caldaie",
        "elettricista": "Installazione e manutenzione impianti elettrici, quadri elettrici, illuminazione, cablaggio",
        "edilizia": "Costruzione, ristrutturazione, muratura, impresa edile, restauro",
        "giardinaggio": "Manutenzione giardini, potatura, irrigazione, cura piante, prato",
        "pulizie": "Servizi di pulizia, sanificazione, igienizzazione, pulizia uffici e case",
        "ristorazione": "Ristoranti, pizzerie, bar, caffè, trattorie, catering",
        "arredamento": "Vendita e installazione mobili, cucine, bagni, complementi d'arredo",
        "informatica": "Assistenza computer, reti, software, hardware, sviluppo siti web",
        "climatizzazione": "Installazione e manutenzione climatizzatori, condizionatori, pompe di calore",
    }
    
    # Industry descriptions (English)
    INDUSTRY_DESCRIPTIONS_EN = {
        "fotovoltaico": "Installation, maintenance and sale of photovoltaic systems, solar panels, storage systems, inverters",
        "idraulico": "Plumbing services, leak repair, hydraulic system installation, boiler maintenance",
        "elettricista": "Installation and maintenance of electrical systems, electrical panels, lighting, wiring",
        "edilizia": "Construction, renovation, masonry, construction company, restoration",
        "giardinaggio": "Garden maintenance, pruning, irrigation, plant care, lawn",
        "pulizie": "Cleaning services, sanitation, disinfection, office and home cleaning",
        "ristorazione": "Restaurants, pizzerias, bars, cafes, trattorias, catering",
        "arredamento": "Furniture sales and installation, kitchens, bathrooms, furniture accessories",
        "informatica": "Computer assistance, networks, software, hardware, web development",
        "climatizzazione": "Installation and maintenance of air conditioners, air conditioners, heat pumps",
    }
    
    def __init__(
        self,
        api_key: str,
        industry: str = "fotovoltaico",
        model: str = "mistral-tiny",
        max_content_length: int = 15000,
        timeout: int = 30,
        max_retries: int = 3,
        rate_limit_delay: float = 0.1,
        language: str = "italian"
    ):
        """Initialize the analyzer."""
        if not api_key:
            raise ValueError("Mistral API key is required")
        
        if model not in self.AVAILABLE_MODELS:
            logger.warning(f"Model {model} not in available models, using mistral-tiny")
            model = "mistral-tiny"
        
        self.api_key = api_key
        self.industry = industry.lower()
        self.model = model
        self.max_content_length = max_content_length
        self.timeout = timeout
        self.max_retries = max_retries
        self.rate_limit_delay = rate_limit_delay
        self.language = language.lower()
        self.session = None
        
        # Select prompts based on language
        self.system_prompt = (
            self.DEFAULT_SYSTEM_PROMPT_IT if self.language == "italian" 
            else self.DEFAULT_SYSTEM_PROMPT_EN
        )
        
        # Get industry description
        descriptions = (
            self.INDUSTRY_DESCRIPTIONS_IT if self.language == "italian" 
            else self.INDUSTRY_DESCRIPTIONS_EN
        )
        self.industry_description = descriptions.get(industry, f"{industry} industry")
        
        logger.info(f"Initialized Mistral analyzer for industry: {industry}")
        logger.info(f"Using model: {model}")
        logger.info(f"Language: {language}")
    
    def _clean_html(self, html: str) -> str:
        """Remove unwanted HTML tags and clean content."""
        if not html:
            return ""
        
        text = html
        
        # Remove script, style, and other unwanted tags
        for pattern in self.HTML_TAGS_TO_REMOVE:
            text = re.sub(pattern, " ", text, flags=re.DOTALL | re.IGNORECASE)
        
        # Replace multiple spaces and newlines
        text = re.sub(r'\s+', ' ', text)
        text = text.strip()
        
        return text
    
    def _extract_main_content(self, html: str) -> str:
        """Extract main content from HTML, focusing on visible text."""
        if not html:
            return ""
        
        # Try to extract content from common containers
        content_patterns = [
            r'<main[^>]*>(.*?)</main>',
            r'<article[^>]*>(.*?)</article>',
            r'<div class="content"[^>]*>(.*?)</div>',
            r'<div id="content"[^>]*>(.*?)</div>',
            r'<body[^>]*>(.*?)</body>',
        ]
        
        for pattern in content_patterns:
            match = re.search(pattern, html, re.DOTALL | re.IGNORECASE)
            if match:
                return match.group(1)
        
        return html
    
    def _truncate_content(self, text: str, max_length: Optional[int] = None) -> str:
        """Truncate text to maximum length."""
        max_len = max_length or self.max_content_length
        if len(text) <= max_len:
            return text
        
        # Try to truncate at a sentence boundary
        truncated = text[:max_len]
        last_period = truncated.rfind('.')
        last_exclamation = truncated.rfind('!')
        last_question = truncated.rfind('?')
        
        last_boundary = max(last_period, last_exclamation, last_question)
        if last_boundary > max_len * 0.8:  # If boundary is close to end
            truncated = truncated[:last_boundary + 1]
        
        return truncated + "... [TRUNCATED]"
    
    def _build_prompt(self, content: str, url: str) -> str:
        """Build the prompt for Mistral API."""
        industry_context = f"Industria/Nicchia: {self.industry} ({self.industry_description})"
        
        prompt = f"""URL: {url}
{industry_context}

CONTENUTO SITO WEB:
{content}

Analizza il contenuto sopra e determina se è pertinente alla nicchia specificata.
Rispondi SOLO in formato JSON."""
        
        return prompt
    
    async def _fetch_website_content(self, url: str) -> Optional[str]:
        """Fetch website content asynchronously."""
        if not url:
            return None
        
        # Ensure URL has scheme
        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'it-IT,it;q=0.9,en-US;q=0.8,en;q=0.7',
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers, timeout=self.timeout) as response:
                    if response.status == 200:
                        html = await response.text()
                        return html
                    else:
                        logger.debug(f"HTTP {response.status} for {url}")
                        return None
        except Exception as e:
            logger.debug(f"Error fetching {url}: {e}")
            return None
    
    async def _call_mistral_api(
        self,
        prompt: str,
        retry_count: int = 0
    ) -> Optional[Dict[str, Any]]:
        """Call Mistral API asynchronously."""
        url = "https://api.mistral.ai/v1/chat/completions"
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.2,  # Low temperature for more deterministic results
            "max_tokens": 500,
            "response_format": {"type": "json_object"},  # Request JSON output
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    url, 
                    headers=headers, 
                    json=payload,
                    timeout=self.timeout
                ) as response:
                    if response.status == 200:
                        result = await response.json()
                        return result
                    elif response.status == 429:  # Rate limited
                        if retry_count < self.max_retries:
                            wait_time = 2 ** retry_count  # Exponential backoff
                            logger.warning(f"Rate limited, retrying in {wait_time}s...")
                            await asyncio.sleep(wait_time)
                            return await self._call_mistral_api(prompt, retry_count + 1)
                        else:
                            logger.error("Max retries exceeded for Mistral API")
                            return None
                    else:
                        error_text = await response.text()
                        logger.error(f"Mistral API error {response.status}: {error_text}")
                        return None
                        
        except Exception as e:
            logger.error(f"Error calling Mistral API: {e}")
            if retry_count < self.max_retries:
                await asyncio.sleep(2 ** retry_count)
                return await self._call_mistral_api(prompt, retry_count + 1)
            return None
    
    async def _analyze_with_mistral(self, content: str, url: str) -> Optional[Dict[str, Any]]:
        """Analyze content using Mistral API."""
        if not content:
            return None
        
        # Clean and extract content
        cleaned_content = self._clean_html(content)
        main_content = self._extract_main_content(cleaned_content)
        
        if not main_content or len(main_content.strip()) < 50:
            return None
        
        # Truncate content
        truncated_content = self._truncate_content(main_content)
        
        # Build prompt
        prompt = self._build_prompt(truncated_content, url)
        
        # Call Mistral API
        result = await self._call_mistral_api(prompt)
        
        if not result or 'choices' not in result:
            return None
        
        try:
            # Parse JSON response
            content_text = result['choices'][0]['message']['content'].strip()
            
            # Extract JSON from response (in case it's wrapped in markdown)
            if content_text.startswith('```json'):
                content_text = content_text[7:]
            if content_text.startswith('```'):
                content_text = content_text[3:]
            if content_text.endswith('```'):
                content_text = content_text[:-3]
            
            import json
            analysis = json.loads(content_text)
            
            # Extract usage info
            tokens_used = result.get('usage', {}).get('total_tokens', 0)
            
            return {
                **analysis,
                'tokens_used': tokens_used,
                'url': url
            }
            
        except (json.JSONDecodeError, KeyError, IndexError) as e:
            logger.error(f"Error parsing Mistral response: {e}")
            return None
    
    async def analyze_website_async(self, url: str) -> AnalysisResult:
        """
        Analyze a single website asynchronously.
        
        Args:
            url: Website URL to analyze
            
        Returns:
            AnalysisResult with relevance analysis
        """
        try:
            # Fetch website content
            html = await self._fetch_website_content(url)
            
            if not html:
                return AnalysisResult(
                    url=url,
                    is_relevant=False,
                    category="Sconosciuto",
                    confidence=0.0,
                    error="Failed to fetch website content"
                )
            
            # Analyze with Mistral
            analysis = await self._analyze_with_mistral(html, url)
            
            if not analysis:
                return AnalysisResult(
                    url=url,
                    is_relevant=False,
                    category="Sconosciuto", 
                    confidence=0.0,
                    error="Failed to analyze content"
                )
            
            return AnalysisResult(
                url=url,
                is_relevant=analysis.get('is_relevant', False),
                category=analysis.get('category', 'Sconosciuto'),
                confidence=float(analysis.get('confidence', 0.0)),
                analysis_text=analysis.get('reasoning'),
                tokens_used=analysis.get('tokens_used')
            )
            
        except Exception as e:
            logger.error(f"Error analyzing {url}: {e}")
            return AnalysisResult(
                url=url,
                is_relevant=False,
                category="Sconosciuto",
                confidence=0.0,
                error=str(e)
            )
    
    async def analyze_websites_async(
        self,
        urls: List[str],
        max_concurrent: int = 5
    ) -> List[AnalysisResult]:
        """
        Analyze multiple websites asynchronously.
        
        Args:
            urls: List of website URLs to analyze
            max_concurrent: Maximum number of concurrent analyses (default: 5)
            
        Returns:
            List of AnalysisResult objects
        """
        results = []
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def process_url(url: str) -> AnalysisResult:
            async with semaphore:
                result = await self.analyze_website_async(url)
                if self.rate_limit_delay > 0:
                    await asyncio.sleep(self.rate_limit_delay)
                return result
        
        tasks = [process_url(url) for url in urls]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Convert exceptions to error results
        final_results = []
        for result in results:
            if isinstance(result, Exception):
                final_results.append(AnalysisResult(
                    url="unknown",
                    is_relevant=False,
                    category="Sconosciuto",
                    confidence=0.0,
                    error=str(result)
                ))
            else:
                final_results.append(result)
        
        return final_results
    
    def analyze_website(self, url: str) -> AnalysisResult:
        """
        Analyze a single website synchronously.
        
        Args:
            url: Website URL to analyze
            
        Returns:
            AnalysisResult with relevance analysis
        """
        return asyncio.run(self.analyze_website_async(url))
    
    def analyze_websites(self, urls: List[str], max_concurrent: int = 5) -> List[AnalysisResult]:
        """
        Analyze multiple websites synchronously.
        
        Args:
            urls: List of website URLs to analyze
            max_concurrent: Maximum number of concurrent analyses (default: 5)
            
        Returns:
            List of AnalysisResult objects
        """
        return asyncio.run(self.analyze_websites_async(urls, max_concurrent))
    
    def close(self):
        """Close the analyzer and cleanup resources."""
        if self.session:
            try:
                asyncio.run(self.session.close())
            except:
                pass
        self.session = None
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()


# Convenience function for one-off analysis
async def analyze_website_relevance(
    api_key: str,
    url: str,
    industry: str = "fotovoltaico",
    model: str = "mistral-tiny",
    **kwargs
) -> AnalysisResult:
    """
    Convenience function for one-off website relevance analysis.
    
    Args:
        api_key: Mistral API key
        url: Website URL to analyze
        industry: Target industry
        model: Mistral model to use
        **kwargs: Additional arguments for MistralWebsiteAnalyzer
        
    Returns:
        AnalysisResult
    """
    analyzer = MistralWebsiteAnalyzer(
        api_key=api_key,
        industry=industry,
        model=model,
        **kwargs
    )
    return await analyzer.analyze_website_async(url)


# Batch analysis function
async def analyze_websites_batch(
    api_key: str,
    urls: List[str],
    industry: str = "fotovoltaico",
    model: str = "mistral-tiny",
    max_concurrent: int = 5,
    **kwargs
) -> List[AnalysisResult]:
    """
    Analyze a batch of websites for relevance.
    
    Args:
        api_key: Mistral API key
        urls: List of URLs to analyze
        industry: Target industry
        model: Mistral model to use
        max_concurrent: Maximum concurrent analyses
        **kwargs: Additional arguments for MistralWebsiteAnalyzer
        
    Returns:
        List of AnalysisResult objects
    """
    analyzer = MistralWebsiteAnalyzer(
        api_key=api_key,
        industry=industry,
        model=model,
        **kwargs
    )
    return await analyzer.analyze_websites_async(urls, max_concurrent)
