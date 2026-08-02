from django.contrib import admin
from django.db.models import Count, Sum
from django.db.models.functions import TruncMonth
from django.shortcuts import redirect
from django.urls import path
from django.contrib import messages

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


DEFAULT_MENU = {
    'САЛАТИ': [
        ('Грецький салат', 'Свіжі помідори, огірки, болгарський перець, листя салату, сир фета, чорні оливки та червона цибуля, заправлені оливковою олією й ароматними спеціями. Легкий, соковитий та ідеально доповнює обід.'),
        ('Салат зі свіжої капусти', 'Хрустка білокачанна капуста, морква та свіжа зелень із легкою олійною заправкою. Простий, корисний і дуже свіжий смак.'),
        ('Буряк з хроном', 'Відварений буряк, натуральний хрін та ароматні спеції. Класична українська закуска з яскравим смаком.'),
        ('Морква по-корейськи', 'Соковита морква, приготована за традиційним рецептом із часником, спеціями та ароматною олією. Пікантна й апетитна.')
    ],
    'СУПИ': [
        ('Український борщ зі сметаною', 'Наваристий домашній борщ із буряком, картоплею, капустою, морквою та томатами. Подається зі сметаною. Справжній смак української кухні.'),
        ('Зелений борщ зі сметаною', 'Домашній суп зі щавлем, картоплею, яйцем і свіжою зеленню. Подається зі сметаною та має приємний кислуватий смак.'),
        ('Овочевий суп', 'Легкий бульйон із картоплею, морквою, цибулею та сезонними овочами. Смачний, поживний і водночас легкий.'),
        ('Сирний суп з куркою', 'Ніжний сирний бульйон із шматочками курячого філе, картоплею та овочами. Легкий, ароматний і дуже ситний.'),
        ('Грибний крем-суп', 'Оксамитовий крем-суп із печериць та вершків, подається з хрусткими домашніми сухариками. Насичений грибний смак у кожній ложці.'),
        ('Окрошка', 'Освіжаючий холодний суп із овочами, яйцем, ковбасою та зеленню на кефірі або квасі. Ідеальний вибір у спекотний день.')
    ],
    'ОСНОВНІ СТРАВИ': [
        ('Гуляш', 'Ніжні шматочки м’яса, тушковані в ароматному томатному соусі з цибулею та спеціями. Ситна домашня страва.'),
        ('Домашня котлета', 'Соковита котлета з добірного фаршу зі спеціями та цибулею, обсмажена до рум’яної скоринки. Смак, знайомий з дитинства.'),
        ('Куряча відбивна', 'Ніжне куряче філе у хрусткій золотистій паніровці. Соковите всередині та апетитне зовні.'),
        ('Куряче стегно', 'Запечене куряче стегно з ароматними спеціями до золотистої скоринки. Соковите, ніжне та дуже ситне.'),
        ('Курка в сметанному соусі', 'Шматочки курячого філе, тушковані у вершково-сметанному соусі зі спеціями. Ніжна та ароматна страва.'),
        ('Печінка з цибулею', 'Куряча печінка, обсмажена з ріпчастою цибулею до м’якості. Домашня класика з насиченим смаком.'),
        ('Філе тунця', 'Соковите філе тунця, обсмажене до золотистої скоринки та приправлене ароматними спеціями. Легка й корисна рибна страва.'),
        ('Риба в сметанному соусі', 'Ніжне рибне філе у вершково-сметанному соусі зі спеціями та зеленню. Легкий і вишуканий смак.')
    ],
    'ГАРНІРИ': [
        ('Картопляне пюре', 'Повітряне картопляне пюре з вершковим маслом і молоком. Ніжний смак, що чудово поєднується з будь-якою основною стравою.'),
        ('Картопля по-домашньому', 'Запечена картопля з ароматними спеціями та зеленню, рум’яна зовні й м’яка всередині.'),
        ('Гречка', 'Розсипчаста гречана крупа, приготована до ідеальної текстури. Простий, корисний і поживний гарнір.'),
        ('Рис з овочами', 'Ароматний рис із морквою, кукурудзою, зеленим горошком та іншими овочами. Легкий і яскравий гарнір.'),
        ('Кус-кус', 'Ніжний кус-кус із сезонними овочами та ароматними спеціями. Легкий гарнір із насиченим смаком.')
    ]
}


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
    change_list_template = "admin/product_change_list.html"

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('seed-base-menu/', self.admin_site.admin_view(self.seed_base_menu), name='seed-base-menu'),
        ]
        return custom_urls + urls

    def seed_base_menu(self, request):
        created_categories = 0
        created_products = 0

        for cat_name, products in DEFAULT_MENU.items():
            category, cat_created = FoodCategory.objects.get_or_create(
                name=cat_name,
                defaults={'category_type': 'base'}
            )
            if cat_created:
                created_categories += 1

            for title, desc in products:
                _, prod_created = Product.objects.get_or_create(
                    category=category,
                    title=title,
                    defaults={
                        'description': desc,
                        'price': 0.00,
                        'extra_price': 0.00,
                        'weight_or_portion': ''
                    }
                )
                if prod_created:
                    created_products += 1

        self.message_user(
            request,
            f"✅ Успішно створено: категорій — {created_categories}, нових страв — {created_products}.",
            messages.SUCCESS
        )
        return redirect("..")


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