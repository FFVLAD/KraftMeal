import os
import sys
import json
import traceback
import django


sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'myproject.settings')


try:
    django.setup()
except RuntimeError:
    pass

import gspread
from google.oauth2.service_account import Credentials
from telebot import TeleBot, types

from shop.models import Order, UserProfile, StoreSettings

TOKEN = os.environ.get('BOT_TOKEN', '8605046875:AAEIdjsRa6_CbUq2VgSSfqjegYKR_YhLGR4')
bot = TeleBot(TOKEN)


def append_order_to_google_sheet(order, est_time):
    try:
        scopes = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive"
        ]


        env_creds = os.environ.get('GOOGLE_CREDENTIALS_JSON')
        if env_creds:
            creds_dict = json.loads(env_creds)
            creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
        else:
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            creds_path = os.path.join(base_dir, 'credentials.json')
            if not os.path.exists(creds_path):
                creds_path = 'credentials.json'
            creds = Credentials.from_service_account_file(creds_path, scopes=scopes)

        client = gspread.authorize(creds)
        spreadsheet = client.open_by_key("1A6l5t-sMklrhORoV7K-U73OFpa7EQZLseSz0r5jkNgs")
        sheet = spreadsheet.worksheet("KraftMeal")

        items_list = [f"{item.product.title} (x{item.quantity})" for item in order.items.all()]
        items_text = ", ".join(items_list)

        if order.payment_method == 'card':
            card_title = order.selected_card.title if getattr(order, 'selected_card', None) else 'Не вказано'
            pay_text = f"Картка ({card_title})"
        else:
            pay_text = "Готівка"

        row = [
            order.id,
            order.created_at.strftime("%Y-%m-%d %H:%M") if hasattr(order, 'created_at') and order.created_at else "",
            order.user.username,
            str(order.phone),
            order.address,
            order.delivery_time,
            est_time,
            items_text,
            float(order.total_price),
            pay_text,
            order.comment or ""
        ]

        sheet.append_row(row)
        return True, "OK"
    except Exception as e:
        error_details = f"{type(e).__name__}: {e}"
        print(f"❌ [GSHEETS ERROR]: {error_details}")
        print(traceback.format_exc())
        return False, error_details


def format_order_text(order):
    items = order.items.all()
    items_text = ""

    for item in items:
        items_text += f"• {item.product.title} (x{item.quantity})\n"

    profile, _ = UserProfile.objects.get_or_create(user=order.user)
    regular_badge = "⭐ Постійний клієнт" if getattr(profile, 'is_regular_customer', False) else "👤 Клієнт"

    if order.payment_method == 'card':
        card_info = f"{order.selected_card.title} ({order.selected_card.card_number})" if getattr(order, 'selected_card', None) else "Не вказано"
        pay_badge = f"💳 Карткою на: <b>{card_info}</b>"
    else:
        pay_badge = "💵 Готівкою"

    text = (
        f"🛒 <b>НОВЕ ЗАМОВЛЕННЯ #{order.id} [KraftMeal]</b>\n"
        f"------------------------------\n"
        f"<b>Статус клієнта:</b> {regular_badge}\n"
        f"<b>Користувач:</b> {order.user.username}\n"
        f"<b>Телефон:</b> {order.phone}\n"
        f"<b>Адреса доставки:</b> {order.address}\n"
        f"<b>Бажаний час:</b> {order.delivery_time}\n"
        f"<b>Оплата:</b> {pay_badge}\n"
        f"<b>Сума:</b> {order.total_price}€\n\n"
        f"<b>Склад замовлення:</b>\n{items_text}\n"
        f"<b>Коментар:</b> {order.comment or 'Немає'}"
    )
    return text


def get_admin_keyboard(order_id):
    keyboard = types.InlineKeyboardMarkup(row_width=2)
    btn_confirm = types.InlineKeyboardButton("✅ Прийняти", callback_data=f"confirm_{order_id}")
    btn_cancel = types.InlineKeyboardButton("❌ Відхилити", callback_data=f"cancel_{order_id}")
    keyboard.add(btn_confirm, btn_cancel)
    return keyboard


@bot.message_handler(commands=['start'])
def start_cmd(message):
    bot.send_message(
        message.chat.id,
        "Вітаємо у KraftMeal! 🍲\n\nЯкщо ви оформили замовлення з оплатою карткою, будь ласка, **надішліть сюди фото/скріншот чека** про оплату."
    )


@bot.message_handler(content_types=['photo'])
def handle_photo_receipt(message):
    try:
        user_orders = Order.objects.filter(
            status='pending',
            payment_method='card'
        ).order_by('-id')

        order = None
        if message.from_user.username:
            for o in user_orders:
                if o.user.username.lower() == message.from_user.username.lower():
                    order = o
                    break

        if not order and user_orders.exists():
            order = user_orders.first()

        if not order:
            bot.reply_to(message, "❌ Не знайдено активного замовлення з оплатою карткою, яке очікує підтвердження.")
            return

        caption_text = format_order_text(order)
        keyboard = get_admin_keyboard(order.id)
        photo_id = message.photo[-1].file_id

        try:
            settings_obj = StoreSettings.objects.get(id=1)
            admin_ids = settings_obj.get_admin_ids_list()
        except StoreSettings.DoesNotExist:
            admin_ids = []

        if not admin_ids:
            bot.reply_to(message, "⚠️ Помилка: В системі не налаштовано ID адміністраторів.")
            return

        for admin_id in admin_ids:
            try:
                bot.send_photo(
                    chat_id=admin_id,
                    photo=photo_id,
                    caption=caption_text,
                    parse_mode="HTML",
                    reply_markup=keyboard
                )
            except Exception as admin_err:
                print(f"Помилка надсилання адміну {admin_id}: {admin_err}")

        bot.reply_to(message, "✅ Чек отримано! Дякуємо. Адміністратор перевірить оплату та підтвердить замовлення.")

    except Exception as e:
        print(f"Помилка при обробці чека: {e}")
        bot.reply_to(message, "⚠️ Виникла помилка при обробці чека. Спробуйте ще раз.")


