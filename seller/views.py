import re
from django.db.models import Q
from datetime import timedelta
from django.utils.timezone import now
from django.core.paginator import Paginator
from django.contrib.auth import update_session_auth_hash
from django.http import HttpResponse, JsonResponse
from django.contrib import messages
from django.shortcuts import render, redirect, get_object_or_404
from core.models import User
from seller.decorators import seller_required, new_seller_only
from django.contrib.auth.decorators import login_required
from django.core.validators import validate_email
from django.core.exceptions import ValidationError


from customer.models import Order
from .models import SellerProfile, SellerEditRequest
from .models import Product,ProductImage
from core.models import SubCategory,Category
from django.utils.text import slugify



def seller_register(request):
    if request.method == "POST":
        first_name = request.POST.get("first_name")
        last_name = request.POST.get("last_name")
        email = request.POST.get("email")
        phone_number = request.POST.get("phone_number")
        password = request.POST.get("password")
        confirm_password = request.POST.get("confirm_password")
        profile_image = request.FILES.get("profile_image")
        print(first_name, last_name, email, phone_number, password, confirm_password)
        try:
            validate_email(email)
        except ValidationError:
            return render(request, "seller/register.html", {"error": "Invalid email"})

        if not phone_number.isdigit() or len(phone_number) != 10:
            return render(request, "seller/register.html", {"error": "Enter valid 10-digit phone number"})

        if User.objects.filter(phone_number=phone_number).exists():
            return render(request,"seller/register.html",{"error":"phone number is already registered"})
        if password != confirm_password:
            return render(request, "seller/register.html", {"error": "Passwords do not match"})

        if User.objects.filter(username=email).exists() or User.objects.filter(email=email).exists():
            return render(request, "seller/register.html", {"error": " This email is already registered as a user."})

        user = User.objects.create_user(
            username=email.strip().lower(),
            email=email.strip().lower(),
            password=password,
            first_name=first_name,
            last_name=last_name,
            phone_number=phone_number,
            role="SELLER"
        )
        if profile_image:
            user.profile_image = profile_image
            user.save()
        messages.success(request, "Account created successfully! Please log in.")
        return redirect("login")

    return render(request, "seller/register.html")






@new_seller_only
@login_required
def seller_profile(request):

    seller = SellerProfile.objects.filter(user=request.user).first()

    if seller:

        if seller.status == "PENDING":
            return redirect("pending_approval")

        elif seller.status == "REJECTED":
            return redirect('approval_rejection')

        else:
            return redirect("seller_dashboard")

    if request.method == "POST":
        shop_name = request.POST.get("shop_name")
        category = request.POST.get("category")
        website = request.POST.get("website")
        description = request.POST.get("description")
        business_email = request.POST.get("business_email")
        gst_number = request.POST.get("gst_number")
        pan_number = request.POST.get("pan_number")
        bank_account_number = request.POST.get("bank_account_number")
        ifsc_code = request.POST.get("ifsc_code")
        business_address = request.POST.get("business_address")

        if not shop_name:
            return render(request, "seller/seller_profile.html", {
                "error": "Please fill all required fields"
            })
        base_slug = slugify(shop_name)
        slug = base_slug
        counter = 1

        while SellerProfile.objects.filter(shop_slug=slug).exists():
            slug = f"{base_slug}-{counter}"
            counter += 1

        seller = SellerProfile.objects.create(
            user=request.user,
            shop_name=shop_name,
            shop_slug=slug,
            category=category,
            website=website,
            description=description,
            business_email=business_email,
            gst_number=gst_number,
            pan_number=pan_number.upper(),
            bank_account_number=bank_account_number,
            ifsc_code=ifsc_code,
            business_address=business_address,
            status="PENDING"
        )
        if request.FILES.get("logo"):
            seller.logo = request.FILES.get("logo")
            seller.save()
        return redirect("pending_approval")

    categories = Category.objects.all()

    return render(request, "seller/seller_profile.html", { "categories": categories})





