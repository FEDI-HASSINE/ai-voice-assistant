"""
LinkedIn Profile Scraper Module

This module provides functionality to scrape LinkedIn profiles and extract structured data.
It includes multiple approaches for data extraction with proper error handling and rate limiting.
"""

import os
import re
import time
import json
import logging
import asyncio
from typing import Dict, List, Optional, Any, Union
from urllib.parse import urlparse, urljoin
from dataclasses import dataclass, asdict

import requests
from bs4 import BeautifulSoup
import httpx

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
)
DEFAULT_TIMEOUT = 30
DEFAULT_RETRY_DELAY = 2
MAX_RETRIES = 3


@dataclass
class LinkedInProfile:
    """Data class for LinkedIn profile information"""
    name: Optional[str] = None
    headline: Optional[str] = None
    location: Optional[str] = None
    summary: Optional[str] = None
    experience: List[Dict[str, Any]] = None
    education: List[Dict[str, Any]] = None
    skills: List[str] = None
    connections: Optional[str] = None
    profile_url: Optional[str] = None
    
    def __post_init__(self):
        if self.experience is None:
            self.experience = []
        if self.education is None:
            self.education = []
        if self.skills is None:
            self.skills = []

    def to_dict(self) -> Dict[str, Any]:
        """Convert profile to dictionary"""
        return asdict(self)

    def to_json(self) -> str:
        """Convert profile to JSON string"""
        return json.dumps(self.to_dict(), indent=2, ensure_ascii=False)


