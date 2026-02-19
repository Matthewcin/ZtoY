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

# Configuración
TOKEN = os.getenv("TELEGRAM_TOKEN")
GOOGLE_TOKEN = os.environ.get('GOOGLE_TOKEN_JSON')
ZOOM_ACCOUNT_ID = os.getenv("ZOOM_ACCOUNT_ID")
ZOOM_CLIENT_ID = os.getenv("ZOOM_CLIENT_ID")
ZOOM_CLIENT_SECRET = os.getenv("ZOOM_CLIENT_SECRET")

bot = telebot.TeleBot(TOKEN)
app = Flask(__name__)

# Teclados
def menu_principal_kb():
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("📽 Cloud Recordings", callback_data="list_events"),
        types.InlineKeyboardButton("📊 Estado YouTube", callback_data="yt_status"),
        types.InlineKeyboardButton("🧪 Test Upload", callback_data="test_run"),
        types.InlineKeyboardButton("⚙️ Config Zoom", callback_data="zoom_config")
    )
    return markup

# Handlers
@bot.message_handler(commands=['start'])
def command_start(message):
    bot.send_message(message.chat.id, "💎 **Panel VirusNTO**", reply_markup=menu_principal_kb(), parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: call.data == "main_menu")
def back_main(call):
    bot.edit_message_text("💎 **Panel VirusNTO**", call.message.chat.id, call.message.message_id, reply_markup=menu_principal_kb(), parse_mode="Markdown")

# NUEVO: Handler para Config Zoom
@bot.callback_query_handler(func=lambda call: call.data == "zoom_config")
def zoom_config(call):
    # Verificamos si las variables existen en Render
    status_account = "✅" if ZOOM_ACCOUNT_ID else "❌"
    status_client = "✅" if ZOOM_CLIENT_ID else "❌"
    status_secret = "✅" if ZOOM_CLIENT_SECRET else "❌"
    
    texto = (
        "⚙️ **Configuración de Zoom**\n\n"
        f"Account ID: {status_account}\n"
        f"Client ID: {status_client}\n"
        f"Client Secret: {status_secret}\n\n"
        "Asegúrate de tener estos valores en las variables de entorno de Render."
    )
    
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("⬅️ Volver", callback_data="main_menu"))
    bot.edit_message_text(texto, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")

# Handlers de navegación ya existentes
@bot.callback_query_handler(func=lambda call: call.data == "yt_status")
def yt_status(call):
    status = "Conectado ✅" if GOOGLE_TOKEN else "Desconectado ❌"
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("⬅️ Volver", callback_data="main_menu"))
    bot.edit_message_text(f"📊 **Estado YouTube**\nToken: {status}", call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")

@app.route('/health')
def health(): return "OK", 200

def run_flask(): app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))

if __name__ == "__main__":
    threading.Thread(target=run_flask, daemon=True).start()
    try:
        bot.delete_webhook()
        time.sleep(1)
    except: pass
    bot.infinity_polling()
