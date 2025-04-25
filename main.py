from config import BOT_TOKEN, CHANNEL_ID, ADMINS, OWNER_ID, MODERATION_GROUP_ID
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, Message
import telebot
import uuid
import json
import os
from flask import Flask
from threading import Thread


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

import logging

logging.basicConfig(
    format='%(asctime)s %(levelname)s %(name)s %(message)s',
    level=logging.INFO
)

def safe_handler(func):
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception:
            logging.exception(f"Error in handler {func.__name__}")
            # здесь можно уведомить администратора или просто проигнорировать
    return wrapper

bot = telebot.TeleBot(BOT_TOKEN)

# Путь к папке данных внутри контейнера (Replit или другой хост)
BASE_DIR = os.path.join(os.getcwd(), 'data')
os.makedirs(BASE_DIR, exist_ok=True)


PENDING_POSTS = os.path.join(BASE_DIR, 'messages.json')
APPROVED_POSTS = os.path.join(BASE_DIR, 'approved.json')
PENDING_REPLIES = os.path.join(BASE_DIR, 'replies.json')
# USERS_FILE = os.path.join(BASE_DIR, 'users.json')
COUNTER_FILE = os.path.join(BASE_DIR, 'counter.json')
BLOCKED_FILE = os.path.join(BASE_DIR, 'blocked.json')
PENDING_MEDIA = os.path.join(BASE_DIR, 'media.json')


def save_json(path, data):
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

@bot.message_handler(commands=['user'])
def handle_user_command(message):
    try:
        args = message.text.split()
        if len(args) != 2:
            bot.reply_to(message, "Использование: /user <user_id>")
            return

        user_id = int(args[1])
        user = bot.get_chat(user_id)

        if user.username:
            link = f"https://t.me/{user.username}"
            name = f"@{user.username}"
        else:
            name = user.first_name
            if user.last_name:
                name += f" {user.last_name}"
            link = f"tg://user?id={user.id}"

        hyperlink = f'<a href="{link}">{name}</a>'
        bot.reply_to(message, f'Профиль: {hyperlink}')

    except Exception as e:
        bot.reply_to(message, f"Ошибка: {e}")
        
def save_media_json(message, item, user_id, cap, n, type):
    file_id = None
    if type == 'photo':
        file_id = message.photo[-1].file_id  # Самое большое фото
    else:
        file_id = message.video.file_id
    # user_id = str(message.from_user.id)  # ID пользователя

    # Загружаем media.json
    try:
        with open('media.json', "r", encoding="utf-8") as f:
            media_data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        media_data = {}

    # Сохраняем фото в словарь
    media_data[item] = {
        "type": type,
        "file_id": file_id,
        "user_id": user_id,
        "cap": cap,
        "number": n
    }

    # Записываем обратно в media.json только если есть изменения
    with open('media.json', "w", encoding="utf-8") as f:
        json.dump(media_data, f, ensure_ascii=False, indent=2)
    pending_media.update(media_data)


def load_json(path):
    if not os.path.exists(path):
        save_json(path, {})
        return {}
    with open(path, 'r', encoding='utf-8') as f:
        txt = f.read().strip()
    return json.loads(txt) if txt else {}


# Загрузка данных
# users = load_json(USERS_FILE)
pending_posts = load_json(PENDING_POSTS)
approved_posts = load_json(APPROVED_POSTS)
pending_replies = load_json(PENDING_REPLIES)
blocked_users = load_json(BLOCKED_FILE)
pending_media = load_json(PENDING_MEDIA)


def save_blocked():
    save_json(BLOCKED_FILE, blocked_users)


def load_counter():
    return load_json(COUNTER_FILE).get('total', 0)


def save_counter(val):
    save_json(COUNTER_FILE, {'total': val})


def is_admin(uid):
    return uid in ADMINS or uid == OWNER_ID


waiting_for_name = set()
user_reply_flow = {}

# --- /start и глубокие ссылки ---


