import requests
import uuid
import os
import logging
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO)

YOO_KASSA_SHOP_ID = os.getenv('YOOKASSA_SHOP_ID')
YOO_KASSA_SECRET_KEY = os.getenv('YOOKASSA_SECRET_KEY')
REDIRECT_URL = os.getenv('CHANNEL_LINK')


def create_payment(amount, description, user_id, first_payment=False):
    url = 'https://api.yookassa.ru/v3/payments'
    headers = {
        'Content-Type': 'application/json',
        'Idempotence-Key': str(uuid.uuid4()),
    }
    data = {
        "amount": {
            "value": f"{amount:.2f}",
            "currency": "RUB"
        },
        "confirmation": {
            "type": "redirect",
            "return_url": REDIRECT_URL
        },
        "capture": True,
        "description": description,
        "metadata": {
            "user_id": str(user_id),
            "first_payment": str(first_payment).lower()
        }
    }

    response = requests.post(url, json=data, headers=headers, auth=(YOO_KASSA_SHOP_ID, YOO_KASSA_SECRET_KEY))

    # Логируем полный ответ для отладки
    logging.info(f"Response status: {response.status_code}")
    logging.info(f"Response text: {response.text}")

    try:
        response_data = response.json()
        logging.info(f"Response JSON: {response_data}")
    except Exception as e:
        logging.error(f"Failed to parse response JSON: {e}")
        raise

    if response.status_code != 200:
        logging.error(f"Error in create_payment: {response.status_code} - {response.text}")
        raise Exception("Failed to create payment")

    if 'confirmation' not in response_data:
        logging.error(f"Error in create_payment: missing 'confirmation' key in response: {response_data}")
        raise KeyError("Missing 'confirmation' key in response")

    return response_data
