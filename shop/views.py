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
    StoreSettings,
    PaymentCard
)

TELEGRAM_BOT_TOKEN = "8605046875:AAEIdjsRa6_CbUq2VgSSfqjegYKR_YhLGR4"


def get_settings():
    settings_obj, _ = StoreSettings.objects.get_or_create(id=1)
    return settings_obj


def calculate_cart_total(user):
    """
    Калькулятор комплексного меню:
    - Збирає товари за Базовими категоріями.
    - Кожен повний набір (по 1 страві з УСІХ базових категорій) = Ціна Меню (напр. 10€).
    - Всі залишки базових страв рахуються за extra_price.
    - Товари з простих категорій рахуються за стандартною price.
    """
    cart_items = CartItem.objects.filter(user=user).select_related('product', 'product__category')
    if not cart_items.exists():
        return 0.0

    settings_obj = get_settings()
    menu_price = float(settings_obj.menu_price)

    base_categories = list(FoodCategory.objects.filter(category_type='base'))
    num_base_cats = len(base_categories)

    total_sum = 0.0

    if num_base_cats > 0:
        base_cat_counts = {cat.id: 0 for cat in base_categories}
        base_items = []

        for item in cart_items:
            cat = item.product.category
            if cat.category_type == 'base':
                base_cat_counts[cat.id] = base_cat_counts.get(cat.id, 0) + item.quantity
                for _ in range(item.quantity):
                    base_items.append(item.product)
            else:
                total_sum += float(item.product.price) * item.quantity

        full_menus_count = min(base_cat_counts.values()) if base_cat_counts else 0
        total_sum += full_menus_count * menu_price

        if full_menus_count > 0:
            used_per_cat = {cat.id: full_menus_count for cat in base_categories}
            for prod in base_items:
                cat_id = prod.category.id
                if used_per_cat[cat_id] > 0:
                    used_per_cat[cat_id] -= 1
                else:
                    total_sum += float(prod.extra_price)
        else:
            for prod in base_items:
                total_sum += float(prod.extra_price)
    else:
        for item in cart_items:
            total_sum += float(item.product.price) * item.quantity

    return round(total_sum, 2)


def send_telegram_order(order, items_text, profile):
    settings_obj = get_settings()
    admin_ids = settings_obj.get_admin_ids_list()

    regular_badge = "⭐ Постійний клієнт" if getattr(profile, 'is_regular_customer', False) else "👤 Клієнт"

    if order.payment_method == 'card':
        card_info = f"{order.selected_card.title} ({order.selected_card.card_number})" if order.selected_card else "Не вказано"
        pay_badge = f"💳 Карткою на: <b>{card_info}</b>"
    else:
        pay_badge = "💵 Готівкою"

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
        f"<b>Склад замовлення:</b>\n{items_text}\n\n"
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
        cart_total = calculate_cart_total(request.user)

        active_order = Order.objects.filter(user=request.user, is_dismissed=False).last()

    context = {
        'categories': categories,
        'selected_cat': selected_cat,
        'products': products,
        'active_order': active_order,
        'user_cart_ids': user_cart_ids,
        'cart_items_count': cart_items_count,
        'cart_total': cart_total,
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
        cart_total = calculate_cart_total(request.user)

        return JsonResponse({
            'status': status,
            'cart_total': float(cart_total),
            'cart_count': cart_qs.count()
        })
    return JsonResponse({'status': 'error'}, status=400)


@login_required
def update_cart_quantity(request, item_id):
    """ Зміна кількості або видалення позиції у кошику """
    if request.method == 'POST':
        action = request.POST.get('action')
        cart_item = get_object_or_404(CartItem, id=item_id, user=request.user)

        if action == 'increase':
            cart_item.quantity += 1
            cart_item.save()
        elif action == 'decrease':
            if cart_item.quantity > 1:
                cart_item.quantity -= 1
                cart_item.save()
            else:
                cart_item.delete()
                cart_item = None
        elif action == 'remove':
            cart_item.delete()
            cart_item = None

        cart_total = calculate_cart_total(request.user)
        remaining_items = CartItem.objects.filter(user=request.user).count()

        return JsonResponse({
            'status': 'ok',
            'quantity': cart_item.quantity if cart_item else 0,
            'cart_total': float(cart_total),
            'remaining_items': remaining_items
        })

    return JsonResponse({'status': 'error'}, status=400)


@login_required
def checkout(request):
    cart_items = CartItem.objects.filter(user=request.user).select_related('product', 'product__category')
    if not cart_items.exists():
        return redirect('index')

    cart_total = calculate_cart_total(request.user)
    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    cards = PaymentCard.objects.filter(is_active=True)

    if request.method == 'POST':
        address = request.POST.get('address')
        phone = request.POST.get('phone')
        delivery_time = request.POST.get('delivery_time')
        comment = request.POST.get('comment', '')
        payment_method = request.POST.get('payment_method', 'cash')
        card_id = request.POST.get('selected_card')

        selected_card_obj = None
        if payment_method == 'card' and card_id:
            selected_card_obj = PaymentCard.objects.filter(id=card_id).first()

        order = Order.objects.create(
            user=request.user,
            address=address,
            phone=phone,
            delivery_time=delivery_time,
            comment=comment,
            total_price=cart_total,
            payment_method=payment_method,
            selected_card=selected_card_obj,
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
            items_text_list.append(f"• {c_item.product.title} (x{c_item.quantity})")

        cart_items.delete()

        profile.phone = phone
        profile.save()

        try:
            items_formatted_text = "\n".join(items_text_list)
            send_telegram_order(order, items_formatted_text, profile)
        except Exception as e:
            print(f"Error sending order to Telegram: {e}")

        return redirect('order_success', order_id=order.id)

    context = {
        'cart_items': cart_items,
        'cart_total': cart_total,
        'profile': profile,
        'cards': cards
    }
    return render(request, 'shop/checkout.html', context)


@login_required
def order_success(request, order_id):
    order = get_object_or_404(Order, id=order_id, user=request.user)
    return render(request, 'shop/order_success.html', {
        'order': order,
        'card': order.selected_card
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


@login_required
def profile_view(request):

    orders = Order.objects.filter(user=request.user).prefetch_related('items__product').order_by('-created_at')
    profile, _ = UserProfile.objects.get_or_create(user=request.user)

    return render(request, 'shop/profile.html', {
        'orders': orders,
        'profile': profile
    })


@login_required
def repeat_order(request, order_id):

    if request.method == 'POST':
        old_order = get_object_or_404(Order, id=order_id, user=request.user)


        CartItem.objects.filter(user=request.user).delete()


        for item in old_order.items.all():
            CartItem.objects.create(
                user=request.user,
                product=item.product,
                quantity=item.quantity
            )

        return JsonResponse({'status': 'ok'})
    return JsonResponse({'status': 'error'}, status=400)