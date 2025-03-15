import streamlit as st
import assemblyai as aai
import requests
import time
import os
import io
import tempfile
import numpy as np
import soundfile as sf
from pydub import AudioSegment
import streamlit_webrtc
from streamlit_webrtc import webrtc_streamer, WebRtcMode, RTCConfiguration
import av
import queue
import threading
import uuid

# Configuração da página Streamlit
st.set_page_config(page_title="Transcrição de Áudio", page_icon="🎙️")

# Obter a API key do AssemblyAI dos secrets do Streamlit Cloud
if 'assemblyai' in st.secrets:
    aai_api_key = st.secrets["assemblyai"]["api_key"]
else:
    aai_api_key = os.getenv("ASSEMBLYAI_API_KEY", "")
    if not aai_api_key:
        aai_api_key = st.text_input("Digite sua API key do AssemblyAI:", type="password")
        if not aai_api_key:
            st.warning("⚠️ É necessário fornecer uma API key válida do AssemblyAI para continuar.")
            st.stop()

aai.settings.api_key = aai_api_key

# Configuração da interface
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

# Classe para a gravação de áudio
class AudioProcessor:
    def __init__(self):
        self.audio_frames = []
        self.recording = False
        self.recorded_file = None
    
    def process_audio(self, frame):
        if self.recording:
            sound = frame.to_ndarray()
            sound = sound.reshape(-1)
            self.audio_frames.append(sound)
            
        return frame

    def start_recording(self):
        self.audio_frames = []
        self.recording = True
    
    def stop_recording(self):
        self.recording = False
        return self.save_recording()
    
    def save_recording(self):
        if not self.audio_frames:
            return None
            
        # Concatenate recorded audio frames
        audio_data = np.concatenate(self.audio_frames, axis=0)
        
        # Create temp file
        temp_dir = tempfile.mkdtemp()
        temp_file = os.path.join(temp_dir, f"recorded_audio_{uuid.uuid4()}.wav")
        
        # Save as WAV file
        sf.write(temp_file, audio_data, 48000)
        st.session_state.recorded_file_path = temp_file
        
        return temp_file

def upload_to_assemblyai(file_path):
    """ Faz upload do arquivo para a API do AssemblyAI e retorna a URL """
    headers = {"authorization": aai_api_key}
    with open(file_path, "rb") as f:
        response = requests.post("https://api.assemblyai.com/v2/upload", 
                                headers=headers, 
                                files={"file": f})

    if response.status_code == 200:
        upload_url = response.json()["upload_url"]
        st.write(f"✅ Arquivo enviado com sucesso!")
        return upload_url
    else:
        st.error(f"❌ Erro no upload. Código {response.status_code}")
        st.error(f"Resposta: {response.text}")
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
        st.error(f"❌ Erro ao solicitar transcrição. Código: {response.status_code}")
        st.error(f"Resposta: {response.text}")
        return None

    transcript_id = response.json()["id"]
    st.write(f"📡 Transcrição iniciada. ID: {transcript_id}")
    
    progress_bar = st.progress(0)
    status_placeholder = st.empty()

    while True:
        status_response = requests.get(f"https://api.assemblyai.com/v2/transcript/{transcript_id}", headers=headers)
        status_json = status_response.json()

        if status_json["status"] == "completed":
            progress_bar.progress(100)
            status_placeholder.success("✅ Transcrição concluída!")
            return status_json["text"]
        elif status_json["status"] == "error" or status_json["status"] == "failed":
            progress_bar.empty()
            status_placeholder.error(f"❌ Erro na transcrição: {status_json.get('error', 'Desconhecido')}")
            return None
        else:
            # Atualiza o status
            progress = 0
            if status_json["status"] == "queued":
                status_placeholder.info("⏳ Na fila para processamento...")
                progress = 10
            elif status_json["status"] == "processing":
                if "audio_duration" in status_json and status_json["audio_duration"] > 0:
                    progress = min(90, int((status_json.get("audio_start", 0) / status_json["audio_duration"]) * 100))
                else:
                    progress = 50
                status_placeholder.info(f"⚙️ Processando áudio... {progress}%")
            progress_bar.progress(progress)
            time.sleep(3)

# Inicializar variáveis de estado da sessão
if 'audio_processor' not in st.session_state:
    st.session_state.audio_processor = AudioProcessor()
    
if 'recording' not in st.session_state:
    st.session_state.recording = False
    
if 'recorded_file_path' not in st.session_state:
    st.session_state.recorded_file_path = None
    
if 'webrtc_ctx' not in st.session_state:
    st.session_state.webrtc_ctx = None

