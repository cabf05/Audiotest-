import streamlit as st
import assemblyai as aai
import os

# Obter a API key do AssemblyAI dos secrets do Streamlit Cloud
aai_api_key = st.secrets["assemblyai"]["api_key"]
aai.settings.api_key = aai_api_key

st.title("Transcrição de Áudio com AssemblyAI")

st.write("Escolha entre fornecer a URL do áudio ou fazer upload do arquivo.")

# Permitir upload de arquivos, incluindo ogg
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
            # Salva o arquivo de áudio temporariamente
            temp_file = "temp_audio"
            with open(temp_file, "wb") as f:
                f.write(audio_file.getbuffer())
            st.info("Transcrevendo áudio, aguarde...")
            transcriber = aai.Transcriber()
            transcript = transcriber.transcribe(temp_file)
            st.subheader("Transcrição:")
            st.write(transcript.text)
            os.remove(temp_file)
        else:
            st.error("Por favor, faça o upload de um arquivo de áudio.")
