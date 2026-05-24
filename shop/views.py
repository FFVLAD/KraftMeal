from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from .models import Product, CartItem, GenderCategory


def index_view(request):

    gender_filter = request.GET.get('gender')
    search_query = request.GET.get('q')

    products = Product.objects.all()


    if gender_filter in ['Hombre', 'Mujer']:
        products = products.filter(genders__name=gender_filter)


    if search_query:
        products = products.filter(
            Q(title__icontains=search_query) | Q(description__icontains=search_query)
        )

    products = products.distinct()

    user_cart_ids = []
    cart_items = []
    cart_total = 0

    if request.user.is_authenticated:
        cart_items_query = CartItem.objects.filter(user=request.user).select_related('product')
        cart_items = [item.product for item in cart_items_query]
        user_cart_ids = [product.id for product in cart_items]
        cart_total = sum(product.price for product in cart_items)

    return render(request, 'shop/index.html', {
        'products': products,
        'user_cart_ids': user_cart_ids,
        'cart_items': cart_items,
        'cart_total': cart_total,
        'current_gender': gender_filter,
        'current_search': search_query or ''
    })


def product_detail_view(request, product_id):
    product = get_object_or_404(Product, id=product_id)

    all_images = [product.image_url] + [img.image_url for img in product.additional_images.all()]

    user_cart_ids = []
    if request.user.is_authenticated:
        user_cart_ids = CartItem.objects.filter(user=request.user).values_list('product_id', flat=True)

    return render(request, 'shop/product_detail.html', {
        'product': product,
        'all_images': all_images,
        'is_in_cart': product.id in user_cart_ids
    })


def register_view(request):
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect('index')
    else:
        form = UserCreationForm()
        form.fields['username'].help_text = ""
    return render(request, 'shop/auth.html', {'form': form, 'type': 'Registrarse'})


def login_view(request):
    if request.method == 'POST':
        form = AuthenticationForm(data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            return redirect('index')
    else:
        form = AuthenticationForm()
        form.fields['username'].help_text = ""
    return render(request, 'shop/auth.html', {'form': form, 'type': 'Iniciar Sesión'})


def logout_view(request):
    logout(request)
    return redirect('index')


@login_required
def toggle_cart_api(request, product_id):
    if request.method == 'POST':
        try:
            product = Product.objects.get(id=product_id)
            cart_item = CartItem.objects.filter(user=request.user, product=product).first()
            if cart_item:
                cart_item.delete()
                return JsonResponse({'status': 'removed'})
            else:
                CartItem.objects.create(user=request.user, product=product)
                return JsonResponse({'status': 'added'})
        except Product.DoesNotExist:
            return JsonResponse({'error': 'Producto no encontrado'}, status=404)
    return JsonResponse({'error': 'Solicitud no válida'}, status=400)