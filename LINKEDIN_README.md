# LinkedIn Profile Scraper Documentation

## Overview

The LinkedIn Profile Scraper is a comprehensive module that provides functionality to extract structured data from LinkedIn profiles. It supports both URL-based scraping and text-based parsing for copy-pasted profile content.

## Features

### Core Functionality
- **URL Validation**: Validates LinkedIn profile URLs before scraping
- **Profile Scraping**: Extracts data from LinkedIn profile URLs (with limitations due to anti-bot measures)
- **Text Parsing**: Parses profile data from copy-pasted LinkedIn content
- **Structured Output**: Returns standardized profile data with consistent format
- **Error Handling**: Robust error handling for network issues and invalid inputs
- **Async Support**: Both synchronous and asynchronous implementations

### Data Extraction
The scraper extracts the following profile information:
- **Name**: Full name of the profile owner
- **Headline**: Professional title/headline
- **Location**: Geographic location
- **Summary**: About/summary section content
- **Skills**: List of skills and technologies
- **Experience**: Work experience (structure prepared for future enhancement)
- **Education**: Educational background (structure prepared for future enhancement)
- **Profile URL**: Original LinkedIn profile URL

## API Endpoints

### POST /linkedin/parse
Parses LinkedIn profile data from raw text (copy-pasted content).

**Request Body:**
```json
{
  "profile_text": "John Doe\nSoftware Engineer at Google\nNew York, NY\n..."
}
```

**Response:**
```json
{
  "profile_data": {
    "name": "John Doe",
    "headline": "Software Engineer at Google",
    "location": "New York, NY",
    "summary": "...",
    "skills": ["Python", "JavaScript", "..."],
    "experience": [],
    "education": [],
    "connections": null,
    "profile_url": null
  },
  "formatted_summary": "**Nom:** John Doe\n\n**Titre:** Software Engineer at Google\n...",
  "success": true
}
```

### POST /linkedin/scrape
Scrapes LinkedIn profile from a URL.

**Request Body:**
```json
{
  "url": "https://www.linkedin.com/in/username"
}
```

**Response:**
```json
{
  "url": "https://www.linkedin.com/in/username",
  "profile_data": { ... },
  "formatted_summary": "...",
  "success": true
}
```

**Note**: URL scraping may be limited due to LinkedIn's anti-bot measures and will often return error responses.

## Usage Examples

### Command Line Interface
```bash
# Parse text content
python linkedin.py "John Doe\nSoftware Engineer\nParis, France\n..."

# Scrape URL (may fail due to anti-bot measures)
python linkedin.py "https://www.linkedin.com/in/username"
```

### Python API
```python
from linkedin import parse_linkedin_text, scrape_linkedin_profile

# Parse text content
profile_data = parse_linkedin_text(profile_text)

# Scrape URL
profile_data = scrape_linkedin_profile(profile_url)

# Format for display
from linkedin import format_profile_summary
summary = format_profile_summary(profile_data)
```

### FastAPI Integration
```python
import requests

# Parse text content
response = requests.post('http://localhost:8000/linkedin/parse', 
                        json={'profile_text': text_content})
result = response.json()

# Scrape URL
response = requests.post('http://localhost:8000/linkedin/scrape',
                        json={'url': linkedin_url})
result = response.json()
```

## Configuration

The scraper supports several configuration options:

- **USER_AGENT**: Browser user agent string for requests
- **TIMEOUT**: Request timeout in seconds (default: 30)
- **RETRY_DELAY**: Delay between retry attempts (default: 2 seconds)
- **MAX_RETRIES**: Maximum number of retry attempts (default: 3)

## Limitations and Considerations

### LinkedIn Anti-Bot Measures
- LinkedIn actively blocks automated scraping attempts
- URL-based scraping will often fail and return error responses
- Text-based parsing is more reliable as it works with already-extracted content
- The scraper includes multiple selectors to handle different LinkedIn layouts

### Rate Limiting
- Implements retry logic with exponential backoff
- Respects server response codes and error conditions
- Includes proper logging for debugging failed requests

### Data Accuracy
- Text parsing uses heuristic patterns to identify profile elements
- Results may vary depending on profile format and language
- Skills extraction looks for common patterns but may miss some entries

## Error Handling

The scraper provides comprehensive error handling:

1. **Invalid URLs**: Validates LinkedIn profile URL format
2. **Network Errors**: Handles timeouts, connection issues, and HTTP errors
3. **Anti-Bot Detection**: Detects and reports LinkedIn's anti-bot measures
4. **Parsing Errors**: Gracefully handles malformed or unexpected content
5. **Empty Content**: Handles empty or minimal profile content

All errors are logged and returned in a structured format with the original input preserved.

## Testing

A comprehensive test suite is included (`test_linkedin.py`) that validates:
- URL validation functionality
- Text parsing accuracy
- Error handling for edge cases
- Async functionality
- API response structure

Run tests with:
```bash
python test_linkedin.py
```

## Dependencies

Required packages:
- `requests`: HTTP client for web scraping
- `beautifulsoup4`: HTML parsing
- `httpx`: Async HTTP client
- `lxml`: XML/HTML parser backend

Install with:
```bash
pip install requests beautifulsoup4 httpx lxml
```

## Integration with Existing App

The LinkedIn scraper is fully integrated with the existing AI Voice Assistant FastAPI application:

1. **Endpoints**: Added `/linkedin/parse` and `/linkedin/scrape` endpoints
2. **Error Handling**: Consistent with existing app error patterns
3. **Logging**: Uses the same logging configuration
4. **Models**: Uses Pydantic models for request/response validation
5. **Structure**: Follows the same code organization patterns

The scraper module is imported conditionally, so the app continues to work even if LinkedIn dependencies are missing.

## Security and Ethics

- The scraper respects LinkedIn's robots.txt and terms of service
- Implements reasonable rate limiting to avoid overwhelming servers
- Handles personal data responsibly and doesn't store extracted information
- Provides clear error messages when scraping is blocked
- Encourages use of text-based parsing over URL scraping when possible

## Future Enhancements

Potential improvements for future versions:
1. Enhanced experience and education parsing
2. Support for additional LinkedIn profile sections
3. Integration with LinkedIn's official API (when available)
4. Improved language detection and multilingual support
5. Better handling of different LinkedIn profile layouts
6. Export functionality to various formats (JSON, CSV, PDF)