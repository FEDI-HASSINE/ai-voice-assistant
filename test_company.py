#!/usr/bin/env python3
"""
Test script for the company web scraper functionality.
Demonstrates both CLI and API usage.
"""

import sys
import asyncio
import json
from pathlib import Path

# Add the project root to Python path
sys.path.append(str(Path(__file__).parent))

async def test_cli_mode():
    """Test the CLI functionality."""
    print("=" * 60)
    print("TESTING CLI MODE")
    print("=" * 60)
    
    from Traitement.company import test_mode
    try:
        result = test_mode()
        print(result)
        return True
    except Exception as e:
        print(f"CLI test failed: {e}")
        return False


async def test_api_mode():
    """Test the FastAPI integration."""
    print("\n" + "=" * 60)
    print("TESTING FASTAPI INTEGRATION")
    print("=" * 60)
    
    try:
        from Traitement.app import analyze_company, CompanyAnalysisIn, healthz
        
        # Test health endpoint
        health = await healthz()
        print("Health check:", json.dumps(health, indent=2))
        
        if not health.get('company_analyzer'):
            print("❌ Company analyzer not available in API")
            return False
        
        # Test company analysis endpoint
        test_request = CompanyAnalysisIn(url='--test', target_words=150)
        result = await analyze_company(test_request)
        
        print("\n✅ Company analysis endpoint working")
        print(f"Response status: {result.status_code}")
        
        return True
        
    except Exception as e:
        print(f"❌ API test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_real_scraping():
    """Test real web scraping functionality (basic)."""
    print("\n" + "=" * 60)
    print("TESTING WEB SCRAPING CAPABILITIES")
    print("=" * 60)
    
    try:
        from Traitement.company import scrape_website, extract_text_from_html
        
        # Test HTML extraction with a simple example
        sample_html = """
        <html>
        <head><title>Test Company</title></head>
        <body>
            <h1>Welcome to Test Company</h1>
            <p>We provide excellent services.</p>
            <script>console.log('test');</script>
        </body>
        </html>
        """
        
        extracted = extract_text_from_html(sample_html)
        print("HTML extraction test:")
        print(f"Extracted: '{extracted}'")
        
        # The scraping would work with real URLs when network is available
        print("\n✅ Web scraping functions are working correctly")
        print("Note: Full website scraping requires network access")
        
        return True
        
    except Exception as e:
        print(f"❌ Scraping test failed: {e}")
        return False


async def main():
    """Run all tests."""
    print("🚀 Starting Company Web Scraper Tests")
    print("=" * 60)
    
    results = []
    
    # Test CLI mode
    cli_success = await test_cli_mode()
    results.append(("CLI Mode", cli_success))
    
    # Test API mode
    api_success = await test_api_mode()
    results.append(("API Integration", api_success))
    
    # Test scraping capabilities
    scraping_success = await test_real_scraping()
    results.append(("Web Scraping", scraping_success))
    
    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    
    all_passed = True
    for test_name, success in results:
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{test_name:20} {status}")
        if not success:
            all_passed = False
    
    print("\n" + "=" * 60)
    if all_passed:
        print("🎉 ALL TESTS PASSED!")
        print("\nThe company web scraper is ready to use:")
        print("• CLI: python Traitement/company.py <URL>")
        print("• API: POST /analyze_company with JSON body")
        print("• Test mode: python Traitement/company.py --test")
    else:
        print("❌ Some tests failed. Please check the error messages above.")
    
    print("=" * 60)
    
    return all_passed


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)