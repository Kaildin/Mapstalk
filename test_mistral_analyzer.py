#!/usr/bin/env python3
"""
Test script for Mistral Website Relevance Analyzer.

This script demonstrates how to use the MistralWebsiteAnalyzer to analyze
websites for relevance to a specific industry.

Usage:
    # Set your Mistral API key as environment variable
    export MISTRAL_API_KEY="your-api-key"
    
    # Run the test
    python test_mistral_analyzer.py
    
    # Or with custom parameters
    python test_mistral_analyzer.py --industry fotovoltaico --urls https://example1.com https://example2.com
    
    # For batch testing
    python test_mistral_analyzer.py --batch --urls-file urls.txt --output results.json
"""

import argparse
import asyncio
import json
import logging
import os
from typing import List
import sys

# Add src to path
sys.path.insert(0, str(os.path.dirname(os.path.abspath(__file__))))

from src.mistral_analyzer import MistralWebsiteAnalyzer, analyze_website_relevance, analyze_websites_batch

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s',
    handlers=[
        logging.FileHandler("mistral_analyzer_test.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


def get_api_key() -> str:
    """Get Mistral API key from environment or prompt."""
    api_key = os.getenv('MISTRAL_API_KEY')
    
    if not api_key:
        api_key = input("Enter your Mistral API key: ").strip()
        if not api_key:
            raise ValueError("Mistral API key is required")
        
        # Optionally save to environment for this session
        os.environ['MISTRAL_API_KEY'] = api_key
    
    return api_key


def read_urls_from_file(file_path: str) -> List[str]:
    """Read URLs from a text file (one per line)."""
    urls = []
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    urls.append(line)
        logger.info(f"Read {len(urls)} URLs from {file_path}")
    except Exception as e:
        logger.error(f"Error reading URLs from {file_path}: {e}")
    
    return urls


async def test_single_website(api_key: str, url: str, industry: str = "fotovoltaico"):
    """Test analysis of a single website."""
    logger.info(f"Analyzing single website: {url}")
    logger.info(f"Industry: {industry}")
    
    analyzer = MistralWebsiteAnalyzer(
        api_key=api_key,
        industry=industry,
        model="mistral-tiny",
        max_content_length=10000,
        rate_limit_delay=0.5  # Be gentle with API
    )
    
    result = await analyzer.analyze_website_async(url)
    
    print("\n" + "=" * 60)
    print("ANALYSIS RESULT")
    print("=" * 60)
    print(f"URL: {result.url}")
    print(f"Relevant: {result.is_relevant}")
    print(f"Category: {result.category}")
    print(f"Confidence: {result.confidence:.2%}")
    if result.analysis_text:
        print(f"Reasoning: {result.analysis_text}")
    if result.tokens_used:
        print(f"Tokens used: {result.tokens_used}")
    if result.error:
        print(f"Error: {result.error}")
    print("=" * 60)
    
    return result


async def test_batch_websites(api_key: str, urls: List[str], industry: str = "fotovoltaico"):
    """Test analysis of multiple websites in batch."""
    logger.info(f"Analyzing {len(urls)} websites in batch")
    logger.info(f"Industry: {industry}")
    
    results = await analyze_websites_batch(
        api_key=api_key,
        urls=urls,
        industry=industry,
        model="mistral-tiny",
        max_concurrent=3,  # Keep it low for testing
        max_content_length=8000,
        rate_limit_delay=0.5
    )
    
    # Print summary
    print("\n" + "=" * 60)
    print("BATCH ANALYSIS SUMMARY")
    print("=" * 60)
    
    relevant_count = sum(1 for r in results if r.is_relevant)
    total_tokens = sum(r.tokens_used or 0 for r in results)
    error_count = sum(1 for r in results if r.error)
    
    print(f"Total websites analyzed: {len(results)}")
    print(f"Relevant websites: {relevant_count}")
    print(f"Irrelevant websites: {len(results) - relevant_count}")
    print(f"Total tokens used: {total_tokens}")
    print(f"Errors: {error_count}")
    print("=" * 60)
    
    # Print detailed results
    print("\nDETAILED RESULTS:")
    print("-" * 60)
    
    for i, result in enumerate(results, 1):
        status = "✓" if result.is_relevant else "✗"
        print(f"[{i}] {status} {result.url}")
        print(f"    Category: {result.category}")
        print(f"    Confidence: {result.confidence:.2%}")
        if result.error:
            print(f"    Error: {result.error}")
        if result.tokens_used:
            print(f"    Tokens: {result.tokens_used}")
        print()
    
    return results


async def interactive_test(api_key: str):
    """Interactive test mode."""
    print("\n" + "=" * 60)
    print("INTERACTIVE MISTRAL ANALYZER TEST")
    print("=" * 60)
    
    industry = input("Enter industry/niche (default: fotovoltaico): ").strip() or "fotovoltaico"
    
    while True:
        url = input("\nEnter URL to analyze (or 'quit' to exit): ").strip()
        
        if url.lower() in ['quit', 'exit', 'q']:
            break
        
        if not url:
            continue
        
        await test_single_website(api_key, url, industry)
    
    print("Goodbye!")


async def main():
    parser = argparse.ArgumentParser(
        description="Test Mistral Website Relevance Analyzer"
    )
    parser.add_argument('--urls', nargs='+', default=[],
                       help='URLs to analyze')
    parser.add_argument('--urls-file', type=str, default=None,
                       help='Text file with URLs (one per line)')
    parser.add_argument('--industry', type=str, default='fotovoltaico',
                       help='Industry/niche to analyze for (default: fotovoltaico)')
    parser.add_argument('--batch', action='store_true',
                       help='Run batch analysis')
    parser.add_argument('--output', type=str, default=None,
                       help='Output file for results (JSON)')
    parser.add_argument('--interactive', action='store_true',
                       help='Interactive mode')
    
    args = parser.parse_args()
    
    # Get API key
    try:
        api_key = get_api_key()
    except ValueError as e:
        logger.error(str(e))
        return
    
    # Collect URLs
    urls = args.urls.copy()
    if args.urls_file:
        file_urls = read_urls_from_file(args.urls_file)
        urls.extend(file_urls)
    
    # Remove duplicates
    urls = list(set(urls))
    
    if args.interactive:
        await interactive_test(api_key)
        return
    
    if not urls:
        # No URLs provided, show help and interactive mode
        parser.print_help()
        print("\nNo URLs provided. Running in interactive mode...")
        await interactive_test(api_key)
        return
    
    # Run analysis
    if args.batch or len(urls) > 1:
        results = await test_batch_websites(api_key, urls, args.industry)
    else:
        results = [await test_single_website(api_key, urls[0], args.industry)]
    
    # Save results if output file specified
    if args.output and results:
        try:
            with open(args.output, 'w', encoding='utf-8') as f:
                json.dump(
                    [r.__dict__ for r in results],
                    f,
                    indent=2,
                    ensure_ascii=False
                )
            logger.info(f"Results saved to {args.output}")
        except Exception as e:
            logger.error(f"Error saving results: {e}")


if __name__ == "__main__":
    asyncio.run(main())
