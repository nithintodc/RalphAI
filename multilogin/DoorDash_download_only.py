import requests
import random
import time
import os
import json
import sys
import mysql.connector
from datetime import datetime, timedelta, UTC
import pandas as pd
from selenium.webdriver.chromium.options import ChromiumOptions
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import pytz

import gspread
from oauth2client.service_account import ServiceAccountCredentials

# json and os already imported above
from dotenv import load_dotenv
from selenium import webdriver
import zipfile
import shutil
from pathlib import Path


MLX_BASE = "https://api.multilogin.com"
MLX_LAUNCHER = "https://launcher.mlx.yt:45001/api/v1"
BASE_URL = 'https://api.multilogin.com/profile/create'
MLX_LAUNCHER_V2 = "https://launcher.mlx.yt:45001/api/v2"
MLX_LAUNCHER_STOP = "https://launcher.mlx.yt:45001/api/v1"
LOCALHOST = "http://127.0.0.1"
HEADERS = {"Accept": "application/json", "Content-Type": "application/json"}
LOCALHOST = "http://127.0.0.1"
load_dotenv()

USERNAME = os.getenv("MULTILOGIN_USERNAME")
PASSWORD = os.getenv("MULTILOGIN_PASSWORD")

# Get the directory where the script is located
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# FastAPI endpoint configuration for auto-upload
FASTAPI_ENDPOINT = "https://csv-uploader-886692368169.us-central1.run.app"
DOWNLOAD_FOLDER = os.path.join(SCRIPT_DIR, "downloads")
MANUAL_UPLOAD_FOLDER = os.path.join(SCRIPT_DIR, "manual_upload")
PROCESSED_FOLDER = os.path.join(SCRIPT_DIR, "processed")
UPLOAD_LOG_FILE = os.path.join(SCRIPT_DIR, "upload_log.json")
CREDENTIALS_FILE = os.path.join(SCRIPT_DIR, "DD_Creds_with_profiles.csv")

# Create necessary directories
for folder in [DOWNLOAD_FOLDER, MANUAL_UPLOAD_FOLDER, PROCESSED_FOLDER]:
    os.makedirs(folder, exist_ok=True)

# Initialize upload log to track processed files
def load_upload_log():
    """Load the upload log to track processed files"""
    if os.path.exists(UPLOAD_LOG_FILE):
        try:
            with open(UPLOAD_LOG_FILE, 'r') as f:
                return json.load(f)
        except Exception as e:
            print(f"Warning: Could not load upload log: {e}")
    return {"processed_files": {}, "failed_files": {}, "manual_files": {}}

def save_upload_log(upload_log):
    """Save the upload log"""
    try:
        with open(UPLOAD_LOG_FILE, 'w') as f:
            json.dump(upload_log, f, indent=2)
    except Exception as e:
        print(f"Warning: Could not save upload log: {e}")

def get_file_hash(file_path):
    """Get a unique hash for a file based on name, size, and modification time"""
    try:
        stat = os.stat(file_path)
        filename = os.path.basename(file_path)
        # Create a unique identifier based on filename, size, and modification time
        file_id = f"{filename}_{stat.st_size}_{int(stat.st_mtime)}"
        return file_id
    except Exception:
        return None

def is_file_already_processed(file_path, upload_log):
    """Check if a file has already  been processed"""
    file_hash = get_file_hash(file_path)
    if not file_hash:
        return False
    
    return file_hash in upload_log["processed_files"] or file_hash in upload_log["failed_files"] or file_hash in upload_log["manual_files"]

def clear_upload_log():
    """Clear the upload log to allow reprocessing of all files"""
    try:
        if os.path.exists(UPLOAD_LOG_FILE):
            os.remove(UPLOAD_LOG_FILE)
            print("SUCCESS: Upload log cleared. All files will be reprocessed on next run.")
        else:
            print("info No upload log found to clear.")
    except Exception as e:
        print(f"ERROR: Error clearing upload log: {e}")

def show_upload_status():
    """Show the current upload status"""
    upload_log = load_upload_log()
    
    print("INFO: Upload Status Report")
    print("=" * 50)
    print(f"SUCCESS: Successfully processed: {len(upload_log['processed_files'])} files")
    print(f"ERROR: Failed uploads: {len(upload_log['failed_files'])} files")
    print(f"  Manual processing: {len(upload_log['manual_files'])} files")
    
    if upload_log['processed_files']:
        print("\nSUCCESS: Recently processed files:")
        for file_hash, info in list(upload_log['processed_files'].items())[-5:]:
            print(f"  - {info['filename']} ({info['timestamp']})")
    
    if upload_log['failed_files']:
        print("\nERROR: Recently failed files:")
        for file_hash, info in list(upload_log['failed_files'].items())[-5:]:
            print(f"  - {info['filename']} - {info['error']}")
    
    if upload_log['manual_files']:
        print("\n  Recently manual files:")
        for file_hash, info in list(upload_log['manual_files'].items())[-5:]:
            print(f"  - {info['filename']} - {info['reason']}")

def move_existing_files_to_downloads():
    """Move any existing DoorDash files from script directory to downloads folder"""
    print("SEARCHING: Checking for existing files in script directory...")
    
    # Look for DoorDash files in the script directory
    door_dash_files = []
    for file in os.listdir(SCRIPT_DIR):
        file_path = os.path.join(SCRIPT_DIR, file)
        if os.path.isfile(file_path):
            # Check if it's a DoorDash file (zip or csv with DoorDash patterns)
            if (file.endswith('.zip') or file.endswith('.csv')) and any(keyword in file.lower() for keyword in ['doordash', 'reconciliation', 'operations', 'marketing', 'financial']):
                door_dash_files.append(file_path)
    
    if door_dash_files:
        print(f"  Found {len(door_dash_files)} existing DoorDash files in script directory")
        for file_path in door_dash_files:
            filename = os.path.basename(file_path)
            destination = os.path.join(DOWNLOAD_FOLDER, filename)
            
            # If file already exists in downloads, add timestamp
            if os.path.exists(destination):
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                name, ext = os.path.splitext(filename)
                filename = f"{name}_{timestamp}{ext}"
                destination = os.path.join(DOWNLOAD_FOLDER, filename)
            
            try:
                shutil.move(file_path, destination)
                print(f" SUCCESS: Moved {filename} to downloads folder")
            except Exception as e:
                print(f"ERROR: Error moving {filename}: {e}")
    else:
        print("info No existing DoorDash files found in script directory")

