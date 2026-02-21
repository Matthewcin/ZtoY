import os
import time
import telebot
import threading
import requests
import json
import hashlib
import hmac
from datetime import datetime, timedelta
from flask import Flask, request, jsonify
from telebot import types
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from googleapiclient.http import MediaFileUpload
import urllib.parse

TOKEN = os.getenv("TELEGRAM_TOKEN")
GOOGLE_TOKEN = os.environ.get('GOOGLE_TOKEN_JSON')
ZOOM_ACCOUNT_ID = os.getenv("ZOOM_ACCOUNT_ID")
ZOOM_CLIENT_ID = os.getenv("ZOOM_CLIENT_ID")
ZOOM_CLIENT_SECRET = os.getenv("ZOOM_CLIENT_SECRET")
ZOOM_WEBHOOK_SECRET = os.getenv("ZOOM_WEBHOOK_SECRET")
ADMIN_CHAT_ID = os.getenv("ADMIN_CHAT_ID")

bot = telebot.TeleBot(TOKEN)
app = Flask(__name__)

def get_zoom_token():
    url = f"https://zoom.us/oauth/token?grant_type=account_credentials&account_id={ZOOM_ACCOUNT_ID}"
    r = requests.post(url, auth=(ZOOM_CLIENT_ID, ZOOM_CLIENT_SECRET))
    return r.json().get('access_token')

def get_youtube_service():
    info = json.loads(GOOGLE_TOKEN)
    creds = Credentials.from_authorized_user_info(info)
    return build('youtube', 'v3', credentials=creds)

def get_participants(uuid_safe):
    try:
        token = get_zoom_token()
        headers = {"Authorization": f"Bearer {token}"}
        r = requests.get(f"https://api.zoom.us/v2/report/meetings/{uuid_safe}", headers=headers)
        if r.status_code == 200:
            return r.json().get('participants_count', 'Desconocido')
        r2 = requests.get(f"https://api.zoom.us/v2/past_meetings/{uuid_safe}", headers=headers)
        if r2.status_code == 200:
            return r2.json().get('participants_count', 'Desconocido')
        return 'Desconocido'
    except:
        return 'Desconocido'

def download_with_retry(download_url, file_path, chat_id, message_id):
    max_retries = 15
    wait_seconds = 60
    
    for i in range(max_retries):
        token = get_zoom_token()
        headers = {"Authorization": f"Bearer {token}"}
        
        with requests.get(download_url, headers=headers, stream=True) as r:
            if r.status_code == 404 or r.status_code == 403:
                bot.edit_message_text(
                    f"⏳ Zoom procesando el video...\nReintentando en {wait_seconds}s (Intento {i+1}/{max_retries})", 
                    chat_id, message_id
                )
                time.sleep(wait_seconds)
                continue
            
            r.raise_for_status()
            bot.edit_message_text("✅ ¡Procesamiento terminado en Zoom!\n⬇️ Descargando archivo MP4 a Render...", chat_id, message_id)
            with open(file_path, 'wb') as f:
                for chunk in r.iter_content(chunk_size=8192):
                    f.write(chunk)
            return True
            
    raise Exception("Timeout esperando a que Zoom procese el video.")

