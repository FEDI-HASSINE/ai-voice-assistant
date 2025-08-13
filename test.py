import os
import asyncio
import random
import argparse
from typing import List, Dict, Any, Optional

import httpx

# Config depuis l'environnement
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama3-8b-8192")
GROQ_ENDPOINT = os.getenv("GROQ_ENDPOINT", "https://api.groq.com/openai/v1/chat/completions")
LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0.3"))
LLM_TOP_P = float(os.getenv("LLM_TOP_P", "0.9"))
LLM_MAX_TOKENS = int(os.getenv("LLM_MAX_TOKENS", "512"))
REQUEST_TIMEOUT = float(os.getenv("LLM_REQUEST_TIMEOUT", "60"))
SLEEP_BETWEEN = float(os.getenv("LLM_SLEEP_BETWEEN", "2"))  # pause entre prompts
MAX_RETRIES = int(os.getenv("LLM_MAX_RETRIES", "5"))        # nb retries sur 429/5xx

# Contexte (surchageable via ENGINEER_BIO)
ENGINEER_BIO = os.getenv(
    "ENGINEER_BIO",
    (
        "Profil: Étudiant en pré-ingénierie (ISIMS, Sfax) orienté IA/ML, systèmes embarqués et agents conversationnels.\n"
        "Projets phares:\n"
        "- Smart Grid Failure Prediction (Jan–Avr 2025): LSTM, TensorFlow, Pandas, >90% précision, dashboard (TSYP 25).\n"
        "- Energy-Harvesting Wearables (Nov 2024–Jan 2025): Bracelet thermoélectrique (Peltier) & chaussure piézoélectrique, Arduino, capteurs, 3D.\n"
        "- Assistant Agricole IA (Mar–Mai 2025): NLP, Dialogflow, chatbot FR/AR, recommandations cultures via pH/humidité/nutriments.\n"
        "- AIAvatarKit (Jul 2025–…): Agent voix temps réel multimodal (VAD, STT, LLM, TTS), WebSocket/SSE, edge (Raspberry Pi), Twilio, tool-calling.\n"
        "- n8n-Puppeteer Node: login, scraping, PDF/screenshots, cookies, proxy, stealth, Docker/remote Chrome.\n"
        "- Canvas PDF Merger: agrégation PDFs via Canvas API (Python), auth via env.\n"
        "- GenAI Workflow Hub: Next.js/TS/Tailwind, 7+ automatisations GenAI (incl. Gemini), Figma API, crawlers web.\n"
        "- Crypto Price Predictor: pipeline ML serverless (Cerebrium), CometML (tracking/registry), CI/CD GitHub Actions.\n"
        "- Unified MCP Tool Graph: 11k+ APIs, Neo4j, orchestration JIT, LangGraph/A2A.\n"
        "Expériences (simulations): TCS Data Viz, EA Software Eng (C++/UML), Citi ICG Tech (UML/Java/ML risque).\n"
        "Compétences: Python, TensorFlow, Pandas, LSTM, NLP/Dialogflow, Arduino, capteurs, 3D printing, Next.js/TS/Tailwind, Git, Linux, Agile.\n"
        "Langues: Arabe (nat.), Français (pro), Anglais (interm.), Allemand (débutant).\n"
        "Objectif: réponses claires, structurées et factuelles, en français par défaut, avec exemples concrets et extraits de code minimalistes si pertinent."
    ),
)

def build_system_prompt() -> str:
    return (
        ENGINEER_BIO
        + "\n\nDirectives:\n"
        "- Répondre en français (sauf demande explicite contraire).\n"
        "- Être clair, structuré, pédagogique et concis.\n"
        "- Citer brièvement des approches/outils pertinents (ex: LSTM, TensorFlow, Dialogflow, Next.js, Neo4j).\n"
        "- Fournir des extraits de code minimalistes et corrects si la question est technique.\n"
        "- Demander des précisions si la question est ambiguë; ne pas inventer.\n"
    )

def build_messages(user_text: str) -> List[Dict[str, Any]]:
    return [
        {"role": "system", "content": build_system_prompt()},
        {"role": "user", "content": user_text},
    ]

