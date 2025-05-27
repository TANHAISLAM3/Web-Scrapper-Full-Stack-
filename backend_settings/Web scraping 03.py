import os
import sys
import django
from decimal import Decimal
import re
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend_settings.settings')

# Add the project root directory (the parent of 'backend_settings' folder) to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
django.setup()
print("sys.path:", sys.path)
print(f"DJANGO_SETTINGS_MODULE: {os.environ.get('DJANGO_SETTINGS_MODULE')}")
# Check the sys.path after modifying it

# Initialize Django
django.setup()

from tracker.models import Product, Review
# Check if the model is accessible
print("Model imported successfully!")

# Optionally, try querying the model to check if everything is working
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import StaleElementReferenceException
import logging
import time



# Set up logging for better visibility
logging.basicConfig(level=logging.INFO, format='%(message)s')
driver = webdriver.Chrome()
base_url = "https://www.yesstyle.com/en/beauty-skin-care/list.html/bcc.15544_bpt.46"


def create_page_url(page_num):
    """Generates URL dynamically."""
    if page_num == 1:
        return base_url
    return f"https://www.yesstyle.com/en/beauty-skin-care/list.html/bcc.15544_bpt.46#/s=10&pn={page_num}&bpt=46&bt=37&sb=136&bcc=15544&l=1"


def wait_for_products():
    try:
        WebDriverWait(driver, 15).until(
            EC.presence_of_all_elements_located((By.CLASS_NAME, "itemContainer"))
        )
    except Exception as e:
        logging.warning("Products not loaded yet: %s", e)


def scroll_page():
    """Scroll to the bottom of the page to ensure all elements are loaded."""
    last_height = driver.execute_script("return document.body.scrollHeight")
    while True:
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(4)  # Wait for lazy loading
        new_height = driver.execute_script("return document.body.scrollHeight")
        if new_height == last_height:
            break
        last_height = new_height


def get_product_containers():
    return driver.find_elements(By.CLASS_NAME, "itemContainer")


def retry_on_stale(func, *args, retries=3, **kwargs):
    for attempt in range(retries):
        try:
            return func(*args, **kwargs)
        except StaleElementReferenceException:
            logging.warning(f"Stale element encountered. Retrying {attempt + 1}/{retries}...")
            wait_for_products()
    raise StaleElementReferenceException("Max retries reached for function.")


def extract_product_data():
    """Extract product data while handling stale elements."""
    products_extracted = []
    try:
        wait_for_products()
        scroll_page()  # Ensure all elements are lazy-loaded
        product_containers = get_product_containers()

        for i, product in enumerate(product_containers):
            try:
                logging.info(f"Processing product {i + 1} of {len(product_containers)}")
                driver.execute_script("arguments[0].scrollIntoView(true);", product)

                wait = WebDriverWait(driver, timeout=2)
                revealed = product.find_element(By.CLASS_NAME, "itemTitle")
                wait.until(lambda d: revealed.is_displayed())

                # Get title and anchor
                title_el = retry_on_stale(product.find_element, By.CLASS_NAME, "itemTitle")
                title = title_el.text.strip()

                # First check if title_el itself is an <a> tag
                tag_name = title_el.tag_name.lower()
                if tag_name == "a":
                    product_url = title_el.get_attribute("href")
                else:
                    try:
                        anchor_tag = product.find_element(By.CSS_SELECTOR, "a[href*='/en/']")
                        product_url = anchor_tag.get_attribute("href")
                    except Exception:
                        product_url = None

                # Validate URL
                if not product_url or 'null' in product_url or 'void(0)' in product_url:
                    logging.warning(f"Invalid product URL for {title}. HTML: {title_el.get_attribute('outerHTML')}")
                    continue

                price = retry_on_stale(product.find_element, By.CSS_SELECTOR,
                                       ".layout-row.layout-wrap.itemPrice.notranslate").text
                review = retry_on_stale(product.find_element, By.CLASS_NAME, "reviewCount").text

                # Open product in new tab
                driver.execute_script("window.open(arguments[0]);", product_url)
                driver.switch_to.window(driver.window_handles[-1])
                time.sleep(3)  # Give time for the new page to load

                review_list = extract_reviews_from_product_page()

                driver.close()
                driver.switch_to.window(driver.window_handles[0])

                products_extracted.append({
                    "title": title,
                    "price": price,
                    "review": review,
                    "full_reviews": review_list
                })
                logging.info(f"✅ Extracted: {title} | {price} | {review} | {len(review_list)} reviews")

            except StaleElementReferenceException as stale_err:
                logging.warning(f"Stale element for product {i + 1}: {stale_err}")
                continue
            except Exception as e:
                logging.error(f"Unexpected error on product {i + 1}: {e}")
                continue

    except Exception as e:
        logging.error(f"Error during extraction: {e}")

    return products_extracted