class LinkedInScraper:
    """LinkedIn profile scraper with multiple extraction methods"""
    
    def __init__(self, 
                 user_agent: str = DEFAULT_USER_AGENT,
                 timeout: int = DEFAULT_TIMEOUT,
                 retry_delay: int = DEFAULT_RETRY_DELAY,
                 max_retries: int = MAX_RETRIES):
        self.user_agent = user_agent
        self.timeout = timeout
        self.retry_delay = retry_delay
        self.max_retries = max_retries
        self.session = self._create_session()
        
    def _create_session(self) -> requests.Session:
        """Create a configured requests session"""
        session = requests.Session()
        session.headers.update({
            'User-Agent': self.user_agent,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        })
        return session
    
    def is_valid_linkedin_url(self, url: str) -> bool:
        """Validate if URL is a LinkedIn profile URL"""
        try:
            parsed = urlparse(url)
            return (
                parsed.netloc.lower() in ['www.linkedin.com', 'linkedin.com'] and
                '/in/' in parsed.path.lower()
            )
        except Exception:
            return False
    
    def clean_text(self, text: str) -> str:
        """Clean extracted text"""
        if not text:
            return ""
        # Remove extra whitespace and newlines
        text = re.sub(r'\s+', ' ', text.strip())
        # Remove common LinkedIn UI elements
        text = re.sub(r'\b(LinkedIn Member|View profile|Connect|Message)\b', '', text, flags=re.IGNORECASE)
        return text.strip()
    
    def extract_profile_from_html(self, html: str, url: str) -> LinkedInProfile:
        """Extract profile data from HTML content"""
        soup = BeautifulSoup(html, 'html.parser')
        profile = LinkedInProfile(profile_url=url)
        
        try:
            # Extract name (multiple selectors for different layouts)
            name_selectors = [
                'h1[data-test="fullName"]',
                'h1.text-heading-xlarge',
                'h1.break-words',
                '.pv-text-details__left-panel h1',
                'h1.top-card-layout__title'
            ]
            
            for selector in name_selectors:
                name_element = soup.select_one(selector)
                if name_element:
                    profile.name = self.clean_text(name_element.get_text())
                    break
            
            # Extract headline
            headline_selectors = [
                '.text-body-medium.break-words',
                '.pv-text-details__left-panel .text-body-medium',
                '.top-card-layout__headline',
                '[data-test="headline"]'
            ]
            
            for selector in headline_selectors:
                headline_element = soup.select_one(selector)
                if headline_element:
                    profile.headline = self.clean_text(headline_element.get_text())
                    break
            
            # Extract location
            location_selectors = [
                '.text-body-small.inline.t-black--light.break-words',
                '.pv-text-details__left-panel .text-body-small',
                '.top-card-layout__first-subline'
            ]
            
            for selector in location_selectors:
                location_element = soup.select_one(selector)
                if location_element:
                    profile.location = self.clean_text(location_element.get_text())
                    break
            
            # Extract summary/about section
            summary_selectors = [
                '.pv-shared-text-with-see-more .break-words span',
                '#about .pv-shared-text-with-see-more',
                '.core-section-container__content .break-words'
            ]
            
            for selector in summary_selectors:
                summary_element = soup.select_one(selector)
                if summary_element:
                    profile.summary = self.clean_text(summary_element.get_text())
                    break
            
            # Try to extract JSON-LD data if available
            json_scripts = soup.find_all('script', type='application/ld+json')
            for script in json_scripts:
                try:
                    data = json.loads(script.string)
                    if isinstance(data, dict):
                        if data.get('@type') == 'Person':
                            if not profile.name and data.get('name'):
                                profile.name = data['name']
                            if not profile.headline and data.get('jobTitle'):
                                profile.headline = data['jobTitle']
                except (json.JSONDecodeError, KeyError):
                    continue
            
            logger.info(f"Extracted profile data: name={profile.name}, headline={profile.headline}")
            
        except Exception as e:
            logger.error(f"Error extracting profile data: {e}")
        
        return profile
    
    def scrape_profile_basic(self, url: str) -> LinkedInProfile:
        """Basic scraping method using requests"""
        if not self.is_valid_linkedin_url(url):
            raise ValueError(f"Invalid LinkedIn URL: {url}")
        
        for attempt in range(self.max_retries):
            try:
                response = self.session.get(url, timeout=self.timeout)
                response.raise_for_status()
                
                # Check for LinkedIn's anti-bot measures
                if "challenge" in response.url.lower() or response.status_code == 999:
                    raise Exception("LinkedIn anti-bot challenge detected")
                
                return self.extract_profile_from_html(response.text, url)
                
            except requests.exceptions.RequestException as e:
                logger.warning(f"Attempt {attempt + 1} failed: {e}")
                if attempt < self.max_retries - 1:
                    time.sleep(self.retry_delay * (attempt + 1))
                else:
                    raise Exception(f"Failed to scrape profile after {self.max_retries} attempts: {e}")
    
    async def scrape_profile_async(self, url: str) -> LinkedInProfile:
        """Async scraping method using httpx"""
        if not self.is_valid_linkedin_url(url):
            raise ValueError(f"Invalid LinkedIn URL: {url}")
        
        headers = {
            'User-Agent': self.user_agent,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
        }
        
        async with httpx.AsyncClient(headers=headers, timeout=self.timeout) as client:
            for attempt in range(self.max_retries):
                try:
                    response = await client.get(url)
                    response.raise_for_status()
                    
                    if "challenge" in str(response.url).lower() or response.status_code == 999:
                        raise Exception("LinkedIn anti-bot challenge detected")
                    
                    return self.extract_profile_from_html(response.text, url)
                    
                except httpx.RequestError as e:
                    logger.warning(f"Async attempt {attempt + 1} failed: {e}")
                    if attempt < self.max_retries - 1:
                        await asyncio.sleep(self.retry_delay * (attempt + 1))
                    else:
                        raise Exception(f"Failed to scrape profile after {self.max_retries} attempts: {e}")

    def parse_profile_text(self, profile_text: str) -> LinkedInProfile:
        """Parse LinkedIn profile data from raw text (copy-pasted profile)"""
        profile = LinkedInProfile()
        
        try:
            lines = [line.strip() for line in profile_text.split('\n') if line.strip()]
            
            if not lines:
                return profile
            
            # First line is usually the name
            profile.name = lines[0]
            
            # Look for headline patterns
            for i, line in enumerate(lines[1:3], 1):  # Check first few lines
                if any(keyword in line.lower() for keyword in ['engineer', 'developer', 'manager', 'analyst', 'consultant', 'director', 'specialist']):
                    profile.headline = line
                    break
            
            # Look for location patterns (often contains city names)
            location_patterns = [
                r'.*,\s*[A-Z]{2,3}(?:\s|$)',  # City, State
                r'.*,\s*\w+(?:\s|$)',  # City, Country
            ]
            
            for line in lines:
                for pattern in location_patterns:
                    if re.match(pattern, line):
                        profile.location = line
                        break
                if profile.location:
                    break
            
            # Look for summary/about section
            summary_keywords = ['about', 'summary', 'experienced', 'passionate', 'background']
            summary_lines = []
            in_summary = False
            
            for line in lines:
                line_lower = line.lower()
                if any(keyword in line_lower for keyword in summary_keywords) and len(line) > 50:
                    in_summary = True
                    summary_lines.append(line)
                elif in_summary and len(line) > 20:
                    summary_lines.append(line)
                elif in_summary and len(line) < 20:
                    break
            
            if summary_lines:
                profile.summary = ' '.join(summary_lines)
            
            # Extract skills (often listed with commas or bullets)
            skills_patterns = [
                r'skills?:?\s*(.+)',
                r'technologies?:?\s*(.+)',
                r'expertise:?\s*(.+)'
            ]
            
            for line in lines:
                for pattern in skills_patterns:
                    match = re.search(pattern, line, re.IGNORECASE)
                    if match:
                        skills_text = match.group(1)
                        # Split by common delimiters
                        skills = [s.strip() for s in re.split('[,•·|]', skills_text) if s.strip()]
                        profile.skills.extend(skills)
            
            logger.info(f"Parsed profile from text: name={profile.name}, headline={profile.headline}")
            
        except Exception as e:
            logger.error(f"Error parsing profile text: {e}")
        
        return profile


