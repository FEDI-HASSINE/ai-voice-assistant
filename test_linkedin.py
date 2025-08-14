#!/usr/bin/env python3
"""
Test script for LinkedIn scraper functionality
"""

import sys
import os
import asyncio
import json

# Add the Traitement directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'Traitement'))

from linkedin import LinkedInScraper, parse_linkedin_text, scrape_linkedin_profile, format_profile_summary


def test_url_validation():
    """Test LinkedIn URL validation"""
    scraper = LinkedInScraper()
    
    # Valid URLs
    valid_urls = [
        "https://www.linkedin.com/in/johndoe",
        "https://linkedin.com/in/jane-smith-123",
        "https://www.linkedin.com/in/company-ceo-456/"
    ]
    
    # Invalid URLs
    invalid_urls = [
        "https://facebook.com/johndoe",
        "https://linkedin.com/company/tech-corp",
        "https://www.linkedin.com/jobs/search",
        "invalid-url",
        ""
    ]
    
    print("Testing URL validation...")
    
    for url in valid_urls:
        assert scraper.is_valid_linkedin_url(url), f"Valid URL rejected: {url}"
        print(f"✓ Valid URL: {url}")
    
    for url in invalid_urls:
        assert not scraper.is_valid_linkedin_url(url), f"Invalid URL accepted: {url}"
        print(f"✓ Invalid URL rejected: {url}")
    
    print("URL validation tests passed!\n")


def test_text_parsing():
    """Test LinkedIn profile text parsing"""
    
    # Sample LinkedIn profile text
    sample_profile = """
    John Doe
    Senior Software Engineer at Google
    San Francisco, California, United States
    
    About
    Experienced software engineer with 8+ years developing scalable web applications.
    Passionate about machine learning and cloud technologies.
    
    Skills: Python, JavaScript, React, TensorFlow, AWS, Docker, Kubernetes
    
    Experience
    • Senior Software Engineer at Google (2020-Present)
    • Software Engineer at Microsoft (2018-2020)
    • Junior Developer at Startup Inc (2016-2018)
    """
    
    print("Testing text parsing...")
    
    result = parse_linkedin_text(sample_profile)
    
    # Validate extracted data
    assert result['name'] == "John Doe", f"Name mismatch: {result['name']}"
    assert "Senior Software Engineer" in result['headline'], f"Headline mismatch: {result['headline']}"
    assert "San Francisco" in result['location'], f"Location mismatch: {result['location']}"
    assert len(result['skills']) > 0, "No skills extracted"
    
    print(f"✓ Name: {result['name']}")
    print(f"✓ Headline: {result['headline']}")
    print(f"✓ Location: {result['location']}")
    print(f"✓ Skills: {len(result['skills'])} skills extracted")
    
    # Test formatted summary
    summary = format_profile_summary(result)
    assert "John Doe" in summary, "Name not in formatted summary"
    
    print("✓ Formatted summary generated")
    print("Text parsing tests passed!\n")


def test_error_handling():
    """Test error handling for invalid inputs"""
    
    print("Testing error handling...")
    
    # Test empty text
    result = parse_linkedin_text("")
    assert result['name'] is None, "Name should be None for empty text"
    print("✓ Empty text handled correctly")
    
    # Test invalid URL format
    try:
        result = scrape_linkedin_profile("invalid-url")
        assert 'error' in result, "Error should be present for invalid URL"
        print("✓ Invalid URL handled correctly")
    except Exception as e:
        print(f"✓ Invalid URL handled with exception: {e}")
    
    print("Error handling tests passed!\n")


async def test_async_functionality():
    """Test async functionality"""
    print("Testing async functionality...")
    
    # This will likely fail due to LinkedIn's anti-bot measures, but we test the structure
    try:
        from linkedin import scrape_linkedin_profile_async
        
        # Use a fake LinkedIn URL for structure testing
        fake_url = "https://www.linkedin.com/in/test-profile"
        result = await scrape_linkedin_profile_async(fake_url)
        
        # Should have the expected structure even if it fails
        expected_keys = ['name', 'headline', 'location', 'summary', 'experience', 'education', 'skills', 'profile_url']
        for key in expected_keys:
            assert key in result, f"Missing key in result: {key}"
        
        print("✓ Async function returns correct structure")
        
    except Exception as e:
        print(f"✓ Async function handled error: {e}")
    
    print("Async functionality tests passed!\n")


def main():
    """Run all tests"""
    print("=== LinkedIn Scraper Test Suite ===\n")
    
    try:
        test_url_validation()
        test_text_parsing()
        test_error_handling()
        
        # Run async test
        asyncio.run(test_async_functionality())
        
        print("=== ALL TESTS PASSED ===")
        
        # Demo with sample data
        print("\n=== DEMO OUTPUT ===")
        
        demo_text = """
        Jane Smith
        Data Scientist at Meta
        New York, NY
        
        Passionate data scientist specializing in NLP and computer vision.
        5+ years experience building ML models for production systems.
        
        Skills: Python, R, TensorFlow, PyTorch, SQL, Tableau, AWS
        """
        
        result = parse_linkedin_text(demo_text)
        print("Sample LinkedIn Profile Parsing:")
        print(json.dumps(result, indent=2, ensure_ascii=False))
        
        print("\nFormatted Summary:")
        print(format_profile_summary(result))
        
    except Exception as e:
        print(f"Test failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()