def check_downloads_folder():
    """Check what files are in the downloads folder"""
    print(f"  Checking downloads folder: {DOWNLOAD_FOLDER}")
    
    if not os.path.exists(DOWNLOAD_FOLDER):
        print("ERROR: Downloads folder does not exist")
        return
    
    files = os.listdir(DOWNLOAD_FOLDER)
    if not files:
        print("info Downloads folder is empty")
        return
    
    print(f" Found {len(files)} files in downloads folder:")
    for file in files:
        file_path = os.path.join(DOWNLOAD_FOLDER, file)
        if os.path.isfile(file_path):
            size = os.path.getsize(file_path)
            print(f"  - {file} ({size} bytes)")
        else:
            print(f"  - {file} (directory)")

# Table mapping for DoorDash files
TABLE_MAPPING = {
    "error_charges_adjustments_default": "dd_raw_error_charges_adjustments_default",
    "financials_detailed_transactions_summarized_us": "dd_raw_financials_detailed_transactions_summarized_us",
    "financials_payout_summary_us": "dd_raw_financials_payout_summary",
    "financials_detailed_transactions_us": "dd_raw_financials_detailed_transactions_us",
    "financials_simplified_transactions_us": "dd_raw_financials_simplified_transactions_us",
    "operations_quality_avoidable_wait_orders_default": "dd_raw_operations_quality_avoidable_wait_orders_default",
    "operations_quality_cancelled_orders_default": "dd_raw_operations_quality_cancelled_orders_default",
    "operations_quality_missing_incorrect_orders_default": "dd_raw_operations_quality_missing_incorrect_orders",
    "promo_campaign_performance_for_non_storefront": "dd_raw_promotion_campaigns",
    "sponsored_listing_campaign_performance_default": "dd_raw_sponsored_listings"
}

def create_profile_with_proxy(name, host, port, username, password, folder_id):
    payload = {
        "name": name,
        "browser_type": "mimic",
        "folder_id": folder_id,
        "os_type": "windows",
        "notes": "Profile with proxy and full fingerprint config",
        "parameters": {
            "flags": {
                "audio_masking": "mask",
                "fonts_masking": "custom",
                "geolocation_masking": "custom",
                "geolocation_popup": "prompt",
                "graphics_masking": "custom",
                "graphics_noise": "mask",
                "localization_masking": "custom",
                "media_devices_masking": "custom",
                "navigator_masking": "custom",
                "ports_masking": "mask",
                "proxy_masking": "custom",
                "screen_masking": "custom",
                "timezone_masking": "custom",
                "webrtc_masking": "custom",
                "canvas_noise": "mask",
                "startup_behavior": "custom"
            },
            "storage": {
                "is_local": False,
                "save_service_worker": True
            },
            "fingerprint": {
                "navigator": {
                    "hardware_concurrency": 4,
                    "platform": "Win32",
                    "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
                    "os_cpu": "Windows NT 10.0"
                },
                "localization": {
                    "languages": "en-US,en",
                    "locale": "en-US",
                    "accept_languages": "en-US,en;q=0.9"
                },
                "timezone": {
                    "zone": "America/New_York"
                },
                "graphic": {
                    "vendor": "Google Inc.",
                    "renderer": "ANGLE (Intel, Intel(R) UHD Graphics, Direct3D11 vs_5_0 ps_5_0)"
                },
                "webrtc": {
                    "public_ip": "93.184.216.34"
                },
                "media_devices": {
                    "audio_inputs": 1,
                    "audio_outputs": 1,
                    "video_inputs": 1
                },
                "screen": {
                    "height": 1080,
                    "width": 1920,
                    "pixel_ratio": 1.0
                },
                "geolocation": {
                    "accuracy": 10.0,
                    "altitude": 50.5,
                    "latitude": 40.7128,
                    "longitude": -74.0060
                },
                "ports": [80, 443],
                "fonts": ["Arial", "Courier New", "Times New Roman"],
                "cmd_params": {
                    "params": [
                        {"flag": "--disable-web-security", "value": "true"}
                    ]
                }
            },
            "proxy": {
                "type": "socks5",
                "host": host,
                "port": int(port),
                "username": username,
                "password": password,
                "save_traffic": False
            },
            "custom_start_urls": [
                "https://quotes.toscrape.com/w"
            ]
        }
    }

    response = requests.post(BASE_URL, json=payload, headers=HEADERS)

    if response.status_code == 201:
        profile_id = response.json()['data']['ids'][0]
        print(f"[ SUCCESS:] Profile created successfully with proxy. ID: {profile_id}")
        return profile_id
    else:
        print(f"[ERROR:] Failed to create profile: {response.status_code} - {response.text}")
        return None


def get_proxy():
    url = "https://profile-proxy.multilogin.com/v1/proxy/connection_url"

    payload = "{\r\n  \"country\": \"us\",\r\n  \"sessionType\": \"sticky\",\r\n  \"protocol\": \"socks5\"}"

    response = requests.request("POST", url, headers=HEADERS, data=payload)
    if response.status_code == 201:
        return response.json()
    else:
        return None


