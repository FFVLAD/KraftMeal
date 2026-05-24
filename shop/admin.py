from django.contrib import admin
from .models import Product, ProductImage, CartItem, GenderCategory, SizeCategory

class ProductImageInline(admin.TabularInline):
    model = ProductImage
    extra = 7

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('title', 'price')
    inlines = [ProductImageInline]
    filter_horizontal = ('genders', 'sizes')

admin.site.register(GenderCategory)
admin.site.register(SizeCategory)
admin.site.register(CartItem)