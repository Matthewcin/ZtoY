import os
import time
import telebot
import threading
import requests
import json
from datetime import datetime, timedelta
from flask import Flask
from telebot import types
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from googleapiclient.http import MediaFileUpload

TOKEN = os.getenv("TELEGRAM_TOKEN")
GOOGLE_TOKEN = os.environ.get('GOOGLE_TOKEN_JSON')
ZOOM_ACCOUNT_ID = os.getenv("ZOOM_ACCOUNT_ID")
ZOOM_CLIENT_ID = os.getenv("ZOOM_CLIENT_ID")
ZOOM_CLIENT_SECRET = os.getenv("ZOOM_CLIENT_SECRET")
ZOOM_USER = os.getenv("ZOOM_USER", "me")

bot = telebot.TeleBot(TOKEN)
app = Flask(__name__)

global_chat_id = None
notified_recordings = set()
processed_videos = set()

def get_zoom_token():
    url = f"https://zoom.us/oauth/token?grant_type=account_credentials&account_id={ZOOM_ACCOUNT_ID}"
    r = requests.post(url, auth=(ZOOM_CLIENT_ID, ZOOM_CLIENT_SECRET))
    return r.json().get('access_token')

def get_youtube_service():
    info = json.loads(GOOGLE_TOKEN)
    creds = Credentials.from_authorized_user_info(info)
    return build('youtube', 'v3', credentials=creds)

def download_and_upload(download_url, title):
    token = get_zoom_token()
    headers = {"Authorization": f"Bearer {token}"}
    r = requests.get(download_url, headers=headers, stream=True)
    r.raise_for_status()
    
    file_path = f"/tmp/{title.replace(' ', '_').replace('/', '_')}.mp4"
    with open(file_path, 'wb') as f:
        for chunk in r.iter_content(chunk_size=8192):
            f.write(chunk)
            
    service = get_youtube_service()
    body = {
        'snippet': {'title': title, 'categoryId': '22'},
        'status': {'privacyStatus': 'unlisted', 'selfDeclaredMadeForKids': False}
    }
    media = MediaFileUpload(file_path, chunksize=-1, resumable=True)
    request_yt = service.videos().insert(part='snippet,status', body=body, media_body=media)
    
    response = None
    while response is None:
        status, response = request_yt.next_chunk()
        
    video_id = response.get('id')
    os.remove(file_path)
    return video_id

def auto_monitor():
    global global_chat_id
    while True:
        time.sleep(60)
        if not global_chat_id:
            continue
            
        try:
            token = get_zoom_token()
            headers = {"Authorization": f"Bearer {token}"}
            hoy = datetime.now()
            fecha_from = (hoy - timedelta(days=1)).strftime('%Y-%m-%d')
            fecha_to = hoy.strftime('%Y-%m-%d')
            
            url = f"https://api.zoom.us/v2/users/{ZOOM_USER}/recordings?from={fecha_from}&to={fecha_to}"
            r = requests.get(url, headers=headers)
            meetings = r.json().get('meetings', [])
            
            for m in meetings:
                m_id = m['uuid']
                topic = m['topic']
                files = m.get('recording_files', [])
                mp4_files = [f for f in files if f.get('file_type') == 'MP4']
                
                if m_id not in notified_recordings:
                    bot.send_message(global_chat_id, f"🔴 Se esta grabando {topic}!")
                    notified_recordings.add(m_id)
                
                all_completed = all(f.get('status') == 'completed' for f in mp4_files) if mp4_files else False
                
                if mp4_files and all_completed and m_id not in processed_videos:
                    processed_videos.add(m_id)
                    bot.send_message(global_chat_id, f"✅ Recording Complete: {topic}\nIniciando subida a YouTube (Unlisted)...")
                    
                    try:
                        download_url = mp4_files[0]['download_url']
                        video_id = download_and_upload(download_url, topic)
                        bot.send_message(global_chat_id, f"🚀 Subida Exitosa: {topic}\nEnlace: https://youtu.be/{video_id}")
                    except Exception as e:
                        bot.send_message(global_chat_id, f"❌ Error subiendo {topic}: {str(e)}")
                        processed_videos.remove(m_id)
        except:
            pass

