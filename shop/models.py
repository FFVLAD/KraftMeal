from django.db import models
from django.contrib.auth.models import User


class StoreSettings(models.Model):
    menu_price = models.DecimalField(max_digits=8, decimal_places=2, default=10.00, verbose_name="Ціна комплексного меню (€)")
    admin_telegram_ids = models.CharField(max_length=255, default="", blank=True, help_text="ID адмінів через кому", verbose_name="Telegram ID адмінів")

    class Meta:
        verbose_name = "Налаштування магазину"
        verbose_name_plural = "Налаштування магазину"

    def get_admin_ids_list(self):
        if not self.admin_telegram_ids:
            return []
        return [aid.strip() for aid in self.admin_telegram_ids.split(",") if aid.strip()]

    def __str__(self):
        return "Налаштування магазину"


class PaymentCard(models.Model):
    title = models.CharField(max_length=100, verbose_name="Назва рахунку/картки (напр. Monobank EUR)")
    card_number = models.CharField(max_length=50, verbose_name="Номер картки або IBAN")
    is_active = models.BooleanField(default=True, verbose_name="Активна")

    class Meta:
        verbose_name = "Картка для оплати"
        verbose_name_plural = "Картки для оплати"

    def __str__(self):
        return f"{self.title} ({self.card_number})"


class FoodCategory(models.Model):
    CATEGORY_TYPES = (
        ('base', 'Базова (входить до створення меню)'),
        ('simple', 'Проста (Заморозка, напої, окремі товари)'),
    )
    SLUG_CHOICES = (
        ('garnir', 'Гарнір'),
        ('main', 'Друга страва'),
        ('soup', 'Суп'),
        ('salad', 'Салат'),
        ('other', 'Інше / Прості товари'),
    )

    name = models.CharField(max_length=100, verbose_name="Назва категорії")
    slug = models.CharField(
        max_length=20,
        choices=SLUG_CHOICES,
        default='other',
        verbose_name="Тип страви для розрахунку сетів"
    )
    category_type = models.CharField(max_length=10, choices=CATEGORY_TYPES, default='base',
                                     verbose_name="Тип категорії")

    class Meta:
        verbose_name = "Категорія"
        verbose_name_plural = "Категорії"

    def __str__(self):
        type_str = "Базова" if self.category_type == 'base' else "Проста"
        return f"{self.name} [{self.get_slug_display()}]"


class Product(models.Model):
    category = models.ForeignKey(
        FoodCategory,
        on_delete=models.CASCADE,
        related_name='products',
        verbose_name="Категорія",
        null=True,
        blank=True
    )
    title = models.CharField(max_length=200, verbose_name="Назва страви")
    description = models.TextField(blank=True, default="", verbose_name="Опис")
    price = models.DecimalField(max_digits=8, decimal_places=2, default=0.00, verbose_name="Стандартна ціна (€)")
    extra_price = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        default=0.00,
        verbose_name="Ціна, якщо додається до сформованого меню (€)"
    )
    weight_or_portion = models.CharField(max_length=100, blank=True, default="", verbose_name="Вага / Порція")
    image = models.ImageField(upload_to='products/', blank=True, null=True, verbose_name="Фотографія страви")

    class Meta:
        verbose_name = "Товар / Страва"
        verbose_name_plural = "Товари та Страви"

    def __str__(self):
        return self.title


class CartItem(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='cart_items')
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)

    class Meta:
        verbose_name = "Елемент кошика"
        verbose_name_plural = "Елементи кошика"

    def __str__(self):
        return f"{self.product.title} (x{self.quantity})"


class Order(models.Model):
    STATUS_CHOICES = (
        ('pending', 'Очікує підтвердження'),
        ('confirmed', 'Прийнято'),
        ('canceled', 'Скасовано'),
    )

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='orders')
    address = models.CharField(max_length=255, verbose_name="Адреса")
    phone = models.CharField(max_length=50, verbose_name="Телефон")
    delivery_time = models.CharField(max_length=100, verbose_name="Бажаний час")
    estimated_delivery_time = models.CharField(max_length=100, blank=True, null=True, verbose_name="Орієнтовний час доставки від адміна")
    comment = models.CharField(max_length=500, blank=True, null=True, default="", verbose_name="Коментар")
    total_price = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, verbose_name="Сума")
    payment_method = models.CharField(max_length=20, default='cash', verbose_name="Метод оплати")
    selected_card = models.ForeignKey(PaymentCard, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Обрана картка")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', verbose_name="Статус")
    cancel_reason = models.TextField(blank=True, null=True, verbose_name="Причина скасування")
    is_dismissed = models.BooleanField(default=False, verbose_name="Приховано користувачем")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Створено")

    class Meta:
        verbose_name = "Замовлення"
        verbose_name_plural = "Замовлення"

    def __str__(self):
        return f"Замовлення #{self.id} — {self.user.username}"


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    price = models.DecimalField(max_digits=8, decimal_places=2, default=0.00)
    quantity = models.PositiveIntegerField(default=1)

    class Meta:
        verbose_name = "Позиція замовлення"
        verbose_name_plural = "Позиції замовлення"


class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    phone = models.CharField(max_length=50, blank=True, default="")
    is_regular_customer = models.BooleanField(default=False, verbose_name="Постійний клієнт")

    class Meta:
        verbose_name = "Профіль користувача"
        verbose_name_plural = "Профілі користувачів"

    def __str__(self):
        return self.user.username