def signin() -> str:
    payload = {
        "email": USERNAME,
        "password": PASSWORD,
    }
    r = requests.post(f"{MLX_BASE}/user/signin", json=payload)
    if r.status_code != 200:
        print(f"\nError during login: {r.text}\n")
    else:
        response = r.json()["data"]
    token = response["token"]
    return token


def delete_profile(headers, profile_id, permanently=True):
    url = "https://api.multilogin.com/profile/remove"
    payload = json.dumps({
        "ids": [profile_id],
        "permanently": permanently
    })
    response = requests.request("POST", url, headers=headers, data=payload)
    print(response.text)


def workspace_folder_id(HEADERS):
    url = "https://api.multilogin.com/user/workspaces"
    payload = {}
    response = requests.request("GET", url, headers=HEADERS, data=payload)
    if response.status_code == 200:
        response_data = response.json()
        workspace_id = response_data['data']['workspaces'][0]['workspace_id']
        return workspace_id
    else:
        return response.text


def get_multi_login_profile(profile_id, folder_id):
    # Start the profile using MultiLogin's API
    response = requests.get(
        f"{MLX_LAUNCHER_V2}/profile/f/{folder_id}/p/{profile_id}/start?automation_type=selenium&headless_mode=false",
        headers=HEADERS,
    )
    if response.status_code == 200:
        print("Profile started successfully.")
        return response.json(), response.status_code
    else:
        print(f"Failed to start profile. Status code: {response.status_code} {response.json()}")
        return response.json(), response.status_code


def stop_all_profiles():
    url = "https://launcher.mlx.yt:45001/api/v1/profile/stop_all?type=regular"
    payload = {}
    response = requests.request("GET", url, headers=HEADERS, data=payload)
    print(response.text)

def stop_profile(MLX_LAUNCHER_STOP,HEADERS,PROFILE_ID) -> None:
    r = requests.get(f'{MLX_LAUNCHER_STOP}/profile/stop/p/{PROFILE_ID}', headers=HEADERS)
    if (r.status_code != 200):
        print(f'\nError while stopping profile: {r.text}\n')
    else:
        print(f'\nProfile {PROFILE_ID} stopped.\n')

def stop_browser(multiloginid, driver):
    driver.quit()
    FOLDER_ID = workspace_folder_id(HEADERS)
    print(FOLDER_ID)
    stop_profile(MLX_LAUNCHER_STOP, HEADERS, multiloginid)


def random_sleep():
    # Sleep for a random time between 5 and 10 seconds
    random_sleep_time = random.uniform(8, 13)
    print(f"Sleeping for {random_sleep_time:.2f} seconds.")
    time.sleep(random_sleep_time)

def update_profile_proxy(HEADERS,profile_id,proxy_host='', proxy_port='', proxy_name='', proxy_password=''):
    # token = signin(MLX_BASE, USERNAME, PASSWORD)
    if proxy_host !='':
        proxy_port = int(proxy_port)
    url = "https://api.multilogin.com/profile/partial_update"
    payload = json.dumps({
        "profile_id": profile_id,
        "proxy": {
            "host": proxy_host,
            "type": "socks5",
            "port": proxy_port,
            "username": proxy_name,
            "password": proxy_password
        }
    })
    response = requests.request("POST", url, headers=HEADERS, data=payload)
    print(response.text)
    return response.text


def unlock_locked_profiles(HEADERS):
    req_url = "https://api.multilogin.com/bpds/profile/unlock_profiles"
    payload = {}

    response = requests.request("GET", req_url, headers=HEADERS, data=payload)
    print(response.text)

def start_selenium_session(profile_id, folder_id, HEADERS):
    profile_data, status_code = get_multi_login_profile(profile_id,folder_id)
    if 'PROXY' in profile_data['status']['error_code']:
        proxies = get_proxy()
        if proxies:
            host = proxies['data'].split(':')[0]
            port = proxies['data'].split(':')[1]
            username = proxies['data'].split(':')[2]
            password = proxies['data'].split(':')[3]
            update_profile_proxy(HEADERS,profile_id,host,port,username,password)
            short_Random_Sleep()
            profile_data, status_code = get_multi_login_profile(profile_id,folder_id)
    if 'LOCK_PROFILE_ERROR' in profile_data['status']['error_code']:
        unlock_locked_profiles(HEADERS)
        short_Random_Sleep()
        profile_data, status_code = get_multi_login_profile(profile_id, folder_id)
    if status_code == 200:
        selenium_port = profile_data.get('data').get('port')
        print(selenium_port)
        option = ChromiumOptions()
        
        driver = webdriver.Remote(command_executor=f'{LOCALHOST}:{selenium_port}', options=option)
        
        # Set download directory after driver creation
        driver.execute_cdp_cmd('Page.setDownloadBehavior', {
            'behavior': 'allow',
            'downloadPath': DOWNLOAD_FOLDER
        })
        
        driver.maximize_window()
        short_Random_Sleep()
        first_tab = driver.window_handles[0]
        driver.switch_to.window(first_tab)
        short_Random_Sleep()
        return driver, profile_data
    else:
        return None

def short_Random_Sleep():
    ran = random.randint(1, 5)
    time.sleep(ran)


def long_Random_Sleep():
    ran = random.randint(20, 30)
    time.sleep(ran)


def medium_Random_Sleep():
    ran = random.randint(5, 7)
    time.sleep(ran)


