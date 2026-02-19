import os
import json
import requests
from flask import Flask, request, jsonify
from telebot import TeleBot, types

app = Flask(__name__)
bot = TeleBot(os.environ.get('TELEGRAM_TOKEN'))

# Variables de entorno en Render
ZOOM_ACCOUNT_ID = os.environ.get('ZOOM_ACCOUNT_ID')
ZOOM_CLIENT_ID = os.environ.get('ZOOM_CLIENT_ID')
ZOOM_CLIENT_SECRET = os.environ.get('ZOOM_CLIENT_SECRET')

def get_zoom_token():
    url = f"https://zoom.us/oauth/token?grant_type=account_credentials&account_id={ZOOM_ACCOUNT_ID}"
    auth = (ZOOM_CLIENT_ID, ZOOM_CLIENT_SECRET)
    r = requests.post(url, auth=auth)
    return r.json().get('access_token')

@bot.message_handler(commands=['start', 'videos'])
def list_videos(message):
    token = get_zoom_token()
    headers = {"Authorization": f"Bearer {token}"}
    # Obtenemos grabaciones de los últimos 7 días
    r = requests.get("https://api.zoom.us/v2/users/me/recordings", headers=headers)
    data = r.json()
    
    markup = types.InlineKeyboardMarkup()
    for meeting in data.get('meetings', []):
        btn = types.InlineKeyboardButton(
            text=f"🎬 {meeting.get('topic')}", 
            callback_data=f"vid_{meeting.get('id')}"
        )
        markup.add(btn)
    
    bot.send_message(message.chat.id, "📅 **Eventos encontrados:**", reply_markup=markup, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: True)
def callback_query(call):
    if call.data == "main_list":
        # Lógica para volver atrás editando el mensaje original
        token = get_zoom_token()
        headers = {"Authorization": f"Bearer {token}"}
        r = requests.get("https://api.zoom.us/v2/users/me/recordings", headers=headers)
        data = r.json()
        markup = types.InlineKeyboardMarkup()
        for meeting in data.get('meetings', []):
            markup.add(types.InlineKeyboardButton(text=meeting.get('topic'), callback_data=f"vid_{meeting.get('id')}"))
        
        bot.edit_message_text("📅 **Eventos encontrados:**", call.message.chat.id, call.message.message_id, reply_markup=markup)

    elif call.data.startswith("vid_"):
        meeting_id = call.data.split("_")[1]
        # Aquí buscarías el detalle del video y mostrarías el botón de subir
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🚀 Subir a YouTube", callback_data=f"up_{meeting_id}"))
        markup.add(types.InlineKeyboardButton("⬅️ Volver", callback_data="main_list"))
        
        bot.edit_message_text(f"Has seleccionado el evento: {meeting_id}\n¿Qué deseas hacer?", call.message.chat.id, call.message.message_id, reply_markup=markup)

@app.route('/' + os.environ.get('TELEGRAM_TOKEN'), methods=['POST'])
def getMessage():
    bot.process_new_updates([types.Update.de_json(request.stream.read().decode("utf-8"))])
    return "!", 200

@app.route("/")
def webhook():
    bot.remove_webhook()
    bot.set_webhook(url='https://' + request.host + '/' + os.environ.get('TELEGRAM_TOKEN'))
    return "Bot de Eventos activo", 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get('PORT', 10000)))