@seller_required
def seller_dashboard(request):
    seller=request.user.seller_profile
    products=Product.objects.filter(seller=seller)
    pending_product = products.filter(approval_status="PENDING").count()
    rejected_product = products.filter(approval_status="REJECTED").count()
    recent_products = products.filter(approval_status="APPROVED",).order_by("-created_at")
    low_stock = products.filter(approval_status="APPROVED",stock_quantity__lte = 15,stock_quantity__gt = 0).count()
    out_of_stock = products.filter(approval_status="APPROVED",stock_quantity=0).count()
    total_items = products.count()
    context={
        "seller":seller,
        "products":products,
        "total_items":total_items,
        "recent_products":recent_products,
        "pending_product":pending_product,
        "rejected_products":rejected_product,
        "out_of_stock":out_of_stock,
        "low_stock":low_stock,
        "review_queue": products.filter(approval_status="PENDING")[:3],
    }
    return render(request, "seller/seller_dashboard.html",context)


@seller_required
def view_seller_profile(request):
    seller=request.user.seller_profile
    products=Product.objects.filter(seller=seller)
    total_items=products.count()
    pending_product=products.filter(approval_status="PENDING").count()
    low_stock = products.filter(stock_quantity__lte=15,stock_quantity__gt=0).count()
    out_of_stock = products.filter(stock_quantity=0).count()
    recent_products= products.order_by("-created_at")
    cooldown_days = 7
    cooldown_fields = {}

    approved_requests = SellerEditRequest.objects.filter(
        seller = seller,
        status = "APPROVED"
    ).order_by("-last_updated_at")

    for req in approved_requests:
        if req.last_updated_at:
            diff = now() - req.last_updated_at

            if diff < timedelta(days=cooldown_days):
                remaining_days = max(1, cooldown_days - diff.days)
                cooldown_fields[req.field_name] = remaining_days

    reject_cooldown_days = 2

    rejected_qs = SellerEditRequest.objects.filter(
        seller=seller,
        status="REJECTED"
    ).order_by("-created_at")

    for req in rejected_qs:
        diff = now() - req.created_at

        if diff < timedelta(days=reject_cooldown_days):
            remaining_days = max(1, reject_cooldown_days - diff.days)

            if req.field_name not in cooldown_fields:
                cooldown_fields[req.field_name] = remaining_days

    rejected_requests = {}

    for req in SellerEditRequest.objects.filter(
            seller=seller,
            status="REJECTED"
    ).order_by("-created_at"):
        if req.field_name not in rejected_requests:
            rejected_requests[req.field_name] = req.rejection_reason

    pending_requests = list(
        SellerEditRequest.objects.filter(
            seller=seller,
            status="PENDING"
        ).values_list("field_name", flat=True)
    )


    context={
        "user":request.user,
        "seller": seller,
        "total_items": total_items,
        "pending_product": pending_product,
        "low_stock": low_stock,
        "out_of_stock": out_of_stock,
        "recent_products": recent_products,
        "pending_requests":pending_requests,
        "rejected_requests":rejected_requests,
        "cooldown_fields":cooldown_fields
    }
    return render(request,"seller/seller_profile_view.html",context)






@seller_required
def seller_profile_edit(request):
    seller=request.user.seller_profile

    if seller.status !="APPROVED":
        return redirect("pending_approval")

    if request.method == "POST":
        shop_name = request.POST.get('shop_name')
        website = request.POST.get('website')
        category = request.POST.get('category')
        business_address=request.POST.get('business_address')
        business_email=request.POST.get('business_email')

        if shop_name:
            seller.shop_name = shop_name

        if website:
            seller.website = website

        if category:
            seller.category = category

        if business_address:
            seller.business_address = business_address

        if business_email:
            seller.business_email = business_email

        if request.FILES.get("logo"):
            seller.logo = request.FILES.get("logo")

        seller.save()

        user = request.user
        first_name = request.POST.get('first_name')
        last_name = request.POST.get('last_name')
        phone_number=request.POST.get('phone_number')

        if first_name :
            user.first_name = first_name

        if last_name :
            user.last_name = last_name

        if phone_number :
            if not phone_number.isdigit or len(phone_number) != 10 :
                messages.error("please enter a valid phone number")

        user.phone_number = phone_number


        if request.FILES.get('profile_image'):
            user.profile_image = request.FILES.get('profile_image')

        user.save()

        return redirect('view_profile')

    categories = Category.objects.all()
    context={
        "seller": seller,
        "categories":categories,
    }
    return render(request,'seller/edit_profile.html',context)





@login_required
def pending_approval(request):
    seller=request.user.seller_profile
    if seller.status == "APPROVED":
        return redirect('seller_dashboard')
    return render(request,'seller/Seller_profile_review.html',{"seller":seller})





