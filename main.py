from aiogram import Bot, Dispatcher, executor, types
from aiogram.types import Message, LabeledPrice, PreCheckoutQuery, callback_query
from aiogram.types import ContentType
from datetime import datetime, timedelta
from aiogram.utils.exceptions import BotBlocked
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from dotenv import load_dotenv
from typing import Union
import logging
import sqlite3
import os

from apscheduler.schedulers.asyncio import AsyncIOScheduler


API_TOKEN = 'API_TOKEN'
PAYMENTS_PROVIDER_TOKEN = os.getenv('PAYMENTS_PROVIDER_TOKEN')
CHANNEL_LINK = os.getenv('CHANNEL_LINK')

# Настройка логирования
logging.basicConfig(level=logging.INFO)

# Инициализация бота и диспетчера
bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)

# Инициализация соединения с базой данных SQLite
conn = sqlite3.connect('subscriptions.db', check_same_thread=False)
cursor = conn.cursor()

#кнопка оплатить
keyboard = InlineKeyboardMarkup(resize_keyboard=True)
button_text = "хочу рецепты 🥣"  # Текст на кнопке
button = InlineKeyboardButton(button_text, callback_data='buy')  # Создаем кнопку с указанным текстом
keyboard.add(button)  # Добавляем кнопку к клавиатуре

# Создание таблицы, если она не существует
cursor.execute('''
CREATE TABLE IF NOT EXISTS subscriptions (
    user_id INTEGER PRIMARY KEY,
    telegram_id TEXT NOT NULL,
    username TEXT,
    full_name TEXT NOT NULL,
    age INTEGER,
    has_subscription BOOLEAN NOT NULL DEFAULT 0,
    subscription_date TEXT,
    first_payment_date TEXT,
    has_paid BOOLEAN NOT NULL DEFAULT 0
)
''')
conn.commit()

# Инициализация планировщика задач
scheduler = AsyncIOScheduler()
scheduler.start()

# Функция для обновления статуса подписки пользователя после успешного платежа
def update_subscription_status(user_id, subscription_date):
    cursor.execute('UPDATE subscriptions SET has_subscription = 1, subscription_date = ? WHERE user_id = ?', (subscription_date, user_id))
    conn.commit()

# Функция для регистрации нового пользователя
def register_user(user_id, telegram_id, username, full_name, age):
    cursor.execute('INSERT INTO subscriptions (user_id, telegram_id, username, full_name, age, has_paid) VALUES (?, ?, ?, ?, ?, ?)',
                   (user_id, telegram_id, username, full_name, age, 0))
    conn.commit()

@dp.message_handler(commands=['start'])
async def start(message: types.Message):
    await message.answer(f'{message.from_user.first_name}, добро пожаловать в магазин')
    # Проверка, есть ли пользователь в базе данных
    cursor.execute('SELECT user_id FROM subscriptions WHERE user_id = ?', (message.from_user.id,))
    result = cursor.fetchone()
    if result is None:
        # Если пользователь не найден, регистрируем его
        register_user(message.from_user.id, message.from_user.id, message.from_user.username, message.from_user.full_name, 0)
        # await message.answer("Вы успешно зарегистрированы!")
        await message.answer("""⭕️ Внимание:
- первоначальный взнос: 800р
- продление подписки: 300р""")
        await message.answer("Чтобы приобрести подписку на канал, нажмите на кнопку ниже", reply_markup=keyboard)
    else:
        # await message.answer("Вы уже зарегистрированы!")
        await message.answer("""⭕️ Внимание:
- первоначальный взнос: 800р
- продление подписки: 300р""")
        await message.answer("Чтобы приобрести подписку на канал, нажмите на кнопку ниже", reply_markup=keyboard)
@dp.errors_handler(exception=BotBlocked)
async def error_bot_blocked_handler(update: types. Update, exception: BotBlocked) -> bool:
    print( 'Нельзя отправить сообщение, потому что нас заблокировали!')

