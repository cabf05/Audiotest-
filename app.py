import streamlit as st
import soundfile as sf
import numpy as np
import io
import requests
import zipfile
import os
from vosk import Model, KaldiRecognizer

# URL do modelo Vosk em português (modelo leve)
MODEL_URL = "https://alphacephei.com/vosk/models/vosk-model-small-pt.zip"
MODEL_PATH = "vosk-model-small-pt"

# Baixar e extrair modelo se não existir
if not os.path.exists(MODEL_PATH):
    st.info("Baixando modelo de transcrição, aguarde...")
    response = requests.get(MODEL_URL, stream=True)
    with open("model.zip", "wb") as f:
        for chunk in response.iter_content(chunk_size=8192):
            f.write(chunk)
    with zipfile.ZipFile("model.zip", "r") as zip_ref:
        zip_ref.extractall(".")
    os.remove("model.zip")

# Carregar o modelo Vosk
model = Model(MODEL_PATH)

st.title("🎙️ Gravação e Transcrição de Áudio em Português")

# Captura de áudio
audio_data = st.audio_recorder()

if audio_data is not None:
    st.audio(audio_data, format="audio/wav")

    if st.button("Transcrever Áudio"):
        audio_bytes = io.BytesIO(audio_data)

        # Ler áudio e converter para PCM
        with sf.SoundFile(audio_bytes) as audio_file:
            audio = audio_file.read(dtype="int16")
            sample_rate = audio_file.samplerate

        # Criar reconhecedor do Vosk
        recognizer = KaldiRecognizer(model, sample_rate)
        recognizer.AcceptWaveform(audio.tobytes())

        # Obter transcrição
        result = recognizer.Result()
        transcript = result.get("text", "")

        st.subheader("📝 Transcrição:")
        st.write(transcript if transcript else "Nenhuma fala reconhecida.")