@seller_required
def add_product(request):

    seller =SellerProfile.objects.get(user=request.user)

    if request.method == "POST":

        name = request.POST.get("name")
        description = request.POST.get("description")
        brand = request.POST.get("brand")
        model_number = request.POST.get("model_number")
        subcategory_id = request.POST.get("subcategory")
        sku = request.POST.get("sku")
        price = request.POST.get("price")
        selling_price=request.POST.get('selling_price')
        cost_price=request.POST.get('cost_price')
        tax_percentage=request.POST.get('tax_percentage',5)
        stock_quantity = request.POST.get("stock_quantity")
        is_returnable = True if request.POST.get("is_returnable") == 'on' else False
        is_cancellable = True if request.POST.get("is_cancellable") == 'on' else False
        return_days=request.POST.get("return_days",5)

        if not name :
            messages.error(request,"product name required")
            return redirect('add_product')

        if not subcategory_id:
               messages.error( request,"Please select a category and subcategory")
               return redirect('add_product')

        if  float(selling_price) >  float(price):
            messages.error(request,"selling price cannot be greater than mrp")
            return redirect('add_product')

        if not stock_quantity.isdigit() or int(stock_quantity) < 0:
            messages.error(request, "Enter a valid stock quantity")
            return redirect("add_product")

        if not stock_quantity.isdigit() or int(stock_quantity) < 0:
            messages.error(request, "Enter a valid stock quantity")
            return redirect("add_product")

        if float(tax_percentage) < 0 or float(tax_percentage) > 100:
            messages.error(request, "Enter a valid tax percentage")
            return redirect("add_product")

        if not sku:
            messages.error(request,"sku field is empty")
            return redirect('add_product')

        if Product.objects.filter(sku_code=sku).exists():
           messages.error(request,"sku code already exists")
           return redirect('add_product')

        subcategory =get_object_or_404(SubCategory,id=subcategory_id)

        slug = slugify(name + "-" + sku)

        if Product.objects.filter(slug=slug).exists():
            messages.error(request, "Slug already exists")
            return redirect('add_product')

        images = request.FILES.getlist("images")

        if not images:
            messages.error(request, "please add at least one image")
            return redirect('add_product')


        product = Product.objects.create(
            seller=seller,
            subcategory=subcategory,
            name=name,
            slug=slug,
            description=description,
            brand=brand,
            model_number=model_number,
            sku_code=sku,
            price=price,
            selling_price=selling_price,
            cost_price=cost_price,
            stock_quantity=stock_quantity,
            tax_percentage=tax_percentage,
            is_returnable=is_returnable,
            is_cancellable=is_cancellable,
            return_days=return_days,
            submission_type="NEW",
            approval_status="PENDING",
        )



        for index, img in enumerate(images)  :
            ProductImage.objects.create(
                product=product,
                image=img,
                is_primary = True if (index == 0 )  else False

            )
        messages.success(request, "Your product is under review and will be updated soon")
        print(request.FILES)
        return redirect("inventory_page")

    categories = Category.objects.all()
    return render(request, "seller/add_product.html", {"categories": categories})


@seller_required
def inventory_page(request):
    seller=request.user.seller_profile
    products = Product.objects.filter(seller=seller).prefetch_related('images').order_by("-created_at")
    active_products=products.filter(approval_status="APPROVED").count()
    pending_products=products.filter(approval_status="PENDING").count()
    low_stock=products.filter(approval_status="APPROVED",stock_quantity__lte=15 , stock_quantity__gt=0).count()
    out_of_stock=products.filter(approval_status="APPROVED",stock_quantity=0).count()
    hidden_products=products.filter(approval_status="APPROVED",is_active=False).count()
    search_keyword=request.GET.get('q')
    status_filter = request.GET.get('status')

    if status_filter == 'active':
        products = products.filter(approval_status="APPROVED", is_active=True, stock_quantity__gt=0)
    elif status_filter == 'low_stock':
        products = products.filter(approval_status="APPROVED", stock_quantity__lte=15, stock_quantity__gt=0)
    elif status_filter == 'out_of_stock':
        products = products.filter(approval_status="APPROVED", stock_quantity=0)
    elif status_filter == 'inactive':
        products = products.filter(is_active=False)

    if search_keyword:
        products = products.filter(
            Q( name__icontains=search_keyword) |
            Q(sku_code__icontains=search_keyword)
        )

    for product in products:
        primary = product.images.filter(is_primary=True).first()
        if primary:
            product.first_image = primary.image
        else:
            first = product.images.first()
            product.first_image = first.image if first else None

    paginator = Paginator(products,6)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    context={
        "seller":seller,
        "products": page_obj,
        "active_products": active_products,
        "pending_products": pending_products,
        "hidden_products":hidden_products,
        "low_stock":low_stock,
        "out_of_stock": out_of_stock,
        "page_obj":page_obj,

    }
    return render(request, "seller/inventory_page.html",context)





