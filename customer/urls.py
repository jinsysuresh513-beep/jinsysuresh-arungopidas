from django.urls import path
from . import views
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('', views.home_view, name='home'),
    path('customer_register/', views.customer_register, name='customer_register'),
    path('customer_profile/', views.customerprofile, name='customer_profile'),
    #----------------------------------------------------------------------------
    path('customerorder/',views.customerorder,name="customer_order"),
    path('ordersuccess/<int:id>/',views.ordersuccess,name="ordersuccess"),
    path("cancelorder/<int:id>/", views.cancelorder, name="cancelorder"),
    path('customerwishlist/',views.customerwishlist,name="customer_wishlist"),
    path('customersettings/',views.customersettings,name="customer_settings"),
    path('productlist/',views.productlist,name="productlist"),
    path('productcollection/',views.productcollection,name="productcollection"),
    path('productcategory/',views.productcategory,name="productcategory"),
    path('singleproduct/<int:id>/',views.singleproduct,name="singleproduct"),
    path('addcart/<int:id>/',views.addcart,name="addcart"),
    path('cartview/',views.cartview,name="cartview"),
    path('removecart/<int:id>/',views.removecart,name="removecart"),
    path('wishlist/<int:id>/',views.wishlist,name="wishlist"),
    path('wishlistview/',views.wishlistview,name="wishlistview"),
    path('removewishlist/<int:id>/',views.removewishlist,name="removewishlist"),
    path('customeraddress/',views.customer_address,name="customer_address"),
    path('saved-addresses/',views.savedaddress,name="saved_address"),
    path('delete_address/<int:id>/',views.deleteaddress,name="delete_address"),
    path('edit_address/<int:id>/',views.editaddress,name="edit_address"),
    path('checkout/',views.checkout,name="checkout"),
    path('proceedcheckout/',views.proceedcheckout,name="proceedcheckout"),
    path('electronics/',views.electronic,name="electronics"),
    path('handbag/',views.handbag,name="handbag"),
    path('footwear/',views.footwear,name="footwear"),
]
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)