def update_proxy(driver, Multilogin_ID, HEADERS):
    stop_browser(Multilogin_ID, driver)
    proxies = get_proxy()
    if proxies:
        host = proxies['data'].split(':')[0]
        port = proxies['data'].split(':')[1]
        username = proxies['data'].split(':')[2]
        password = proxies['data'].split(':')[3]
        update_profile_proxy(HEADERS, Multilogin_ID, host, port, username, password)
        short_Random_Sleep()
        # Get folder_id from workspace
        folder_id = workspace_folder_id(HEADERS)
        profile_data, status_code = get_multi_login_profile(Multilogin_ID, folder_id)
        if status_code == 200:
            selenium_port = profile_data.get('data').get('port')
            print(selenium_port)
            option = ChromiumOptions()
            
            driver = webdriver.Remote(command_executor=f'{LOCALHOST}:{selenium_port}', options=option)
            
            # Set download directory after driver creation
            driver.execute_cdp_cmd('Page.setDownloadBehavior', {
                'behavior': 'allow',
                'downloadPath': DOWNLOAD_FOLDER
            })
            
            driver.maximize_window()
            short_Random_Sleep()
            first_tab = driver.window_handles[0]
            driver.switch_to.window(first_tab)
            short_Random_Sleep()
            return driver, profile_data
        else:
            return None


def test_and_change_proxy(driver, url, MultiloginID, HEADERS, profile_data):
    start = time.time()
    driver.get(url)
    driver.execute_script("return document.readyState")  # wait until DOM ready
    end = time.time()
    time_to_load = end - start
    if time_to_load > 30:
        driver, profile_data = update_proxy(driver,MultiloginID,HEADERS)
        driver.get(url)
    return driver, profile_data

def create_report(driver, report_selection, start_date, end_date):
    
    report_buttons = driver.find_elements(By.CSS_SELECTOR, 'a[kind="BUTTON/PRIMARY"]')
    if report_buttons:
        for i in range(5):
            try:
                button = driver.find_element(By.CSS_SELECTOR, "a[href='/merchant/summary/reports/reports']")
                driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", button)
                driver.execute_script("arguments[0].click();", button)
                print("Clicked on attempt", i + 1)
                break
            except Exception as e:
                print(f"Attempt {i + 1} failed: {e}")
                time.sleep(2)

        time.sleep(7)
        close_rate_popup(driver)
        time.sleep(1)
        
        
        report_elem = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((
                By.XPATH, f"//*[contains(text(), '{report_selection}')]"
            ))
        )
        driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", report_elem)
        time.sleep(1)
        report_elem.click()
        time.sleep(7)
        next_element = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((
                By.XPATH, "//button[.//span[text()='Next']]"
            ))
        )
        driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", next_element)
        short_Random_Sleep()
        next_element.click()
        time.sleep(10)
        start_date_input = WebDriverWait(driver, 10).until(
           EC.presence_of_element_located((
               By.XPATH, "//label[normalize-space()='Select start date']/following::input[1]"
           ))
        )
        time.sleep(3)
        driver.execute_script("""
        arguments[0].value = '';
        arguments[0].dispatchEvent(new Event('input', { bubbles: true }));
        """, start_date_input)
        driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", start_date_input)
        time.sleep(1)
        start_date_input.click()
        time.sleep(1)
        start_date_input.send_keys(start_date)
        time.sleep(1)
        # Find input next to the "Select end date" label
        end_date_input = WebDriverWait(driver, 10).until(
           EC.presence_of_element_located((
               By.XPATH, "//label[normalize-space()='Select end date']/following::input[1]"
           ))
        )
        time.sleep(1)
        driver.execute_script("""
        arguments[0].value = '';
        arguments[0].dispatchEvent(new Event('input', { bubbles: true }));
        """, end_date_input)
        end_date_input.click()
        time.sleep(1)
        end_date_input.send_keys(end_date)
        medium_Random_Sleep()
        # create_button = WebDriverWait(driver, 10).until(
        #     EC.element_to_be_clickable((
        #         By.XPATH, "//button[.//span[text()='Create report']]"
        #     ))
        # )
        for i in range(5):
            try:
                button = driver.find_element(By.XPATH, "//button[.//span[text()='Create report']]")
                time.sleep(1)
                driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", button)
                time.sleep(1)
                driver.execute_script("arguments[0].click();", button)
                print("Clicked on attempt", i + 1)
                break
            except Exception as e:
                print(f"Attempt {i + 1} failed: {e}")
                time.sleep(2)

        # driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", create_button)
        # time.sleep(2)
        # create_button.click()
        medium_Random_Sleep()
        time.sleep(10)


