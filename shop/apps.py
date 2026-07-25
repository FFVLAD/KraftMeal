from django.apps import AppConfig


class ShopConfig(AppConfig):
    name = 'shop'


import os
import threading
from django.apps import AppConfig


class ShopConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'shop'

    def ready(self):

        if os.environ.get('RENDER'):
            from .bot import run_bot

            bot_thread = threading.Thread(target=run_bot, daemon=True)
            bot_thread.start()
            print("🚀 Фоновий потік Telegram-бота успішно стартував!")