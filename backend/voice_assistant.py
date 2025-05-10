from fastapi import FastAPI, File, UploadFile
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import whisper
from TTS.api import TTS
import requests
import os
import tempfile
import soundfile as sf
import numpy as np
import pygame
import logging
import traceback
import re

# Configure logging
logging.basicConfig(level=logging.DEBUG, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

app = FastAPI()

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configuration
OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL_NAME = "deepseek-r1:7b"
WHISPER_MODEL = "tiny"
TTS_MODEL = "tts_models/multilingual/multi-dataset/xtts_v2"
SAMPLE_RATE = 44100

def transcribe_audio(audio_file_path):
    logger.debug(f"Transcribing audio: {audio_file_path}")
    try:
        model = whisper.load_model(WHISPER_MODEL)  # Run on CPU
        result = model.transcribe(audio_file_path, language="en")  # Force English
        text = result["text"].strip()
        logger.debug(f"Transcription result: {text}")
        if not text or len(text.split()) < 2:  # Basic validation
            logger.warning("Transcription too short or empty")
            raise ValueError("Transcription failed: audio too short or unclear")
        return text
    except Exception as e:
        logger.error(f"Transcription error: {str(e)}\n{traceback.format_exc()}")
        raise

def query_ollama(prompt):
    logger.debug(f"Querying Ollama with prompt: {prompt}")
    try:
        # Stricter prompt to suppress reasoning
        full_prompt = f"Answer the following question or statement directly and concisely, without any reasoning, explanation, or <think> tags. Format the response as 'Answer: [your concise answer]' and keep it under 200 characters: {prompt}"
        payload = {
            "model": MODEL_NAME,
            "prompt": full_prompt,
            "stream": False
        }
        response = requests.post(OLLAMA_URL, json=payload)
        response.raise_for_status()
        result = response.json()["response"].strip()
        # Strip <think> tags if present
        result = re.sub(r'<think>.*?</think>', '', result, flags=re.DOTALL).strip()
        # Extract text after "Answer:"
        match = re.search(r'Answer:\s*(.+)', result, re.IGNORECASE)
        if match:
            result = match.group(1).strip()
        else:
            logger.warning("No 'Answer:' found in response, using full response")
        logger.debug(f"Ollama response: {result}")
        if not result:
            raise ValueError("Ollama returned empty response")
        return result
    except Exception as e:
        logger.error(f"Ollama error: {str(e)}\n{traceback.format_exc()}")
        raise

def synthesize_speech(text, output_file):
    logger.debug(f"Synthesizing speech for text: {text}")
    try:
        tts = TTS(model_name=TTS_MODEL, progress_bar=True).to("mps")
        tts.tts_to_file(text=text, file_path=output_file, speaker_wav="reference.wav", language="en")
        logger.debug(f"Synthesized audio saved to: {output_file}")
        # Verify audio file
        audio_data, sr = sf.read(output_file)
        if len(audio_data) == 0:
            raise ValueError("Synthesized audio is empty")
        return output_file
    except Exception as e:
        logger.error(f"TTS error: {str(e)}\n{traceback.format_exc()}")
        raise

@app.post("/process-audio")
async def process_audio(file: UploadFile = File(...)):
    logger.debug("Received audio file upload")
    try:
        # Save uploaded audio to a temporary file
        with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as temp_audio:
            content = await file.read()
            temp_audio.write(content)
            temp_audio_path = temp_audio.name
        logger.debug(f"Saved uploaded audio to: {temp_audio_path}")

        # Step 1: Transcribe audio
        user_text = transcribe_audio(temp_audio_path)
        if not user_text:
            logger.warning("No speech detected in audio")
            os.remove(temp_audio_path)
            return JSONResponse(content={"error": "No speech detected"}, status_code=400)

        # Step 2: Query DeepSeek via Ollama
        response_text = query_ollama(user_text)

        # Step 3: Synthesize speech
        with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as temp_output:
            output_path = synthesize_speech(response_text, temp_output.name)
            with open(output_path, "rb") as f:
                audio_data = f.read()
            # Verify audio data
            if len(audio_data) == 0:
                raise ValueError("No audio data generated")

        # Clean up
        os.remove(temp_audio_path)
        os.remove(output_path)
        logger.debug("Temporary files cleaned up")

        # Return response
        return {
            "user_text": user_text,
            "response_text": response_text,
            "audio": audio_data.hex()
        }
    except Exception as e:
        logger.error(f"Process audio error: {str(e)}\n{traceback.format_exc()}")
        return JSONResponse(content={"error": str(e)}, status_code=500)

# Local testing function (optional)
def test_pipeline(audio_file="input.wav"):
    pygame.mixer.init()
    user_text = transcribe_audio(audio_file)
    response_text = query_ollama(user_text)
    output_path = "output.wav"
    synthesize_speech(response_text, output_path)
    pygame.mixer.music.load(output_path)
    pygame.mixer.music.play()
    while pygame.mixer.music.get_busy():
        pygame.time.Clock().tick(10)
    os.remove(output_path)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)