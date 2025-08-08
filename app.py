from fastapi import FastAPI, Request, UploadFile, File, Form
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import whisper
import numpy as np
import soundfile as sf
import io
from llama_cpp import Llama

app = FastAPI()
templates = Jinja2Templates(directory="templates")

print("Loading Whisper model...")
whisper_model = whisper.load_model("base")
print("Loading LLM model...")
llm = Llama(model_path="models/phi-2.Q4_K_M.gguf", n_ctx=2048, n_threads=4)

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.post("/process_audio")
async def process_audio(file: UploadFile = File(...)):
    # Lire audio envoyé
    audio_bytes = await file.read()
    audio_np, samplerate = sf.read(io.BytesIO(audio_bytes))
    # Whisper transcription
    result = whisper_model.transcribe(audio_np, fp16=False)
    user_text = result["text"]
    # LLM réponse
    prompt = f"[INST] {user_text} [/INST]"
    llm_response = llm(prompt=prompt, max_tokens=200, stop=["</s>"])
    response_text = llm_response['choices'][0]['text'].strip()
    return JSONResponse(content={"user_text": user_text, "response_text": response_text})