@seller_required
def edit_product(request,id):

    product=get_object_or_404(Product,id=id,seller=request.user.seller_profile)

    if request.method =="POST":
        product.name = request.POST.get('name')
        product.description=request.POST.get('description')
        product.brand = request.POST.get('brand')
        product.model_number = request.POST.get('model_number')

        subcategory_id = request.POST.get("subcategory")

        if subcategory_id:
            product.subcategory = SubCategory.objects.get(id=subcategory_id)

        if request.FILES.get("image"):
            product.image=request.FILES.get("image")

        product.sku_code = request.POST.get('sku')

        if Product.objects.filter(sku_code = product.sku_code).exclude(id=product.id).exists():
            messages.error(request,f"{product.sku_code} already exists")
            return redirect('edit_product',id=product.id)

        product.stock_quantity  = request.POST.get('stock_quantity')

        product.slug = slugify(product.name + "-" + product.sku_code)

        if product.approval_status == "APPROVED":
            product.submission_type = "EDIT"
            product.approval_status = "PENDING"

        if Product.objects.filter(slug=product.slug).exclude(id=product.id).exists():
            messages.error(request,f"{product.slug} already exists")
            return redirect('edit_product',id=product.id)


        product.price = request.POST.get('price')
        product.selling_price = request.POST.get('selling_price')
        product.cost_price = request.POST.get('cost_price')
        product.tax_percentage = request.POST.get('tax_percentage')or 5
        product.is_returnable =  request.POST.get("is_returnable") == 'on'
        product.return_days = request.POST.get('return_days') or 7
        product.is_cancellable = request.POST.get("is_cancellable") == 'on'
        product.product_rejection_reason = None


        product.save()

        new_image=request.FILES.getlist("images")
        for img in new_image:
            ProductImage.objects.create(
                product=product,
                image=img,
                is_primary=False
            )

        if not product.images.filter(is_primary=True).exists():
            first_image = product.images.first()
            if first_image:
                first_image.is_primary = True
                first_image.save()

        return redirect('inventory_page')
    categories = Category.objects.all()
    subcategories=SubCategory.objects.all()
    data={
        "product":product,
        "categories":categories,
        "subcategories":subcategories,
    }
    return render(request,'seller/edit_product.html',data)

@seller_required
def primary_image(request,id):
    image=get_object_or_404(
        ProductImage,
        id=id,
        product__seller=request.user.seller_profile
    )

    product=  image.product
    product.images.update(is_primary=False)

    image.is_primary = True
    image.save()

    return redirect('edit_product',id = product.id)

@seller_required
def delete_product_image(request,id):
    image = get_object_or_404(
        ProductImage,
        id=id,
        product__seller= request.user.seller_profile
    )

    product_id = image.product.id
    image.delete()

    return redirect('edit_product', id = product_id)


@seller_required
def delete_product(request,id):
    data=Product.objects.get(id=id,seller=request.user.seller_profile)
    data.delete()
    return redirect('inventory_page')



@seller_required
def analytics_page(request):
    return render(request,"seller/analytics_page.html")



@seller_required
def order_page(request):
    order = Order.objects.filter(seller=request.user.seller_profile)
    return render(request,"seller/order_page.html",{'orders':order})



@seller_required
def product_preview(request,id,slug):
    seller=request.user.seller_profile

    product=get_object_or_404(
        Product,
        id=id,
        seller=seller,
        slug=slug
    )

    images = product.images.all()
    primary_image = images.filter(is_primary=True).first()
    if not primary_image:
        primary_image = images.first()
    context={
        "seller":seller,
        "product":product,
        "images":images,
        "primary_image":primary_image,
    }
    return render(request,"seller/product_preview.html",context)



