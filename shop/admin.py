from django.contrib import admin
from .models import Product, FoodCategory, CartItem, Order, OrderItem, UserProfile, StoreSettings


admin.site.register(FoodCategory)
admin.site.register(Product)
admin.site.register(CartItem)
admin.site.register(Order)
admin.site.register(OrderItem)
admin.site.register(UserProfile)
admin.site.register(StoreSettings)