@bot.message_handler(commands=['start'])
@safe_handler
def cmd_start(m):
    text = m.text or ""
    uid = str(m.from_user.id)
    param = text[len('/start'):].strip()
    if param.startswith('reply_'):
        orig = param[len('reply_'):]
        entry = approved_posts.get(orig)
        entry2 = pending_media.get(orig)
        print(orig)
        if entry:
            bot.send_message(
                m.chat.id,
                f"💬 Вы отвечаете на пост №{entry['number']:06}:\n{entry['text']}\n\nНапишите ответ:"
            )
            user_reply_flow[uid] = orig
        elif entry2:
            if entry2['type'] == 'photo':
                try:
                    # Получаем файл по file_id
                    file = bot.get_file(entry2['file_id'])

                    # Загружаем файл с сервера Telegram
                    # file_path = file.file_path  # Получаем путь к файлу
                    # downloaded_file = bot.download_file(
                    #     file_path)  # Скачиваем файл

                    # # Сохраняем файл на диск
                    # with open(f'{entry2["file_id"]}.jpg', 'wb') as f:
                    #     f.write(downloaded_file)

                    print(
                        f"Фото успешно загружено с file_id {entry2['file_id']}.")
                    bot.send_photo(entry2['user_id'],
                                   entry2['file_id'], caption=f"{entry2['cap']}\n\n💬Вы отвечаете на пост под номером №{entry2['number']:06}.\n\nНапишите сам ответ:")

                except Exception as e:
                    print(f"Ошибка при получении фото: {e}")
            else:
                try:
                    # Получаем файл по file_id
                    file = bot.get_file(entry2['file_id'])

                    # Загружаем файл с сервера Telegram
                    # file_path = file.file_path  # Получаем путь к файлу
                    # downloaded_file = bot.download_file(
                    #     file_path)  # Скачиваем файл

                    # # Сохраняем видео на диск
                    # with open(f'{entry2["file_id"]}.mp4', 'wb') as f:
                    #     f.write(downloaded_file)

                    print(
                        f"Видео успешно загружено с file_id {entry2['file_id']}.")

                    bot.send_video(
                        entry2['user_id'],
                        file,
                        caption=(
                            f"{entry2['cap']}\n\n"
                            f"💬 Вы отвечаете на пост под номером №{entry2['number']:06}.\n\n"
                            "Напишите сам ответ:"
                        )
                    )

                except Exception as e:
                    print(f"Ошибка при получении видео: {e}")

        else:

            bot.send_message(m.chat.id, "❗️ Оригинал не найден.")
        return

    # if uid not in users:
    #     bot.send_message(m.chat.id, "👋 Привет! Введите своё имя:")
    #     waiting_for_name.add(uid)
    # else:
    #     bot.send_message(
    #         m.chat.id, f"Привет, {users[uid]}! Отправьте анонимный пост.")

# --- вспомогательные команды ---


@bot.message_handler(commands=['id'])
@safe_handler
def cmd_id(m):
    bot.reply_to(m, f"🆔 Ваш ID: {m.from_user.id}")


@bot.message_handler(commands=['unblock'])
@safe_handler
def cmd_unblock(m):
    # Разблокировка пользователя по ID: /unblock <user_id>
    if not is_admin(m.from_user.id):
        return bot.reply_to(m, "❌ Только админ.")
    parts = m.text.split()
    if len(parts) != 2:
        return bot.reply_to(m, "Использование: /unblock <user_id>")
    uid = parts[1]
    if uid in blocked_users:
        blocked_users.pop(uid)
        save_blocked()
        bot.reply_to(m, f"✅ Пользователь {uid} разблокирован.")
    else:
        bot.reply_to(m, "⚠️ Этот пользователь не был заблокирован.")


# @bot.message_handler(commands=['name'])
# @safe_handler
# def cmd_name(m):
#     uid = str(m.from_user.id)
#     waiting_for_name.add(uid)
#     bot.send_message(m.chat.id, "✏️ Введите новое имя:")


@bot.message_handler(commands=['counter'])
@safe_handler
def cmd_counter(m):
    bot.send_message(m.chat.id, f"📊 Всего публикаций: {load_counter():06}")


@bot.message_handler(commands=['set_counter'])
@safe_handler
def cmd_reset(m):
    if m.from_user.id != OWNER_ID:
        return bot.reply_to(m, "❌ Только владелец.")
    mm = m.text.split()
    if len(mm) == 2:
        save_counter(int(mm[1]))
    else:
        bot.send_message(
            m.chat.chat_id, 'Использование: /set_counter <целое число>')
    bot.reply_to(m, f"🔄 Счётчик изменен на {mm[1]}.")

# --- основной текстовый хэндлер ---


