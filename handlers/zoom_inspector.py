import os
import json
import requests
from datetime import datetime, timedelta
from telebot import types

def register(bot, get_zoom_token):
    @bot.callback_query_handler(func=lambda call: call.data == "raw_zoom_json")
    def send_raw_json(call):
        bot.edit_message_text("⏳ Obteniendo JSON completo de la API de Zoom...", call.message.chat.id, call.message.message_id)
        try:
            token = get_zoom_token()
            headers = {"Authorization": f"Bearer {token}"}
            
            ZOOM_USER = os.getenv("ZOOM_USER", "me")
            hoy = datetime.now()
            fecha_from = (hoy - timedelta(days=30)).strftime('%Y-%m-%d')
            fecha_to = hoy.strftime('%Y-%m-%d')
            
            url = f"https://api.zoom.us/v2/users/{ZOOM_USER}/recordings?from={fecha_from}&to={fecha_to}"
            r = requests.get(url, headers=headers)
            data = r.json()
            
            file_path = "/tmp/zoom_api_raw.json"
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4, ensure_ascii=False)
            
            with open(file_path, "rb") as doc:
                bot.send_document(call.message.chat.id, doc)
            
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("⬅️ Volver", callback_data="main_menu"))
            bot.send_message(call.message.chat.id, "💎 *Panel VirusNTO*", reply_markup=markup, parse_mode="Markdown")
            
            os.remove(file_path)
        except Exception as e:
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("⬅️ Volver", callback_data="main_menu"))
            bot.edit_message_text(f"❌ Error obteniendo JSON: {str(e)}", call.message.chat.id, call.message.message_id, reply_markup=markup)