def download_report(driver, start_date_rep):
    # For Windows, use this instead:
    us_tz = pytz.timezone('US/Eastern')
    today_str = datetime.now(us_tz).strftime('%b %#d, %Y')
    print(f"Looking for reports from: {today_str}")
    print(f"Files will be downloaded to: {DOWNLOAD_FOLDER}")

    # Step 2: Find all report elements
    time.sleep(5)
    reports_elements = driver.find_elements(By.CSS_SELECTOR, '.BodyRow-sc-xj91vc-3.TVZvw')

    # Step 3: Filter elements that contain today's date
    today_elements = [el for el in reports_elements if today_str in el.text and start_date_rep.split(',')[0] in el.text]
    if len(today_elements) < 4:
        driver.refresh()
        time.sleep(15)
        # Step 2: Find all report elements
        reports_elements = driver.find_elements(By.CSS_SELECTOR, '.BodyRow-sc-xj91vc-3.TVZvw')

        # Step 3: Filter elements that contain today's date
        today_elements = [el for el in reports_elements if today_str in el.text]
    
    if not today_elements:
        print(f"No reports found for today ({today_str})")
        return
    
    print(f"Found {len(today_elements)} report(s) to download")
    
    # for i, today_element in enumerate(today_elements, 1):
    #     try:
    #         download_button = today_element.find_element(By.CSS_SELECTOR, 'button[aria-label="Download"]')
    #         print(f"Downloading report {i}/{len(today_elements)}...")
    #         driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", download_button)
    #         time.sleep(1.5)
    #         try:
    #             download_button.click()
    #         except:
    #             driver.refresh()
    #             download_button = today_element.find_element(By.CSS_SELECTOR, 'button[aria-label="Download"]')
    #             time.sleep(1)
    #             download_button.click()
    #
    #         time.sleep(10)  # Wait for download to complete
    #         print(f"Report {i} download initiated")
    #     except Exception as e:
    #         print(f"Error downloading report {i}: {e}")
    for i, today_element in enumerate(today_elements, 1):
        try:
            print(f"Downloading report {i}/{len(today_elements)}...")

            # Find the download button inside the current element
            download_button = today_element.find_element(By.CSS_SELECTOR, 'button[aria-label="Download"]')

            # Scroll into view
            driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});",
                                  download_button)
            time.sleep(1.5)

            # Try multiple attempts to click (React-safe)
            for attempt in range(5):
                try:
                    driver.execute_script("arguments[0].click();", download_button)
                    print(f"Report {i}: Clicked on attempt {attempt + 1}")
                    break
                except Exception as e:
                    print(f"Attempt {attempt + 1} failed for report {i}: {e}")
                    time.sleep(2)

                    # Re-find the button if DOM reloaded
                    try:
                        download_button = today_element.find_element(By.CSS_SELECTOR, 'button[aria-label=\"Download\"]')
                    except:
                        # Refresh and locate again if not found
                        driver.refresh()
                        time.sleep(3)
                        today_elements = driver.find_elements(By.CSS_SELECTOR, "your-today-element-selector-here")
                        today_element = today_elements[i - 1]
                        download_button = today_element.find_element(By.CSS_SELECTOR, 'button[aria-label=\"Download\"]')

            # Optional: wait for download to start/finish
            time.sleep(10)
            print(f"✅ Report {i} download initiated")

        except Exception as e:
            print(f"❌ Error downloading report {i}: {e}")
    time.sleep(10)
    print("Download process completed!")


def get_table_name_from_filename(filename):
    """Extract table name from filename and map to BigQuery table name"""
    # Remove timestamp and extension
    base_name = filename.replace('.csv', '')
    
    # Find matching table name
    for key, value in TABLE_MAPPING.items():
        if key in base_name:
            return value
    
    return None

def upload_file_to_gcs(file_path, table_name):
    """Upload a CSV file directly to BigQuery via FastAPI"""
    try:
        print(f"Uploading {file_path} to BigQuery...")
        
        # Upload directly to BigQuery via FastAPI endpoint
        with open(file_path, 'rb') as f:
            files = {'file': (os.path.basename(file_path), f, 'text/csv')}
            data = {'table_name': table_name}
            
            response = requests.post(
                f"{FASTAPI_ENDPOINT}/upload-to-gcs",
                files=files,
                data=data,
                timeout=300  # 5 minutes timeout
            )
            
            if response.status_code == 200:
                result = response.json()
                rows_loaded = result.get('rows', 0)
                print(f" SUCCESS: Successfully uploaded {file_path} to BigQuery. Rows loaded: {rows_loaded}")
                return True, result
            else:
                print(f"ERROR: Failed to upload {file_path} to BigQuery. Status: {response.status_code}")
                print(f"Response: {response.text}")
                return False, response.text
                
    except Exception as e:
        print(f"ERROR: Error uploading {file_path} to BigQuery: {str(e)}")
        return False, str(e)



def move_file_to_manual_upload(file_path, reason="", upload_log=None):
    """Move file to manual upload folder and log it"""
    try:
        filename = os.path.basename(file_path)
        destination = os.path.join(MANUAL_UPLOAD_FOLDER, filename)
        
        # If file already exists, add timestamp
        if os.path.exists(destination):
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            name, ext = os.path.splitext(filename)
            filename = f"{name}_{timestamp}{ext}"
            destination = os.path.join(MANUAL_UPLOAD_FOLDER, filename)
        
        shutil.move(file_path, destination)
        print(f"  Moved {filename} to manual upload folder. Reason: {reason}")
        
        # Log the file as manually processed
        if upload_log is not None:
            file_hash = get_file_hash(destination)
            if file_hash:
                upload_log["manual_files"][file_hash] = {
                    "filename": filename,
                    "reason": reason,
                    "timestamp": datetime.now().isoformat(),
                    "original_path": file_path
                }
        
        return destination
    except Exception as e:
        print(f"ERROR: Error moving file {file_path}: {str(e)}")
        return None

def move_file_to_processed(file_path, upload_log=None):
    """Move file to processed folder and log it"""
    try:
        filename = os.path.basename(file_path)
        destination = os.path.join(PROCESSED_FOLDER, filename)
        
        # If file already exists, add timestamp
        if os.path.exists(destination):
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            name, ext = os.path.splitext(filename)
            filename = f"{name}_{timestamp}{ext}"
            destination = os.path.join(PROCESSED_FOLDER, filename)
        
        shutil.move(file_path, destination)
        print(f" SUCCESS: Moved {filename} to processed folder")
        
        # Log the file as successfully processed
        if upload_log is not None:
            file_hash = get_file_hash(destination)
            if file_hash:
                upload_log["processed_files"][file_hash] = {
                    "filename": filename,
                    "timestamp": datetime.now().isoformat(),
                    "original_path": file_path
                }
        
        return destination
    except Exception as e:
        print(f"ERROR: Error moving file {file_path}: {str(e)}")
        return None

