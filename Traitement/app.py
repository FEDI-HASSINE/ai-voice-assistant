import os
import logging
import tempfile
import subprocess
from typing import List, Dict, Any, Optional

import httpx
from fastapi import FastAPI, Request, UploadFile, File, HTTPException, Body
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

# Import company analysis functionality
try:
    from .company import analyze_company_website
    COMPANY_ANALYZER_AVAILABLE = True
except ImportError:
    COMPANY_ANALYZER_AVAILABLE = False
    def analyze_company_website(url: str, target_words: int = 300) -> str:
        return "Module d'analyse d'entreprise non disponible"

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
log = logging.getLogger("ai-voice-assistant")

# ---------------------------------------------------------------------------
# App & Templates
# ---------------------------------------------------------------------------
app = FastAPI()
templates = Jinja2Templates(directory="templates")

# ---------------------------------------------------------------------------
# Config LLM (Groq)
# ---------------------------------------------------------------------------
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama3-8b-8192")
GROQ_ENDPOINT = os.getenv("GROQ_ENDPOINT", "https://api.groq.com/openai/v1/chat/completions")
LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0.3"))
LLM_TOP_P = float(os.getenv("LLM_TOP_P", "0.9"))
LLM_MAX_TOKENS = int(os.getenv("LLM_MAX_TOKENS", "512"))
REQUEST_TIMEOUT = float(os.getenv("LLM_REQUEST_TIMEOUT", "60"))

# ---------------------------------------------------------------------------
# Contexte LLM (CV)
# ---------------------------------------------------------------------------
ENGINEER_BIO = os.getenv(
    "ENGINEER_BIO",
    (
        "Profil: Étudiant en pré-ingénierie (ISIMS, Sfax) orienté IA/ML, systèmes embarqués et agents conversationnels.\n"
        "Projets: Smart Grid LSTM (>90%), Wearables (Peltier/Piezo, Arduino), Assistant Agricole (NLP/Dialogflow FR/AR), "
        "AIAvatarKit (VAD/STT/LLM/TTS temps réel), n8n+Puppeteer, Canvas PDF Merger, GenAI Workflow Hub, "
        "Crypto MLOps (Cerebrium/CometML/CI-CD), Unified MCP Tool Graph (Neo4j/LangGraph).\n"
        "Compétences: Python, TensorFlow, Pandas, LSTM, Dialogflow, Arduino, 3D printing, Next.js/TS/Tailwind, Git, Linux.\n"
        "Réponses: claires, structurées, concises; extraits de code minimalistes si utile; demander précisions en cas d’ambiguïté."
    ),
)

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

# ---------------------------------------------------------------------------
# Whisper (mode vocal)
# ---------------------------------------------------------------------------
try:
    import whisper  # type: ignore
    WHISPER_MODEL_NAME = os.getenv("WHISPER_MODEL", "base")
    log.info("Chargement Whisper (%s)...", WHISPER_MODEL_NAME)
    whisper_model = whisper.load_model(WHISPER_MODEL_NAME)
    log.info("Whisper prêt.")
except Exception as e:
    whisper = None  # type: ignore
    whisper_model = None
    log.warning("Whisper indisponible: %s. Installez openai-whisper et ffmpeg.", e)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _build_system_prompt() -> str:
    return (
        ENGINEER_BIO
        + "\n\nDirectives:\n"
        "- Répondre en français (sauf demande explicite contraire).\n"
        "- Être clair, structuré, pédagogique et concis.\n"
        "- Citer des approches/outils pertinents si utile (LSTM, TensorFlow, Dialogflow, Next.js, Neo4j...).\n"
        "- Extraits de code minimalistes et corrects si question technique.\n"
        "- Demander des précisions si ambigu.\n"
    )

def _messages_from_text(user_text: str) -> List[Dict[str, Any]]:
    return [
        {"role": "system", "content": _build_system_prompt()},
        {"role": "user", "content": user_text},
    ]

