from django.contrib import admin
from .models import Product, FoodCategory, CartItem, Order, OrderItem, UserProfile, StoreSettings


admin.site.register(FoodCategory)
admin.site.register(Product)
admin.site.register(CartItem)
admin.site.register(Order)
admin.site.register(OrderItem)
admin.site.register(UserProfile)
admin.site.register(StoreSettings)

from django.db.models import Count, Sum
from django.db.models.functions import TruncMonth



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