from importlib.metadata import requires
from random import choices
from django.db import IntegrityError
from django.utils.timezone import now
from django.db import models
from core.models import User, SubCategory

class SellerProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="seller_profile")
    shop_name = models.CharField(max_length=255,unique=True)
    shop_slug = models.SlugField(unique=True)
    website = models.URLField(blank=True,null=True)
    category = models.CharField(max_length=200)
    gst_number = models.CharField(max_length=50,unique=True)
    pan_number = models.CharField(max_length=50,unique=True)
    bank_account_number = models.CharField(max_length=50,unique=True)
    ifsc_code = models.CharField(max_length=20)
    business_address = models.TextField()
    business_email=models.EmailField(unique=True,null=True,blank=True)
    rating = models.FloatField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    description = models.TextField(blank=True, null=True)
    STATUS_CHOICES=[
        ("APPROVED",'approved'),
        ("PENDING","pending"),
        ("REJECTED",'rejected')
    ]
    logo = models.ImageField(upload_to='seller_logos/',null=True,blank=True)
    status=models.CharField(max_length=10,choices=STATUS_CHOICES,default="PENDING")
    rejection_reason=models.TextField(blank=True,null=True)

class Product(models.Model):
    seller = models.ForeignKey(SellerProfile, on_delete=models.CASCADE, related_name="products")
    subcategory = models.ForeignKey(SubCategory, on_delete=models.CASCADE, related_name="products")
    name = models.CharField(max_length=255)
    slug = models.SlugField(unique=True,default="temp-slug")
    description = models.TextField()
    brand = models.CharField(max_length=100)
    model_number = models.CharField(max_length=100)
    image = models.ImageField(upload_to='product_images/', null=True, blank=True)
    is_cancellable = models.BooleanField(default=True)
    is_returnable = models.BooleanField(default=True)
    return_days = models.IntegerField(default=7,null=True,blank=True)
    approval_status = models.CharField(max_length=20, choices=(('PENDING', 'Pending'), ('APPROVED', 'Approved'), ('REJECTED', 'Rejected')), default='PENDING')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    sku_code = models.CharField(max_length=100, unique=True)
    price = models.DecimalField(max_digits=10, decimal_places=2,null=True)
    selling_price = models.DecimalField(max_digits=10, decimal_places=2)
    cost_price = models.DecimalField(max_digits=10, decimal_places=2)
    stock_quantity = models.IntegerField(null=True,blank=True)
    tax_percentage = models.FloatField()
    product_rejection_reason = models.TextField(null=True, blank=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    submission_type = models.CharField(max_length=10,choices=(("NEW", "New"),("EDIT", "Edit"),), default="NEW")


class ProductImage(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="images")
    image = models.ImageField(upload_to='product_images/')
    alt_text = models.CharField(max_length=255, blank=True)
    is_primary = models.BooleanField(default=False)


class ProductEditRequest(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    field_name = models.CharField(max_length=100)
    old_value = models.TextField()
    new_value = models.TextField()
    status = models.CharField(max_length=20, default="PENDING")
    created_at = models.DateTimeField(auto_now_add=True)

class InventoryLog(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    change_amount = models.IntegerField()
    reason = models.CharField(max_length=50)
    performed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

class SellerEditRequest(models.Model):
    seller = models.ForeignKey(SellerProfile,on_delete=models.CASCADE)
    current_value=models.TextField()
    requested_value=models.TextField()
    change_reason=models.TextField()
    rejection_reason = models.TextField(null=True, blank=True)

    FIELD_CHOICES=[
        ("gst_number", "GST Number"),
        ("pan_number", "PAN Number"),
        ("bank_account_number", "Bank Account"),
        ("ifsc_code", "IFSC Code")
    ]
    field_name = models.CharField(max_length=50,choices=FIELD_CHOICES)

    STATUS_CHOICES=[
            ("PENDING", "Pending"),
            ("APPROVED", "Approved"),
            ("REJECTED", "Rejected")]

    status = models.CharField(max_length=20,choices=STATUS_CHOICES,default="PENDING")

    created_at = models.DateTimeField(auto_now_add=True)
    last_updated_at = models.DateTimeField(null=True, blank=True)

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)

        if self.status == "APPROVED":
            seller = self.seller

            try:
                setattr(seller, self.field_name, self.requested_value)
                seller.save()

            except IntegrityError:
                self.status = "REJECTED"
                self.rejection_reason = f"{self.get_field_name_display()} already exists"
                super().save(update_fields=["status", "rejection_reason"])
                return

            self.last_updated_at = now()
            super().save(update_fields=["last_updated_at"])
