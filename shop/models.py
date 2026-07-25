from django.db import models
from django.contrib.auth.models import User

class FoodCategory(models.Model):
    name = models.CharField(max_length=100)

    def __str__(self):
        return self.name

class Product(models.Model):
    category = models.ForeignKey(FoodCategory, on_delete=models.CASCADE, related_name='products', null=True, blank=True)
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    price = models.DecimalField(max_length=10, decimal_places=2, max_digits=10)
    weight_or_portion = models.CharField(max_length=100, blank=True, null=True, default="")
    image = models.ImageField(upload_to='products/', blank=True, null=True)
    is_available = models.BooleanField(default=True)

    def __str__(self):
        return self.title

class CartItem(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)

    def get_total_price(self):
        return self.product.price * self.quantity

class Order(models.Model):
    STATUS_CHOICES = (
        ('pending', 'Очікує підтвердження'),
        ('confirmed', 'Прийнято / Готується'),
        ('delivered', 'Доставлено'),
        ('canceled', 'Відхилено'),
        ('dismissed', 'Приховано користувачем'),
    )

    PAYMENT_CHOICES = (
        ('cash', 'Готівка'),
        ('card', 'Картка'),
    )

    user = models.ForeignKey(User, on_delete=models.CASCADE)
    address = models.CharField(max_length=255)
    phone = models.CharField(max_length=50)
    delivery_time = models.CharField(max_length=100)
    comment = models.TextField(blank=True, null=True, default="")
    total_price = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    payment_method = models.CharField(max_length=10, choices=PAYMENT_CHOICES, default='cash')
    is_paid = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    cancel_reason = models.TextField(blank=True, null=True, verbose_name="Причина скасування")
    is_dismissed = models.BooleanField(default=False, verbose_name="Приховано користувачем")

    def __str__(self):
        return f"Замовлення #{self.id} - {self.user.username}"

class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    quantity = models.PositiveIntegerField(default=1)

    def get_total_price(self):
        return self.price * self.quantity

class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    phone = models.CharField(max_length=50, blank=True, null=True, default="")
    telegram_id = models.CharField(max_length=50, blank=True, null=True, default="")
    orders_count = models.PositiveIntegerField(default=0)
    is_regular_customer = models.BooleanField(default=False)

    def check_regular_status(self):
        if self.orders_count >= 3 and not self.is_regular_customer:
            self.is_regular_customer = True
            self.save()

class StoreSettings(models.Model):
    card_number = models.CharField(max_length=30, default="0000 0000 0000 0000", verbose_name="Номер картки для оплати")
    admin_telegram_ids = models.TextField(default="6253830673", help_text="Вказуйте Telegram ID адміністраторів через кому", verbose_name="ID адміністраторів Telegram")

    class Meta:
        verbose_name = "Налаштування магазину"
        verbose_name_plural = "Налаштування магазину"

    def get_admin_ids_list(self):
        return [i.strip() for i in self.admin_telegram_ids.split(',') if i.strip()]

    def __str__(self):
        return "Налаштування магазину"




