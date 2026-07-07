"""Scraping a brain.com.ua product with Playwright: search from the homepage,
open the first result, collect all target fields, and store them into
PostgreSQL via the Django ORM
"""

import re
from decimal import Decimal, InvalidOperation
from pprint import pprint

from playwright.sync_api import sync_playwright, TimeoutError as PWTimeoutError

from load_django import *  # noqa: F401,F403
from parser_app.models import Product

HOME_URL = 'https://brain.com.ua/'
SEARCH_QUERY = 'Apple iPhone 15 128GB Black'
DEFAULT_TIMEOUT = 25000

USER_AGENT = (
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
    'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0 Safari/537.36'
)


def to_price(text):
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
    if text is None:
        return None
    return re.sub(r'\s+', ' ', text).strip()


def first_visible(page, xpath):
    locator = page.locator(f"xpath={xpath}")
    for i in range(locator.count()):
        if locator.nth(i).is_visible():
            return locator.nth(i)
    return None


def search_and_open_first(page):
    page.goto(HOME_URL, wait_until='domcontentloaded')

    page.wait_for_selector(
        "xpath=//input[@class='quick-search-input']", state='attached')
    search_box = first_visible(page, "//input[@class='quick-search-input']")
    search_box.click()
    search_box.press_sequentially(SEARCH_QUERY, delay=60)

    find_button = first_visible(
        page, "//input[@class='search-button-first-form']")
    find_button.click(force=True)

    page.wait_for_url("**/search/**")
    page.wait_for_selector(
        "xpath=//div[contains(@class,'product-wrapper')]", state='attached')
    first_card = page.locator(
        "xpath=//div[contains(@class,'product-wrapper')]").first
    name_link = first_card.locator(
        "xpath=.//a[contains(@href,'.html') and "
        "contains(normalize-space(text()), 'iPhone')]").first

    page.goto(name_link.get_attribute('href'), wait_until='domcontentloaded')
    page.wait_for_selector("xpath=//h1", state='attached')


def expand_specifications(page):
    try:
        expand = first_visible(
            page, "//span[normalize-space(text())='Всі характеристики']")
        if expand is None:
            return
        expand.click()
        page.wait_for_function(
            """() => {
                let n = 0;
                document.querySelectorAll('.br-pr-chr-item div').forEach(d => {
                    const s = d.querySelectorAll(':scope > span');
                    if (s.length === 2 && s[0].offsetParent !== null
                        && s[0].innerText.trim() && s[1].innerText.trim()) n++;
                });
                return n > 10;
            }""")
    except PWTimeoutError:
        pass


def parse_specifications(page):
    specifications = {}
    blocks = page.locator("xpath=//*[contains(@class,'br-pr-chr-item')]")
    for b in range(blocks.count()):
        rows = blocks.nth(b).locator("xpath=.//div")
        for r in range(rows.count()):
            spans = rows.nth(r).locator("xpath=./span")
            if spans.count() != 2:
                continue
            label = normalize(spans.nth(0).inner_text())
            value = normalize(spans.nth(1).inner_text())
            if label and value:
                specifications.setdefault(label, value)
    return specifications


def parse_product(page):
    product = {}

    title_el = first_visible(page, "//h1")
    product['title'] = normalize(title_el.inner_text()) if title_el else None

    try:
        code_el = first_visible(
            page, "//div[contains(@class,'product-code-num')]")
        product['product_code'] = code_el.inner_text().split(':', 1)[1].strip()
    except (AttributeError, IndexError):
        product['product_code'] = None

    try:
        reviews_el = first_visible(
            page, "//li[contains(@class,'scroll-to-reviews')]")
        product['reviews_count'] = int(
            re.search(r'\d+', reviews_el.inner_text()).group())
    except (AttributeError, ValueError):
        product['reviews_count'] = None

    price_el = first_visible(
        page, "//div[contains(@class,'main-price-block')]")
    current_price = to_price(price_el.inner_text()) if price_el else None

    old_el = first_visible(page, "//div[contains(@class,'br-pr-old-price')]")
    old_price = to_price(old_el.inner_text()) if old_el else None

    if old_price:
        product['regular_price'] = old_price
        product['promo_price'] = current_price
    else:
        product['regular_price'] = current_price
        product['promo_price'] = None

    photos = []
    imgs = page.locator("xpath=//img[contains(@class,'br-main-img')]")
    for i in range(imgs.count()):
        src = imgs.nth(i).get_attribute('src')
        if src and src not in photos:
            photos.append(src)
    product['photos'] = photos

    specifications = parse_specifications(page)
    product['specifications'] = specifications

    product['color'] = specifications.get('Колір')
    product['memory'] = specifications.get("Вбудована пам'ять")
    product['manufacturer'] = specifications.get('Виробник')
    product['screen_diagonal'] = specifications.get('Діагональ екрану')
    product['display_resolution'] = specifications.get(
        'Роздільна здатність екрану')

    product['source_url'] = page.url
    return product


def save_product(product):
    Product.objects.update_or_create(
        product_code=product['product_code'],
        defaults=product,
    )


def main():
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent=USER_AGENT, locale='uk-UA',
            viewport={'width': 1400, 'height': 1000})
        page = context.new_page()
        page.set_default_timeout(DEFAULT_TIMEOUT)
        try:
            search_and_open_first(page)
            expand_specifications(page)
            product = parse_product(page)
        finally:
            context.close()
            browser.close()

    pprint(product)
    save_product(product)


if __name__ == '__main__':
    main()