def process_auto_upload(object_data):
    if not ADMIN_CHAT_ID: return
    
    raw_uuid = object_data.get('uuid')
    topic = object_data.get('topic', 'Zoom Recording')
    
    try:
        uuid_safe = urllib.parse.quote(urllib.parse.quote(raw_uuid, safe=''), safe='')
        participantes = get_participants(uuid_safe)
        
        msg = bot.send_message(ADMIN_CHAT_ID, f"🔄 *Grabación Detectada (Auto)*\nIniciando proceso para: {topic}\n👥 Participantes totales: {participantes}", parse_mode="Markdown")
        chat_id = msg.chat.id
        msg_id = msg.message_id
        
        token = get_zoom_token()
        headers = {"Authorization": f"Bearer {token}"}
        url = f"https://api.zoom.us/v2/meetings/{uuid_safe}/recordings"
        r = requests.get(url, headers=headers)
        r.raise_for_status()
        data = r.json()
        
        recording_files = data.get('recording_files', [])
        mp4_files = []
        
        for f in recording_files:
            if f.get('file_type') == 'MP4':
                try:
                    start = datetime.strptime(f.get('recording_start', ''), "%Y-%m-%dT%H:%M:%SZ")
                    end = datetime.strptime(f.get('recording_end', ''), "%Y-%m-%dT%H:%M:%SZ")
                    if (end - start).total_seconds() >= 1:
                        mp4_files.append(f)
                except:
                    mp4_files.append(f)
                    
        mp4_files.sort(key=lambda x: x.get('recording_start', ''))
        
        if not mp4_files:
            bot.edit_message_text("❌ No hay archivo MP4 válido o mayor a 1 segundo para esta reunión.", chat_id, msg_id)
            return
            
        service = get_youtube_service()
        uploaded_links = []
        
        for index, mp4_file in enumerate(mp4_files):
            download_url = mp4_file['download_url']
            file_path = f"/tmp/auto_{uuid_safe}_{index}.mp4"
            part_topic = topic
            if len(mp4_files) > 1:
                part_topic = f"{topic} - Parte {index + 1}"
            
            download_with_retry(download_url, file_path, chat_id, msg_id)
            bot.edit_message_text(f"🚀 Subiendo a YouTube: {part_topic}...\nProgreso: 0%", chat_id, msg_id)
            
            body = {
                'snippet': {'title': part_topic, 'categoryId': '22'},
                'status': {'privacyStatus': 'unlisted', 'selfDeclaredMadeForKids': False}
            }
            media = MediaFileUpload(file_path, chunksize=256*1024, resumable=True)
            request_yt = service.videos().insert(part='snippet,status', body=body, media_body=media)
            
            response = None
            last_progress = 0
            while response is None:
                status, response = request_yt.next_chunk()
                if status:
                    current_progress = int(status.progress() * 100)
                    if current_progress - last_progress >= 10:
                        try:
                            bot.edit_message_text(f"🚀 Subiendo a YouTube: {part_topic}...\nProgreso: {current_progress}% ⏳", chat_id, msg_id)
                            last_progress = current_progress
                        except:
                            pass
            
            video_id = response.get('id')
            os.remove(file_path)
            uploaded_links.append(f"https://youtu.be/{video_id}")
            
        final_text = "✅ Subida Automática Exitosa\n" + "\n".join(uploaded_links)
        bot.edit_message_text(final_text, chat_id, msg_id)
        
    except Exception as e:
        bot.send_message(ADMIN_CHAT_ID, f"❌ Error en subida automática: {str(e)}")

def menu_principal_kb():
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("📽 Cloud Recordings", callback_data="list_events"),
        types.InlineKeyboardButton("📊 Estado YouTube", callback_data="yt_status"),
        types.InlineKeyboardButton("🧪 Test Upload", callback_data="test_run"),
        types.InlineKeyboardButton("⚙️ Config Sistema", callback_data="zoom_config")
    )
    return markup

@bot.message_handler(commands=['start'])
def command_start(message):
    bot.send_message(message.chat.id, "💎 *Panel VirusNTO*", reply_markup=menu_principal_kb(), parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: call.data == "main_menu")
def back_main(call):
    bot.edit_message_text("💎 *Panel VirusNTO*", call.message.chat.id, call.message.message_id, reply_markup=menu_principal_kb(), parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: call.data == "zoom_config")
def zoom_config(call):
    status_account = "✅" if ZOOM_ACCOUNT_ID else "❌"
    status_client = "✅" if ZOOM_CLIENT_ID else "❌"
    status_secret = "✅" if ZOOM_CLIENT_SECRET else "❌"
    status_wh = "✅" if ZOOM_WEBHOOK_SECRET else "❌"
    status_admin = "✅" if ADMIN_CHAT_ID else "❌"
    
    texto = f"⚙️ *Configuración de Sistema*\n\nAccount ID: {status_account}\nClient ID: {status_client}\nClient Secret: {status_secret}\nWebhook Secret: {status_wh}\nAdmin Chat ID: {status_admin}\n"
    
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("⬅️ Volver", callback_data="main_menu"))
    bot.edit_message_text(texto, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: call.data == "yt_status")
def yt_status(call):
    status = "Conectado ✅" if GOOGLE_TOKEN else "Desconectado ❌"
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("⬅️ Volver", callback_data="main_menu"))
    bot.edit_message_text(f"📊 *Estado YouTube*\nToken: {status}", call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: call.data == "list_events")