async def _call_groq_text(user_text: str) -> str:
    if not user_text.strip():
        return "Veuillez saisir un prompt."
    if not GROQ_API_KEY:
        return "Mode dégradé: aucune clé Groq fournie."
    payload = {
        "model": GROQ_MODEL,
        "messages": _messages_from_text(user_text),
        "temperature": LLM_TEMPERATURE,
        "top_p": LLM_TOP_P,
        "max_tokens": LLM_MAX_TOKENS,
    }
    headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}
    try:
        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
            r = await client.post(GROQ_ENDPOINT, json=payload, headers=headers)
            r.raise_for_status()
            data = r.json()
            return (
                data.get("choices", [{}])[0]
                .get("message", {})
                .get("content", "")
                .strip()
                or "Réponse vide du modèle."
            )
    except httpx.HTTPStatusError as e:
        return f"Erreur Groq ({e.response.status_code}): {e.response.text[:200]}"
    except Exception as e:
        return f"Erreur appel Groq: {e}"

def _guess_suffix(content_type: Optional[str]) -> str:
    ct = (content_type or "").lower()
    if "wav" in ct: return ".wav"
    if "webm" in ct: return ".webm"
    if "mpeg" in ct or "mp3" in ct: return ".mp3"
    if "ogg" in ct: return ".ogg"
    return ".bin"

def _transcode_to_wav_16k(src: str) -> str:
    fd, dst = tempfile.mkstemp(suffix=".wav")
    os.close(fd)
    cmd = ["ffmpeg", "-y", "-i", src, "-ac", "1", "-ar", "16000", "-f", "wav", dst]
    subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
    return dst

def _transcribe(path: str) -> str:
    if whisper_model is None:
        return ""
    kwargs: Dict[str, Any] = {
        "fp16": False,
        "temperature": 0.0,
        "verbose": False,
        "condition_on_previous_text": False,
    }
    try:
        result = whisper_model.transcribe(path, **kwargs)  # type: ignore[attr-defined]
        text_val = result.get("text") or ""
        if isinstance(text_val, list):
            text_val = " ".join(str(x) for x in text_val)
        text = text_val.strip()
        return text
    except Exception as e:
        log.error("Transcription échouée: %s", e)
        return ""

# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------
class PromptIn(BaseModel):
    prompt: str


class CompanyAnalysisIn(BaseModel):
    url: str
    target_words: int = 300

# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse(
        "index.html",
        {"request": request, "prompts": PROMPTS, "model": GROQ_MODEL, "has_whisper": whisper_model is not None},
    )

@app.post("/process_prompt")
async def process_prompt(body: PromptIn = Body(...)):
    resp = await _call_groq_text(body.prompt)
    return JSONResponse({"prompt": body.prompt, "response_text": resp})


@app.post("/analyze_company")
async def analyze_company(body: CompanyAnalysisIn = Body(...)):
    """Analyze a company website and extract information."""
    if not COMPANY_ANALYZER_AVAILABLE:
        raise HTTPException(status_code=503, detail="Service d'analyse d'entreprise non disponible")
    
    try:
        analysis = analyze_company_website(body.url, body.target_words)
        return JSONResponse({
            "url": body.url,
            "target_words": body.target_words,
            "analysis": analysis,
            "success": True
        })
    except Exception as e:
        log.error("Erreur analyse entreprise: %s", e)
        return JSONResponse({
            "url": body.url,
            "target_words": body.target_words,
            "analysis": f"Erreur lors de l'analyse: {str(e)[:200]}",
            "success": False
        }, status_code=500)

@app.post("/process_audio")
async def process_audio(file: UploadFile = File(...)):
    if whisper_model is None:
        raise HTTPException(
            503,
            "Whisper indisponible. Installez: pip install openai-whisper et sudo apt-get update && sudo apt-get install -y ffmpeg",
        )
    if not file:
        raise HTTPException(400, "Aucun fichier reçu.")
    data = await file.read()
    if not data:
        raise HTTPException(400, "Fichier vide.")
    suffix = _guess_suffix(file.content_type)
    src = None
    wav = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(data)
            tmp.flush()
            src = tmp.name
        wav = _transcode_to_wav_16k(src) if suffix in (".webm", ".ogg") else src
        user_text = _transcribe(wav) or ""
        if not user_text:
            return JSONResponse({"user_text": "", "response_text": "Je n’ai pas compris l’audio, veuillez réessayer."})
        response_text = await _call_groq_text(user_text)
        return JSONResponse({"user_text": user_text, "response_text": response_text})
    finally:
        for p in (src, wav):
            if p and os.path.exists(p):
                try:
                    os.remove(p)
                except Exception:
                    pass

@app.get("/healthz")
async def healthz():
    return {
        "status": "ok", 
        "model": GROQ_MODEL, 
        "whisper": bool(whisper_model),
        "company_analyzer": COMPANY_ANALYZER_AVAILABLE
    }