# Обработчик нажатия на кнопку "Оплата подписки"
@dp.callback_query_handler(lambda query: query.data == 'buy_subscription')
async def handle_buy_subscription(callback_query: types.CallbackQuery):
    # Отправляем сообщение с кнопкой "Оплатить подписку"
    await bot.send_message(callback_query.from_user.id, "Нажмите кнопку, чтобы оплатить подписку.",
                           reply_markup=types.InlineKeyboardMarkup(
                               inline_keyboard=[
                                   [
                                       types.InlineKeyboardButton("Оплатить подписку", callback_data="buy")
                                   ]
                               ]
                           ))
@dp.message_handler(commands=['buy'])
async def cmd_subscribe(message: types.Message):
    await message.answer("Оплата 💳", reply_markup=keyboard)
# Обработчик команды /buy
@dp.callback_query_handler(lambda query: query.data == 'buy')
async def cmd_subscribe(callback_query: types.CallbackQuery):
    # Проверка, является ли это первый платеж
    cursor.execute('SELECT has_paid FROM subscriptions WHERE user_id = ?', (callback_query.from_user.id,))
    result = cursor.fetchone()
    if result is None or not result[0]:
        # Первый платеж
        await bot.send_invoice(
            callback_query.from_user.id,
            title="Подписка на рецепты",
            description="Оплата стартовой подписки",
            provider_token=PAYMENTS_PROVIDER_TOKEN,
            currency="rub",
            prices=[LabeledPrice(label="Подписка", amount=800*100)],  # 800 рублей
            start_parameter="subscription",
            payload="subscription-payment",
            # photo_url="https://www.google.com/url?sa=i&url=https%3A%2F%2Fsteamcommunity.com%2Fsharedfiles%2Ffiledetails%2F%3Fid%3D2280067424&psig=AOvVaw00vhGqiTKf3BVEWiHfSKbW&ust=1714223201737000&source=images&cd=vfe&opi=89978449&ved=0CBIQjRxqFwoTCNiPlpr534UDFQAAAAAdAAAAABAJ",
            # photo_height=512,
            # photo_width=512,
            # photo_size=51200
        )
    else:
        # Продление подписки
        await bot.send_invoice(
            callback_query.from_user.id,
            title="Продление подписки",
            description="Оплата продления подписки",
            provider_token=PAYMENTS_PROVIDER_TOKEN,
            currency="rub",
            prices=[LabeledPrice(label="Продление", amount=300*100)],  # 300 рублей
            start_parameter="subscription_renewal",
            payload="subscription-renewal-payment",
            # photo_url="https://www.google.com/url?sa=i&url=https%3A%2F%2Fsteamcommunity.com%2Fsharedfiles%2Ffiledetails%2F%3Fid%3D2280067424&psig=AOvVaw00vhGqiTKf3BVEWiHfSKbW&ust=1714223201737000&source=images&cd=vfe&opi=89978449&ved=0CBIQjRxqFwoTCNiPlpr534UDFQAAAAAdAAAAABAJ",
            # photo_height=512,
            # photo_width=512,
            # photo_size=51200
        )
# # Обработчик не успешного платежа
# @dp.pre_checkout_query_handler(lambda query: not query.ok)
# async def not_successful_payment(pre_checkout_q: PreCheckoutQuery):
#     user_id = pre_checkout_q.from_user.id
#     await bot.send_message(user_id, "Извините, ваш платеж не был завершен. Попробуйте снова.")

# Обработчик успешного платежа
@dp.pre_checkout_query_handler(lambda query: True)
async def pre_checkout_query(pre_checkout_q: PreCheckoutQuery):
    await bot.answer_pre_checkout_query(pre_checkout_q.id, ok=True)

# отправляем админу сообщение на исключение пользователя из канала
async def kick_user(user_id):
    cursor.execute('SELECT full_name FROM subscriptions WHERE user_id = ?', (user_id,))
    result = cursor.fetchone()
    admin_id = '640485918'
    if result:
        full_name = result[0]
        # Отправляем сообщение с указанием полного имени
        await bot.send_message(admin_id, f"{full_name}, удали его")
    else:
        print(f"Пользователь с ID {user_id} не найден в базе данных.")
