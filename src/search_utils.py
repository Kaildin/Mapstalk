"""
Local implementations for search utilities.
Replaces outreach_saas dependencies for self-contained operation.
"""

import logging
import requests
import json
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# DuckDuckGo Search (local implementation)
# ---------------------------------------------------------------------------

def ddg_search_improved(query: str, max_results: int = 5, region: str = "it-it") -> List[Dict[str, str]]:
    """
    Perform a search using DuckDuckGo's API.
    Returns a list of result dictionaries with 'title', 'snippet', and 'url'.
    """
    results = []
    
    if not query:
        return results
    
    try:
        # DuckDuckGo HTML API endpoint
        url = "https://html.duckduckgo.com/html/"
        params = {
            "q": query,
            "kl": region,
            "df": "",  # No date filter
        }
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'it-IT,it;q=0.9,en-US;q=0.8,en;q=0.7',
            'Referer': 'https://duckduckgo.com/',
            'DNT': '1',
        }
        
        response = requests.post(url, data=params, headers=headers, timeout=30)
        
        if response.status_code != 200:
            logger.debug(f"DuckDuckGo search failed with status {response.status_code}")
            return results
        
        # Parse the response (DuckDuckGo returns a custom format)
        # Try to extract results from the HTML-like response
        text = response.text
        
        # DuckDuckGo returns results in a custom format with "DDG" markers
        # This is a simplified parser
        lines = text.split('\n')
        current_result = {}
        in_result = False
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            if line == "DDG":
                # New result block
                if current_result and in_result:
                    results.append(current_result)
                current_result = {}
                in_result = True
                continue
            
            if in_result:
                if line.startswith("u:"):
                    current_result["url"] = line[2:].strip()
                elif line.startswith("t:"):
                    current_result["title"] = line[2:].strip()
                elif line.startswith("a:"):
                    current_result["snippet"] = line[2:].strip()
        
        # Add the last result if any
        if current_result and in_result:
            results.append(current_result)
        
        # Limit results
        return results[:max_results]
        
    except Exception as e:
        logger.debug(f"Error in DuckDuckGo search: {e}")
        return results


# ---------------------------------------------------------------------------
# Admin Extraction (local implementation without DeepSeek)
# ---------------------------------------------------------------------------

def extract_admin_with_deepseek(payload: str) -> Optional[str]:
    """
    Local implementation of admin extraction.
    Uses pattern matching instead of DeepSeek API.
    """
    if not payload:
        return None
    
    try:
        # Common patterns for admin names in search results
        # Look for patterns like "Amministratore: Mario Rossi" or "CEO: John Doe"
        admin_patterns = [
            r'amministratore[\s:]+([A-Z][a-z]+\s+[A-Z][a-z]+)',
            r'CEO[\s:]+([A-Z][a-z]+\s+[A-Z][a-z]+)',
            r'CEO[\s:]+([A-Z][a-z]+)',
            r'proprietario[\s:]+([A-Z][a-z]+\s+[A-Z][a-z]+)',
            r'titolare[\s:]+([A-Z][a-z]+\s+[A-Z][a-z]+)',
            r'direttore[\s:]+([A-Z][a-z]+\s+[A-Z][a-z]+)',
            r'founder[\s:]+([A-Z][a-z]+\s+[A-Z][a-z]+)',
            r'owner[\s:]+([A-Z][a-z]+\s+[A-Z][a-z]+)',
            r'manager[\s:]+([A-Z][a-z]+\s+[A-Z][a-z]+)',
            r'contatto[\s:]+([A-Z][a-z]+\s+[A-Z][a-z]+)',
        ]
        
        import re
        for pattern in admin_patterns:
            match = re.search(pattern, payload, re.IGNORECASE)
            if match:
                name = match.group(1).strip()
                # Clean up the name
                name = re.sub(r'\s+', ' ', name)
                if name and len(name.split()) >= 2:  # At least first and last name
                    return name
        
        # Try to find names in LinkedIn URLs
        linkedin_pattern = r'linkedin\.com/(in|pub)/([a-zA-Z0-9-]+)'
        matches = re.findall(linkedin_pattern, payload)
        if matches:
            # Return the first LinkedIn username found
            return matches[0][1].replace('-', ' ').title()
        
        # Try to find email addresses and extract names from them
        email_pattern = r'([a-zA-Z0-9._%+-]+)@'
        email_matches = re.findall(email_pattern, payload)
        if email_matches:
            # Try to extract a name from the local part of the email
            for local_part in email_matches:
                # Common email name patterns: firstname.lastname, firstname_lastname, firstinitiallastname
                if '.' in local_part:
                    parts = local_part.split('.')
                    if len(parts) >= 2:
                        name = ' '.join(part.capitalize() for part in parts)
                        return name
                elif '_' in local_part:
                    parts = local_part.split('_')
                    if len(parts) >= 2:
                        name = ' '.join(part.capitalize() for part in parts)
                        return name
        
        return None
        
    except Exception as e:
        logger.debug(f"Error extracting admin: {e}")
        return None