@seller_required
def pending_products(request):
    seller=request.user.seller_profile
    pending_product=Product.objects.filter(seller=seller,approval_status="PENDING").order_by("-created_at")
    total_pending=pending_product.count()
    search_keyword=request.GET.get("q")
    if search_keyword:
        products = pending_product.filter(
            Q(name__icontains=search_keyword) |
            Q(sku_code__icontains=search_keyword)
        )
    newly_added = pending_product.filter(submission_type="NEW")
    edited_products = pending_product.filter(submission_type="EDIT")

    new_count = newly_added.count()
    edit_count = edited_products.count()
    paginator = Paginator(pending_product, 8)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    for qs in [newly_added, edited_products, page_obj]:
        for product in qs:
            primary = product.images.filter(is_primary=True).first()
            if primary:
                product.first_image = primary.image
            else:
                first = product.images.first()
                product.first_image = first.image if first else None

    context = {
        "pending_product": page_obj,
            "page_obj": page_obj,
            "newly_added": newly_added,
            "edited_products": edited_products,
            "total_pending": total_pending,
            "new_count": new_count,
            "edit_count": edit_count,
         }
    return render(request,"seller/pending_products.html",context)




@seller_required
def rejected_products(request):
    seller=request.user.seller_profile
    product=Product.objects.filter(seller=seller,approval_status='REJECTED')
    rejected_count = product.count()
    sort = request.GET.get("sort")
    if sort == "oldest":
        product = product.order_by("created_at")
    else:
        product = product.order_by("-created_at")

    search_keyword = request.GET.get("q")
    if search_keyword:
        product = product.filter(
            Q(name__icontains= search_keyword) |
            Q(sku_code__icontains= search_keyword)
        )

    paginator = Paginator(product, 8)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    for p in page_obj:
        primary = p.images.filter(is_primary=True).first()
        p.first_image = primary.image if primary else None

    context={
        "products": page_obj,
        "page_obj": page_obj,
        "rejected_count": rejected_count
    }

    return render(request,"seller/rejected_products.html",context)

@seller_required
def product_rejection_view(request,id,slug):
    seller = request.user.seller_profile
    product = get_object_or_404(
        Product,
        id=id,
        slug=slug,
        seller=seller,
        approval_status="REJECTED"
    )
    primary = product.images.filter(is_primary=True).first()
    first_image = primary.image if primary else (
        product.images.first().image if product.images.exists() else None
    )

    rejection_reasons = []

    if hasattr(product, "rejection_reason") and product.rejection_reason:
        rejection_reasons.append({
            "title": "Rejection Reason",
            "description": product.rejection_reason
        })
    else:
        rejection_reasons.append({
            "title": "Needs Review",
            "description": "This listing requires updates before approval."
        })
    context = {
        "product": product,
        "first_image": first_image,
        "rejection_reasons": rejection_reasons,
    }
    return render( request,"seller/rejected_product_preview.html",context)


@seller_required
def coupon_page(request):
    return HttpResponse("coupons page")




@seller_required
def product_management(request):
    seller=request.user.seller_profile
    products = Product.objects.filter(seller=seller).order_by("-created_at")
    active_products=products.filter(approval_status = "APPROVED").count()
    pending_product = products.filter(approval_status = "PENDING").count()
    rejected_products = products.filter(approval_status = "REJECTED").count()
    search_keyword = request.GET.get('q')

    if search_keyword:
        products = products.filter(
            Q(name__icontains=search_keyword) |
            Q(sku_code__icontains=search_keyword)
        )
    status = request.GET.get("status")

    if status == "active":
        products = products.filter(approval_status="APPROVED")

    elif status == "pending":
        products = products.filter(approval_status="PENDING")

    elif status == "rejected":
        products = products.filter(approval_status="REJECTED")

    paginator = Paginator(products, 6)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    context={
        "seller": seller,
        "products": page_obj,
        "page_obj": page_obj,
        "active_products": active_products,
        "pending_product": pending_product,
        "rejected_products": rejected_products,
    }
    return render(request,"seller/product_management.html",context)



@ seller_required
def load_subcategories(request, id):
    sub_category = SubCategory.objects.filter(category_id=id).values('id', 'name')
    return JsonResponse(list(sub_category), safe=False)




