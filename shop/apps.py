import os
import sys
import threading
from django.apps import AppConfig


class ShopConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'shop'

    def ready(self):

        if any(arg in sys.argv for arg in ['collectstatic', 'makemigrations', 'migrate']):
            return


        if os.environ.get('RENDER'):
            try:
                from .bot import run_bot

                bot_thread = threading.Thread(target=run_bot, daemon=True)
                bot_thread.start()
                print("🚀 Фоновий потік Telegram-бота успішно стартував!")
            except Exception as e:
                print(f"⚠️ Помилка старту фонового бота: {e}")