import os
import sys
import tempfile
from typing import List

import httpx

# ---------------- Configuration ----------------
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama3-8b-8192")
GROQ_ENDPOINT = os.getenv("GROQ_ENDPOINT", "https://api.groq.com/openai/v1/chat/completions")

CHUNK_CHAR_LIMIT = int(os.getenv("CV_CHUNK_CHAR_LIMIT", "4500"))
TARGET_WORDS = int(os.getenv("CV_SUMMARY_WORDS", "250"))
TEMPERATURE = float(os.getenv("CV_SUMMARY_TEMPERATURE", "0.25"))
TOP_P = float(os.getenv("CV_SUMMARY_TOP_P", "0.9"))
MAX_TOKENS = int(os.getenv("CV_SUMMARY_MAX_TOKENS", "600"))
REQUEST_TIMEOUT = float(os.getenv("CV_REQUEST_TIMEOUT", "60"))

SYSTEM_PROMPT = (
    "Tu es un assistant qui résume des CV en français de manière professionnelle, structurée et factuelle. "
    "Structure attendue: 1) Profil 2) Compétences clés 3) Réalisations quantifiées 4) Stack / Outils 5) Valeur ajoutée / Positionnement. "
    "Ne pas inventer. Conserver chiffres, métriques, technologies. Ton concis."
)

# Optionnelle extraction PDF
try:
    from pypdf import PdfReader  # pip install pypdf
except Exception:
    PdfReader = None  # type: ignore


# ---------------- Utils ----------------
def read_file_content(path: str) -> str:
    if not os.path.exists(path):
        raise FileNotFoundError(f"Fichier introuvable: {path}")
    if path.lower().endswith(".pdf"):
        return extract_pdf(path)
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        return f.read()


def extract_pdf(path: str) -> str:
    if not PdfReader:
        return "[Impossible d'extraire le PDF (pypdf non installé)]"
    try:
        reader = PdfReader(path)
        pages = []
        for p in reader.pages:
            try:
                pages.append(p.extract_text() or "")
            except Exception:
                pages.append("")
        return "\n".join(pages)
    except Exception as e:
        return f"[Erreur extraction PDF: {e}]"


def clean_text(t: str) -> str:
    lines = [ln.strip() for ln in t.replace("\r", "").split("\n")]
    return "\n".join([ln for ln in lines if ln])


def split_chunks(text: str, limit: int) -> List[str]:
    text = text.strip()
    if len(text) <= limit:
        return [text]
    parts: List[str] = []
    buf = []
    size = 0
    for line in text.splitlines():
        ln = line.strip()
        add = len(ln) + 1
        if size + add > limit and buf:
            parts.append("\n".join(buf).strip())
            buf = [ln]
            size = len(ln)
        else:
            buf.append(ln)
            size += add
    if buf:
        parts.append("\n".join(buf).strip())
    return parts


def call_llm(messages) -> str:
    if not GROQ_API_KEY:
        return "Erreur: variable GROQ_API_KEY absente."
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
                or "(Résumé vide)"
            )
    except httpx.HTTPStatusError as e:
        return f"HTTP {e.response.status_code}: {e.response.text[:200]}"
    except Exception as e:
        return f"Erreur réseau: {e}"


def summarize_chunk(chunk: str, target_words: int) -> str:
    user_prompt = (
        f"Résume ce segment de CV en ~{target_words} mots, puces concises, garde chiffres/tech.\n\n=== SEGMENT ===\n{chunk}"
    )
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ]
    return call_llm(messages)


def summarize_cv(raw_text: str, target_words: int = TARGET_WORDS) -> str:
    raw_text = clean_text(raw_text)
    if not raw_text:
        return "CV vide."
    chunks = split_chunks(raw_text, CHUNK_CHAR_LIMIT)
    if len(chunks) == 1:
        return summarize_chunk(chunks[0], target_words)

    # Résumer chaque segment puis fusion
    per_chunk_goal = max(50, int(target_words * 0.6 / len(chunks)))
    partials = []
    for i, c in enumerate(chunks, 1):
        part = summarize_chunk(c, per_chunk_goal)
        partials.append(f"[Partie {i}/{len(chunks)}]\n{part}")

    merged = "\n\n".join(partials)
    fusion_prompt = (
        f"Fusionne les résumés partiels ci-dessous en un résumé global (~{target_words} mots) "
        "sans répétitions, même structure exigée, conserve métriques & mots-clés.\n\n"
        f"=== RÉSUMÉS PARTIELS ===\n{merged}"
    )
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": fusion_prompt},
    ]
    return call_llm(messages)


# ---------------- CLI ----------------
def main():
    if len(sys.argv) < 2:
        print("Usage: python cv.py chemin_cv.(txt|pdf) [mots_cible]")
        sys.exit(1)
    path = sys.argv[1]
    target = TARGET_WORDS
    if len(sys.argv) >= 3:
        try:
            target = int(sys.argv[2])
        except ValueError:
            pass
    try:
        content = read_file_content(path)
    except Exception as e:
        print(f"Erreur lecture fichier: {e}")
        sys.exit(1)

    summary = summarize_cv(content, target)
    print("\n=== RÉSUMÉ CV ===\n")
    print(summary)
    print("\n=================\n")


if __name__ == "__main__":
    main()