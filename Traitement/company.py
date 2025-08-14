import os
import sys
import re
from typing import List, Dict, Any, Optional
from urllib.parse import urljoin, urlparse

import httpx
import bs4
from bs4 import BeautifulSoup

# ---------------- Configuration ----------------
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama3-8b-8192")
GROQ_ENDPOINT = os.getenv("GROQ_ENDPOINT", "https://api.groq.com/openai/v1/chat/completions")

CHUNK_CHAR_LIMIT = int(os.getenv("COMPANY_CHUNK_CHAR_LIMIT", "5000"))
TARGET_WORDS = int(os.getenv("COMPANY_SUMMARY_WORDS", "300"))
TEMPERATURE = float(os.getenv("COMPANY_SUMMARY_TEMPERATURE", "0.3"))
TOP_P = float(os.getenv("COMPANY_SUMMARY_TOP_P", "0.9"))
MAX_TOKENS = int(os.getenv("COMPANY_SUMMARY_MAX_TOKENS", "800"))
REQUEST_TIMEOUT = float(os.getenv("COMPANY_REQUEST_TIMEOUT", "30"))
SCRAPING_TIMEOUT = float(os.getenv("COMPANY_SCRAPING_TIMEOUT", "15"))

SYSTEM_PROMPT = (
    "Tu es un assistant qui analyse et extrait des informations sur les entreprises à partir de leur site web. "
    "Structure attendue: 1) Nom et secteur d'activité 2) Description de l'entreprise 3) Produits/Services principaux "
    "4) Technologies utilisées 5) Taille/Localisation 6) Valeurs et culture d'entreprise. "
    "Extrait uniquement les informations factuelles présentes sur le site. Ton professionnel et concis."
)

# User-Agent to avoid being blocked by some websites
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"


# ---------------- Utils ----------------
def clean_url(url: str) -> str:
    """Clean and validate URL format."""
    url = url.strip()
    if not url.startswith(('http://', 'https://')):
        url = 'https://' + url
    return url


def extract_text_from_html(html_content: str) -> str:
    """Extract meaningful text content from HTML."""
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # Remove script and style elements
    for script in soup(["script", "style", "nav", "footer", "header"]):
        script.decompose()
    
    # Get text and clean it
    text = soup.get_text()
    
    # Clean up whitespace
    lines = (line.strip() for line in text.splitlines())
    chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
    text = ' '.join(chunk for chunk in chunks if chunk)
    
    return text


def scrape_website(url: str) -> Dict[str, Any]:
    """Scrape website content and extract basic information."""
    result = {
        "url": url,
        "success": False,
        "title": "",
        "content": "",
        "meta_description": "",
        "error": ""
    }
    
    try:
        url = clean_url(url)
        headers = {"User-Agent": USER_AGENT}
        
        with httpx.Client(timeout=SCRAPING_TIMEOUT, verify=False) as client:
            response = client.get(url, headers=headers, follow_redirects=True)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Extract title
            title_tag = soup.find('title')
            result["title"] = title_tag.get_text().strip() if title_tag else ""
            
            # Extract meta description
            meta_desc = soup.find('meta', attrs={'name': 'description'})
            if meta_desc:
                result["meta_description"] = meta_desc.get('content', '').strip()
            
            # Extract main content
            result["content"] = extract_text_from_html(response.text)
            result["success"] = True
            
    except httpx.TimeoutException:
        result["error"] = "Timeout lors de la récupération du site web"
    except httpx.HTTPStatusError as e:
        result["error"] = f"Erreur HTTP {e.response.status_code}: {e.response.text[:100]}"
    except httpx.ConnectError as e:
        result["error"] = f"Erreur de connexion: impossible de joindre le site web"
    except Exception as e:
        result["error"] = f"Erreur lors du scraping: {str(e)[:200]}"
    
    return result


