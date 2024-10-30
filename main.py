import os
from dotenv import load_dotenv

from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes, Application

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
# Список ID операторов
OPERATORS = [832707199, 6836458853]  # замените на реальные ID операторов

# Состояние чатов
chats = {}
# Словарь для хранения сообщений о клиентах у операторов
notification_messages = {}

# Translations dictionary
translations = {
    "start_message": {
        "en": "Hello! Welcome to our support. Write your question, and an operator will soon get in touch with you.",
        "ru": "Здравствуйте! Добро пожаловать в нашу поддержку. Напишите ваш вопрос, и один из операторов скоро свяжется с вами.",
        "uk": "Вітаємо! Ласкаво просимо до нашої підтримки. Напишіть своє запитання, і один з операторів незабаром зв'яжеться з вами."
    },
    "all_operators_busy": {
        "en": "All operators are busy. Please wait until one becomes available.",
        "ru": "Все операторы заняты. Пожалуйста, ожидайте, пока освободится один из операторов.",
        "uk": "Всі оператори зайняті. Будь ласка, зачекайте, поки звільниться один із операторів."
    },
    "new_message_from_client": {
        "en": "New message from client {user_id}: {message_text}",
        "ru": "Новое сообщение от клиента {user_id}: {message_text}",
        "uk": "Нове повідомлення від клієнта {user_id}: {message_text}"
    },
    "request_accepted": {
        "en": "Your request has been accepted by an operator. How can we help?",
        "ru": "Ваш запрос принят оператором. Как мы можем помочь?",
        "uk": "Ваш запит прийнятий оператором. Як ми можемо допомогти?"
    },
    "chat_ended": {
        "en": "Chat ended. Thank you for contacting us!",
        "ru": "Чат завершен. Спасибо за обращение!",
        "uk": "Чат завершено. Дякуємо за звернення!"
    },
    # Add to the translations dictionary
    "end_chat_button": {
        "en": "End Chat",
        "ru": "Завершить чат",
        "uk": "Завершити чат"
    },
    # Add to the translations dictionary
    "take_request_button": {
        "en": "Take Request",
        "ru": "Взять запрос",
        "uk": "Взяти запит"
    }


}
def get_localized_text(key, language_code, **kwargs):
    # Set default to 'en' if language is unsupported
    language = language_code if language_code in translations[key] else "en"
    # Format the message if needed
    return translations[key][language].format(**kwargs)


# Приветственное сообщение при команде /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.chat_id
    user_language = update.message.from_user.language_code
    message_text = get_localized_text("start_message", user_language)

    if user_id in OPERATORS:
        await context.bot.send_message(user_id, message_text)


# Функция для обработки входящего сообщения от клиента
async def handle_client_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.chat_id
    message_text = update.message.text
    user_language = update.message.from_user.language_code

    # Проверка, что сообщение отправлено клиентом
    if user_id not in chats and user_id not in OPERATORS:
        available_operators = [op for op in OPERATORS if op not in chats.values()]

        if available_operators:
            notification_messages[user_id] = {}
            for operator_id in available_operators:
                operator_message = get_localized_text(
                    "new_message_from_client", user_language,
                    user_id=user_id, message_text=message_text
                )
                message = await context.bot.send_message(
                    operator_id,
                    operator_message,
                    reply_markup=InlineKeyboardMarkup(
                        [[InlineKeyboardButton(get_localized_text("take_request_button", user_language), callback_data=f"take_{user_id}")]])
                )
                notification_messages[user_id][operator_id] = message.message_id
        else:
            await context.bot.send_message(
                user_id,
                get_localized_text("all_operators_busy", user_language)
            )

    elif user_id in chats:
        operator_id = chats[user_id]
        await context.bot.send_message(
            operator_id,
            get_localized_text("new_message_from_client", user_language, user_id=user_id, message_text=message_text)
        )

    elif user_id in OPERATORS:
        client_id = next((client for client, operator in chats.items() if operator == user_id), None)
        if client_id:
            await context.bot.send_message(client_id, message_text)


# Обновите также другие функции, например `take_client_callback` и `end_chat_callback`, аналогичным образом
# для отправки локализованных сообщений.
# Функция обработки нажатия кнопки "Взять запрос"
async def take_client_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    operator_id = query.message.chat_id
    client_id = int(query.data.split("_")[1])  # Извлекаем ID клиента из callback_data

    if operator_id in OPERATORS:
        # Закрепляем оператора за клиентом
        chats[client_id] = operator_id

        # Определяем язык клиента для локализации
        user_language = context.user_data.get("language_code", "en")
        operator_message = get_localized_text("request_accepted", user_language)
        client_message = get_localized_text("request_accepted", user_language)

        await context.bot.send_message(operator_id, f"You accepted the request from client {client_id}.")
        await context.bot.send_message(client_id, client_message)

        # Удаляем уведомления у других операторов
        if client_id in notification_messages:
            for op_id, msg_id in notification_messages[client_id].items():
                if op_id != operator_id:
                    try:
                        await context.bot.delete_message(chat_id=op_id, message_id=msg_id)
                    except Exception as e:
                        print(f"Ошибка при удалении сообщения у оператора {op_id}: {e}")
            # Очищаем уведомления после удаления
            del notification_messages[client_id]

        # Создаем кнопку для завершения чата
        keyboard = [
            [InlineKeyboardButton(get_localized_text("end_chat_button", user_language), callback_data=f"end_{client_id}")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        # Обновляем сообщение оператора с новой кнопкой
        await query.edit_message_reply_markup(reply_markup=reply_markup)

# Функция обработки нажатия кнопки "Завершить чат"
async def end_chat_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    operator_id = query.message.chat_id
    client_id = int(query.data.split("_")[1])  # Извлекаем ID клиента из callback_data

    if operator_id in OPERATORS and chats.get(client_id) == operator_id:
        # Удаляем запись о чате из состояния
        del chats[client_id]

        # Определяем язык клиента для локализации
        user_language = context.user_data.get("language_code", "en")
        operator_message = get_localized_text("chat_ended", user_language)
        client_message = get_localized_text("chat_ended", user_language)

        await context.bot.send_message(operator_id, operator_message)
        await context.bot.send_message(client_id, client_message)

        # Убираем клавиатуру из сообщения
        await query.edit_message_reply_markup(reply_markup=None)

# Основная функция для запуска бота
def main():
    app = Application.builder().token(BOT_TOKEN).build()

    # Обработчики команд и сообщений
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_client_message))
    app.add_handler(CallbackQueryHandler(take_client_callback, pattern=r"^take_"))
    app.add_handler(CallbackQueryHandler(end_chat_callback, pattern=r"^end_"))

    app.run_polling()


if __name__ == '__main__':
    main()
