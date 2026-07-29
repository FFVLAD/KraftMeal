import os
import sys
from telebot import TeleBot, types

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'myproject.settings')

import django

django.setup()

from shop.models import Order, UserProfile, StoreSettings

TOKEN = os.environ.get('BOT_TOKEN', '8605046875:AAEIdjsRa6_CbUq2VgSSfqjegYKR_YhLGR4')
bot = TeleBot(TOKEN)

admin_waiting_reason = {}


def format_order_text(order):
    items = order.items.all()
    items_text = ""

    for item in items:
        items_text += f"• {item.product.title} (x{item.quantity})\n"

    profile, _ = UserProfile.objects.get_or_create(user=order.user)
    regular_badge = "⭐ Постійний клієнт" if getattr(profile, 'is_regular_customer', False) else "👤 Клієнт"

    if order.payment_method == 'card':
        card_info = f"{order.selected_card.title} ({order.selected_card.card_number})" if order.selected_card else "Не вказано"
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
    if call.data.startswith("confirm_"):
        order_id = call.data.split("_")[1]
        bot.answer_callback_query(call.id)

        msg = bot.send_message(
            call.message.chat.id,
            f"⏱ Введіть **орієнтовний час доставки** для замовлення #{order_id} (наприклад: '30-40 хв' або 'до 19:30'):"
        )
        bot.register_next_step_handler(msg, process_delivery_time, order_id, call.message)

    elif call.data.startswith("cancel_"):
        order_id = call.data.split("_")[1]
        admin_waiting_reason[call.from_user.id] = order_id
        bot.answer_callback_query(call.id)

        msg = bot.send_message(
            call.message.chat.id,
            f"✍️ Напишіть **причину відмови** для замовлення #{order_id}:"
        )
        bot.register_next_step_handler(msg, process_rejection_reason, order_id, call.message)


def process_delivery_time(message, order_id, original_msg):
    est_time = message.text.strip()
    try:
        order = Order.objects.get(id=order_id)
        order.status = 'confirmed'
        order.estimated_delivery_time = est_time
        order.cancel_reason = None
        order.save()

        status_text = f"\n\n🟢 <b>СТАТУС: ПРИЙНЯТО</b>\n⏱ <b>Очікуваний час доставки:</b> {est_time}"

        if original_msg.photo or original_msg.caption is not None:
            current_caption = original_msg.caption or ""
            bot.edit_message_caption(
                chat_id=original_msg.chat.id,
                message_id=original_msg.message_id,
                caption=current_caption + status_text,
                parse_mode='HTML'
            )
        else:
            current_text = original_msg.text or ""
            bot.edit_message_text(
                chat_id=original_msg.chat.id,
                message_id=original_msg.message_id,
                text=current_text + status_text,
                parse_mode='HTML'
            )

        bot.send_message(message.chat.id,
                         f"✅ Замовлення #{order_id} підтверджено! Час доставки ({est_time}) збережено.")

    except Order.DoesNotExist:
        bot.send_message(message.chat.id, "Замовлення не знайдено.")


def process_rejection_reason(message, order_id, original_msg):
    reason_text = message.text

    try:
        order = Order.objects.get(id=order_id)
        order.status = 'canceled'
        order.cancel_reason = reason_text
        order.save()

        status_text = f"\n\n🔴 <b>СТАТУС: ВІДХИЛЕНО</b>\n❌ <b>Причина:</b> {reason_text}"

        if original_msg.photo or original_msg.caption is not None:
            current_caption = original_msg.caption or ""
            bot.edit_message_caption(
                chat_id=original_msg.chat.id,
                message_id=original_msg.message_id,
                caption=current_caption + status_text,
                parse_mode='HTML'
            )
        else:
            current_text = original_msg.text or ""
            bot.edit_message_text(
                chat_id=original_msg.chat.id,
                message_id=original_msg.message_id,
                text=current_text + status_text,
                parse_mode='HTML'
            )

        bot.send_message(message.chat.id, f"✅ Відмову для замовлення #{order_id} збережено!")

    except Order.DoesNotExist:
        bot.send_message(message.chat.id, "Замовлення не знайдено.")


def run_bot():
    print("🤖 Бот KraftMeal запущений і готовий до роботи...")
    bot.infinity_polling(skip_pending=True)


if __name__ == '__main__':
    run_bot()