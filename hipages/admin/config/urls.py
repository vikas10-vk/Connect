from django.contrib import admin
from django.urls import path

admin.site.site_header  = "ProConnect Admin"
admin.site.site_title   = "ProConnect Admin"
admin.site.index_title  = "Platform Management"

urlpatterns = [
    path('admin/', admin.site.urls),
]