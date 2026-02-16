import os
import json
import threading
import requests
from flask import Flask, request, jsonify
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

app = Flask(__name__)

# --- CONFIGURACIÓN DE ENTORNO ---
# En Render, pegaremos el contenido del JSON en las Variables de Entorno
TOKEN_JSON_STR = os.environ.get('GOOGLE_TOKEN_JSON') 

# Carpeta temporal (en Render usamos /tmp que es escribible)
UPLOAD_FOLDER = '/tmp'

def process_videos(payload):
    print("Iniciando proceso en background...")
    topic = payload.get('topic', 'Clase Zoom')
    files = payload.get('files', [])

    # 1. Reconstruir credenciales desde la Variable de Entorno
    if not TOKEN_JSON_STR:
        print("ERROR: No encontré la variable GOOGLE_TOKEN_JSON")
        return

    # Convertimos el string JSON a diccionario y luego a objeto Credentials
    token_info = json.loads(TOKEN_JSON_STR)
    creds = Credentials.from_authorized_user_info(token_info)

    try:
        youtube = build('youtube', 'v3', credentials=creds)
    except Exception as e:
        print(f"Error conectando a YouTube: {e}")
        return

    for i, file_info in enumerate(files):
        download_url = file_info.get('download_url')
        file_type = file_info.get('file_type')
        
        if file_type != 'MP4':
            continue

        print(f"Procesando video {i+1}...")
        
        # Ruta temporal segura
        local_filename = os.path.join(UPLOAD_FOLDER, f"video_{i}.mp4")

        try:
            # A. DESCARGAR
            with requests.get(download_url, stream=True) as r:
                r.raise_for_status()
                with open(local_filename, 'wb') as f:
                    for chunk in r.iter_content(chunk_size=8192): 
                        f.write(chunk)
            
            # B. SUBIR
            title = f"{topic} - Parte {i+1}"
            request_body = {
                'snippet': {
                    'title': title,
                    'description': f'Grabación automática: {topic}',
                    'tags': ['zoom'],
                    'categoryId': '22'
                },
                'status': {
                    'privacyStatus': 'unlisted',
                    'selfDeclaredMadeForKids': False
                }
            }

            media = MediaFileUpload(local_filename, chunksize=-1, resumable=True)
            youtube.videos().insert(
                part='snippet,status',
                body=request_body,
                media_body=media
            ).execute()
            print(f"Subido OK: {title}")

        except Exception as e:
            print(f"Falló el video {i+1}: {e}")
        
        finally:
            # C. BORRAR (Crucial en Render)
            if os.path.exists(local_filename):
                os.remove(local_filename)

@app.route('/webhook', methods=['POST'])
def webhook():
    data = request.json
    # Responder a Make INMEDIATAMENTE antes de procesar
    thread = threading.Thread(target=process_videos, args=(data,))
    thread.start()
    return jsonify({"status": "received"}), 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)