def clean_text(text: str) -> str:
    """Clean extracted text."""
    if not text:
        return ""
    
    # Remove extra whitespace and normalize
    text = re.sub(r'\s+', ' ', text)
    text = text.strip()
    
    # Remove very short lines that are likely navigation/footer elements
    lines = text.split('\n')
    meaningful_lines = [line.strip() for line in lines if len(line.strip()) > 10]
    
    return '\n'.join(meaningful_lines)


def split_chunks(text: str, limit: int) -> List[str]:
    """Split text into chunks for processing."""
    if len(text) <= limit:
        return [text]
    
    chunks = []
    words = text.split()
    current_chunk = []
    current_length = 0
    
    for word in words:
        if current_length + len(word) + 1 > limit and current_chunk:
            chunks.append(' '.join(current_chunk))
            current_chunk = [word]
            current_length = len(word)
        else:
            current_chunk.append(word)
            current_length += len(word) + 1
    
    if current_chunk:
        chunks.append(' '.join(current_chunk))
    
    return chunks


def call_llm(messages: List[Dict[str, str]]) -> str:
    """Call Groq LLM API."""
    if not GROQ_API_KEY:
        return "Erreur: GROQ_API_KEY non configurée"
    
    payload = {
        "model": GROQ_MODEL,
        "messages": messages,
        "temperature": TEMPERATURE,
        "top_p": TOP_P,
        "max_tokens": MAX_TOKENS,
    }
    headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}
    
    try:
        with httpx.Client(timeout=REQUEST_TIMEOUT) as client:
            r = client.post(GROQ_ENDPOINT, json=payload, headers=headers)
            r.raise_for_status()
            data = r.json()
            return (
                data.get("choices", [{}])[0]
                .get("message", {})
                .get("content", "")
                .strip()
                or "(Analyse vide)"
            )
    except httpx.HTTPStatusError as e:
        return f"HTTP {e.response.status_code}: {e.response.text[:200]}"
    except Exception as e:
        return f"Erreur réseau: {e}"


def analyze_chunk(chunk: str, url: str, target_words: int) -> str:
    """Analyze a chunk of website content."""
    user_prompt = (
        f"Analyse ce contenu du site web {url} et extrait les informations clés sur l'entreprise "
        f"en ~{target_words} mots. Focus sur: activité, produits/services, technologies, valeurs.\n\n"
        f"=== CONTENU ===\n{chunk}"
    )
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ]
    return call_llm(messages)


def analyze_company_website(url: str, target_words: int = TARGET_WORDS) -> str:
    """Main function to scrape and analyze a company website."""
    print(f"Scraping du site: {url}")
    
    # Scrape the website
    scrape_result = scrape_website(url)
    
    if not scrape_result["success"]:
        return f"Échec du scraping: {scrape_result['error']}"
    
    # Combine all available content
    content_parts = []
    if scrape_result["title"]:
        content_parts.append(f"Titre: {scrape_result['title']}")
    if scrape_result["meta_description"]:
        content_parts.append(f"Description: {scrape_result['meta_description']}")
    if scrape_result["content"]:
        content_parts.append(f"Contenu: {scrape_result['content']}")
    
    raw_content = "\n\n".join(content_parts)
    raw_content = clean_text(raw_content)
    
    if not raw_content:
        return "Aucun contenu utilisable trouvé sur le site web."
    
    print(f"Contenu extrait: {len(raw_content)} caractères")
    
    # If no API key, return basic extracted content
    if not GROQ_API_KEY:
        basic_info = f"""
INFORMATIONS EXTRAITES (sans analyse IA):

URL: {url}
Titre: {scrape_result.get('title', 'Non trouvé')}
Meta description: {scrape_result.get('meta_description', 'Non trouvée')}

Contenu principal (premiers 1000 caractères):
{raw_content[:1000]}{'...' if len(raw_content) > 1000 else ''}

Note: Pour une analyse complète avec IA, configurez GROQ_API_KEY
"""
        return basic_info
    
    # Split into chunks if content is too long
    chunks = split_chunks(raw_content, CHUNK_CHAR_LIMIT)
    
    if len(chunks) == 1:
        return analyze_chunk(chunks[0], url, target_words)
    
    # Analyze each chunk then merge
    per_chunk_goal = max(50, int(target_words * 0.7 / len(chunks)))
    partials = []
    
    for i, chunk in enumerate(chunks, 1):
        print(f"Analyse du segment {i}/{len(chunks)}")
        partial = analyze_chunk(chunk, url, per_chunk_goal)
        partials.append(f"[Segment {i}/{len(chunks)}]\n{partial}")
    
    # Merge partial analyses
    merged = "\n\n".join(partials)
    fusion_prompt = (
        f"Synthétise les analyses partielles ci-dessous en une analyse globale de l'entreprise "
        f"({target_words} mots max). Structure: secteur, activité, produits/services, technologies, "
        f"culture d'entreprise. Évite les répétitions.\n\n"
        f"=== ANALYSES PARTIELLES ===\n{merged}"
    )
    
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": fusion_prompt},
    ]
    
    return call_llm(messages)


