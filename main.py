from fastapi import FastAPI, Request, HTTPException
import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.types import Message, LabeledPrice, PreCheckoutQuery, callback_query
from aiogram.utils import executor
import aiosqlite
from datetime import datetime, timedelta
from dotenv import load_dotenv
from typing import Union
import requests
import uuid
import logging
import os
from WebHook import app
from Payment import create_payment
import uvicorn

load_dotenv()

API_TOKEN = os.getenv('API_TOKEN')
YOO_KASSA_SECRET_KEY = os.getenv('YOOKASSA_SECRET_KEY')
PAYMENTS_PROVIDER_TOKEN = os.getenv('PAYMENTS_PROVIDER_TOKEN')

bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)

# Настройка логирования
logging.basicConfig(level=logging.INFO)

DATABASE = 'subscriptions.db'


async def create_db():
    async with aiosqlite.connect(DATABASE) as db:
        await db.execute('''
            CREATE TABLE IF NOT EXISTS subscriptions (
                user_id INTEGER PRIMARY KEY,
                subscription_date TIMESTAMP,
                has_paid BOOLEAN
            )
        ''')
        await db.commit()

@dp.message_handler(commands=['start'])
async def start(message: types.Message):
    user_id = message.from_user.id

    async with aiosqlite.connect(DATABASE) as db:
        # Проверяем, есть ли пользователь в базе данных
        cursor = await db.execute('SELECT user_id FROM subscriptions WHERE user_id = ?', (user_id,))
        result = await cursor.fetchone()

        if result is None:
            # Добавляем пользователя в базу данных
            await db.execute('''
                INSERT INTO subscriptions (user_id, subscription_date, has_paid)
                VALUES (?, ?, ?)
            ''', (user_id, None, False))
            await db.commit()
    await message.answer(f'{message.from_user.first_name}, добро пожаловать!')
    await message.answer("""⭕️ Внимание:
- первоначальный взнос: 800р
- продление подписки: 300р""")
    await message.answer("Чтобы приобрести подписку на канал, нажмите на /buy")

# Обработчик команды /buy
@dp.message_handler(commands=['buy'])
async def process_buy(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id
    logging.info(f"Обработка покупки для пользователя {user_id}")

    async with aiosqlite.connect(DATABASE) as db:
        cursor = await db.execute('SELECT has_paid FROM subscriptions WHERE user_id = ?', (user_id,))
        result = await cursor.fetchone()
        logging.info(f"Результат запроса в БД для пользователя {user_id}: {result}")

        if result is None or not result[0]:
            # Первый платеж
            try:
                payment = create_payment(800.00, "Первый платеж за подписку", user_id, first_payment=True)
                payment_url = payment['confirmation']['confirmation_url']
                await bot.send_message(user_id, f"Для оплаты перейдите по ссылке: {payment_url}")
                logging.info(f"Ссылка для оплаты первого платежа отправлена пользователю {user_id}: {payment_url}")
            except Exception as e:
                await bot.send_message(user_id, f"Ошибка при создании платежа: {e}")
                logging.error(f"Ошибка при создании первого платежа для пользователя {user_id}: {e}")
        else:
            # Продление подписки
            try:
                payment = create_payment(300.00, "Продление подписки", user_id, first_payment=False)
                payment_url = payment['confirmation']['confirmation_url']
                await bot.send_message(user_id, f"Для оплаты перейдите по ссылке: {payment_url}")
                logging.info(f"Ссылка для оплаты продления подписки отправлена пользователю {user_id}: {payment_url}")
            except Exception as e:
                await bot.send_message(user_id, f"Ошибка при создании платежа: {e}")
                logging.error(f"Ошибка при создании продления подписки для пользователя {user_id}: {e}")


logging.basicConfig(level=logging.INFO)
loop = asyncio.get_event_loop()
loop.create_task(create_db())
executor.start_polling(dp, skip_updates=True)
uvicorn.run(app, host="0.0.0.0", port=8000)