@bot.message_handler(func=lambda m: True, content_types=['text'])
def all_text(m):
    if m.chat.type != 'private':
        return

    uid = str(m.from_user.id)

    if uid in blocked_users:
        return bot.send_message(m.chat.id, "🚫 Вы заблокированы и не можете отправлять посты или ответы.")

    if uid in user_reply_flow:
        orig = user_reply_flow.pop(uid)
        reply_id = str(uuid.uuid4())
        pending_replies[reply_id] = {'orig': orig,
                                     'text': m.text.strip(), 'from': uid}
        save_json(PENDING_REPLIES, pending_replies)

        entry = approved_posts.get(orig, {})
        num = entry.get('number', 0)
        u = m.from_user
        author_mention = f'<a href="tg://user?id={u.id}">{u.first_name}</a>'

        markup = InlineKeyboardMarkup()
        markup.row(
            InlineKeyboardButton("✅ Одобрить",
                                 callback_data=f"approve_reply:{reply_id}"),
            InlineKeyboardButton("❌ Отклонить",
                                 callback_data=f"reject_reply:{reply_id}")
        )
        markup.row(
            InlineKeyboardButton(
                "🚫 Заблокировать", callback_data=f"block_user_reply:{reply_id}"),
            InlineKeyboardButton(
                "⚠️ Убрать имя", callback_data=f"remove_name_reply:{reply_id}")
        )
        bot.send_message(
            MODERATION_GROUP_ID,
            (
                f"📨 <b>Запрос модерации ответа</b>\n\n"
                f"Ответ на пост №{num:06}:\n{entry.get('text', '')}\n\n"
                f"✉️ Текст ответа:\n{m.text}\n\n"
                f"👤 Автор ответа: {author_mention} (ID: <code>{u.id}</code>)"
            ),
            parse_mode='HTML',
            disable_web_page_preview=True,
            reply_markup=markup
        )
        return bot.send_message(m.chat.id, "🔄 Ответ отправлен на модерацию.")

    # if uid in waiting_for_name:
    #     users[uid] = m.text.strip()
    #     save_json(USERS_FILE, users)
    #     waiting_for_name.remove(uid)
    #     return bot.send_message(m.chat.id, f"✅ Ваше имя: {users[uid]}")

    # if uid not in users:
    #     return bot.send_message(m.chat.id, "❗ Сначала /start и введите имя.")

    post_id = str(uuid.uuid4())
    pending_posts[post_id] = {'text': m.text.strip(), 'from': uid}
    save_json(PENDING_POSTS, pending_posts)

    u = m.from_user
    author_mention = f'<a href="tg://user?id={u.id}">{u.first_name}</a>'

    markup = InlineKeyboardMarkup()
    markup.row(
        InlineKeyboardButton(
            "✅ Принять", callback_data=f"approve_post:{post_id}"),
        InlineKeyboardButton("❌ Отклонить",
                             callback_data=f"reject_post:{post_id}")
    )
    markup.row(
        InlineKeyboardButton(
            "🚫 Заблокировать", callback_data=f"block_user_post:{post_id}"),
        InlineKeyboardButton(
            "⚠️ Убрать имя", callback_data=f"remove_name_post:{post_id}")
    )
    bot.send_message(
        MODERATION_GROUP_ID,
        (
            f"📬 <b>Запрос модерации поста</b>\n\n"
            f"✉️ Текст поста:\n{m.text}\n\n"
            f"👤 Автор поста: {author_mention} (ID: <code>{u.id}</code>)"
        ),
        parse_mode='HTML',
        disable_web_page_preview=True,
        reply_markup=markup
    )
    bot.send_message(m.chat.id, "✅ Пост отправлен на модерацию.")

# --- обработка медиа (фото/видео) ---


@bot.message_handler(content_types=['photo', 'video'])
def handle_media(m: Message):
    if m.chat.type != 'private':
        return
    uid = str(m.from_user.id)
    if uid in blocked_users:
        return bot.send_message(m.chat.id, "🚫 Вы заблокированы и не можете отправлять медиа.")
    # if uid not in users:
    #     return bot.send_message(m.chat.id, "❗ Сначала /start и введите имя.")

    file = m.photo[-1] if m.content_type == 'photo' else m.video
    if hasattr(file, 'file_size') and file.file_size > 400 * 1024 * 1024:
        return bot.send_message(m.chat.id, "⚠️ Медиа превышает 400MB.")

    media_id = str(uuid.uuid4())
    pending_media[media_id] = {
        'file_id': file.file_id,
        'type': m.content_type,
        'caption': getattr(m, 'caption', '') or '',
        'from': uid
    }
    save_json(PENDING_MEDIA, pending_media)

    u = m.from_user
    author_mention = f'<a href="tg://user?id={u.id}">{u.first_name}</a>'
    markup = InlineKeyboardMarkup()
    markup.row(
        InlineKeyboardButton("✅ Одобрить медиа",
                             callback_data=f"approve_media:{media_id}"),
        InlineKeyboardButton("❌ Отклонить медиа",
                             callback_data=f"reject_media:{media_id}")
    )
    markup.row(
        InlineKeyboardButton(
            "🚫 Заблокировать", callback_data=f"block_user_media:{media_id}"),
        InlineKeyboardButton(
            "⚠️ Убрать имя", callback_data=f"remove_name_media:{media_id}")
    )

    # Отправляем превью в группу модерации
    if m.content_type == 'photo':
        bot.send_photo(MODERATION_GROUP_ID, file.file_id,
                       caption=(f"🖼 <b>Модерация фото</b>\n\n{m.caption or ''}\n\n"
                                f"👤 Автор: {author_mention} (ID: <code>{u.id}</code>)"),
                       parse_mode='HTML', reply_markup=markup)
    else:
        bot.send_video(MODERATION_GROUP_ID, file.file_id,
                       caption=(f"📹 <b>Модерация видео</b>\n\n{m.caption or ''}\n\n"
                                f"👤 Автор: {author_mention} (ID: <code>{u.id}</code>)"),
                       parse_mode='HTML', reply_markup=markup)

    bot.send_message(m.chat.id, "📤 Ваше медиа отправлено на модерацию.")

