import os
import time
import telebot
import threading
import requests
import json
from flask import Flask
from telebot import types
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google.oauth2.credentials import Credentials

# 1. Configuración de Variables
TOKEN = os.getenv("TELEGRAM_TOKEN")
GOOGLE_TOKEN = os.getenv("GOOGLE_TOKEN_JSON")
bot = telebot.TeleBot(TOKEN)
app = Flask(__name__)

# 2. Servidor Web (Keep Alive)
@app.route('/health')
def health(): return "OK", 200

@app.route('/')
def index(): return "Monitor VirusNTO Activo", 200

def run_flask():
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))

# 3. Utilidad YouTube (Subida)
def upload_test_video():
    if not GOOGLE_TOKEN: return "Error: No hay token de Google"
    try:
        info = json.loads(GOOGLE_TOKEN)
        creds = Credentials.from_authorized_user_info(info)
        youtube = build('youtube', 'v3', credentials=creds)
        
        # Aquí puedes poner un link a un mp4 pequeño de prueba o un path local si existe
        return "Simulación: Conexión con YouTube API Exitosa ✅"
    except Exception as e:
        return f"Error en API: {str(e)}"

# 4. Teclados Expandidos (Monitoreo)
def menu_principal_kb():
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("📽 Cloud Recordings", callback_data="list_events"),
        types.InlineKeyboardButton("📊 Estado YouTube", callback_data="yt_status"),
        types.InlineKeyboardButton("🧪 Test Upload", callback_data="test_run"),
        types.InlineKeyboardButton("⚙️ Config Zoom", callback_data="zoom_config")
    )
    return markup

def monitor_cloud_kb():
    markup = types.InlineKeyboardMarkup(row_width=1)
    # Estos botones se llenarán con la API de Zoom más adelante
    markup.add(
        types.InlineKeyboardButton("🔴 Grabación: Clase Yoga 19/02", callback_data="detail_1"),
        types.InlineKeyboardButton("⚪ Grabación: Workshop Python", callback_data="detail_2"),
        types.InlineKeyboardButton("⬅️ Volver al Panel", callback_data="main_menu")
    )
    return markup

# 5. Handlers
@bot.message_handler(commands=['start'])
def command_start(message):
    bot.send_message(
        message.chat.id,
        "💎 **SISTEMA DE MONITOREO VIRUSNTO**\nPanel de control de grabaciones y YouTube.",
        reply_markup=menu_principal_kb(),
        parse_mode="Markdown"
    )

@bot.callback_query_handler(func=lambda call: call.data == "main_menu")
def back_main(call):
    bot.edit_message_text(
        "💎 **Panel VirusNTO**\nSelecciona un módulo para monitorear:",
        call.message.chat.id, call.message.message_id,
        reply_markup=menu_principal_kb(), parse_mode="Markdown"
    )

@bot.callback_query_handler(func=lambda call: call.data == "list_events")
def list_events(call):
    bot.edit_message_text(
        "📁 **Cloud Recordings (Zoom)**\nGrabaciones detectadas en la nube:",
        call.message.chat.id, call.message.message_id,
        reply_markup=monitor_cloud_kb(), parse_mode="Markdown"
    )

@bot.callback_query_handler(func=lambda call: call.data == "test_run")
def test_run(call):
    bot.edit_message_text("⏳ Iniciando prueba de conexión con YouTube...", call.message.chat.id, call.message.message_id)
    resultado = upload_test_video()
    
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("⬅️ Volver", callback_data="main_menu"))
    
    bot.edit_message_text(f"🧪 **Resultado del Test:**\n{resultado}", 
                          call.message.chat.id, call.message.message_id, 
                          reply_markup=markup, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: call.data == "yt_status")
def yt_status(call):
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("⬅️ Volver", callback_data="main_menu"))
    # Aquí puedes chequear si el token ha expirado
    status = "Conectado ✅" if GOOGLE_TOKEN else "Desconectado ❌"
    bot.edit_message_text(f"📊 **Estado de YouTube:**\nCanal: Vinculado\nToken: {status}", 
                          call.message.chat.id, call.message.message_id, 
                          reply_markup=markup, parse_mode="Markdown")

# 6. Loop Principal
def main_loop():
    threading.Thread(target=run_flask, daemon=True).start()
    print("🤖 Monitor iniciado...")
    try:
        bot.delete_webhook()
        time.sleep(1)
    except: pass
    bot.infinity_polling(timeout=60)

if __name__ == "__main__":
    main_loop()