def menu_principal_kb():
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("📽 Cloud Recordings", callback_data="list_events"),
        types.InlineKeyboardButton("📊 Estado YouTube", callback_data="yt_status"),
        types.InlineKeyboardButton("🧪 Test Upload", callback_data="test_run"),
        types.InlineKeyboardButton("⚙️ Config Zoom", callback_data="zoom_config")
    )
    return markup

@bot.message_handler(commands=['start'])
def command_start(message):
    global global_chat_id
    global_chat_id = message.chat.id
    bot.send_message(message.chat.id, "💎 *Panel Zoom to Youtube*", reply_markup=menu_principal_kb(), parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: call.data == "main_menu")
def back_main(call):
    global global_chat_id
    global_chat_id = call.message.chat.id
    bot.edit_message_text("💎 *Panel Zoom to Youtube*", call.message.chat.id, call.message.message_id, reply_markup=menu_principal_kb(), parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: call.data == "zoom_config")
def zoom_config(call):
    status_account = "✅" if ZOOM_ACCOUNT_ID else "❌"
    status_client = "✅" if ZOOM_CLIENT_ID else "❌"
    status_secret = "✅" if ZOOM_CLIENT_SECRET else "❌"
    
    texto = f"⚙️ *Configuración de Zoom*\n\nAccount ID: {status_account}\nClient ID: {status_client}\nClient Secret: {status_secret}\n"
    
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
        
        url = f"https://api.zoom.us/v2/users/{ZOOM_USER}/recordings?from={fecha_from}&to={fecha_to}"
        r = requests.get(url, headers=headers)
        meetings = r.json().get('meetings', [])

        markup = types.InlineKeyboardMarkup()
        if meetings:
            for m in meetings[:5]:
                markup.add(types.InlineKeyboardButton(f"🎬 {m['topic']}", callback_data=f"detail_{m['id']}"))
        else:
            markup.add(types.InlineKeyboardButton("No hay grabaciones", callback_data="none"))
        
        markup.add(types.InlineKeyboardButton("⬅️ Volver", callback_data="main_menu"))
        bot.edit_message_text("📁 Grabaciones en la Nube (Últimos 30 días):", call.message.chat.id, call.message.message_id, reply_markup=markup)
    except Exception as e:
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("⬅️ Volver", callback_data="main_menu"))
        bot.edit_message_text(f"❌ Error conectando a Zoom: {e}", call.message.chat.id, call.message.message_id, reply_markup=markup)

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
                    
        bot.edit_message_text("🚀 Subiendo video a YouTube...", call.message.chat.id, call.message.message_id)
        
        service = get_youtube_service()
        body = {
            'snippet': {'title': 'Test Upload by Matthew Bot', 'categoryId': '22'},
            'status': {'privacyStatus': 'unlisted', 'selfDeclaredMadeForKids': False}
        }
        media = MediaFileUpload(file_path, chunksize=-1, resumable=True)
        request_yt = service.videos().insert(part='snippet,status', body=body, media_body=media)
        
        response = None
        while response is None:
            status, response = request_yt.next_chunk()
            
        video_id = response.get('id')
        os.remove(file_path)
        
        bot.edit_message_text(f"✅ Test Exitoso\nEl video se ha subido como Unlisted.\nEnlace: https://youtu.be/{video_id}", call.message.chat.id, call.message.message_id, reply_markup=markup)
        
    except Exception as e:
        bot.edit_message_text(f"❌ Error en la subida: {str(e)}", call.message.chat.id, call.message.message_id, reply_markup=markup)

@app.route('/health')
def health(): return "OK", 200

def run_flask(): app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))

if __name__ == "__main__":
    threading.Thread(target=run_flask, daemon=True).start()
    threading.Thread(target=auto_monitor, daemon=True).start()
    try:
        bot.delete_webhook()
        time.sleep(1)
    except: pass
    bot.infinity_polling(timeout=60, allowed_updates=["message", "callback_query"])