def extract_and_process_zip_files(upload_log):
    """Extract zip files and process CSV files"""
    print(" Looking for zip files in downloads folder and subfolders...")
    
    # Find all zip files in downloads folder and all subfolders
    zip_files = []
    for root, dirs, files in os.walk(DOWNLOAD_FOLDER):
        for file in files:
            if file.endswith('.zip'):
                zip_files.append(os.path.join(root, file))
    
    if not zip_files:
        print("No zip files found in downloads folder or subfolders")
        return
    
    print(f" Found {len(zip_files)} zip files to process")
    
    for zip_file in zip_files:
        zip_path = zip_file
        zip_name = os.path.basename(zip_file)
        folder_name = os.path.basename(os.path.dirname(zip_file))
        print(f" Processing zip file: {zip_name} from folder: {folder_name}")
        
        try:
            # Extract zip file to the same folder it's in
            extract_folder = os.path.dirname(zip_path)
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(extract_folder)
            
            # Find CSV files in the extracted content (same folder)
            csv_files = []
            for file in os.listdir(extract_folder):
                if file.endswith('.csv'):
                    csv_files.append(os.path.join(extract_folder, file))
            
            print(f"Found {len(csv_files)} CSV files in {folder_name}")
            
            # Process each CSV file
            for csv_file in csv_files:
                process_csv_file(csv_file, upload_log)
            
            # Move zip file to processed folder
            move_file_to_processed(zip_path, upload_log)
            
        except Exception as e:
            print(f"ERROR: Error processing zip file {zip_name}: {str(e)}")

def process_csv_file(file_path, upload_log):
    """Process a single CSV file"""
    filename = os.path.basename(file_path)
    print(f"\n Processing CSV file: {filename}")
    
    # Check if file has already been processed
    if is_file_already_processed(file_path, upload_log):
        print(f" Skipping {filename} - already processed")
        return
    
    # Get table name from filename
    table_name = get_table_name_from_filename(filename)
    
    if not table_name:
        print(f"ERROR: Could not determine table name for {filename}")
        move_file_to_manual_upload(file_path, "Unknown table mapping", upload_log)
        return
    
    print(f"Table name: {table_name}")
    
    # Upload directly to BigQuery via FastAPI
    success, result = upload_file_to_gcs(file_path, table_name)
    
    if success:
        # Move to processed folder
        move_file_to_processed(file_path, upload_log)
    else:
        # Log as failed and move to manual upload folder
        file_hash = get_file_hash(file_path)
        if file_hash:
            upload_log["failed_files"][file_hash] = {
                "filename": filename,
                "error": result,
                "timestamp": datetime.now().isoformat(),
                "original_path": file_path
            }
        move_file_to_manual_upload(file_path, f"Processing failed: {result}", upload_log)

def auto_upload_downloaded_files():
    """Main function to automatically upload downloaded files"""
    print("START: Starting automatic file upload process...")
    print(f"  Downloads folder: {DOWNLOAD_FOLDER}")
    print(f"  Manual upload folder: {MANUAL_UPLOAD_FOLDER}")
    print(f"  Processed folder: {PROCESSED_FOLDER}")
    print(f" Upload log: {UPLOAD_LOG_FILE}")
    
    # First, move any existing files from script directory to downloads
    move_existing_files_to_downloads()
    
    # Check what's in the downloads folder
    check_downloads_folder()
    
    # Load upload log
    upload_log = load_upload_log()
    print(f"Found {len(upload_log['processed_files'])} previously processed files")
    print(f"Found {len(upload_log['failed_files'])} previously failed files")
    print(f"Found {len(upload_log['manual_files'])} previously manual files")
    
    # Process zip files first
    extract_and_process_zip_files(upload_log)
    
    # Process any remaining CSV files in downloads folder and subfolders
    csv_files = []
    for root, dirs, files in os.walk(DOWNLOAD_FOLDER):
        for file in files:
            if file.endswith('.csv'):
                csv_files.append(os.path.join(root, file))
    
    if csv_files:
        print(f"\n Found {len(csv_files)} CSV files to process")
        for csv_file in csv_files:
            process_csv_file(csv_file, upload_log)
    else:
        print("No CSV files found to process")
    
    # Save upload log
    save_upload_log(upload_log)
    
    print("\n SUCCESS: Automatic upload process completed!")
    print(f"Check the '{MANUAL_UPLOAD_FOLDER}' folder for files that need manual processing")
    print(f" Upload log saved to: {UPLOAD_LOG_FILE}")

def get_previous_monday_to_sunday():
    """Calculate the date range from previous Monday to Sunday."""
    today = datetime.now()
    
    # Find the most recent Monday (0 = Monday, 6 = Sunday)
    days_since_monday = today.weekday()
    
    # Calculate previous Monday
    previous_monday = today - timedelta(days=days_since_monday + 7)
    
    # Calculate previous Sunday (6 days after Monday)
    previous_sunday = previous_monday + timedelta(days=6)
    
    # Format dates as MM/DD/YYYY (Windows format)
    start_date = previous_monday.strftime('%#m/%#d/%Y')
    end_date = previous_sunday.strftime('%#m/%#d/%Y')
    start_date_report = previous_monday.strftime('%b %#d, %Y')
    
    return start_date, end_date, start_date_report


def load_accounts_from_csv():
    """Load all accounts from the CSV file."""
    try:
        df = pd.read_csv(CREDENTIALS_FILE)
        # Filter out rows with empty MultiLogin_ID
        df = df.dropna(subset=['MultiLogin_ID'])
        df = df[df['MultiLogin_ID'].str.strip() != '']
        
        accounts = []
        for _, row in df.iterrows():
            account = {
                'name': row['DD Name'],
                'username': row['DD UN'],
                'password': row['DD PW'],
                'multilogin_id': row['MultiLogin_ID']
            }
            accounts.append(account)
        
        print(f" Loaded {len(accounts)} accounts from CSV")
        return accounts
    except Exception as e:
        print(f"ERROR: Error loading accounts from CSV: {e}")
        return []


def close_reports_popup(driver):
    """Close the reports popup modal if it appears."""
    try:
        # Look for the close button with the specific aria-label
        close_button = WebDriverWait(driver, 5).until(
            EC.element_to_be_clickable((
                By.XPATH, "//button[@aria-label='Close All your DoorDash reports in one place']"
            ))
        )
        print(" Reports popup detected, closing...")
        close_button.click()
        time.sleep(2)
        print(" SUCCESS: Reports popup closed successfully")
        return True
    except Exception:
        # No popup found, which is fine
        return False

