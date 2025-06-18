import telebot
from telebot import types
from rembg import remove
from PIL import Image
from io import BytesIO
import logging
from flask import Flask
from threading import Thread
import os




# === Flask для UptimeRobot ===

app = Flask('')


@app.route('/')
def home():
    return "Я жив!"


def run():
    app.run(host='0.0.0.0', port=3000)


def keep_alive():
    t = Thread(target=run)
    t.start()


keep_alive()


TOKEN = '7560565832:AAFQXWb1QWbyg3kAh056pFTUML3yS9xLbrA'
bot = telebot.TeleBot(TOKEN)
ALLOWED_USERS = [5644397480, 796365934]
user_images = {}
user_states = {}
global_background = None


@bot.message_handler(commands=['start'])
def start(msg):
    if msg.from_user.id not in ALLOWED_USERS:
        return bot.reply_to(msg, "⛔️ У тебя нет доступа.")
    bot.send_message(msg.chat.id,
                     "👋 Добро пожаловать!\n\n"
                     "Отправь фото с объектом (можно несколько подряд), и я наложу их на фон.\n"
                     "Заверши отправку фото командой /done\n"
                     "Фон устанавливается через /setbg")


@bot.message_handler(commands=['setbg'])
def set_background_start(msg):
    if msg.from_user.id not in ALLOWED_USERS:
        return bot.reply_to(msg, "⛔️ Нет доступа.")
    bot.send_message(msg.chat.id, "📸 Отправь изображение для фона.")
    user_images[msg.chat.id] = {'awaiting_bg': True}


@bot.message_handler(commands=['done'])
def finish_upload(msg):
    chat_id = msg.chat.id

    if chat_id not in user_images or not user_images[chat_id].get('photos'):
        return bot.send_message(chat_id, "❌ Сначала отправьте хотя бы одно фото.")

    bot.send_message(chat_id, "💰 Введите цену:")
    user_states[chat_id] = {
        'step': 'price',
        'images': user_images[chat_id]['photos']
    }
    user_images.pop(chat_id)


@bot.message_handler(content_types=['photo'])
def handle_photo(msg):
    chat_id = msg.chat.id
    user_id = msg.from_user.id

    if user_id not in ALLOWED_USERS:
        return bot.reply_to(msg, "⛔️ У тебя нет доступа.")

    file_info = bot.get_file(msg.photo[-1].file_id)
    downloaded_file = bot.download_file(file_info.file_path)
    image = Image.open(BytesIO(downloaded_file)).convert("RGBA")

    if chat_id in user_images and user_images[chat_id].get('awaiting_bg'):
        global global_background
        global_background = image
        user_images.pop(chat_id)
        return bot.send_message(chat_id, "✅ Фон успешно установлен.")

    if global_background is None:
        return bot.send_message(chat_id, "⚠️ Сначала установи фон командой /setbg")

    bot.send_message(chat_id, "🛠 Обрабатываю фото...")

    buffered = BytesIO()
    image.save(buffered, format="PNG")
    no_bg = remove(buffered.getvalue())
    object_no_bg = Image.open(BytesIO(no_bg)).convert("RGBA")

    bg = global_background.copy()
    bg_w, bg_h = bg.size
    obj_w, obj_h = object_no_bg.size
    scale = min((bg_w * 0.7) / obj_w, (bg_h * 0.7) / obj_h)
    new_size = (int(obj_w * scale), int(obj_h * scale))
    object_resized = object_no_bg.resize(new_size, Image.LANCZOS)
    pos = ((bg_w - new_size[0]) // 2, (bg_h - new_size[1]) // 2)
    bg.paste(object_resized, pos, object_resized)

    output = BytesIO()
    bg.save(output, format="PNG")
    output.seek(0)

    if chat_id not in user_images:
        user_images[chat_id] = {'photos': []}
    if 'photos' not in user_images[chat_id]:
        user_images[chat_id]['photos'] = []

    user_images[chat_id]['photos'].append(output)
    bot.send_message(chat_id, "📥 Фото добавлено. Отправь следующее или напиши /done")


@bot.message_handler(content_types=['text'])
def handle_text(msg):
    chat_id = msg.chat.id

    if chat_id not in user_states:
        return

    state = user_states[chat_id]

    if state['step'] == 'price':
        state['price'] = msg.text
        state['step'] = 'category'
        bot.send_message(chat_id, "🏷 Введите категорию (например, #обувь):")

    elif state['step'] == 'category':
        state['category'] = msg.text
        state['step'] = 'brand'
        bot.send_message(chat_id, "🧵 Введите бренд:")

    elif state['step'] == 'brand':
        state['brand'] = msg.text
        state['step'] = 'size'
        bot.send_message(chat_id, "📏 Введите размеры (например, S, M, 40-44):")

    elif state['step'] == 'size':
        state['size'] = msg.text
        state['step'] = 'color'
        bot.send_message(chat_id, "📏 Введите цвета:")

    elif state['step'] == 'color':
        state['color'] = msg.text

        caption = (
            f"🖤 <b>𝗠𝗢𝗡𝗩𝗢𝗜𝗥</b> | <i>Эстетика в каждой детали</i>\n\n"
            f"✨ <b>Люксовое качество</b>. Отборные модели, продуманные до мелочей.\n\n"
            f"💸 <b>Цена:</b> <code>{state['price']}</code>\n"
            f"🏷 <b>Категория:</b> {state['category']}\n"
            f"👔 <b>Бренд:</b> {state['brand']}\n"
            f"📏 <b>Размеры:</b> {state['size']}\n"
            f"🎨 <b>Цвет:</b> {state.get('color', '—')}\n\n"
            f"🚚 <b>Карго:</b> <i>7–11 дней по Узбекистану</i>\n"
            f"📦 <i>Ограниченный тираж. Успей оформить до распродажи!</i>"
        )

        media_group = []
        images = state['images']
        for i, img in enumerate(images):
            img.seek(0)
            media = telebot.types.InputMediaPhoto(img, caption=caption if i == 0 else None, parse_mode='HTML')
            media_group.append(media)

        bot.send_media_group(chat_id, media_group)
        user_states.pop(chat_id)


bot.infinity_polling(
    timeout=15,
    long_polling_timeout=10,
    skip_pending=True
)