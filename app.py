import streamlit as st
import assemblyai as aai
import requests
import time
import os
import io
from pydub import AudioSegment
from streamlit_webrtc import webrtc_streamer, WebRtcMode, ClientSettings

# Obter a API key do AssemblyAI dos secrets do Streamlit Cloud
aai_api_key = st.secrets["assemblyai"]["api_key"]
aai.settings.api_key = aai_api_key

st.sidebar.title("Menu")
page = st.sidebar.radio("Escolha uma opção", ["Transcrição de Áudio", "Conversor OGG para WAV"])

# Opção para escolher o idioma do áudio
language_map = {
    "Português": "pt",
    "Inglês": "en",
    "Espanhol": "es",
    "Francês": "fr"
}
language = st.sidebar.selectbox("Selecione o idioma do áudio:", list(language_map.keys()))
language_code = language_map[language]

def upload_to_assemblyai(file_path):
    """ Faz upload do arquivo para a API do AssemblyAI e retorna a URL """
    headers = {"authorization": aai_api_key}
    with open(file_path, "rb") as f:
        response = requests.post("https://api.assemblyai.com/v2/upload", headers=headers, files={"file": f})

    if response.status_code == 200:
        upload_url = response.json()["upload_url"]
        st.write(f"✅ Arquivo enviado com sucesso: [Ver arquivo]({upload_url})")
        return upload_url
    else:
        st.error(f"❌ Erro no upload. Código {response.status_code}")
        return None

def transcribe_with_wait(upload_url, language_code):
    """ Envia a solicitação de transcrição e aguarda até estar pronta """
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
    st.write(f"📡 Transcrição iniciada. ID: {transcript_id}")

    while True:
        status_response = requests.get(f"https://api.assemblyai.com/v2/transcript/{transcript_id}", headers=headers)
        status_json = status_response.json()

        if status_json["status"] == "completed":
            return status_json["text"]
        elif status_json["status"] == "failed":
            st.error("❌ Erro na transcrição do áudio.")
            return None
        else:
            st.info("⌛ Aguardando transcrição...")
            time.sleep(5)

if page == "Transcrição de Áudio":
    st.title("🎙️ Transcrição de Áudio com AssemblyAI")
    option = st.radio("Selecione a fonte de áudio:", ("URL", "Upload de arquivo", "Gravar Áudio"))

    if option == "URL":
        audio_url = st.text_input("Insira a URL do áudio:")

    elif option == "Gravar Áudio":
        st.write("🎤 Clique no botão abaixo para gravar o áudio")
        webrtc_ctx = webrtc_streamer(
            key="audio",
            mode=WebRtcMode.SENDONLY,
            media_stream_constraints={"audio": True, "video": False},  # Removida aspas extras aqui ✅
            client_settings=ClientSettings(
                rtc_configuration={"iceServers": [{"urls": ["stun:stun.l.google.com:19302"]}]},
                media_stream_constraints={"audio": True, "video": False}  # Removida aspas extras aqui ✅
            ),
        )

    else:
        audio_file = st.file_uploader("Faça upload do arquivo de áudio", type=["wav", "mp3", "m4a", "mp4", "ogg"])

    if st.button("Transcrever"):
        if option == "URL":
            if audio_url:
                st.info(f"Transcrevendo áudio em {language}...")
                transcript_text = transcribe_with_wait(audio_url, language_code)
                if transcript_text:
                    st.subheader("📝 Transcrição:")
                    st.write(transcript_text)
            else:
                st.error("❌ Insira uma URL válida.")

        elif option == "Gravar Áudio":
            if webrtc_ctx and webrtc_ctx.audio_receiver:
                audio_frames = webrtc_ctx.audio_receiver.get_frames()
                audio_data = b"".join([frame.to_ndarray().tobytes() for frame in audio_frames])

                temp_file = "recorded_audio.wav"
                with open(temp_file, "wb") as f:
                    f.write(audio_data)

                upload_url = upload_to_assemblyai(temp_file)

                if upload_url:
                    st.info(f"📡 Enviando para transcrição em {language}...")
                    transcript_text = transcribe_with_wait(upload_url, language_code)

                    if transcript_text:
                        st.subheader("📝 Transcrição:")
                        st.write(transcript_text)

                os.remove(temp_file)
            else:
                st.error("❌ Nenhum áudio gravado.")

        else:
            if audio_file:
                temp_file = "temp_audio"
                with open(temp_file, "wb") as f:
                    f.write(audio_file.getbuffer())

                if audio_file.name.endswith(".ogg"):
                    st.info("🔄 Convertendo OGG para WAV...")
                    temp_wav = "converted_audio.wav"
                    audio = AudioSegment.from_file(temp_file, format="ogg")
                    audio.export(temp_wav, format="wav")
                    temp_file = temp_wav

                upload_url = upload_to_assemblyai(temp_file)

                if upload_url:
                    st.info(f"📡 Enviando para transcrição em {language}...")
                    transcript_text = transcribe_with_wait(upload_url, language_code)

                    if transcript_text:
                        st.subheader("📝 Transcrição:")
                        st.write(transcript_text)

                os.remove(temp_file)
                if os.path.exists("converted_audio.wav"):
                    os.remove("converted_audio.wav")
            else:
                st.error("❌ Faça o upload de um arquivo de áudio.")

elif page == "Conversor OGG para WAV":
    st.title("🔄 Conversor de Áudio OGG para WAV")
    ogg_file = st.file_uploader("Faça upload do arquivo OGG", type=["ogg"])

    if ogg_file:
        if st.button("Converter para WAV"):
            st.info("🔄 Convertendo arquivo OGG para WAV...")

            audio = AudioSegment.from_file(io.BytesIO(ogg_file.getbuffer()), format="ogg")
            wav_io = io.BytesIO()
            audio.export(wav_io, format="wav")
            wav_io.seek(0)

            st.success("✅ Conversão concluída! Baixe o arquivo WAV abaixo.")
            st.download_button(label="📥 Baixar WAV", data=wav_io, file_name="convertido.wav", mime="audio/wav")