def close_rate_popup(driver):
    """Close the reports popup modal if it appears."""
    try:
        # Look for the close button with the specific aria-label
        close_button = WebDriverWait(driver, 5).until(
            EC.element_to_be_clickable((
                By.CSS_SELECTOR, "[class='QSIWebResponsiveDialog-Layout1-SI_6hdn6evIXCRk1P8_close-btn']"
            ))
        )
        print(" Reports popup detected, closing...")
        close_button.click()
        time.sleep(2)
        print(" SUCCESS: Reports popup closed successfully")
        return True
    except Exception:
        # No popup found, which is fine
        return False


def extract_zip_files_in_account_folder(account_folder_path):
    """Extract zip files in an account folder and organize them into separate folders."""
    print(f" Extracting zip files in: {os.path.basename(account_folder_path)}")
    
    # Find all zip files in the account folder
    zip_files = [f for f in os.listdir(account_folder_path) if f.endswith('.zip')]
    
    if not zip_files:
        print("info No zip files found to extract")
        return
    
    print(f" Found {len(zip_files)} zip files to extract")
    
    for zip_file in zip_files:
        zip_path = os.path.join(account_folder_path, zip_file)
        zip_name = os.path.splitext(zip_file)[0]  # Remove .zip extension
        
        # Create a shorter, safer folder name to avoid path length issues
        safe_folder_name = zip_name[:50] if len(zip_name) > 50 else zip_name
        extract_folder = os.path.join(account_folder_path, safe_folder_name)
        os.makedirs(extract_folder, exist_ok=True)
        
        try:
            print(f" Extracting {zip_file} to {safe_folder_name}/")
            
            # Extract zip file to the new folder
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                # Get list of files in zip before extracting
                file_list = zip_ref.namelist()
                print(f" Files in zip: {len(file_list)}")
                
                # Extract files one by one to handle long filenames
                for file_info in zip_ref.infolist():
                    try:
                        # Extract single file
                        zip_ref.extract(file_info, extract_folder)
                    except Exception as file_error:
                        print(f"⚠️ Warning: Could not extract {file_info.filename}: {file_error}")
                        continue
            
            # Count extracted files
            extracted_files = []
            for root, dirs, files in os.walk(extract_folder):
                for file in files:
                    extracted_files.append(file)
            
            print(f" SUCCESS: Extracted {len(extracted_files)} files from {zip_file}")
            
            # Move the original zip file to the extracted folder
            zip_destination = os.path.join(extract_folder, zip_file)
            shutil.move(zip_path, zip_destination)
            print(f"  Moved {zip_file} to {safe_folder_name}/ folder")
            
        except Exception as e:
            print(f"ERROR: Error extracting {zip_file}: {str(e)}")
            # Try to clean up the folder if it was created
            try:
                if os.path.exists(extract_folder) and os.listdir(extract_folder) == []:
                    os.rmdir(extract_folder)
            except:
                pass
    
    print(f" SUCCESS: Zip extraction completed for {os.path.basename(account_folder_path)}")


def process_single_account(account, start_date, end_date, start_date_rep, folder_id, headers):
    """Process a single account - create reports and download them."""
    print(f"\n Processing account: {account['name']}")
    print(f" Date range: {start_date} to {end_date}")
    
    try:
        # Create account-specific download folder
        account_folder_name = f"{account['name']}_{start_date.replace('/', '-')}_to_{end_date.replace('/', '-')}"
        account_download_folder = os.path.join(DOWNLOAD_FOLDER, account_folder_name)
        os.makedirs(account_download_folder, exist_ok=True)
        print(f"  Created download folder: {account_folder_name}")
        
        # Start selenium session for this account
        driver, profile_data = start_selenium_session(account['multilogin_id'], folder_id, headers)
        if not driver:
            print(f"ERROR: Failed to start session for {account['name']}")
            return False
        
        
        
        # Navigate to DoorDash portal
        driver, profile_data = test_and_change_proxy(
            driver, 
            "https://merchant-portal.doordash.com/merchant/reports", 
            account['multilogin_id'], 
            headers, 
            profile_data
        )
        # Set download directory for this specific account
        driver.execute_cdp_cmd('Page.setDownloadBehavior', {
            'behavior': 'allow',
            'downloadPath': account_download_folder
        })
        
        time.sleep(15)
        
        # Check for and close reports popup if it appears
        close_reports_popup(driver)
        close_rate_popup(driver)
        
        # Create reports for this account
        reports_list_dict = [{'Name':'Financial report', 'Type':'Financials'}, {'Name':'Operations report', 'Type':'Operations'}, {'Name':'Marketing report', 'Type':'Marketing'}, {'Name':'Sales report', 'Type':'Sales'}]
        #reports_list = ['Marketing report']
        us_tz = pytz.timezone('US/Eastern')
        today_str = datetime.now(us_tz).strftime('%b %#d, %Y')
        print(f"Looking for reports from: {today_str}")
        print(f"Files will be downloaded to: {DOWNLOAD_FOLDER}")

        # Step 2: Find all report elements
        time.sleep(5)
        reports_elements = driver.find_elements(By.CSS_SELECTOR, '.BodyRow-sc-xj91vc-3.TVZvw')

        # Step 3: Filter elements that contain today's date
        today_elements = [el for el in reports_elements if today_str in el.text and start_date_rep.split(',')[0] in el.text]
        if len(today_elements) < 7:
            for report_type in reports_list_dict:
                reports_elements = driver.find_elements(By.CSS_SELECTOR, '.BodyRow-sc-xj91vc-3.TVZvw')
                # Step 3: Filter elements that contain today's date
                today_elements = [el for el in reports_elements if
                                  today_str in el.text and start_date_rep.split(',')[0] in el.text]
                if len([v for v in today_elements if report_type['Type'] in v.text]) == 0:
                    print(f"Creating {report_type['Name']} for {account['name']}...")
                    create_report(driver, report_type['Name'], start_date, end_date)
                    driver.get("https://merchant-portal.doordash.com/merchant/reports")
                    time.sleep(20)
                    close_rate_popup(driver)


            # Navigate back to reports page and download
            driver.get("https://merchant-portal.doordash.com/merchant/reports")
            time.sleep(15)

        # # Check for and close reports popup again (in case it appears after navigation)
        time.sleep(10)
        close_reports_popup(driver)
        close_rate_popup(driver)

        while True:
            try:
                driver.find_element(By.CSS_SELECTOR, '.styles__ButtonRoot-sc-1ldytso-0.dHEiWH')
                time.sleep(15)
                driver.get("https://merchant-portal.doordash.com/merchant/reports")
            except Exception:
                break
        # Download reports
        time.sleep(5)
        download_report(driver, start_date_rep)
        print(f" SUCCESS: Reports downloaded for {account['name']} to folder: {account_folder_name}")
        
        # Extract zip files after download
        extract_zip_files_in_account_folder(account_download_folder)
        
        # Stop browser session
        stop_browser(account['multilogin_id'], driver)
        
        return True
        
    except Exception as e:
        print(f"ERROR: Error processing account {account['name']}: {e}")
        #try:
        #    stop_browser(account['multilogin_id'], driver)
        #except:
        #    pass
        return False