# Функция для отмены подписки
async def cancel_subscription(user_id, start_date):
    cursor.execute('UPDATE subscriptions SET has_subscription = 0 WHERE user_id = ?', (user_id,))
    conn.commit()
    await bot.send_message(user_id, "Подписка автоматически отменена из-за неоплаты продления.")
    await kick_user(user_id)
    admin_id = '640485918'

# Функция для проверки, прошёл ли месяц с момента последней оплаты
async def check_subscription_expiration(user_id):
    cursor.execute('SELECT has_subscription, subscription_date FROM subscriptions WHERE user_id = ?', (user_id,))
    result = cursor.fetchone()
    if result and result[0]:  # Если есть подписка
        subscription_date = datetime.strptime(result[1], '%Y-%m-%d %H:%M:%S')
        if subscription_date + timedelta(seconds=10) <= datetime.now():
            # Отправка напоминания о продлении подписки
            await bot.send_message(user_id, "Ваша подписка заканчивается. Пожалуйста, продлите её.")


# Обработчик успешного платежа
@dp.message_handler(content_types=ContentType.SUCCESSFUL_PAYMENT)
async def successful_payment(message: Message):

    # Обновление статуса подписки и оплаты пользователя
    subscription_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    update_subscription_status(message.from_user.id, subscription_date)

    # Set has_paid to True for the user
    cursor.execute('UPDATE subscriptions SET has_paid = 1 WHERE user_id = ?', (message.from_user.id,))
    conn.commit()

    await check_subscription_expiration(message.from_user.id)

    await bot.send_message(message.chat.id, "Спасибо за покупку!")
    await bot.send_message(message.chat.id, f'ссылка на канал {CHANNEL_LINK}')

    # Запланировать проверку подписки через 10 секунд 
    scheduler.add_job(check_subscription_expiration, 'date', run_date=datetime.now() + timedelta(seconds=10),
                      args=[message.from_user.id])

    cursor.execute('SELECT has_subscription FROM subscriptions WHERE user_id = ?', (message.from_user.id,))
    result = cursor.fetchone()
    if result and result[0]:
        # Запланировать отмену подписки через 20 секунд после успешной оплаты, если has_subscription = 0
        start_date = datetime.now() + timedelta(seconds=20)
        scheduler.add_job(cancel_subscription, 'date', run_date=start_date, args=[message.from_user.id, start_date])

# Функция для получения статуса подписки пользователя
def get_subscription_status(user_id):
    cursor = conn.cursor()
    cursor.execute('SELECT has_subscription FROM subscriptions WHERE user_id = ?', (user_id,))
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else False

#обработка команды:Пригласить друзей
@dp.message_handler(commands=['share'])
async def share(message: Message):
        invite_message = "Поделись мной со своими друзьями, отправив им эту ссылку: https://t.me/Oksyourselfbot"
        await message.answer(invite_message)


# обработка команды проверки статуса подписки
@dp.message_handler(commands=['status'])
async def check_subscription_status(message: types.Message):
    cursor = conn.cursor()
    cursor.execute('SELECT has_subscription FROM subscriptions WHERE user_id = ?', (message.from_user.id,))
    result = cursor.fetchone()
    if result is not None:
        has_subscription = result[0]
        if has_subscription:
            await bot.send_message(message.chat.id, "Подписка активна")
        else:
            await bot.send_message(message.chat.id, "Подписка не активна", reply_markup=keyboard)
    else:
        await bot.send_message(message.chat.id, "Пользователь не найден в базе данных")
#обработка команды: отмена подписки
@dp.message_handler(commands=['cancel'])
async def cancel(message: Message):
    cursor = conn.cursor()
    cursor.execute('UPDATE subscriptions SET has_subscription = 0 WHERE user_id = ?', (message.from_user.id,))
    conn.commit()
    await bot.send_message(message.chat.id, "Ваша подписка отменена")
    await bot.send_message(message.chat.id, "спасибо что были с нами ❤️")

#обработка команды: помощь
@dp.message_handler(commands=['help'])
async def help(message: Message):
    await bot.send_message(message.chat.id, "Напишите нам мы вас внимательно выслушаем: https://t.me/Oksyourself")

# Запуск бота и планировщика задач
if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)