# --- обработка всех callback’ов модерации ---


@bot.callback_query_handler(func=lambda c: c.data.split(':')[0] in (
    'approve_post', 'reject_post', 'approve_reply', 'reject_reply',
    'block_user_post', 'remove_name_post',
    'block_user_reply', 'remove_name_reply',
    'approve_media', 'reject_media', 'block_user_media', 'remove_name_media'
))
def on_moderate(c):
    action, item = c.data.split(':', 1)
    mod = c.from_user
    mod_mention = f'<a href="tg://user?id={mod.id}">{mod.first_name}</a>'

    # --- Модерация поста ---
    if action in ('approve_post', 'reject_post', 'block_user_post', 'remove_name_post'):
        data = pending_posts.pop(item, None)
        save_json(PENDING_POSTS, pending_posts)
        if not data:
            return bot.answer_callback_query(c.id, "⚠️ Уже обработан.")

        u_id = data['from']
        u = bot.get_chat(u_id)
        author_mention = f'<a href="tg://user?id={u_id}">{u.first_name}</a>'

        if action == 'block_user_post':
            blocked_users[u_id] = True
            save_blocked()
            status = f"🚫 Заблокирован: {mod_mention}"
        elif action == 'remove_name_post':
            sent = bot.send_message(
                CHANNEL_ID,
                f"№{load_counter()+1:06}:\n{data['text']}\n\n<a href=\"https://t.me/{bot.get_me().username}?start=reply_{item}\">Ответить</a>",
                parse_mode='HTML',
                disable_web_page_preview=True
            )
            num = load_counter() + 1
            save_counter(num)
            approved_posts[item] = {
                'text': data['text'],
                'from': u_id,
                'number': num,
                'channel_message_id': sent.message_id
            }
            save_json(APPROVED_POSTS, approved_posts)
            status = f"⚠️ Опубликовано без имени: {mod_mention}"
        elif action == 'approve_post':
            sent = bot.send_message(
                CHANNEL_ID,
                f"№{load_counter()+1:06}:\n{data['text']}\n\n"
                f"<a href=\"https://t.me/{bot.get_me().username}?start=reply_{item}\">Ответить</a>",
                parse_mode='HTML',
                disable_web_page_preview=True
            )
            num = load_counter() + 1
            save_counter(num)
            approved_posts[item] = {
                'text': data['text'],
                'from': u_id,
                'number': num,
                'channel_message_id': sent.message_id
            }
            save_json(APPROVED_POSTS, approved_posts)
            status = f"Одобрил: {mod_mention}"
        else:
            status = f"Отклонил: {mod_mention}"

        bot.edit_message_text(
            chat_id=c.message.chat.id,
            message_id=c.message.message_id,
            text=(f"📬 <b>Запрос модерации поста</b>\n\n"
                  f"✉️ Текст поста:\n{data['text']}\n\n"
                  f"👤 Автор поста: {author_mention} (ID: <code>{u_id}</code>)\n\n"
                  f"{status}"),
            parse_mode='HTML',
            disable_web_page_preview=True
        )
        return bot.answer_callback_query(c.id, "")

    # --- Модерация ответа ---
    if action in ('approve_reply', 'reject_reply', 'block_user_reply', 'remove_name_reply'):
        data = pending_replies.pop(item, None)
        save_json(PENDING_REPLIES, pending_replies)
        if not data:
            return bot.answer_callback_query(c.id, "⚠️ Уже обработан.")

        orig = data['orig']
        entry = approved_posts.get(orig)
        u_id = data['from']
        u = bot.get_chat(u_id)
        author_mention = f'<a href="tg://user?id={u_id}">{u.first_name}</a>'

        if action == 'block_user_reply':
            blocked_users[u_id] = True
            save_blocked()
            status = f"🚫 Заблокирован: {mod_mention}"
        elif action == 'remove_name_reply':
            bot.send_message(
                CHANNEL_ID,
                f"№{load_counter()+1:06}:\n{data['text']}\n\n<a href=\"https://t.me/{bot.get_me().username}?start=reply_{orig}\">Ответить</a>",
                parse_mode='HTML',
                disable_web_page_preview=True,
                reply_to_message_id=entry['channel_message_id']
            )
            num = load_counter() + 1
            save_counter(num)
            status = f"⚠️ Опубликован без имени: {mod_mention}"
        elif action == 'approve_reply':
            bot.send_message(
                CHANNEL_ID,
                f"№{load_counter()+1:06}:\n{data['text']}\n\n"
                f"<a href=\"https://t.me/{bot.get_me().username}?start=reply_{orig}\">Ответить</a>",
                parse_mode='HTML',
                disable_web_page_preview=True,
                reply_to_message_id=entry['channel_message_id']
            )
            num = load_counter() + 1
            save_counter(num)
            status = f"Одобрил: {mod_mention}"
        else:
            status = f"Отклонил: {mod_mention}"

        bot.edit_message_text(
            chat_id=c.message.chat.id,
            message_id=c.message.message_id,
            text=(f"📨 <b>Запрос модерации ответа</b>\n\n"
                  f"Ответ на пост №{entry['number']:06}:\n{entry['text']}\n\n"
                  f"✉️ Текст ответа:\n{data['text']}\n\n"
                  f"👤 Автор ответа: {author_mention} (ID: <code>{u_id}</code>)\n\n"
                  f"{status}"),
            parse_mode='HTML',
            disable_web_page_preview=True
        )
        return bot.answer_callback_query(c.id, "")

    # --- Модерация медиа ---
    data = pending_media.pop(item, None)
    save_json(PENDING_MEDIA, pending_media)
    if not data:
        return bot.answer_callback_query(c.id, "⚠️ Уже обработан.")

    u_id = data['from']
    file_id = data['file_id']
    ctype = data['type']
    cap = data.get('caption', '')

    if action == 'block_user_media':
        blocked_users[u_id] = True
        save_blocked()
        status = f"🚫 Заблокирован: {mod_mention}"
    elif action == 'remove_name_media':
        caption = f"№{load_counter()+1:06}\n{cap}\n\n<a href=\"https://t.me/{bot.get_me().username}?start=reply_{item}\">Ответить</a>"
        if ctype == 'photo':
            bot.send_photo(CHANNEL_ID, file_id,
                           caption=caption, parse_mode='HTML')
        else:
            bot.send_video(CHANNEL_ID, file_id,
                           caption=caption, parse_mode='HTML')
        num = load_counter() + 1
        save_counter(num)
        status = f"⚠️ Опубликовано без имени: {mod_mention}"
        save_media_json(c.message, item, u_id, cap, load_counter(), ctype)
    elif action == 'approve_media':
        caption = f"№{load_counter()+1:06}\n{cap}\n\n<a href=\"https://t.me/{bot.get_me().username}?start=reply_{item}\">Ответить</a>"
        if ctype == 'photo':
            bot.send_photo(CHANNEL_ID, file_id,
                           caption=caption, parse_mode='HTML')
        else:
            bot.send_video(CHANNEL_ID, file_id,
                           caption=caption, parse_mode='HTML')
        num = load_counter() + 1
        save_counter(num)
        status = f"Одобрил: {mod_mention}"
        save_media_json(c.message, item, u_id, cap, load_counter(), ctype)
    else:
        status = f"Отклонил: {mod_mention}"

    bot.edit_message_caption(
        chat_id=c.message.chat.id,
        message_id=c.message.message_id,
        caption=(f"🖼 <b>Запрос модерации медиа</b>\n\n"
                 f"👤 ID: <code>{u_id}</code>\n\n"
                 f"{status}"),
        parse_mode='HTML'
    )

    bot.answer_callback_query(c.id, "")

bot.infinity_polling(
  timeout=15,              # ждём ответа от сервера до 15 секунд
  long_polling_timeout=10,  # сервер держит соединение до 10 секунд
  skip_pending=True
)

