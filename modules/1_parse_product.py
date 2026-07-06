"""Parse a single brain.com.ua product page with Requests + BeautifulSoup4
and store the collected data into PostgreSQL via the Django ORM."""

import re
from decimal import Decimal, InvalidOperation
from pprint import pprint

import requests
from bs4 import BeautifulSoup

from load_django import *  # noqa: F401,F403  (bootstraps Django settings)
from parser_app.models import Product

PRODUCT_URL = (
    'https://brain.com.ua/ukr/Mobilniy_telefon_Apple_iPhone_16_Pro_Max_'
    '256GB_Black_Titanium-p1145443.html'
)

HEADERS = {
    'User-Agent': (
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
        'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36'
    ),
    'Accept-Language': 'uk,en-US;q=0.9,en;q=0.8',
    'Accept': (
        'text/html,application/xhtml+xml,application/xml;q=0.9,'
        'image/webp,image/apng,*/*;q=0.8'
    ),
    'Referer': 'https://www.google.com/',
    'Connection': 'keep-alive',
    'Upgrade-Insecure-Requests': '1',
    'Sec-Fetch-Dest': 'document',
    'Sec-Fetch-Mode': 'navigate',
    'Sec-Fetch-Site': 'same-origin',
    'Sec-Fetch-User': '?1',
}


def to_price(text):
    """Convert a raw price string like '65 799 ₴' into a Decimal, or None."""
    if not text:
        return None
    digits = re.sub(r'[^\d]', '', text)
    if not digits:
        return None
    try:
        return Decimal(digits)
    except InvalidOperation:
        return None


def normalize(text):
    """Collapse whitespace runs (incl. non-breaking spaces) into one space."""
    if text is None:
        return None
    return re.sub(r'\s+', ' ', text).strip()


def parse_specifications(soup):
    """Collect every characteristic from the specs blocks into a dictionary.

    Each characteristic row holds two direct spans: the label and the value.
    Rows are matched by structure (label span + value span), never by index.
    """
    specifications = {}
    for block in soup.select('.br-pr-chr-item'):
        for row in block.find_all('div'):
            spans = row.find_all('span', recursive=False)
            if len(spans) != 2:
                continue
            label = normalize(spans[0].get_text(' ', strip=True))
            value = normalize(spans[1].get_text(' ', strip=True))
            if label and value:
                specifications.setdefault(label, value)
    return specifications


def parse_product(html):
    """Extract all required product fields from the page HTML."""
    soup = BeautifulSoup(html, 'lxml')
    product = {}

    # Full product title
    try:
        product['title'] = soup.h1.get_text(strip=True)
    except AttributeError:
        product['title'] = None

    # Product code: located by its label wrapper, value taken after the colon
    try:
        code_block = soup.find('div', attrs={'class': 'product-code-num'})
        code_text = code_block.get_text(strip=True)
        product['product_code'] = code_text.split(':', 1)[1].strip()
    except (AttributeError, IndexError):
        product['product_code'] = None

    # Number of reviews: parse the integer inside "Відгуки (N)"
    try:
        reviews_block = soup.find('li', attrs={'class': 'scroll-to-reviews'})
        reviews_text = reviews_block.get_text(strip=True)
        product['reviews_count'] = int(re.search(r'\d+', reviews_text).group())
    except (AttributeError, ValueError):
        product['reviews_count'] = None

    # Regular price (current, displayed price)
    try:
        price_block = soup.find('div', attrs={'class': 'main-price-block'})
        current_price = to_price(price_block.get_text(' ', strip=True))
    except AttributeError:
        current_price = None

    # Promotional price: present only when an old (crossed) price exists.
    # Then the crossed price is the regular one and the current one is promo.
    try:
        old_block = soup.find('div', attrs={'class': 'br-pr-old-price'})
        old_price = to_price(old_block.get_text(' ', strip=True))
    except AttributeError:
        old_price = None

    if old_price:
        product['regular_price'] = old_price
        product['promo_price'] = current_price
    else:
        product['regular_price'] = current_price
        product['promo_price'] = None

    # All product photo URLs collected into a list (order preserved, unique)
    try:
        photos = []
        for img in soup.select('img.br-main-img'):
            src = img.get('src') or img.get('data-src')
            if src and src not in photos:
                photos.append(src)
        product['photos'] = photos
    except AttributeError:
        product['photos'] = []

    # Full specifications collected as a dictionary
    specifications = parse_specifications(soup)
    product['specifications'] = specifications

    # Fields derived from specifications, matched by their label (not index)
    product['color'] = specifications.get('Колір')
    product['memory'] = specifications.get("Вбудована пам'ять")
    product['manufacturer'] = specifications.get('Виробник')
    product['screen_diagonal'] = specifications.get('Діагональ екрану')
    product['display_resolution'] = specifications.get(
        'Роздільна здатність екрану'
    )

    product['source_url'] = PRODUCT_URL
    return product


def save_product(product):
    """Store the parsed product into the database via the Django ORM."""
    Product.objects.update_or_create(
        product_code=product['product_code'],
        defaults=product,
    )


def main():
    response = requests.get(PRODUCT_URL, headers=HEADERS, timeout=30)
    response.raise_for_status()

    product = parse_product(response.text)
    pprint(product)

    save_product(product)


if __name__ == '__main__':
    main()