# Página de Transcrição de Áudio
if page == "Transcrição de Áudio":
    st.title("🎙️ Transcrição de Áudio com AssemblyAI")
    option = st.radio("Selecione a fonte de áudio:", ("Upload de arquivo", "URL", "Gravar Áudio"))

    if option == "URL":
        audio_url = st.text_input("Insira a URL do áudio:")
        
        if st.button("Transcrever URL"):
            if audio_url:
                st.info(f"Transcrevendo áudio em {language}...")
                with st.spinner("Processando..."):
                    transcript_text = transcribe_with_wait(audio_url, language_code)
                    if transcript_text:
                        st.subheader("📝 Transcrição:")
                        st.write(transcript_text)
                        
                        # Opção para baixar a transcrição
                        transcript_download = transcript_text.encode()
                        st.download_button(
                            label="📥 Baixar transcrição como TXT",
                            data=transcript_download,
                            file_name="transcricao.txt",
                            mime="text/plain"
                        )
            else:
                st.error("❌ Insira uma URL válida.")

    elif option == "Gravar Áudio":
        st.write("🎤 Gravação de áudio")
        
        col1, col2 = st.columns(2)
        
        with col1:
            webrtc_state = st.empty()
            if not st.session_state.recording:
                if st.button("🎙️ Iniciar Gravação"):
                    st.session_state.recording = True
                    st.session_state.audio_processor.start_recording()
                    st.experimental_rerun()
            else:
                if st.button("⏹️ Parar Gravação"):
                    recorded_file = st.session_state.audio_processor.stop_recording()
                    st.session_state.recording = False
                    if recorded_file:
                        st.session_state.recorded_file_path = recorded_file
                        st.success(f"✅ Áudio gravado com sucesso!")
                    st.experimental_rerun()
                    
        with col2:
            if st.session_state.recording:
                webrtc_state.warning("⚠️ Gravando áudio... Clique em 'Parar Gravação' quando terminar.")
            else:
                webrtc_state.info("🎙️ Clique em 'Iniciar Gravação' para começar.")
                
        # WebRTC Streamer
        rtc_configuration = RTCConfiguration({"iceServers": [{"urls": ["stun:stun.l.google.com:19302"]}]})
        
        def audio_frame_callback(frame):
            return st.session_state.audio_processor.process_audio(frame)
            
        st.session_state.webrtc_ctx = webrtc_streamer(
            key="sendonly-audio",
            mode=WebRtcMode.SENDONLY,
            rtc_configuration=rtc_configuration,
            media_stream_constraints={"video": False, "audio": True},
            audio_frame_callback=audio_frame_callback,
            async_processing=True,
        )
        
        # Opção para transcrever o áudio gravado
        if st.session_state.recorded_file_path and os.path.exists(st.session_state.recorded_file_path):
            st.audio(st.session_state.recorded_file_path, format="audio/wav")
            
            if st.button("📝 Transcrever Áudio Gravado"):
                upload_url = upload_to_assemblyai(st.session_state.recorded_file_path)
                if upload_url:
                    with st.spinner(f"Transcrevendo áudio em {language}..."):
                        transcript_text = transcribe_with_wait(upload_url, language_code)
                        if transcript_text:
                            st.subheader("📝 Transcrição:")
                            st.write(transcript_text)
                            
                            # Opção para baixar a transcrição
                            transcript_download = transcript_text.encode()
                            st.download_button(
                                label="📥 Baixar transcrição como TXT",
                                data=transcript_download,
                                file_name="transcricao.txt",
                                mime="text/plain"
                            ) 

    else:  # Upload de arquivo
        st.write("📁 Faça upload do arquivo de áudio")
        audio_file = st.file_uploader("Selecione um arquivo de áudio", type=["wav", "mp3", "m4a", "mp4", "ogg"])
        
        if audio_file is not None:
            # Exibir informações do arquivo
            file_details = {
                "Nome do arquivo": audio_file.name,
                "Tipo MIME": audio_file.type,
                "Tamanho": f"{audio_file.size / 1024 / 1024:.2f} MB"
            }
            st.write("Detalhes do arquivo:")
            for key, value in file_details.items():
                st.write(f"- {key}: {value}")
            
            # Salvar o arquivo temporariamente
            with tempfile.NamedTemporaryFile(delete=False, suffix=f".{audio_file.name.split('.')[-1]}") as tmp_file:
                tmp_file.write(audio_file.getbuffer())
                temp_path = tmp_file.name
            
            # Converter OGG para WAV se necessário
            if audio_file.name.endswith(".ogg"):
                st.info("🔄 Convertendo OGG para WAV...")
                try:
                    audio = AudioSegment.from_file(temp_path, format="ogg")
                    wav_path = temp_path.replace(".ogg", ".wav")
                    audio.export(wav_path, format="wav")
                    temp_path = wav_path
                    st.success("✅ Arquivo convertido com sucesso!")
                except Exception as e:
                    st.error(f"❌ Erro ao converter o arquivo: {str(e)}")
                    if os.path.exists(temp_path):
                        os.unlink(temp_path)
                    st.stop()
            
            # Reproduzir o áudio
            try:
                st.audio(temp_path)
            except Exception as e:
                st.error(f"❌ Erro ao reproduzir o áudio: {str(e)}")
            
            # Botão para transcrever
            if st.button("📝 Transcrever"):
                upload_url = upload_to_assemblyai(temp_path)
                if upload_url:
                    with st.spinner(f"Transcrevendo áudio em {language}..."):
                        transcript_text = transcribe_with_wait(upload_url, language_code)
                        if transcript_text:
                            st.subheader("📝 Transcrição:")
                            st.write(transcript_text)
                            
                            # Opção para baixar a transcrição
                            transcript_download = transcript_text.encode()
                            st.download_button(
                                label="📥 Baixar transcrição como TXT",
                                data=transcript_download,
                                file_name="transcricao.txt",
                                mime="text/plain"
                            )
                
                # Limpar o arquivo temporário após o uso
                if os.path.exists(temp_path):
                    os.unlink(temp_path)

# Página de Conversor OGG para WAV
elif page == "Conversor OGG para WAV":
    st.title("🔄 Conversor de Áudio OGG para WAV")
    st.write("""
    Este conversor permite transformar arquivos OGG em arquivos WAV, 
    que são mais amplamente compatíveis com diferentes sistemas.
    """)
    
    ogg_file = st.file_uploader("Faça upload do arquivo OGG", type=["ogg"])

    if ogg_file:
        st.write("Arquivo OGG carregado!")
        
        if st.button("🔄 Converter para WAV"):
            st.info("🔄 Convertendo arquivo OGG para WAV...")
            
            try:
                # Salvar o arquivo OGG temporariamente
                with tempfile.NamedTemporaryFile(delete=False, suffix=".ogg") as tmp_file
