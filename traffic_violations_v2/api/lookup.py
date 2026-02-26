from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from urllib.parse import urljoin
import time
import random
import os
import uuid
import easyocr
from PIL import Image, ImageEnhance
import numpy as np
import io
import frappe
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.support.ui import Select


BASE_URL = "https://fees2.moi.gov.qa"


_ocr_reader=None    

def get_ocr_reader():
    global _ocr_reader
    if _ocr_reader is  None:
        _ocr_reader = easyocr.Reader(['en'],gpu=False)
    return _ocr_reader


def build_driver():
    options = Options()
    options.add_argument("--headless=new")      # newer headless
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1400,900")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--start-maximized")

    driver = webdriver.Chrome(options=options)
    driver.set_page_load_timeout(30)
    return driver

def open_page(driver, url):
    driver.get(url)
    wait = WebDriverWait(driver, 40)
    return wait

def select_vehicle_type(driver, wait, vehicle_type):

    dropdown = wait.until(
        EC.element_to_be_clickable((By.ID, "plateType"))
    )

    select = Select(dropdown)

    # 🔥 SELECT BY VALUE INSTEAD OF TEXT
    select.select_by_value(vehicle_type)

def select_owner_type(driver, wait, company_id=None):

    if company_id:
        company_radio = wait.until(
            EC.presence_of_element_located((By.ID, "ownerTypeCpyId"))
        )

        # ✅ Scroll into view
        driver.execute_script(
            "arguments[0].scrollIntoView({block:'center'});",
            company_radio
        )

        time.sleep(0.5)

        # ✅ JS click (bypasses interception)
        driver.execute_script(
            "arguments[0].click();",
            company_radio
        )

        # ✅ wait for form to stabilize
        wait.until(
            EC.presence_of_element_located((By.ID, "ownerQid"))
        )

        time.sleep(0.8)
        

def fill_company_id(driver, wait, company_id):
    """
    company_id expected format: XXXXXXXX (8 digits)
    splits into 2-4-2
    """

    company_id = str(company_id).strip()

    if len(company_id) != 8:
        raise Exception("Company ID must be exactly 8 digits")

    part1 = company_id[:2]
    part2 = company_id[2:6]
    part3 = company_id[6:]

    # field 1 (2 digits)
    f1 = wait.until(
        EC.visibility_of_element_located((By.ID, "ownnerCpyType"))
    )
    f1.clear()
    f1.send_keys(part1)

    # field 2 (4 digits)
    f2 = wait.until(
        EC.visibility_of_element_located((By.ID, "ownnerCpyNo"))
    )
    f2.clear()
    f2.send_keys(part2)

    # field 3 (2 digits)
    f3 = wait.until(
        EC.visibility_of_element_located((By.ID, "ownnerCpyBrnNo"))
    )
    f3.clear()
    f3.send_keys(part3)

def fill_vehicle_info(driver, wait, plate, qid=None, company_id=None, vehicle_type=None):

    # 1️⃣ select owner type
    select_owner_type(driver, wait, company_id)

    # 2️⃣ vehicle type
    if vehicle_type:
        select_vehicle_type(driver, wait, vehicle_type)

    # 3️⃣ fill ID based on type
    if company_id:
        fill_company_id(driver, wait, company_id)
    else:
        id_field = wait.until(
            EC.visibility_of_element_located((By.ID, "ownerQid"))
        )
        id_field.clear()
        id_field.send_keys(qid)

    # 4️⃣ plate
    plate_field = wait.until(
        EC.visibility_of_element_located((By.ID, "plateNo"))
    )
    plate_field.clear()
    plate_field.send_keys(plate)



def human_pause(min_s=0.3, max_s=1.2):
    time.sleep(random.uniform(min_s, max_s))

def capture_captcha_from_browser(driver, wait):
    element = wait.until(
        EC.visibility_of_element_located((By.ID, "captchaImgPlateNum"))
    )

    # Scroll into view (important)
    driver.execute_script("arguments[0].scrollIntoView(true);", element)
    time.sleep(0.5)

    filename = f"captcha_{uuid.uuid4().hex}.png"
    save_path = os.path.join("/tmp", filename)

    # Capture using full page screenshot crop (more reliable)
    png = driver.get_screenshot_as_png()
    img = Image.open(io.BytesIO(png))

    location = element.location_once_scrolled_into_view
    size = element.size

    left = int(location['x'])
    top = int(location['y'])
    right = int(left + size['width'])
    bottom = int(top + size['height'])

    img = img.crop((left, top, right, bottom))
    img.save(save_path)

    return save_path



def preprocess_for_ocr(image_path):
    img = Image.open(image_path)

    # Convert to grayscale
    img = img.convert("L")

    # Tight crop (remove borders)
    bbox = img.getbbox()
    if bbox:
        img = img.crop(bbox)

    # Boost contrast
    enhancer = ImageEnhance.Contrast(img)
    img = enhancer.enhance(3.0)

    # Resize larger for OCR clarity
    img = img.resize((img.width * 4, img.height * 4), Image.BICUBIC)

    # Binary threshold
    arr = np.array(img)
    arr = np.where(arr > 150, 255, 0).astype(np.uint8)
    img = Image.fromarray(arr)

    processed_path = image_path.replace(".png", "_processed.png")
    img.save(processed_path)

    return processed_path



