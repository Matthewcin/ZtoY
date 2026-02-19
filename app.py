import os
import json
import telebot
from flask import Flask, request
from telebot import types

# Variables de entorno
TOKEN_DATA = os.environ.get('GOOGLE_TOKEN_JSON')
TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN')
RENDER_URL = os.environ.get('RENDER_EXTERNAL_URL')

bot = telebot.TeleBot(TELEGRAM_TOKEN)
app = Flask(__name__)

# Generación de teclado principal
def get_main_keyboard():
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("📅 Ver Eventos", callback_data="list_events"))
    return markup

@bot.message_handler(commands=['start'])
def start(message):
    bot.send_message(
        message.chat.id, 
        "💎 **Panel VirusNTO**", 
        reply_markup=get_main_keyboard(), 
        parse_mode="Markdown"
    )

@bot.callback_query_handler(func=lambda call: True)
def handle_query(call):
    # Navegación: Volver al inicio
    if call.data == "back_home":
        bot.edit_message_text(
            "💎 **Panel VirusNTO**", 
            call.message.chat.id, 
            call.message.message_id, 
            reply_markup=get_main_keyboard(), 
            parse_mode="Markdown"
        )

    # Listar Eventos (Single Message)
    elif call.data == "list_events":
        markup = types.InlineKeyboardMarkup()
        # Aquí se integrarán los videos reales de Zoom más adelante
        markup.add(types.InlineKeyboardButton("🎬 Clase Reciente", callback_data="detail_1"))
        markup.add(types.InlineKeyboardButton("⬅️ Volver", callback_data="back_home"))
        
        bot.edit_message_text(
            "Selecciona un evento:", 
            call.message.chat.id, 
            call.message.message_id, 
            reply_markup=markup
        )

# Rutas para Render y Webhooks
@app.route('/' + TELEGRAM_TOKEN, methods=['POST'])
def getMessage():
    json_string = request.get_data().decode('utf-8')
    update = telebot.types.Update.de_json(json_string)
    bot.process_new_updates([update])
    return "!", 200

@app.route("/health")
def health():
    return "OK", 200

@app.route("/")
def index():
    bot.remove_webhook()
    bot.set_webhook(url=f"{RENDER_URL}/{TELEGRAM_TOKEN}")
    return "Bot Activo y Webhook Configurado", 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get('PORT', 10000)))
