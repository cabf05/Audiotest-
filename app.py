import streamlit as st
import assemblyai as aai
import requests
import time
import os
import io
from pydub import AudioSegment
from streamlit_webrtc import webrtc_streamer, WebRtcMode, ClientSettings

# Configuração da API do AssemblyAI
aai_api_key = st.secrets["assemblyai"]["api_key"]
aai.settings.api_key = aai_api_key

st.sidebar.title("Menu")
page = st.sidebar.radio("Escolha uma opção", ["Transcrição de Áudio", "Conversor OGG para WAV"])

# Seleção de idioma
language_map = {"Português": "pt", "Inglês": "en", "Espanhol": "es", "Francês": "fr"}
language = st.sidebar.selectbox("Selecione o idioma do áudio:", list(language_map.keys()))
language_code = language_map[language]

def upload_to_assemblyai(file_path):
    """Faz upload do arquivo para a API do AssemblyAI e retorna a URL"""
    headers = {"authorization": aai_api_key}
    with open(file_path, "rb") as f:
        response = requests.post("https://api.assemblyai.com/v2/upload", headers=headers, files={"file": f})
    if response.status_code == 200:
        return response.json()["upload_url"]
    else:
        st.error(f"❌ Erro no upload: {response.status_code}")
        return None

def transcribe_with_wait(upload_url, language_code):
    """Envia solicitação de transcrição e aguarda o resultado"""
    headers = {"authorization": aai_api_key, "content-type": "application/json"}
    response = requests.post(
        "https://api.assemblyai.com/v2/transcript",
        json={"audio_url": upload_url, "language_code": language_code},
        headers=headers
    )
    if response.status_code != 200:
        st.error("❌ Erro ao solicitar transcrição.")
        return None

    transcript_id = response.json()["id"]
    while True:
        status_response = requests.get(f"https://api.assemblyai.com/v2/transcript/{transcript_id}", headers=headers)
        status_json = status_response.json()
        if status_json["status"] == "completed":
            return status_json["text"]
        elif status_json["status"] == "failed":
            st.error("❌ Erro na transcrição.")
            return None
        st.info("⌛ Aguardando transcrição...")
        time.sleep(5)

if page == "Transcrição de Áudio":
    st.title("🎙️ Transcrição de Áudio com AssemblyAI")
    option = st.radio("Selecione a fonte de áudio:", ("URL", "Upload de arquivo", "Gravar Áudio"))

    if option == "URL":
        audio_url = st.text_input("Insira a URL do áudio:")
        if st.button("Transcrever") and audio_url:
            transcript_text = transcribe_with_wait(audio_url, language_code)
            if transcript_text:
                st.subheader("📝 Transcrição:")
                st.write(transcript_text)

    elif option == "Gravar Áudio":
        st.write("🎤 Grave seu áudio abaixo:")
        webrtc_ctx = webrtc_streamer(
            key="audio",
            mode=WebRtcMode.SENDONLY,
            audio=True,
            video=False,
            client_settings=ClientSettings(
                rtc_configuration={"iceServers": [{"urls": ["stun:stun.l.google.com:19302"]}]},
                media_stream_constraints={"audio": True, "video": False}
            )
        )
        if webrtc_ctx.audio_receiver and st.button("Transcrever"):
            audio_frames = []
            for frame in webrtc_ctx.audio_receiver.get_frames(timeout=10):
                audio_frames.append(frame.to_ndarray().tobytes())
            if audio_frames:
                audio_data = b"".join(audio_frames)
                with open("temp_audio.wav", "wb") as f:
                    f.write(audio_data)
                AudioSegment.from_file("temp_audio.wav").export("recorded_audio.wav", format="wav")
                upload_url = upload_to_assemblyai("recorded_audio.wav")
                if upload_url:
                    transcript_text = transcribe_with_wait(upload_url, language_code)
                    if transcript_text:
                        st.subheader("📝 Transcrição:")
                        st.write(transcript_text)
                os.remove("temp_audio.wav")
                os.remove("recorded_audio.wav")
            else:
                st.error("❌ Nenhum áudio gravado.")

    else:
        audio_file = st.file_uploader("Faça upload do arquivo de áudio", type=["wav", "mp3", "m4a", "mp4", "ogg"])
        if audio_file and st.button("Transcrever"):
            temp_file = "temp_audio"
            with open(temp_file, "wb") as f:
                f.write(audio_file.read())
            if audio_file.name.endswith(".ogg"):
                audio = AudioSegment.from_ogg(temp_file)
                temp_file = "converted_audio.wav"
                audio.export(temp_file, format="wav")
            upload_url = upload_to_assemblyai(temp_file)
            if upload_url:
                transcript_text = transcribe_with_wait(upload_url, language_code)
                if transcript_text:
                    st.subheader("📝 Transcrição:")
                    st.write(transcript_text)
            os.remove(temp_file)
            if os.path.exists("converted_audio.wav"):
                os.remove("converted_audio.wav")

elif page == "Conversor OGG para WAV":
    st.title("🔄 Conversor de Áudio OGG para WAV")
    ogg_file = st.file_uploader("Faça upload do arquivo OGG", type=["ogg"])
    if ogg_file and st.button("Converter para WAV"):
        audio = AudioSegment.from_ogg(io.BytesIO(ogg_file.read()))
        wav_io = io.BytesIO()
        audio.export(wav_io, format="wav")
        wav_io.seek(0)
        st.download_button(
            label="📥 Baixar WAV",
            data=wav_io,
            file_name="converted_audio.wav",
            mime="audio/wav"
        )
