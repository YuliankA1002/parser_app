"""Admin registration for parser_app models."""

from django.contrib import admin

from .models import Product


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('product_code', 'title', 'regular_price', 'promo_price')
    search_fields = ('product_code', 'title')
