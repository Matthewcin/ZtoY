import os
import time
import telebot
import threading
from flask import Flask
from telebot import types

# 1. Configuración y Carga de variables
TOKEN = os.getenv("TELEGRAM_TOKEN")
bot = telebot.TeleBot(TOKEN)
app = Flask(__name__)

# 2. Servidor Web para Keep Alive (UptimeRobot)
@app.route('/health')
def health():
    return "OK", 200

@app.route('/')
def index():
    return "Servidor Eventos Vivo", 200

def run_flask():
    # Render usa el puerto 10000 por defecto
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))

# 3. Teclados (Keyboards)
def menu_principal_kb():
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("📅 Ver Eventos", callback_data="list_events"))
    return markup

def eventos_kb():
    markup = types.InlineKeyboardMarkup()
    # Aquí irán los videos reales de Zoom luego
    markup.add(types.InlineKeyboardButton("🎬 Clase Reciente", callback_data="detail_1"))
    markup.add(types.InlineKeyboardButton("⬅️ Volver", callback_data="main_menu"))
    return markup

# 4. Handlers (Lógica del Bot)
@bot.message_handler(commands=['start'])
def command_start(message):
    nombre = message.from_user.first_name
    bot.send_message(
        message.chat.id,
        f"🛠 **Panel VirusNTO**\nHola {nombre}, sistema de Eventos listo.",
        reply_markup=menu_principal_kb(),
        parse_mode="Markdown"
    )

@bot.callback_query_handler(func=lambda call: call.data == "main_menu")
def back_main(call):
    bot.edit_message_text(
        "💎 **Panel VirusNTO**\nSelecciona opción:",
        call.message.chat.id,
        call.message.message_id,
        reply_markup=menu_principal_kb(),
        parse_mode="Markdown"
    )

@bot.callback_query_handler(func=lambda call: call.data == "list_events")
def list_events(call):
    bot.edit_message_text(
        "📅 **Lista de Eventos**\nSelecciona una grabación:",
        call.message.chat.id,
        call.message.message_id,
        reply_markup=eventos_kb(),
        parse_mode="Markdown"
    )

# 5. Loop Principal (Blindado)
def main_loop():
    # Iniciamos Flask en un hilo separado para el Keep Alive
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()

    print("🤖 Bot Iniciado...")
    
    # TRUCO: Borrar webhook previo para que el polling funcione
    try:
        bot.delete_webhook()
        time.sleep(1)
    except Exception as e:
        print(f"⚠️ Webhook cleanup: {e}")

    while True:
        try:
            print("🔄 Conectando a Telegram via Polling...")
            bot.infinity_polling(timeout=60, long_polling_timeout=60, allowed_updates=["message", "callback_query"])
        except Exception as e:
            print(f"⚠️ Error en polling: {e}")
            time.sleep(5)

if __name__ == "__main__":
    main_loop()
