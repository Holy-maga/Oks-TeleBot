from fastapi import FastAPI, Request, HTTPException
import hmac
import hashlib
import base64
import json
import aiosqlite
from datetime import datetime
import logging
import os
from dotenv import load_dotenv
import uvicorn

load_dotenv()

logging.basicConfig(level=logging.INFO)

app = FastAPI()

YOO_KASSA_SHOP_ID = os.getenv('YOOKASSA_SHOP_ID')
YOO_KASSA_SECRET_KEY = os.getenv('YOOKASSA_SECRET_KEY')
REDIRECT_URL = os.getenv('CHANNEL_LINK')
DATABASE = 'subscriptions.db'

async def update_subscription(user_id, first_payment):
    async with aiosqlite.connect(DATABASE) as db:
        cur = db.cursor()
        if first_payment:
            cur.execute("UPDATE subscriptions SET has_paid = 1, subscription_date = ? WHERE user_id = ?,", (datetime.now(), user_id))
            logging.info(f"Первый платеж успешно записан в базу данных для пользователя {user_id}")
        else:
            cur.execute("UPDATE subscriptions SET subscription_date = ? WHERE user_id = ?", (datetime.now(), user_id))
            logging.info(f"Продление подписки успешно записано в базу данных для пользователя {user_id}")
        cur.commit()

async def verify_signature(request: Request) -> bool:
    body = await request.body()
    signature = request.headers.get('HTTP_CONTENT_HMAC')

    digest = hmac.new(
        YOO_KASSA_SECRET_KEY.encode('utf-8'),
        body,
        hashlib.sha256
    ).digest()
    signature_check = base64.b64encode(digest).decode('utf-8')
    return hmac.compare_digest(signature, signature_check)

@app.post("/yookassa-webhook")
async def yookassa_webhook(request: Request):
    if not await verify_signature(request):
        logging.error("Invalid signature")
        raise HTTPException(status_code=400, detail="Invalid signature")

    body = await request.json()
    logging.info(f"Webhook received: {body}")

    try:
        if body['event'] == 'payment.succeeded':
            user_id = int(body['object']['metadata']['user_id'])
            first_payment = body['object']['metadata'].get('first_payment', 'false') == 'true'
            await update_subscription(user_id, first_payment)
            logging.info(f"Обработка успешного платежа для пользователя {user_id}")
        else:
            logging.info("Received event is not 'payment.succeeded'")
    except KeyError as e:
        logging.error(f"Ошибка при обработке вебхука: отсутствует ключ {e}")
    except Exception as e:
        logging.error(f"Ошибка при обработке вебхука: {e}")

    return {"status": "ok"}

async def update_subscription(user_id, first_payment):
    try:
        async with aiosqlite.connect(DATABASE) as db:
            if first_payment:
                await db.execute('''
                    UPDATE subscriptions 
                    SET has_paid = TRUE, subscription_date = ? 
                    WHERE user_id = ?
                ''', (datetime.now(), user_id))
                logging.info(f"Первый платеж успешно записан в базу данных для пользователя {user_id}")
            else:
                await db.execute('''
                    UPDATE subscriptions 
                    SET subscription_date = ? 
                    WHERE user_id = ?
                ''', (datetime.now(), user_id))
                logging.info(f"Продление подписки успешно записано в базу данных для пользователя {user_id}")
            await db.commit()
    except Exception as e:
        logging.error(f"Ошибка при обновлении подписки для пользователя {user_id}: {e}")


import uvicorn
uvicorn.run(app, host="0.0.0.0", port=8001)