"""Scraping a brain.com.ua product with Selenium: search from the homepage,
open the first result, collect all target fields, and store them into
PostgreSQL via the Django ORM
"""

import re
from decimal import Decimal, InvalidOperation
from pprint import pprint

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.common.exceptions import (
    NoSuchElementException,
    TimeoutException,
)
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from load_django import *  # noqa: F401,F403
from parser_app.models import Product

HOME_URL = 'https://brain.com.ua/'
SEARCH_QUERY = 'Apple iPhone 15 128GB Black'
WAIT_SECONDS = 25

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


def first_displayed(driver, xpath):
    for element in driver.find_elements(By.XPATH, xpath):
        if element.is_displayed():
            return element
    return None


def count_spec_rows(driver):
    rows = 0
    for block in driver.find_elements(
            By.XPATH, "//*[contains(@class,'br-pr-chr-item')]"):
        for row in block.find_elements(By.XPATH, ".//div"):
            spans = row.find_elements(By.XPATH, "./span")
            if len(spans) == 2 and spans[0].text.strip() and spans[1].text.strip():
                rows += 1
    return rows


def build_driver():
    options = Options()
    options.add_argument('--headless=new')
    options.add_argument('--window-size=1400,1000')
    options.add_argument('--lang=uk-UA')
    options.add_argument(f'--user-agent={USER_AGENT}')
    return webdriver.Chrome(options=options)


def search_and_open_first(driver, wait):
    driver.get(HOME_URL)

    search_box = wait.until(lambda d: first_displayed(
        d, "//input[@class='quick-search-input']"))
    search_box.click()
    search_box.send_keys(SEARCH_QUERY)

    find_button = wait.until(lambda d: first_displayed(
        d, "//input[@type='submit' and @value='Знайти']"))
    find_button.click()

    wait.until(EC.presence_of_element_located(
        (By.XPATH, "//div[contains(@class,'product-wrapper')]")))
    first_card = driver.find_element(
        By.XPATH, "//div[contains(@class,'product-wrapper')]")
    name_link = first_card.find_element(
        By.XPATH, ".//a[contains(@href,'.html') and "
                  "contains(normalize-space(text()), 'iPhone')]")
    driver.execute_script("arguments[0].click();", name_link)

    wait.until(EC.presence_of_element_located((By.XPATH, "//h1")))


def expand_specifications(driver, wait):
    try:
        expand = first_displayed(
            driver, "//span[normalize-space(text())='Всі характеристики']")
        if expand is None:
            return
        driver.execute_script(
            "arguments[0].scrollIntoView({block:'center'});", expand)
        driver.execute_script("arguments[0].click();", expand)
        wait.until(lambda d: count_spec_rows(d) > 10)
    except (NoSuchElementException, TimeoutException):
        pass


def parse_specifications(driver):
    specifications = {}
    for block in driver.find_elements(
            By.XPATH, "//*[contains(@class,'br-pr-chr-item')]"):
        for row in block.find_elements(By.XPATH, ".//div"):
            spans = row.find_elements(By.XPATH, "./span")
            if len(spans) != 2:
                continue
            label = normalize(spans[0].text)
            value = normalize(spans[1].text)
            if label and value:
                specifications.setdefault(label, value)
    return specifications


def parse_product(driver):
    product = {}

    title_el = first_displayed(driver, "//h1")
    product['title'] = normalize(title_el.text) if title_el else None

    try:
        code_el = first_displayed(
            driver, "//div[contains(@class,'product-code-num')]")
        product['product_code'] = code_el.text.split(':', 1)[1].strip()
    except (AttributeError, IndexError):
        product['product_code'] = None

    try:
        reviews_el = first_displayed(
            driver, "//li[contains(@class,'scroll-to-reviews')]")
        product['reviews_count'] = int(re.search(r'\d+', reviews_el.text).group())
    except (AttributeError, ValueError):
        product['reviews_count'] = None

    try:
        price_el = first_displayed(
            driver, "//div[contains(@class,'main-price-block')]")
        current_price = to_price(price_el.text)
    except AttributeError:
        current_price = None

    try:
        old_el = first_displayed(
            driver, "//div[contains(@class,'br-pr-old-price')]")
        old_price = to_price(old_el.text) if old_el else None
    except AttributeError:
        old_price = None

    if old_price:
        product['regular_price'] = old_price
        product['promo_price'] = current_price
    else:
        product['regular_price'] = current_price
        product['promo_price'] = None

    photos = []
    for img in driver.find_elements(
            By.XPATH, "//img[contains(@class,'br-main-img')]"):
        src = img.get_attribute('src')
        if src and src not in photos:
            photos.append(src)
    product['photos'] = photos

    specifications = parse_specifications(driver)
    product['specifications'] = specifications

    product['color'] = specifications.get('Колір')
    product['memory'] = specifications.get("Вбудована пам'ять")
    product['manufacturer'] = specifications.get('Виробник')
    product['screen_diagonal'] = specifications.get('Діагональ екрану')
    product['display_resolution'] = specifications.get(
        'Роздільна здатність екрану')

    product['source_url'] = driver.current_url
    return product


def save_product(product):
    Product.objects.update_or_create(
        product_code=product['product_code'],
        defaults=product,
    )


def main():
    driver = build_driver()
    wait = WebDriverWait(driver, WAIT_SECONDS)
    try:
        search_and_open_first(driver, wait)
        expand_specifications(driver, wait)
        product = parse_product(driver)
    finally:
        driver.quit()

    pprint(product)
    save_product(product)


if __name__ == '__main__':
    main()
