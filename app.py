import os
import time
import telebot
import threading
import requests
import json
from flask import Flask
from telebot import types
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials

TOKEN = os.getenv("TELEGRAM_TOKEN")
GOOGLE_TOKEN = os.environ.get('GOOGLE_TOKEN_JSON')
ZOOM_ACCOUNT_ID = os.getenv("ZOOM_ACCOUNT_ID")
ZOOM_CLIENT_ID = os.getenv("ZOOM_CLIENT_ID")
ZOOM_CLIENT_SECRET = os.getenv("ZOOM_CLIENT_SECRET")

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
    bot.send_message(message.chat.id, "💎 **Panel VirusNTO**", reply_markup=menu_principal_kb(), parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: call.data == "main_menu")
def back_main(call):
    bot.edit_message_text("💎 **Panel VirusNTO**", call.message.chat.id, call.message.message_id, reply_markup=menu_principal_kb(), parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: call.data == "zoom_config")
def zoom_config(call):
    status_account = "✅" if ZOOM_ACCOUNT_ID else "❌"
    status_client = "✅" if ZOOM_CLIENT_ID else "❌"
    status_secret = "✅" if ZOOM_CLIENT_SECRET else "❌"
    
    texto = (
        "⚙️ **Configuración de Zoom**\n\n"
        f"Account ID: {status_account}\n"
        f"Client ID: {status_client}\n"
        f"Client Secret: {status_secret}\n"
    )
    
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("⬅️ Volver", callback_data="main_menu"))
    bot.edit_message_text(texto, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: call.data == "yt_status")
def yt_status(call):
    status = "Conectado ✅" if GOOGLE_TOKEN else "Desconectado ❌"
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("⬅️ Volver", callback_data="main_menu"))
    bot.edit_message_text(f"📊 **Estado YouTube**\nToken: {status}", call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: call.data == "list_events")
def list_events(call):
    bot.edit_message_text("🔍 Consultando Zoom...", call.message.chat.id, call.message.message_id)
    try:
        token = get_zoom_token()
        headers = {"Authorization": f"Bearer {token}"}
        r = requests.get("https://api.zoom.us/v2/users/me/recordings", headers=headers)
        meetings = r.json().get('meetings', [])

        markup = types.InlineKeyboardMarkup()
        if meetings:
            for m in meetings[:5]:
                markup.add(types.InlineKeyboardButton(f"🎬 {m['topic']}", callback_data=f"detail_{m['id']}"))
        else:
            markup.add(types.InlineKeyboardButton("No hay grabaciones", callback_data="none"))
        
        markup.add(types.InlineKeyboardButton("⬅️ Volver", callback_data="main_menu"))
        bot.edit_message_text("📁 **Grabaciones en la Nube:**", call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")
    except Exception as e:
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("⬅️ Volver", callback_data="main_menu"))
        bot.edit_message_text(f"❌ Error conectando a Zoom: {e}", call.message.chat.id, call.message.message_id, reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data == "test_run")
def test_run(call):
    bot.answer_callback_query(call.id, "Iniciando test de API...")
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("⬅️ Volver", callback_data="main_menu"))
    try:
        service = get_youtube_service()
        channels = service.channels().list(part="snippet", mine=True).execute()
        canal = channels['items'][0]['snippet']['title']
        bot.edit_message_text(f"✅ Conectado a YouTube\nCanal validado: {canal}", call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")
    except Exception as e:
        bot.edit_message_text(f"❌ Error con Google: {str(e)}", call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")

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
