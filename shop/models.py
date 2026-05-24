from django.db import models
from django.contrib.auth.models import User


class GenderCategory(models.Model):
    name = models.CharField(max_length=50, unique=True, verbose_name="Категория пола (Hombre/Mujer)")

    def __str__(self):
        return self.name


class SizeCategory(models.Model):
    name = models.CharField(max_length=10, unique=True, verbose_name="Размер (XS, S, M...)")

    def __str__(self):
        return self.name


class Product(models.Model):
    title = models.CharField(max_length=200, verbose_name="Название товара")
    price = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Цена (USD)")
    image_url = models.URLField(max_length=500, verbose_name="Главное фото товара (Ссылка)")
    description = models.TextField(blank=True, verbose_name="Описание товара")


    genders = models.ManyToManyField(GenderCategory, related_name="products", verbose_name="Пол")
    sizes = models.ManyToManyField(SizeCategory, related_name="products", verbose_name="Доступные размеры", blank=True)

    def __str__(self):
        return self.title


class ProductImage(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="additional_images")
    image_url = models.URLField(max_length=500, verbose_name="Дополнительное фото (Ссылка)")

    def __str__(self):
        return f"Фото для {self.product.title}"


class CartItem(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='cart')
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    added_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} - {self.product.title}"