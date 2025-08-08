# AI Voice Assistant

## Installation

1. Clone this repo.
2. Téléchargez le modèle Phi-2 GGUF et placez-le dans `models/` :
   - Exemple : `models/phi-2.Q4_K_M.gguf`
   - Lien modèle : https://huggingface.co/TheBloke/phi-2-GGUF
3. Installez les dépendances :
   ```bash
   pip install -r requirements.txt
   ```
4. Lancez le serveur :
   ```bash
   uvicorn app:app --reload
   ```
5. Ouvrez dans votre navigateur :
   [http://localhost:8000](http://localhost:8000)

## Utilisation

- Cliquez sur "Start Recording" pour poser une question.
- Cliquez sur "Stop Recording" quand vous avez fini de parler.
- Le texte transcrit et la réponse du modèle s'affichent.