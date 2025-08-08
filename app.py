from fastapi import FastAPI, Request, UploadFile, File
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
import whisper
from llama_cpp import Llama
import tempfile
import os

app = FastAPI()
templates = Jinja2Templates(directory="templates")

print("Loading Whisper model...")
whisper_model = whisper.load_model("base")
print("Loading LLM model...")
llm = Llama(model_path="models/phi-2.Q4_K_M.gguf", n_ctx=2048, n_threads=4)

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

from typing import Optional

def _guess_suffix(content_type: Optional[str]) -> str:
    ct = (content_type or "").lower()
    if "wav" in ct:
        return ".wav"
    if "webm" in ct:
        return ".webm"
    if "mpeg" in ct or "mp3" in ct:
        return ".mp3"
    if "ogg" in ct:
        return ".ogg"
    return ".bin"

@app.post("/process_audio")
async def process_audio(file: UploadFile = File(...)):
    # Lire les octets uploadés et les écrire dans un fichier temporaire
    audio_bytes = await file.read()
    suffix = _guess_suffix(file.content_type)
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(audio_bytes)
            tmp.flush()
            tmp_path = tmp.name

        # Laisser Whisper décoder (via ffmpeg) en lui passant le chemin de fichier
        result = whisper_model.transcribe(tmp_path, fp16=False)
        text_result = result.get("text", "")
        if isinstance(text_result, list):
            user_text = " ".join(str(seg) for seg in text_result).strip()
        else:
            user_text = str(text_result).strip()

        # Générer la réponse du LLM
        prompt = f"[INST] {user_text} [/INST]"
        llm_response_iter = llm(prompt=prompt, max_tokens=200, stop=["</s>"])
        llm_response_list = list(llm_response_iter)
        response_text = ""
        if llm_response_list:
            response_text = str(llm_response_list[0]).strip()

        return JSONResponse(content={"user_text": user_text, "response_text": response_text})
    finally:
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except Exception:
                pass