PROMPTS: List[str] = [
    "Explique ta solution Smart Grid Failure Prediction (données, features, LSTM, entraînement) et propose 3 améliorations pour la mise en prod.",
    "Comment intégrer bracelet thermoélectrique et chaussure piézoélectrique dans une architecture IoT low-power avec collecte, stockage et analytics temps réel ?",
    "Conçois un assistant agricole FR/AR: pipeline capteurs sol (pH, humidité, nutriments), prétraitement, modèle de recommandation de cultures et interface Dialogflow.",
    "Décris une architecture agent voix temps réel multimodal (AIAvatarKit) avec VAD, STT, LLM, TTS, WebSocket/SSE et tool-calling. Donne un schéma de flux textuel.",
    "Quelles bonnes pratiques de sécurité et robustesse pour un node n8n basé sur Puppeteer (auth, gestion cookies, proxy, anti-bot, timeouts, Docker, remote Chrome) ?",
    "Propose une structure Python modulaire pour agréger des PDF depuis Canvas API (auth via variables d’environnement) et produire un PDF unique bien indexé.",
    "Comment concevoir des automatisations GenAI (Next.js/TS/Tailwind) fiables: gestion des prompts, contexte, limites tokens, latence, observabilité ?",
    "Donne un pipeline MLOps pour prédire des prix crypto (Cerebrium + CometML + CI/CD GitHub Actions), avec versionnement, registry et déploiement sans interruption.",
    "Décris un graphe Neo4j pour 11k+ outils MCP: schéma (noeuds/rels), stratégies d’orchestration JIT, recherche sémantique, et intégration LangGraph/A2A.",
    "Qu’as-tu appris des programmes virtuels TCS/EA/Citi (UML, C++, Java, data viz, risque) et comment l’appliquer à un stage IA/logiciel ?",
]

def _retry_delay(attempt: int, base: float = 1.5, cap: float = 30.0) -> float:
    # Exponential backoff + jitter
    return min(cap, (base ** attempt) + random.uniform(0, 0.5))

def _headers_delay(headers: httpx.Headers) -> Optional[float]:
    # Si l’API renvoie Retry-After, on le respecte
    ra = headers.get("retry-after")
    if ra:
        try:
            return float(ra)
        except ValueError:
            return None
    # Extensions possibles: autres en-têtes spécifiques Groq
    return None

async def call_groq_with_retries(prompt: str, client: httpx.AsyncClient) -> str:
    if not GROQ_API_KEY:
        return "Mode dégradé: GROQ_API_KEY manquante."
    payload = {
        "model": GROQ_MODEL,
        "messages": build_messages(prompt),
        "temperature": LLM_TEMPERATURE,
        "top_p": LLM_TOP_P,
        "max_tokens": LLM_MAX_TOKENS,
    }
    headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}

    last_err = None
    for attempt in range(MAX_RETRIES + 1):
        try:
            r = await client.post(GROQ_ENDPOINT, json=payload, headers=headers)
            if r.status_code == 429:
                # Rate limit: attendre puis retry
                hdr_delay = _headers_delay(r.headers)
                delay = hdr_delay if hdr_delay is not None else _retry_delay(attempt)
                print(f"429 Too Many Requests — attente {delay:.1f}s puis retry (tentative {attempt+1}/{MAX_RETRIES})")
                await asyncio.sleep(delay)
                continue
            r.raise_for_status()
            data = r.json()
            return (
                data.get("choices", [{}])[0]
                .get("message", {})
                .get("content", "")
                .strip()
                or "(réponse vide)"
            )
        except httpx.HTTPStatusError as e:
            # Réessayer sur 5xx, sinon arrêter
            status = e.response.status_code
            if 500 <= status < 600 and attempt < MAX_RETRIES:
                delay = _retry_delay(attempt)
                print(f"HTTP {status} — attente {delay:.1f}s puis retry (tentative {attempt+1}/{MAX_RETRIES})")
                await asyncio.sleep(delay)
                last_err = e
                continue
            return f"Erreur HTTP: {status} - {e.response.text[:300]}"
        except httpx.HTTPError as e:
            # Erreurs réseau (transitoires) -> retry
            if attempt < MAX_RETRIES:
                delay = _retry_delay(attempt)
                print(f"Erreur réseau — attente {delay:.1f}s puis retry (tentative {attempt+1}/{MAX_RETRIES})")
                await asyncio.sleep(delay)
                last_err = e
                continue
            return f"Erreur réseau: {e}"
    return f"Échec après retries: {last_err}"

async def main() -> None:
    parser = argparse.ArgumentParser(description="Tester l’API Groq sur plusieurs prompts.")
    parser.add_argument("--start", type=int, default=1, help="Index de départ (1-based).")
    parser.add_argument("--end", type=int, default=len(PROMPTS), help="Index de fin inclus (1-based).")
    parser.add_argument("--sleep", type=float, default=SLEEP_BETWEEN, help="Pause entre prompts (secondes).")
    args = parser.parse_args()

    start = max(1, args.start)
    end = min(len(PROMPTS), args.end)
    if start > end:
        print("Plage invalide. Vérifiez --start/--end.")
        return

    print(f"Modèle: {GROQ_MODEL} | Endpoint: {GROQ_ENDPOINT}")
    print(f"Prompts: {start} -> {end} | pause: {args.sleep}s | retries: {MAX_RETRIES}")

    timeout = httpx.Timeout(REQUEST_TIMEOUT)
    async with httpx.AsyncClient(timeout=timeout) as client:
        for i in range(start, end + 1):
            p = PROMPTS[i - 1]
            print("\n" + "=" * 80)
            print(f"[{i}] Prompt:\n{p}")
            print("-" * 80)
            resp = await call_groq_with_retries(p, client)
            print(f"Réponse:\n{resp}")
            if i < end:
                await asyncio.sleep(args.sleep)

if __name__ == "__main__":
    asyncio.run(main())