def list_events(call):
    bot.edit_message_text("🔍 Consultando Zoom...", call.message.chat.id, call.message.message_id)
    try:
        token = get_zoom_token()
        headers = {"Authorization": f"Bearer {token}"}
        
        hoy = datetime.now()
        hace_un_mes = hoy - timedelta(days=30)
        fecha_to = hoy.strftime('%Y-%m-%d')
        fecha_from = hace_un_mes.strftime('%Y-%m-%d')
        
        url = f"https://api.zoom.us/v2/users/me/recordings?from={fecha_from}&to={fecha_to}"
        r = requests.get(url, headers=headers)
        meetings = r.json().get('meetings', [])
        
        meetings = [m for m in meetings if m.get('duration', 0) >= 1]
        meetings.sort(key=lambda x: x.get('start_time', ''))

        markup = types.InlineKeyboardMarkup()
        if meetings:
            for m in meetings[:10]:
                uuid_safe = urllib.parse.quote(urllib.parse.quote(m['uuid'], safe=''), safe='')
                markup.add(types.InlineKeyboardButton(f"🎬 {m['topic']}", callback_data=f"detail_{uuid_safe}"))
        else:
            markup.add(types.InlineKeyboardButton("No hay grabaciones válidas", callback_data="none"))
        
        markup.add(types.InlineKeyboardButton("⬅️ Volver", callback_data="main_menu"))
        bot.edit_message_text("📁 Grabaciones en la Nube (Orden Cronológico):", call.message.chat.id, call.message.message_id, reply_markup=markup)
    except Exception as e:
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("⬅️ Volver", callback_data="main_menu"))
        bot.edit_message_text(f"❌ Error conectando a Zoom: {e}", call.message.chat.id, call.message.message_id, reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("detail_"))
def upload_real_video(call):
    uuid = call.data.split("_", 1)[1]
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("⬅️ Volver", callback_data="list_events"))
    
    try:
        bot.edit_message_text("🔍 Obteniendo enlaces de descarga...", call.message.chat.id, call.message.message_id)
        
        token = get_zoom_token()
        headers = {"Authorization": f"Bearer {token}"}
        url = f"https://api.zoom.us/v2/meetings/{uuid}/recordings"
        r = requests.get(url, headers=headers)
        r.raise_for_status()
        data = r.json()
        
        recording_files = data.get('recording_files', [])
        mp4_files = []
        
        for f in recording_files:
            if f.get('file_type') == 'MP4':
                try:
                    start = datetime.strptime(f.get('recording_start', ''), "%Y-%m-%dT%H:%M:%SZ")
                    end = datetime.strptime(f.get('recording_end', ''), "%Y-%m-%dT%H:%M:%SZ")
                    if (end - start).total_seconds() >= 1:
                        mp4_files.append(f)
                except:
                    mp4_files.append(f)
                    
        mp4_files.sort(key=lambda x: x.get('recording_start', ''))
        
        if not mp4_files:
            bot.edit_message_text("❌ No hay archivo MP4 válido o mayor a 1 segundo para esta reunión.", call.message.chat.id, call.message.message_id, reply_markup=markup)
            return
            
        service = get_youtube_service()
        uploaded_links = []
        
        for index, mp4_file in enumerate(mp4_files):
            download_url = mp4_file['download_url']
            file_path = f"/tmp/{uuid}_{index}.mp4"
            topic = data.get('topic', 'Zoom Recording')
            if len(mp4_files) > 1:
                topic = f"{topic} - Parte {index + 1}"
            
            download_with_retry(download_url, file_path, call.message.chat.id, call.message.message_id)
            
            bot.edit_message_text(f"🚀 Subiendo a YouTube: {topic}...\nProgreso: 0%", call.message.chat.id, call.message.message_id)
            
            body = {
                'snippet': {'title': topic, 'categoryId': '22'},
                'status': {'privacyStatus': 'unlisted', 'selfDeclaredMadeForKids': False}
            }
            media = MediaFileUpload(file_path, chunksize=256*1024, resumable=True)
            request_yt = service.videos().insert(part='snippet,status', body=body, media_body=media)
            
            response = None
            last_progress = 0
            while response is None:
                status, response = request_yt.next_chunk()
                if status:
                    current_progress = int(status.progress() * 100)
                    if current_progress - last_progress >= 10:
                        try:
                            bot.edit_message_text(f"🚀 Subiendo a YouTube: {topic}...\nProgreso: {current_progress}% ⏳", call.message.chat.id, call.message.message_id)
                            last_progress = current_progress
                        except:
                            pass
                
            video_id = response.get('id')
            os.remove(file_path)
            uploaded_links.append(f"https://youtu.be/{video_id}")
        
        final_text = "✅ Subida Exitosa\n" + "\n".join(uploaded_links)
        bot.edit_message_text(final_text, call.message.chat.id, call.message.message_id, reply_markup=markup)
        
    except Exception as e:
        bot.edit_message_text(f"❌ Error general: {str(e)}", call.message.chat.id, call.message.message_id, reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data == "test_run")
