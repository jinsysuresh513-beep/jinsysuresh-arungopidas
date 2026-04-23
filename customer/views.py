import uuid

from django.shortcuts import render,redirect,get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from core.models import *
from seller.models import *
from customer.models import *
from django.contrib.auth import get_user_model
from django.contrib.auth import login
from django.db.models import Q
from django.db import transaction
import razorpay
from django.conf import settings
User = get_user_model()


# Create your views here.
def home_view(request):
    product = Product.objects.filter(approval_status="APPROVED").prefetch_related("images")
    search = request.GET.get("search", "")
    if search:
        product = product.filter(Q(name__icontains=search))
    category = Category.objects.all()
    return render(request, 'customer/home.html', {"products": product, "categories": category, "search": search})

def customer_register(request):
    if request.method == "POST":
        first_name = request.POST.get("first_name")
        last_name = request.POST.get("last_name")
        email = request.POST.get("email")
        phone = request.POST.get("phone_number")
        password = request.POST.get("password")
        confirm_password = request.POST.get("confirm_password")
        profile_image = request.FILES.get("profile_image")

        if not first_name or not email or not password:
            messages.error(request, "All fields are required")
            return redirect("customer_register")

        email = email.strip().lower()

        if password != confirm_password:
            messages.error(request, "Passwords do not match")
            return redirect("customer_register")

        if User.objects.filter(email=email).exists():
            messages.error(request, "Email already exists")
            return redirect("customer_register")

        if phone and User.objects.filter(phone_number=phone).exists():
            messages.error(request, "Phone number already exists")
            return redirect("customer_register")

        try:
            user = User.objects.create_user(
                username=email,
                email=email,
                password=password,
                first_name=first_name,
                last_name=last_name,
            )
            user.role = "CUSTOMER"
            user.phone_number = phone
            if profile_image:
                user.profile_image = profile_image
            user.save()
            print('hloo')
            messages.success(request, "Account created successfully")
            return redirect("login")
        except Exception:
            messages.error(request, "Something went wrong")
            return redirect("customer_register")
    return render(request, "customer/customer_register.html")



@login_required
def customerprofile(request):
    user=request.user
    if user.role !="CUSTOMER":
        return redirect("login")
    return render(request,'customer/profile.html',{"user":user})

def productlist(request):
    sort= request.GET.get("sort")
    product=Product.objects.filter(approval_status="APPROVED").prefetch_related("images")
    if sort == "newest":
        product=product.order_by("-created_at")
    elif sort == "low":
        product=product.order_by("selling_price")
    elif sort == "high":
        product=product.order_by("-selling_price")
    return render(request,"customer/productlist.html",{"products":product})

def productcollection(request):
    return render(request,"customer/productcollection.html")

def productcategory(request):
    return render(request,"customer/productcategory.html")


def singleproduct(request,id):
    product=Product.objects.get(id=id)
    return render(request,"customer/singleproduct.html",{"product":product})
@login_required
def addcart(request,id):
    user=request.user
    product=Product.objects.get(id=id)
    cart,created=Cart.objects.get_or_create(user=user)
    
    try:
       cartitem=CartItem.objects.get(cart=cart,product=product)
       cartitem.quantity+=1
       cartitem.save()
    except:
        cartitem=CartItem.objects.create(
            cart=cart,
            product=product,
            quantity=1,
            price_at_time=product.selling_price
        )
    return redirect("cartview")
@login_required
def cartview(request):
    user=request.user
    cartitem=CartItem.objects.filter(cart__user=user)
    return render(request,"customer/cart.html",{"cartitems":cartitem})

@login_required
def removecart(request,id):
    user=request.user
    CartItem.objects.filter(
        id=id,
        cart__user=user,).delete()
    return redirect("cartview")

@login_required
def wishlist(request,id):
    user=request.user
    product=Product.objects.get(id=id)
    wishlist,created=Wishlist.objects.get_or_create(user=user)
    wishlistitem= WishlistItem.objects.filter(
        wishlist=wishlist,
        product=product
        ).first()
    if not wishlistitem:
        WishlistItem.objects.create(
            wishlist=wishlist,
            product=product
        )

    return redirect("wishlistview")
@login_required   
def wishlistview(request):
    user=request.user
    wishlistitem=WishlistItem.objects.filter(wishlist__user=user).distinct()
    return render(request,"customer/wishlist.html",{"wishlistitems":wishlistitem})

@login_required
def removewishlist(request,id):
    user=request.user
    WishlistItem.objects.filter(
        id=id,
        wishlist__user=user).delete()
    return redirect("wishlistview")


@login_required
def customer_address(request):
    user=request.user

    if request.method == "POST":
        full_name = request.POST.get("full_name")
        phone_number = request.POST.get("phone_number")
        pincode = request.POST.get("pincode")
        locality = request.POST.get("locality")
        house_info = request.POST.get("house_info")
        city = request.POST.get("city")
        state = request.POST.get("state")
        country = request.POST.get("country")
        landmark = request.POST.get("landmark")
        address_type = request.POST.get("address_type")
        is_default = request.POST.get("is_default") == "on"

        Address.objects.create(
            user=user,
            full_name=full_name,
            phone_number=phone_number,
            pincode=pincode,
            locality=locality,
            house_info=house_info,
            city=city,
            state=state,
            country=country,
            landmark=landmark,
            address_type=address_type,
            is_default=is_default
        )
        return redirect("saved_address")
    address=Address.objects.filter(user=user)
    return render(request,"customer/address.html",{"address":address})