# Utility functions for integration with existing app
def scrape_linkedin_profile(url: str) -> Dict[str, Any]:
    """
    Scrape a LinkedIn profile URL and return structured data
    
    Args:
        url: LinkedIn profile URL
        
    Returns:
        Dictionary containing profile data
    """
    try:
        scraper = LinkedInScraper()
        profile = scraper.scrape_profile_basic(url)
        return profile.to_dict()
    except Exception as e:
        logger.error(f"Error scraping LinkedIn profile: {e}")
        return {
            "error": str(e),
            "name": None,
            "headline": None,
            "location": None,
            "summary": None,
            "experience": [],
            "education": [],
            "skills": [],
            "profile_url": url
        }


async def scrape_linkedin_profile_async(url: str) -> Dict[str, Any]:
    """
    Async version of LinkedIn profile scraper
    
    Args:
        url: LinkedIn profile URL
        
    Returns:
        Dictionary containing profile data
    """
    try:
        scraper = LinkedInScraper()
        profile = await scraper.scrape_profile_async(url)
        return profile.to_dict()
    except Exception as e:
        logger.error(f"Error scraping LinkedIn profile async: {e}")
        return {
            "error": str(e),
            "name": None,
            "headline": None,
            "location": None,
            "summary": None,
            "experience": [],
            "education": [],
            "skills": [],
            "profile_url": url
        }


def parse_linkedin_text(profile_text: str) -> Dict[str, Any]:
    """
    Parse LinkedIn profile data from raw text (copy-pasted content)
    
    Args:
        profile_text: Raw text from LinkedIn profile
        
    Returns:
        Dictionary containing parsed profile data
    """
    try:
        scraper = LinkedInScraper()
        profile = scraper.parse_profile_text(profile_text)
        return profile.to_dict()
    except Exception as e:
        logger.error(f"Error parsing LinkedIn text: {e}")
        return {
            "error": str(e),
            "name": None,
            "headline": None,
            "location": None,
            "summary": profile_text[:200] + "..." if len(profile_text) > 200 else profile_text,
            "experience": [],
            "education": [],
            "skills": [],
            "profile_url": None
        }


def format_profile_summary(profile_data: Dict[str, Any]) -> str:
    """
    Format LinkedIn profile data into a readable summary
    
    Args:
        profile_data: Dictionary containing profile data
        
    Returns:
        Formatted string summary
    """
    summary_parts = []
    
    if profile_data.get('name'):
        summary_parts.append(f"**Nom:** {profile_data['name']}")
    
    if profile_data.get('headline'):
        summary_parts.append(f"**Titre:** {profile_data['headline']}")
    
    if profile_data.get('location'):
        summary_parts.append(f"**Localisation:** {profile_data['location']}")
    
    if profile_data.get('summary'):
        summary_parts.append(f"**Résumé:** {profile_data['summary']}")
    
    if profile_data.get('skills'):
        skills_str = ', '.join(profile_data['skills'][:10])  # Limit to first 10 skills
        summary_parts.append(f"**Compétences:** {skills_str}")
    
    if profile_data.get('experience'):
        exp_count = len(profile_data['experience'])
        summary_parts.append(f"**Expérience:** {exp_count} poste(s)")
    
    if profile_data.get('error'):
        summary_parts.append(f"**Erreur:** {profile_data['error']}")
    
    return '\n\n'.join(summary_parts)


# CLI functionality for testing
def main():
    """CLI interface for testing the LinkedIn scraper"""
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python linkedin.py <linkedin_url_or_text>")
        print("Examples:")
        print("  python linkedin.py https://www.linkedin.com/in/username")
        print("  python linkedin.py 'John Doe\\nSoftware Engineer\\nParis, France\\n...'")
        sys.exit(1)
    
    input_data = sys.argv[1]
    
    # Check if it's a URL or text
    if input_data.startswith('http') and 'linkedin.com' in input_data:
        print("Scraping LinkedIn profile URL...")
        result = scrape_linkedin_profile(input_data)
    else:
        print("Parsing LinkedIn profile text...")
        result = parse_linkedin_text(input_data)
    
    print("\n=== LINKEDIN PROFILE DATA ===")
    print(json.dumps(result, indent=2, ensure_ascii=False))
    
    print("\n=== FORMATTED SUMMARY ===")
    print(format_profile_summary(result))


if __name__ == "__main__":
    main()