# ---------------- CLI ----------------
def test_mode():
    """Test mode with a sample HTML content."""
    print("Mode test - analyse d'un contenu HTML simulé")
    
    # Sample HTML content for a fictional company
    sample_html = """
    <html>
    <head>
        <title>TechCorp - Solutions informatiques innovantes</title>
        <meta name="description" content="TechCorp développe des solutions logicielles pour l'industrie 4.0">
    </head>
    <body>
        <h1>TechCorp - Leader en solutions informatiques</h1>
        <p>Depuis 15 ans, TechCorp développe des solutions logicielles innovantes pour les entreprises.</p>
        <h2>Nos services</h2>
        <ul>
            <li>Développement d'applications web avec React et Node.js</li>
            <li>Solutions cloud avec AWS et Azure</li>
            <li>Intelligence artificielle et machine learning</li>
            <li>Consulting en transformation digitale</li>
        </ul>
        <h2>Notre équipe</h2>
        <p>Plus de 50 développeurs expérimentés basés à Paris et Lyon.</p>
        <h2>Nos valeurs</h2>
        <p>Innovation, excellence technique, collaboration et respect de l'environnement.</p>
    </body>
    </html>
    """
    
    # Extract content like we would from a real website
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(sample_html, 'html.parser')
    
    title = soup.find('title').get_text().strip()
    meta_desc = soup.find('meta', attrs={'name': 'description'}).get('content', '').strip()
    content = extract_text_from_html(sample_html)
    
    print(f"Titre: {title}")
    print(f"Description: {meta_desc}")
    print(f"Contenu extrait: {len(content)} caractères")
    print("\nContenu:")
    print(content[:500] + ("..." if len(content) > 500 else ""))
    
    return f"""
ANALYSE DE L'ENTREPRISE (Mode test):

URL: Mode test - TechCorp
Titre: {title}
Meta description: {meta_desc}

INFORMATIONS EXTRAITES:
{content}

Note: Ceci est un exemple de fonctionnement. Pour analyser un vrai site web, utilisez: python company.py <URL>
"""


def main():
    """Command line interface."""
    if len(sys.argv) < 2:
        print("Usage: python company.py <URL_ENTREPRISE>")
        print("       python company.py --test    (pour tester avec un exemple)")
        print("Exemple: python company.py https://example.com")
        sys.exit(1)
    
    if sys.argv[1] == "--test":
        try:
            result = test_mode()
            print("\n" + "="*60)
            print("TEST D'ANALYSE D'ENTREPRISE")
            print("="*60)
            print(result)
        except Exception as e:
            print(f"Erreur en mode test: {e}")
            sys.exit(1)
        return
    
    company_url = sys.argv[1]
    
    try:
        result = analyze_company_website(company_url)
        print("\n" + "="*60)
        print("ANALYSE DE L'ENTREPRISE")
        print("="*60)
        print(result)
    except KeyboardInterrupt:
        print("\nInterrompu par l'utilisateur.")
        sys.exit(1)
    except Exception as e:
        print(f"Erreur: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()