def extract_reviews_from_product_page():
    """Extracts up to 20 reviews from a product page by clicking the 'Load More' button until limit or exhaustion."""
    reviews = []

    try:
        logging.info("Waiting for reviews to load...")
        time.sleep(3)

        while len(reviews) < 20:
            try:
                load_more_btn = WebDriverWait(driver, 5).until(
                    EC.element_to_be_clickable((By.CLASS_NAME, "customerreviews_loadMore__QSkIB"))
                )
                driver.execute_script("arguments[0].click();", load_more_btn)
                logging.info("Clicked 'Load More' to load additional reviews...")
                time.sleep(2)
            except:
                logging.info("No more 'Load More' button or all reviews loaded.")
                break

            # Early exit if we already have 20 or more
            if len(driver.find_elements(By.CLASS_NAME, "customerreviews_reviewCard__4V1EE")) >= 20:
                break

        # Wait until some reviews are visible
        WebDriverWait(driver, 10).until(
            EC.presence_of_all_elements_located((By.CLASS_NAME, "customerreviews_reviewCard__4V1EE"))
        )

        review_boxes = driver.find_elements(By.CLASS_NAME, "customerreviews_reviewCard__4V1EE")
        logging.info(f"Found {len(review_boxes)} review containers. Extracting up to 20...")

        for box in review_boxes[:20]:
            try:
                name_el = box.find_element(By.CLASS_NAME, "customerreviews_header__UJ2Qd")
                name = name_el.text.strip().split('\n')[-1]

                title = box.find_element(By.TAG_NAME, "h6").text.strip()
                text = box.find_element(By.TAG_NAME, "p").text.strip()
                date = box.find_element(By.TAG_NAME, "time").text.strip()

                try:
                    star_span = box.find_element(By.CLASS_NAME, "ratingstar_colored__SKzSk")
                    width = star_span.value_of_css_property("width")
                    rating = round(float(width.replace("px", "")) / 27.2, 1)
                except:
                    rating = None



                if len(reviews) >= 20:
                    break
            except Exception as e:
                logging.warning(f"Error parsing a review: {e}")
                continue

    except Exception as e:
        logging.error(f"Failed to extract reviews: {e}")

    return reviews

def save_to_database(extracted_products):
    for product_data in extracted_products:
        try:
            price_cleaned = Decimal(re.sub(r"[^\d.]", "", product_data["price"]))
            review_count = int(re.sub(r"[^\d]", "", product_data["review"])) if product_data["review"] else 0

            product = Product.objects.create(
                name=product_data['title'],
                price=price_cleaned,
                reviews=review_count
            )

            for review in product_data['full_reviews'][:20]:  # Save only up to 20
                Review.objects.create(
                    product=product,
                    name=review['name'],
                    title=review['title'],
                    text=review['text'],
                    date=review['date'],
                    rating=review['rating']
                )

        except Exception as e:
            logging.error(f"Failed to save product {product_data['title']}: {e}")


for page_num in range(1):
    try:
        logging.info(f"Loading page {page_num}")
        url = create_page_url(page_num)  # Create dynamic URL
        driver.get(url)

        wait_for_products()

        # Extract product data from the current page
        extracted_products = extract_product_data()
        logging.info(f"Extracted {len(extracted_products)} products from page {page_num}")
        for product in extracted_products:
            print(f"\n Product: {product['title']}")
            print(f" Price: {product['price']}")
            print(f" Review Count: {product['review']}")
            print(f"Full Reviews ({len(product['full_reviews'])}):")
            for review in product['full_reviews']:
                print(f"  📝 {review['title']}: {review['text']}")
            print("=" * 60)

        # Save to database
        save_to_database(extracted_products)

    except Exception as e:
        logging.error(f"Failed to process page {page_num}: {e}")
    finally:
        # Ensure to wait for DOM stabilization before next page
        wait_for_products()

driver.quit()