def run_download_and_auto_upload():
    """Run the complete download and auto-upload process"""
    print("START: Starting DoorDash download and auto-upload process...")
    
    # First run the original download automation
    print(" Step 1: Downloading DoorDash reports...")
    
    # Run the original main logic
    token = signin()
    HEADERS.update({"Authorization": f"Bearer {token}"})
    folder_id = workspace_folder_id(HEADERS)
    MultiloginID = '447eb1c4-cc59-492e-89c6-f5ecb4294056'
    driver, profile_data = start_selenium_session(MultiloginID, folder_id, HEADERS)
    driver, profile_data = test_and_change_proxy(driver, "https://merchant-portal.doordash.com/merchant/reports", MultiloginID, HEADERS, profile_data)
    
    time.sleep(15)
    while True:
        try:
            driver.find_element(By.CSS_SELECTOR, '.styles__ButtonRoot-sc-1ldytso-0.dHEiWH')
            time.sleep(5)
        except Exception:
            break

    download_report(driver)
    print(" SUCCESS: Download process completed!")
    
    # Wait for downloads to complete
    print(" Waiting for downloads to complete...")
    time.sleep(30)
    
    # Then run the auto-upload process
    print(" Step 2: Auto-uploading files to BigQuery...")
    auto_upload_downloaded_files()
    
    print(" SUCCESS: Complete process finished!")


def extract_all_existing_zip_files():
    """Extract all existing zip files in all account folders."""
    print(" Looking for existing zip files to extract...")
    
    if not os.path.exists(DOWNLOAD_FOLDER):
        print("ERROR: Downloads folder does not exist")
        return
    
    # Find all account folders
    account_folders = []
    for item in os.listdir(DOWNLOAD_FOLDER):
        item_path = os.path.join(DOWNLOAD_FOLDER, item)
        if os.path.isdir(item_path):
            account_folders.append(item_path)
    
    if not account_folders:
        print("info No account folders found in downloads")
        return
    
    print(f"  Found {len(account_folders)} account folders")
    
    for account_folder in account_folders:
        extract_zip_files_in_account_folder(account_folder)
    
    print(" SUCCESS: All existing zip files have been extracted!")


if __name__ == '__main__':
    print("START: Starting DoorDash report automation for all accounts...")
    
    # Get date range (previous Monday to Sunday)
    start_date, end_date, start_date_rep = get_previous_monday_to_sunday()
    print(f" Using date range: {start_date} to {end_date}")
    
    # Load all accounts from CSV
    accounts = load_accounts_from_csv()
    if not accounts:
        print("ERROR: No accounts found in CSV file. Exiting.")
        sys.exit(1)
    
    # Initialize MultiLogin
    token = signin()
    HEADERS.update({"Authorization": f"Bearer {token}"})
    folder_id = workspace_folder_id(HEADERS)
    
    # Process each account
    successful_accounts = 0
    failed_accounts = 0
    tries = 0
    for i, account in enumerate(accounts, 1):
        print(f"\n{'='*60}")
        print(f"Processing account {i}/{len(accounts)}: {account['name']}")
        print(f"{'='*60}")
        
        success = process_single_account(account, start_date, end_date, start_date_rep, folder_id, HEADERS)

        if success:
            successful_accounts += 1
            print(f" SUCCESS: Successfully processed {account['name']}")
        else:
            failed_accounts += 1
            print(f"ERROR: Failed to process {account['name']}")
        
        # Wait between accounts to avoid overwhelming the system
        if i < len(accounts):
            print(" Waiting 30 seconds before next account...")
            time.sleep(30)
        tries += 1
        if tries > 3:
            token = signin()
            HEADERS.update({"Authorization": f"Bearer {token}"})
            folder_id = workspace_folder_id(HEADERS)
            tries = 0
    
    # Summary
    print(f"\n{'='*60}")
    print("PROCESSING SUMMARY")
    print(f"{'='*60}")
    print(f" SUCCESS: Successfully processed: {successful_accounts} accounts")
    print(f"ERROR: Failed to process: {failed_accounts} accounts")
    print(f"  Check the downloads folder for all downloaded reports")
    print(" DoorDash report automation completed!")
