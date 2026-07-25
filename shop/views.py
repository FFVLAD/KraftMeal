
import requests
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.models import User
from django.contrib import messages
from django.http import JsonResponse

from django.contrib.auth.decorators import login_required

from .models import (
    Product,
    FoodCategory,
    CartItem,
    Order,
    OrderItem,
    UserProfile,
    StoreSettings
)

TELEGRAM_BOT_TOKEN = "8605046875:AAEIdjsRa6_CbUq2VgSSfqjegYKR_YhLGR4"


def get_settings():

    settings_obj, _ = StoreSettings.objects.get_or_create(id=1)
    return settings_obj


def send_telegram_order(order, items_text, profile):

    settings_obj = get_settings()
    admin_ids = settings_obj.get_admin_ids_list()

    regular_badge = "⭐ Постійний клієнт" if getattr(profile, 'is_regular_customer', False) else "👤 Клієнт"
    pay_badge = "💳 Карткою" if order.payment_method == 'card' else "💵 Готівкою"

    message = (
        f"<b>🛒 НОВЕ ЗАМОВЛЕННЯ #{order.id} [KraftMeal]</b>\n"
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

    keyboard = {
        "inline_keyboard": [
            [
                {"text": "✅ Прийняти", "callback_data": f"confirm_{order.id}"},
                {"text": "❌ Відхилити", "callback_data": f"cancel_{order.id}"}
            ]
        ]
    }

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    for admin_id in admin_ids:
        payload = {
            "chat_id": admin_id,
            "text": message,
            "parse_mode": "HTML",
            "reply_markup": keyboard
        }
        try:
            requests.post(url, json=payload, timeout=5)
        except Exception as e:
            print(f"Помилка відправки адміністратору {admin_id}: {e}")


def index(request):

    categories = FoodCategory.objects.all()

    selected_cat = request.GET.get('category')
    if selected_cat:
        products = Product.objects.filter(category__name=selected_cat)
    else:
        products = Product.objects.all()

    active_order = None
    user_cart_ids = []
    cart_items_count = 0
    cart_total = 0.0

    if request.user.is_authenticated:
        cart_items = CartItem.objects.filter(user=request.user)
        user_cart_ids = list(cart_items.values_list('product_id', flat=True))

        cart_items_count = cart_items.count()
        cart_total = sum(item.get_total_price() for item in cart_items)

        # Останнє активне замовлення, яке НЕ приховане клієнтом
        active_order = Order.objects.filter(user=request.user, is_dismissed=False).last()

    context = {
        'categories': categories,
        'selected_cat': selected_cat,
        'products': products,
        'active_order': active_order,
        'user_cart_ids': user_cart_ids,
        'cart_items_count': cart_items_count,
        'cart_total': round(float(cart_total), 2),
    }

    return render(request, 'shop/index.html', context)


def product_detail(request, product_id):

    product = get_object_or_404(Product, id=product_id)
    return render(request, 'shop/product_detail.html', {'product': product})


@login_required
def dismiss_order(request, order_id):

    if request.method == 'POST':
        try:
            order = Order.objects.get(id=order_id, user=request.user)
            order.is_dismissed = True
            order.save()
            return JsonResponse({'status': 'ok'})
        except Order.DoesNotExist:
            return JsonResponse({'status': 'error', 'message': 'Not found'}, status=404)
    return JsonResponse({'status': 'error'}, status=400)


@login_required
def toggle_cart(request, product_id):

    if request.method == 'POST':
        product = get_object_or_404(Product, id=product_id)
        item, created = CartItem.objects.get_or_create(user=request.user, product=product)

        if not created:
            item.delete()
            status = 'removed'
        else:
            status = 'added'

        cart_qs = CartItem.objects.filter(user=request.user)
        cart_total = sum(i.get_total_price() for i in cart_qs)

        return JsonResponse({
            'status': status,
            'cart_total': float(cart_total),
            'cart_count': cart_qs.count()
        })
    return JsonResponse({'status': 'error'}, status=400)


@login_required
def checkout(request):

    cart_items = CartItem.objects.filter(user=request.user)
    if not cart_items.exists():
        return redirect('index')

    cart_total = sum(item.get_total_price() for item in cart_items)
    profile, _ = UserProfile.objects.get_or_create(user=request.user)

    if request.method == 'POST':
        address = request.POST.get('address')
        phone = request.POST.get('phone')
        delivery_time = request.POST.get('delivery_time')
        comment = request.POST.get('comment', '')
        payment_method = request.POST.get('payment_method', 'cash')


        order = Order.objects.create(
            user=request.user,
            address=address,
            phone=phone,
            delivery_time=delivery_time,
            comment=comment,
            total_price=cart_total,
            payment_method=payment_method,
            status='pending'
        )


        items_text_list = []
        for c_item in cart_items:
            OrderItem.objects.create(
                order=order,
                product=c_item.product,
                price=c_item.product.price,
                quantity=c_item.quantity
            )
            items_text_list.append(f"• {c_item.product.title} (x{c_item.quantity}) - {c_item.get_total_price()}€")


        cart_items.delete()


        profile.phone = phone
        profile.save()


        if payment_method == 'cash':
            try:
                items_formatted_text = "\n".join(items_text_list)
                send_telegram_order(order, items_formatted_text, profile)
            except Exception as e:
                print(f"Error sending order to Telegram: {e}")


        return redirect('order_success', order_id=order.id)

    context = {
        'cart_items': cart_items,
        'cart_total': cart_total,
        'profile': profile
    }
    return render(request, 'shop/checkout.html', context)


@login_required
def order_success(request, order_id):

    order = get_object_or_404(Order, id=order_id, user=request.user)
    settings_obj = get_settings()
    return render(request, 'shop/order_success.html', {
        'order': order,
        'card_number': settings_obj.card_number
    })


def login_view(request):

    if request.user.is_authenticated:
        return redirect('index')

    if request.method == 'POST':
        username_input = request.POST.get('username')
        password_input = request.POST.get('password')

        user = authenticate(request, username=username_input, password=password_input)
        if user is not None:
            login(request, user)
            return redirect('index')
        else:
            messages.error(request, "Невірне ім'я користувача або пароль")

    return render(request, 'shop/login.html')


def register_view(request):

    if request.user.is_authenticated:
        return redirect('index')

    if request.method == 'POST':
        username = request.POST.get('username')
        email = request.POST.get('email')
        password = request.POST.get('password')
        password_confirm = request.POST.get('password_confirm')

        if password != password_confirm:
            messages.error(request, 'Паролі не збігаються!')
            return render(request, 'shop/register.html')

        if User.objects.filter(username=username).exists():
            messages.error(request, 'Користувач з таким логіном вже існує!')
            return render(request, 'shop/register.html')

        user = User.objects.create_user(username=username, email=email, password=password)
        user.save()

        login(request, user)
        messages.success(request, 'Реєстрація успішна!')
        return redirect('index')

    return render(request, 'shop/register.html')


def logout_view(request):

    logout(request)
    return redirect('index')