@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    try:
        bot.answer_callback_query(call.id)

        if call.data.startswith("confirm_"):
            order_id = call.data.split("_")[1]

            prompt_msg = bot.send_message(
                call.message.chat.id,
                f"⏱ Введіть **орієнтовний час доставки** для замовлення #{order_id} (наприклад: '30-40 хв' або 'до 19:30'):"
            )

            bot.register_next_step_handler(prompt_msg, process_delivery_time, order_id, call.message)

        elif call.data.startswith("cancel_"):
            order_id = call.data.split("_")[1]

            prompt_msg = bot.send_message(
                call.message.chat.id,
                f"✍️ Напишіть **причину відмови** для замовлення #{order_id}:"
            )
            bot.register_next_step_handler(prompt_msg, process_rejection_reason, order_id, call.message)

    except Exception as err:
        print(f"❌ Помилка в callback_handler: {err}")
        bot.send_message(call.message.chat.id, f"⚠️ Виникла помилка під час обробки натискання: {err}")


def process_delivery_time(message, order_id, original_msg):
    est_time = message.text.strip()
    try:
        order = Order.objects.get(id=order_id)
        order.status = 'confirmed'
        order.estimated_delivery_time = est_time
        order.cancel_reason = None
        order.save()


        success, sheet_err = append_order_to_google_sheet(order, est_time)

        status_text = f"\n\n🟢 <b>СТАТУС: ПРИЙНЯТО</b>\n⏱ <b>Очікуваний час доставки:</b> {est_time}"

        try:
            if original_msg.photo or original_msg.caption is not None:
                current_caption = original_msg.caption or ""
                bot.edit_message_caption(
                    chat_id=original_msg.chat.id,
                    message_id=original_msg.message_id,
                    caption=current_caption + status_text,
                    parse_mode='HTML',
                    reply_markup=None
                )
            else:
                current_text = original_msg.text or ""
                bot.edit_message_text(
                    chat_id=original_msg.chat.id,
                    message_id=original_msg.message_id,
                    text=current_text + status_text,
                    parse_mode='HTML',
                    reply_markup=None
                )
        except Exception as edit_err:
            print(f"Помилка оновлення тексту замовлення: {edit_err}")

        if success:
            bot.send_message(message.chat.id, f"✅ Замовлення #{order_id} підтверджено та успішно записано в Google Таблицю!")
        else:
            bot.send_message(message.chat.id, f"⚠️ Замовлення #{order_id} підтверджено, але виникла ПОМИЛКА запису в Google Таблицю:\n<code>{sheet_err}</code>", parse_mode="HTML")

    except Order.DoesNotExist:
        bot.send_message(message.chat.id, "❌ Замовлення не знайдено.")
    except Exception as e:
        print(f"Помилка під час підтвердження замовлення: {e}")
        bot.send_message(message.chat.id, f"⚠️ Помилка: {e}")


def process_rejection_reason(message, order_id, original_msg):
    reason_text = message.text.strip()

    try:
        order = Order.objects.get(id=order_id)
        order.status = 'canceled'
        order.cancel_reason = reason_text
        order.save()

        status_text = f"\n\n🔴 <b>СТАТУС: ВІДХИЛЕНО</b>\n❌ <b>Причина:</b> {reason_text}"

        try:
            if original_msg.photo or original_msg.caption is not None:
                current_caption = original_msg.caption or ""
                bot.edit_message_caption(
                    chat_id=original_msg.chat.id,
                    message_id=original_msg.message_id,
                    caption=current_caption + status_text,
                    parse_mode='HTML',
                    reply_markup=None
                )
            else:
                current_text = original_msg.text or ""
                bot.edit_message_text(
                    chat_id=original_msg.chat.id,
                    message_id=original_msg.message_id,
                    text=current_text + status_text,
                    parse_mode='HTML',
                    reply_markup=None
                )
        except Exception as edit_err:
            print(f"Помилка оновлення тексту замовлення: {edit_err}")

        bot.send_message(message.chat.id, f"✅ Відмову для замовлення #{order_id} збережено!")

    except Order.DoesNotExist:
        bot.send_message(message.chat.id, "❌ Замовлення не знайдено.")
    except Exception as e:
        print(f"Помилка під час відхилення замовлення: {e}")
        bot.send_message(message.chat.id, f"⚠️ Помилка: {e}")


def run_bot():
    print("🤖 Бот KraftMeal запущений і готовий до роботи...")
    bot.infinity_polling(skip_pending=True)


if __name__ == '__main__':
    run_bot()