def test_run(call):
    bot.edit_message_text("⏳ Descargando video de prueba...", call.message.chat.id, call.message.message_id)
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("⬅️ Volver", callback_data="main_menu"))
    
    try:
        url = "https://www.w3schools.com/html/mov_bbb.mp4"
        file_path = "/tmp/test.mp4"
        with requests.get(url, stream=True) as r:
            r.raise_for_status()
            with open(file_path, 'wb') as f:
                for chunk in r.iter_content(chunk_size=8192):
                    f.write(chunk)
                    
        bot.edit_message_text("🚀 Subiendo video a YouTube...\nProgreso: 0%", call.message.chat.id, call.message.message_id)
        
        service = get_youtube_service()
        body = {
            'snippet': {'title': 'Test Upload VirusNTO', 'categoryId': '22'},
            'status': {'privacyStatus': 'private', 'selfDeclaredMadeForKids': False}
        }
        media = MediaFileUpload(file_path, chunksize=256*1024, resumable=True)
        request_yt = service.videos().insert(part='snippet,status', body=body, media_body=media)
        
        response = None
        last_progress = 0
        while response is None:
            status, response = request_yt.next_chunk()
            if status:
                current_progress = int(status.progress() * 100)
                if current_progress - last_progress >= 10:
                    try:
                        bot.edit_message_text(f"🚀 Subiendo video a YouTube...\nProgreso: {current_progress}% ⏳", call.message.chat.id, call.message.message_id)
                        last_progress = current_progress
                    except:
                        pass
            
        video_id = response.get('id')
        os.remove(file_path)
        
        bot.edit_message_text(f"✅ Test Exitoso\nEl video se ha subido como Privado.\nEnlace: https://youtu.be/{video_id}", call.message.chat.id, call.message.message_id, reply_markup=markup)
        
    except Exception as e:
        bot.edit_message_text(f"❌ Error en la subida: {str(e)}", call.message.chat.id, call.message.message_id, reply_markup=markup)

@app.route('/zoom_webhook', methods=['POST'])
def zoom_webhook():
    data = request.json
    event = data.get('event')
    
    if event == 'endpoint.url_validation':
        secret = ZOOM_WEBHOOK_SECRET or ""
        plain_token = data['payload']['plainToken']
        hashed_token = hmac.new(
            secret.encode('utf-8'), 
            plain_token.encode('utf-8'), 
            hashlib.sha256
        ).hexdigest()
        return jsonify({"plainToken": plain_token, "encryptedToken": hashed_token}), 200
        
    if event == 'meeting.started':
        payload = data.get('payload', {})
        object_data = payload.get('object', {})
        topic = object_data.get('topic', 'Reunión de Zoom')
        if ADMIN_CHAT_ID:
            bot.send_message(ADMIN_CHAT_ID, f"🟢 *Reunión Iniciada*\nLa reunión '{topic}' acaba de comenzar.", parse_mode="Markdown")

    if event == 'recording.stopped':
        payload = data.get('payload', {})
        object_data = payload.get('object', {})
        topic = object_data.get('topic', 'Zoom Recording')
        raw_uuid = object_data.get('uuid', '')
        uuid_safe = urllib.parse.quote(urllib.parse.quote(raw_uuid, safe=''), safe='')
        participantes = get_participants(uuid_safe)
        
        if ADMIN_CHAT_ID:
            bot.send_message(ADMIN_CHAT_ID, f"⏳ *Grabación Detenida*\nEl video '{topic}' se está procesando en Zoom. Te avisaré cuando esté listo para subir.\n👥 Participantes totales: {participantes}", parse_mode="Markdown")
            
    if event == 'recording.completed':
        payload = data.get('payload', {})
        object_data = payload.get('object', {})
        threading.Thread(target=process_auto_upload, args=(object_data,)).start()
        
    return "OK", 200

@app.route('/health')
def health(): return "OK", 200

def run_flask(): app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))

if __name__ == "__main__":
    threading.Thread(target=run_flask, daemon=True).start()
    try:
        bot.delete_webhook()
        time.sleep(1)
    except: pass
    bot.infinity_polling(timeout=60, allowed_updates=["message", "callback_query"])