def read_captcha_text(save_path):
    reader = get_ocr_reader()

    processed = preprocess_for_ocr(save_path)

    results = reader.readtext(
        processed,
        detail=0,
        paragraph=False,
        allowlist='0123456789'
    )

    text = "".join(results).strip()
    return text

def fill_captcha(driver, wait, text):
    field = wait.until(
        EC.element_to_be_clickable((By.ID, "captchaResponsePlateNo"))
    )

    field.clear()
    field.send_keys(text)


def click_submit(driver, wait):
    button = wait.until(
        EC.element_to_be_clickable(
            (By.XPATH, "//button[contains(., 'استعلم')]")
        )
    )
    button.click()

def detect_moi_error(driver, wait):

    try:
        popup_text = driver.find_elements(
            By.XPATH,
            "//div[contains(@class,'sweet-alert')]//p"
        )

        if not popup_text:
            return None

        error_text = popup_text[0].text.strip().lower()
        print("MOI ERROR TEXT:", error_text)

        # =========================
        # ✅ ENGLISH — ID
        # =========================
        if "entered id" in error_text and "invalid" in error_text:
            return "invalid_id"

        # =========================
        # ✅ ENGLISH — PLATE
        # =========================
        if "invalid" in error_text and (
            "plate" in error_text or "vehicle" in error_text
        ):
            return "invalid_plate"

        # =========================
        # ✅ ARABIC — ID
        # =========================
        if "الرقم" in error_text and "غير صحيح" in error_text:
            return "invalid_id"

        # =========================
        # ✅ ARABIC — PLATE (FIXED)
        # =========================
        if (
            "نوع اللوحة" in error_text
            or "رقم اللوحة" in error_text
        ) and "غير صحيح" in error_text:
            return "invalid_plate"

        return None

    except Exception as e:
        print("Error detecting MOI popup:", e)
        return None

def wait_for_results(driver, wait):

    try:
        wait.until(
            EC.any_of(

                # 🚨 SweetAlert error text appears
                EC.presence_of_element_located(
                    (By.XPATH, "//div[contains(@class,'sweet-alert')]//p")
                ),

                # ✅ No violations text
                EC.presence_of_element_located(
                    (By.XPATH, "//*[contains(text(),'لا توجد مخالفات')]")
                ),

                # ✅ Violations table
                EC.presence_of_element_located(
                    (By.XPATH, "//table")
                )
            )
        )

        # ⭐ small stabilization pause (important)
        time.sleep(0.8)

    except TimeoutException:
        with open("/tmp/moi_timeout.html", "w", encoding="utf-8") as f:
            f.write(driver.page_source)

        raise Exception("MOI site did not return expected results")






def extract_violations(driver, wait):
    print("=== checking for MOI errors ===")

    # =============================
    # 1️⃣ Check specific popup errors
    # =============================
    error_type = detect_moi_error(driver, wait)

    if error_type == "invalid_id":
        return {
            "status": "invalid_id",
            "violations": []
        }

    if error_type == "invalid_plate":
        return {
            "status": "invalid_plate",
            "violations": []
        }

    # =============================
    # 2️⃣ Check clean case (NO violations)
    # =============================
    if driver.find_elements(By.XPATH, "//*[contains(text(),'لا توجد مخالفات')]"):
        return {
            "status": "clean",
            "violations": []
        }

    # =============================
    # 3️⃣ Check violations table
    # =============================
    rows = driver.find_elements(By.XPATH, "//table//tr")

    violations = []

    for row in rows:
        cols = row.find_elements(By.TAG_NAME, "td")

        if len(cols) < 4:
            continue

        number = cols[1].text.strip()
        info = cols[2].text.strip()
        amount = cols[3].text.strip()

        if not number:
            continue

        parts = info.split("\n", 1)
        date = parts[0] if parts else ""
        description = parts[1] if len(parts) > 1 else ""

        violations.append({
            "violation_no": number,
            "date": date,
            "description": description,
            "amount": amount
        })

    # ✅ If violations found
    if violations:
        return {
            "status": "violations found",
            "violations": violations
        }

    # =============================
    # 4️⃣ Truly unknown
    # =============================
    return {
        "status": "error",
        "violations": []
    }



@frappe.whitelist()
def lookup_violations(plate, qid=None, company_id=None,vehicle_type=None):

    URL = "https://fees2.moi.gov.qa/moipay/inquiry/violation"
    driver = build_driver()

    try:
        wait = open_page(driver, URL)

        fill_vehicle_info(
            driver,
            wait,
            plate=plate,
            qid=qid,
            company_id=company_id,
            vehicle_type=vehicle_type
        )

        # Solve captcha
        image_path = capture_captcha_from_browser(driver, wait)
        captcha_text = read_captcha_text(image_path)

        print("OCR:", captcha_text)

        fill_captcha(driver, wait, captcha_text)
        click_submit(driver, wait)

        # Wait for results page
        wait_for_results(driver, wait)

        # Extract table
        data = extract_violations(driver,wait)

        return data

    finally:
        driver.quit()

@frappe.whitelist()
def lookup(plate, qid=None, company_id=None, vehicle_type=None):

    result = lookup_violations(
        plate=plate,
        qid=qid,
        company_id=company_id,
        vehicle_type=vehicle_type
    )

    if result["status"] == "invalid_id":
        frappe.throw("The entered ID is invalid")
    if result["status"] == "invalid_plate":
        frappe.throw("Type of Vehicle / Plate Number is invalid")
