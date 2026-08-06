from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('product/<int:product_id>/', views.product_detail, name='product_detail'),
    path('toggle_cart/<int:product_id>/', views.toggle_cart, name='toggle_cart'),
    path('checkout/', views.checkout, name='checkout'),
    path('order_success/<int:order_id>/', views.order_success, name='order_success'),
    path('dismiss_order/<int:order_id>/', views.dismiss_order, name='dismiss_order'),
    path('login/', views.login_view, name='login'),
    path('register/', views.register_view, name='register'),
    path('logout/', views.logout_view, name='logout'),
    path('profile/', views.profile_view, name='profile'),
    path('order/repeat/<int:order_id>/', views.repeat_order, name='repeat_order'),
]