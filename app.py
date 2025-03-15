import streamlit as st
import assemblyai as aai
import requests
import io
import os
from pydub import AudioSegment

# Obter a API key do AssemblyAI dos secrets do Streamlit Cloud
aai_api_key = st.secrets["assemblyai"]["api_key"]
aai.settings.api_key = aai_api_key

st.sidebar.title("Menu")
page = st.sidebar.radio("Escolha uma opção", ["Transcrição de Áudio", "Conversor OGG para WAV"])

def upload_to_assemblyai(file_path):
    """ Faz upload do arquivo para a API do AssemblyAI e retorna a URL """
    headers = {"authorization": aai_api_key}
    with open(file_path, "rb") as f:
        response = requests.post("https://api.assemblyai.com/v2/upload", headers=headers, files={"file": f})
    
    if response.status_code == 200:
        return response.json()["upload_url"]
    else:
        st.error(f"Erro ao fazer upload do arquivo. Código {response.status_code}")
        return None

if page == "Transcrição de Áudio":
    st.title("🎙️ Transcrição de Áudio com AssemblyAI")

    option = st.radio("Selecione a fonte de áudio:", ("URL", "Upload de arquivo"))

    if option == "URL":
        audio_url = st.text_input("Insira a URL do áudio:")
    else:
        audio_file = st.file_uploader("Faça upload do arquivo de áudio", type=["wav", "mp3", "m4a", "mp4", "ogg"])

    if st.button("Transcrever"):
        if option == "URL":
            if audio_url:
                st.info("Transcrevendo áudio, aguarde...")
                transcriber = aai.Transcriber()
                transcript = transcriber.transcribe(audio_url)
                st.subheader("Transcrição:")
                st.write(transcript.text)
            else:
                st.error("Por favor, insira a URL do áudio.")
        else:
            if audio_file:
                # Salva o arquivo temporariamente
                temp_file = "temp_audio"
                with open(temp_file, "wb") as f:
                    f.write(audio_file.getbuffer())

                # Se for OGG, converte antes de enviar para transcrição
                if audio_file.name.endswith(".ogg"):
                    st.info("Convertendo arquivo OGG para WAV...")
                    temp_wav = "converted_audio.wav"
                    audio = AudioSegment.from_file(temp_file, format="ogg")
                    audio.export(temp_wav, format="wav")
                    temp_file = temp_wav

                # Faz o upload do arquivo para o AssemblyAI
                upload_url = upload_to_assemblyai(temp_file)

                if upload_url:
                    st.info("Transcrevendo áudio, aguarde...")
                    transcriber = aai.Transcriber()
                    transcript = transcriber.transcribe(upload_url)
                    
                    st.subheader("Transcrição:")
                    st.write(transcript.text)
                else:
                    st.error("Falha no envio do arquivo para AssemblyAI.")

                # Remover arquivos temporários
                os.remove(temp_file)
                if os.path.exists("converted_audio.wav"):
                    os.remove("converted_audio.wav")
            else:
                st.error("Por favor, faça o upload de um arquivo de áudio.")

elif page == "Conversor OGG para WAV":
    st.title("🔄 Conversor de Áudio OGG para WAV")
    ogg_file = st.file_uploader("Faça upload do arquivo OGG", type=["ogg"])

    if ogg_file:
        if st.button("Converter para WAV"):
            st.info("Convertendo arquivo OGG para WAV...")

            # Ler o arquivo OGG da memória
            audio = AudioSegment.from_file(io.BytesIO(ogg_file.getbuffer()), format="ogg")

            # Salvar como WAV na memória
            wav_io = io.BytesIO()
            audio.export(wav_io, format="wav")
            wav_io.seek(0)

            st.success("Conversão concluída! Baixe o arquivo WAV abaixo.")
            st.download_button(label="📥 Baixar WAV", data=wav_io, file_name="convertido.wav", mime="audio/wav")
