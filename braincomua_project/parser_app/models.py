"""Database models for scraped brain.com.ua product data."""

from django.db import models


class Product(models.Model):
    """A single product parsed from a brain.com.ua product page."""

    product_code = models.CharField(max_length=64, unique=True)
    title = models.CharField(max_length=512)
    color = models.CharField(max_length=128, null=True, blank=True)
    memory = models.CharField(max_length=64, null=True, blank=True)
    manufacturer = models.CharField(max_length=128, null=True, blank=True)
    regular_price = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True
    )
    promo_price = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True
    )
    reviews_count = models.PositiveIntegerField(null=True, blank=True)
    screen_diagonal = models.CharField(max_length=64, null=True, blank=True)
    display_resolution = models.CharField(max_length=64, null=True, blank=True)
    photos = models.JSONField(default=list, blank=True)
    specifications = models.JSONField(default=dict, blank=True)
    source_url = models.URLField(max_length=512)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f'{self.product_code} - {self.title}'
