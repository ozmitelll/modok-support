import os
from dotenv import load_dotenv

from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes, Application

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
# Список ID операторов
OPERATORS = [832707199, 666372937]  # замените на реальные ID операторов

# Состояние чатов
chats = {}
# Словарь для хранения сообщений о клиентах у операторов
notification_messages = {}

# Приветственное сообщение при команде /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.chat_id
    if user_id not in OPERATORS:
        await context.bot.send_message(
            user_id,
            "Здравствуйте! Добро пожаловать в нашу поддержку. Напишите ваш вопрос, и один из операторов скоро свяжется с вами."
        )

# Функция для обработки входящего сообщения от клиента
async def handle_client_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.chat_id
    message_text = update.message.text

    # Проверка, что сообщение отправлено клиентом
    if user_id not in chats and user_id not in OPERATORS:
        # Проверяем, есть ли свободные операторы
        available_operators = [op for op in OPERATORS if op not in chats.values()]

        if available_operators:
            # Если есть свободные операторы, уведомляем их о новом запросе и сохраняем ID уведомлений
            keyboard = [
                [InlineKeyboardButton("Взять запрос", callback_data=f"take_{user_id}")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)

            # Отправляем уведомления операторам и сохраняем ID сообщений
            notification_messages[user_id] = {}
            for operator_id in available_operators:
                message = await context.bot.send_message(
                    operator_id,
                    f"Новое сообщение от клиента {user_id}: {message_text}",
                    reply_markup=reply_markup
                )
                # Сохраняем ID сообщения для каждого оператора
                notification_messages[user_id][operator_id] = message.message_id
        else:
            # Если все операторы заняты, отправляем сообщение клиенту
            await context.bot.send_message(
                user_id,
                "Все операторы заняты. Пожалуйста, ожидайте, пока освободится один из операторов."
            )

    elif user_id in chats:
        # Если сообщение отправлено клиентом, перенаправляем его закрепленному оператору
        if user_id not in OPERATORS:
            operator_id = chats[user_id]
            await context.bot.send_message(operator_id, f"Сообщение от клиента {user_id}: {message_text}")

    # Если сообщение отправлено оператором
    elif user_id in OPERATORS:
        # Определяем клиента, который закреплен за этим оператором
        client_id = None
        for client, operator in chats.items():
            if operator == user_id:
                client_id = client
                break

        # Если оператор действительно закреплен за клиентом, пересылаем его сообщение клиенту
        if client_id is not None:
            await context.bot.send_message(client_id, message_text)


# Функция обработки нажатия кнопки "Взять запрос"
async def take_client_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    operator_id = query.message.chat_id
    client_id = int(query.data.split("_")[1])  # Извлекаем ID клиента из callback_data

    if operator_id in OPERATORS:
        # Закрепляем оператора за клиентом
        chats[client_id] = operator_id
        await context.bot.send_message(operator_id, f"Вы взяли запрос клиента {client_id}. Отвечайте от имени бота.")
        await context.bot.send_message(client_id, "Ваш запрос принят оператором. Как мы можем помочь?")

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
            [InlineKeyboardButton("Завершить чат", callback_data=f"end_{client_id}")]
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
        del chats[client_id]
        await context.bot.send_message(operator_id, f"Вы завершили разговор с клиентом {client_id}.")
        await context.bot.send_message(client_id, "Чат завершен. Спасибо за обращение!")

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