@login_required
def savedaddress(request):
    user=request.user
    if request.method == "POST":
        address_id=request.POST.get("address_id")
        address=Address.objects.get(id=address_id, user=user)
        address.is_default=True
        address.save()
    addresses=Address.objects.filter(user=user)
    return render(request,'customer/saved_address.html',{'address':addresses})

@login_required
def deleteaddress(request,id):
    user=request.user
    Address.objects.filter(
        id=id,
        user=user).delete()
    return redirect("saved_address")


@login_required
def editaddress(request,id):
    user=request.user
    address=Address.objects.get(id=id,user=user)
    if request.method == "POST":

        address.full_name = request.POST.get("full_name")
        address.phone_number = request.POST.get("phone_number")
        address.pincode = request.POST.get("pincode")
        address.locality = request.POST.get("locality")
        address.house_info = request.POST.get("house_info")
        address.city = request.POST.get("city")
        address.state = request.POST.get("state")
        address.country = request.POST.get("country")
        address.landmark = request.POST.get("landmark")
        address.address_type = request.POST.get("address_type")
        address.save()
        return redirect("saved_address")
    return render(request,'customer/address.html',{"address":address})




@login_required
def checkout(request):
    user = request.user
    cart_items = CartItem.objects.filter(cart__user=user).select_related("product")
    addresses = Address.objects.filter(user=user)
    total = sum(item.price_at_time * item.quantity for item in cart_items)
    primary_address = addresses.filter(is_default=True).first()
    if not primary_address and addresses.exists():
        primary_address = addresses.first()
    other_address = addresses.exclude(id=primary_address.id).first() if primary_address else None
    return render(request, "customer/checkout.html", {
        "cart": cart_items,
        "total": total,
        "addresses": addresses,
        "primary_address": primary_address,
        "other_address": other_address,
        "has_addresses": addresses.exists(),
    })
    
@login_required
def proceedcheckout(request):
    if request.method == "POST":
        user = request.user
        cart_items = CartItem.objects.filter(cart__user=user).select_related("product")
        if not cart_items.exists():
            return redirect('cartview')
        payment_method = request.POST.get("payment_method")
        address_id = request.POST.get("address_id")
        shipping_address = get_object_or_404(Address, id=address_id, user=user)

        if payment_method == "COD":
            with transaction.atomic():
                total = sum(item.price_at_time * item.quantity for item in cart_items)
                order = Order.objects.create(
                    user=user,
                    order_number=f"ORD-{uuid.uuid4().hex[:10].upper()}",
                    total_amount=total,
                      
                )
                for item in cart_items:
                    OrderItem.objects.create(
                        order=order,
                        product=item.product,
                        seller=item.product.seller,
                        quantity=item.quantity,
                        price_at_purchase=item.price_at_time,
                    )
                cart_items.delete()
            return redirect("ordersuccess", id=order.id)            
        elif payment_method == "ONLINE":
            total = sum(item.price_at_time * item.quantity for item in cart_items)

    client = razorpay.Client(
        auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET)
    )

    payment = client.order.create({
        "amount": int(total * 100),
        "currency": "INR",
        "payment_capture": 1
    })

    order = Order.objects.create(
        user=user,
        order_number=f"ORD-{uuid.uuid4().hex[:10].upper()}",
        total_amount=total,
        payment_method="ONLINE",
        payment_status="PENDING"
    )

    request.session["order_id"] = order.id

    context = {
        "razorpay_key": settings.RAZORPAY_KEY_ID,
        "amount": payment["amount"],
        "currency": payment["currency"],
        "order_id": payment["id"],
        "order": order
    }

    return render(request, "customer/razorpay_payment.html", context)


@login_required
def customer_dashboard(request):
    return render(request,"customer/dashboard.html")

#-----------------------------------------------------------------------
@login_required
def customerorder(request):
    user = request.user
    orders = Order.objects.filter(user=user).exclude(order_status="CANCELLED").prefetch_related("items")
    return render(request,"customer/order.html", {"orders": orders})

@login_required
def ordersuccess(request,id):
    user=request.user
    order=Order.objects.get(id=id,user=user)
    return render(request,"customer/ordersuccess.html",{"order":order})

@login_required
def cancelorder(request, id):
    user = request.user
    order = get_object_or_404(Order, id=id, user=user)
    if order.order_status in ["PENDING", "PROCESSING"]:
        order.order_status = "CANCELLED"
        order.save()
        messages.success(request, "Order cancelled successfully.")
    else:
        messages.error(request, "Order cannot be cancelled at this stage.")
    return redirect("customer_order")

@login_required
def customerwishlist(request):
    return render(request,"customer/wishlist.html")

@login_required
def customersettings(request):
    return render(request,"customer/settings.html")
#----------------------------------------------
@login_required
def electronic(request):
    return render(request,"customer/electronics.html")
@login_required
def handbag(request):
    return render(request,"customer/handbag.html")
@login_required
def footwear(request):
    return render(request,"customer/footwear.html")