@seller_required
def change_password(request):

    if request.method == "POST":
        password=request.POST.get("current_password").strip()
        new_password = request.POST.get("new_password")
        confirm_password = request.POST.get("confirm_password")
        print(request.POST)
        user=request.user
        if not user.check_password(password):
            messages.error(request, "Current password is incorrect", extra_tags="password")
            return redirect('view_profile')

        if new_password != confirm_password:
            messages.error(request,"password didn't match", extra_tags="password")
            return redirect('view_profile')


        if len(new_password) < 8 :
            messages.error(request, "password must be at least 8 characters long ", extra_tags="password")
            return redirect('view_profile')


        if not re.search(r"[A-Z]",new_password):
            messages.error(request,"Password must include at least on Uppercase Character", extra_tags="password")
            return redirect('view_profile')


        if not re.search(r"[a-z]",new_password):
            messages.error(request,"Password must include at least on lowercase character", extra_tags="password")
            return redirect('view_profile')

        if not re.search(r"[0-9]", new_password):
            messages.error(request, "Password must include at least one number", extra_tags="password")
            return redirect('view_profile')

        if not re.search(r"[!@#*]", new_password):
            messages.error(request, "Password must include at least one symbol (! @ # *)", extra_tags="password")
            return redirect('view_profile')

        if re.search(r"[<>{}\[\]/\\\"'$; ]", new_password):
            messages.error(request, "Password contains invalid characters", extra_tags="password")
            return redirect('view_profile')

        if user.check_password(new_password):
            messages.error(request, "New password cannot be same as old password", extra_tags="password")
            return redirect('view_profile')

        user.set_password(new_password)
        user.save()
        print(user)

        update_session_auth_hash(request,user)

        messages.success(request, "Password updated successfully", extra_tags="password")
        return redirect('view_profile')

    return redirect('view_profile')



@seller_required
def request_edit_field(request):
    if request.method == "POST":

        seller = request.user.seller_profile
        field_name=request.POST.get("field_name")
        new_value=request.POST.get("new_value")
        reason=request.POST.get("reason")
        print(request.POST)

        if not new_value or not reason:
            messages.error(request, "All fields are required", extra_tags=field_name)
            return redirect("view_profile")

        if SellerEditRequest.objects.filter(seller=seller,field_name=field_name,status="PENDING").exists():
            messages.error(request,"Request already pending for this field",extra_tags=field_name)
            return redirect('view_profile')

        cooldown_days = 7
        reject_cooldown_days= 2

        last_rejected = SellerEditRequest.objects.filter(
            seller=seller,
            field_name=field_name,
            status = "REJECTED"
        ).order_by("-created_at").first()

        if last_rejected:
            diff = now() - last_rejected.created_at

            if diff < timedelta(days=reject_cooldown_days):
                remaining_days = max(1,reject_cooldown_days - diff.days)
                messages.error(request,f"You can resubmit after {remaining_days} day(s)",extra_tags=field_name)
                return redirect("view_profile")


        last_approved = SellerEditRequest.objects.filter(
            seller = seller,
            field_name = field_name,
            status = "APPROVED"
        ).order_by("-last_updated_at").first()

        if last_approved and last_approved.last_updated_at:
            if now() - last_approved.last_updated_at < timedelta(days=cooldown_days):
                remaining_days = max(1,cooldown_days - (now() - last_approved.last_updated_at).days)
                messages.error(request,f"you can update this field after {remaining_days} day(s)",extra_tags=field_name)
                return redirect('view_profile')

        current_value = getattr(seller,field_name)

        SellerEditRequest.objects.create(
            seller=seller,
            field_name=field_name,
            current_value=current_value,
            requested_value=new_value,
            change_reason=reason
        )
        messages.warning(request, "Request submitted for approval",extra_tags=field_name)
        return redirect("view_profile")



@seller_required
def update_stock(request,id):
    seller=request.user.seller_profile
    product=get_object_or_404(Product,id=id,seller=seller)

    if request.method == "POST":
        quantity = request.POST.get("stock_quantity")

        if not quantity.isdigit() or int(quantity) <= 0:
            messages.error(request,"enter a valid stock quantity")
            return redirect ("inventory_page")

        product.stock_quantity += int(quantity)
        product.save()
        messages.success(request,f"{product.name}stock updated successfully")
    return redirect('inventory_page')


@seller_required
def toggle_product_visibility(request,id):
    seller = request.user.seller_profile
    product = get_object_or_404(Product,id=id,seller=seller)

    if product.is_active:
        product.is_active = False
        messages.error(request, f"{product.name} has been hidden")

    else:
        product.is_active = True
        messages.success(request, f"{product.name} is now visible")

    product.save()
    return  redirect('inventory_page')