from django.contrib import admin
from django.db.models import Count, Sum
from django.db.models.functions import TruncMonth

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


@admin.register(StoreSettings)
class StoreSettingsAdmin(admin.ModelAdmin):
    list_display = ('menu_price', 'admin_telegram_ids')


@admin.register(PaymentCard)
class PaymentCardAdmin(admin.ModelAdmin):
    list_display = ('title', 'card_number', 'is_active')
    list_editable = ('is_active',)


@admin.register(FoodCategory)
class FoodCategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'category_type')
    list_filter = ('category_type',)


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('title', 'category', 'price', 'extra_price', 'weight_or_portion')
    list_filter = ('category', 'category__category_type')
    search_fields = ('title', 'description')


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'total_price', 'payment_method', 'selected_card', 'status', 'created_at')
    list_filter = ('status', 'payment_method', 'created_at')
    search_fields = ('user__username', 'phone', 'address')
    inlines = [OrderItemInline]


admin.site.register(CartItem)
admin.site.register(OrderItem)
admin.site.register(UserProfile)


# --- Бухгалтерія (Proxy Model) ---

class AccountingProxy(Order):
    class Meta:
        proxy = True
        verbose_name = "📊 Бухгалтерія (Звіт)"
        verbose_name_plural = "📊 Бухгалтерія (Звіти)"


@admin.register(AccountingProxy)
class AccountingAdmin(admin.ModelAdmin):
    change_list_template = 'admin/accounting_change_list.html'

    def changelist_view(self, request, extra_context=None):
        response = super().changelist_view(request, extra_context=extra_context)

        try:
            qs = response.context_data['cl'].queryset
        except (AttributeError, KeyError):
            return response

        client_monthly_stats = (
            qs.annotate(month=TruncMonth('created_at'))
            .values('month', 'user__username', 'user__first_name', 'user__last_name')
            .annotate(
                total_orders=Count('id'),
                total_spent=Sum('total_price')
            )
            .order_by('-month', '-total_orders')
        )

        product_stats = (
            OrderItem.objects.filter(order__in=qs)
            .values('product__title')
            .annotate(total_quantity=Sum('quantity'))
            .order_by('-total_quantity')
        )

        extra_context = extra_context or {}
        extra_context['client_monthly_stats'] = client_monthly_stats
        extra_context['product_stats'] = product_stats

        return super().changelist_view(request, extra_context=extra_context)