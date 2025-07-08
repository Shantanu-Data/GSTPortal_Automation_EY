"""
downloader.py
-------------
Wraps the original long Selenium script in a single function
so Streamlit can call it for any user + any mix of documents.

You only need to edit *inside* the five task-blocks (marked ###)
if you want to tweak locators.  Everything else is unchanged.
"""
from __future__ import annotations

import os
import glob
import time
import pandas as pd
from pathlib import Path
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC

# ────────────────────────────────────────────────────────────────────────────────
# Helpers (unchanged from your original script)
# ────────────────────────────────────────────────────────────────────────────────
def wait_for_download_and_move(
    src_dir: str | Path,
    target_dir: str | Path,
    label: str,
    timeout: int = 30
) -> None:
    print(f"⏳ Waiting for {label} file to download…")
    end_time = time.time() + timeout
    downloaded = None

    while time.time() < end_time:
        files = glob.glob(os.path.join(src_dir, "*.pdf")) + \
                glob.glob(os.path.join(src_dir, "*.csv"))
        cr_files = glob.glob(os.path.join(src_dir, "*.crdownload"))
        if files and not cr_files:
            downloaded = max(files, key=os.path.getctime)
            break
        time.sleep(1)

    if downloaded:
        Path(target_dir).mkdir(parents=True, exist_ok=True)
        dest = Path(target_dir, Path(downloaded).name)
        os.rename(downloaded, dest)
        print(f"✅ {label} downloaded → {dest}")
    else:
        print(f"❌ {label} download timed-out.")


def wait_overlay(driver):
    """Block until the GST portal’s ‘dimmer-holder’ overlay disappears."""
    try:
        WebDriverWait(driver, 3).until_not(
            EC.presence_of_element_located((By.CLASS_NAME, "dimmer-holder"))
        )
    except Exception:
        WebDriverWait(driver, 3).until(
            lambda d: d.execute_script(
                "return document.querySelector('.dimmer-holder')?.style.display === 'none'"
            )
        )


# ────────────────────────────────────────────────────────────────────────────────
#              🔑  Main entry-point called by the Streamlit UI
# ────────────────────────────────────────────────────────────────────────────────
def run_automation(
    row: pd.Series,
    tasks: list[str],
    base_download_dir: str | Path = "downloads"
) -> None:
    """
    Parameters
    ----------
    row   : one row from Data.xlsx (Username, Password, dates, FY, etc.)
    tasks : any combo of ['gstr1','gstr3b','cash','credit','reversal']
    base_download_dir : root folder for all PDFs/Excels
    """
    base_dir     = Path(base_download_dir).resolve()
    gstr3b_dir   = base_dir / "GSTR-3B"
    gstr1_dir    = base_dir / "GSTR-1"
    cash_dir     = base_dir / "Cash Ledger"
    credit_dir   = base_dir / "Credit Ledger"
    reversal_dir = base_dir / "Credit-Reversal"
    base_dir.mkdir(exist_ok=True)

    # Unpack spreadsheet fields
    username = row["Username"]
    password = row["Password"]
    from_dt  = row.get("From")         # expect datetime, not str
    to_dt    = row.get("To")
    fy       = row.get("Financial year")
    qtr      = row.get("Quarter")
    period   = row.get("Period")

    # Selenium options
    opts = webdriver.EdgeOptions()
    opts.use_chromium = True
    opts.add_experimental_option("prefs", {
        "download.default_directory": str(base_dir),
        "download.prompt_for_download": False,
        "plugins.always_open_pdf_externally": True,
        "profile.default_content_setting_values.automatic_downloads": 1
    })

    driver = webdriver.Edge(options=opts)
    wait   = WebDriverWait(driver, 15)

    try:
        # ── Login ───────────────────────────────────────────────────────────────
        max_attempts = 3

        for attempt in range(1, max_attempts + 1):
         driver.get("https://services.gst.gov.in/services/login")
         wait.until(EC.presence_of_element_located((By.ID, "username"))).send_keys(username)
         driver.find_element(By.ID, "user_pass").send_keys(password)
         print("⌛  PLEASE solve the CAPTCHA within 7 s…")
         time.sleep(7)  # manual CAPTCHA
         wait.until(EC.element_to_be_clickable(
             (By.XPATH, "//button[normalize-space()='Login']"))).click()
         time.sleep(3)
         if "login" not in driver.current_url:
                print("✅  Logged in successfully")
                break
         if "login" in driver.current_url:
             print("⚠️  Login failed (wrong creds or CAPTCHA).")
             if attempt == max_attempts:
              print(f"❌  All {max_attempts} login attempts failed for {username}, skipping user.")
              return  

        # Close “Remind me later” modal (best-effort)
        try:
             wait.until(EC.element_to_be_clickable(
                 (By.XPATH, "//a[normalize-space(text())='Remind me later']"))).click()
        except  Exception:
             pass

        # ── DOCUMENT-SPECIFIC SECTIONS ─────────────────────────────────────────
        # NOTE: each block is *identical* to your original code, just under
        #       an `if "<task>" in tasks:` guard
        # ----------------------------------------------------------------------
        ## 1. GSTR-3B ###########################################################
        if "gstr3b" in tasks:
            time.sleep(3)
            wait.until(EC.element_to_be_clickable(
                (By.XPATH, "//a[normalize-space(text())='Dashboard']"))).click()
            wait_overlay(driver)

            file_returns_btn = wait.until(EC.presence_of_element_located((
                By.XPATH,
                "//a[.//span[contains(translate(normalize-space(text()),"
                " 'abcdefghijklmnopqrstuvwxyz', 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'),"
                " 'FILE RETURNS')]]"
            )))
            driver.execute_script("arguments[0].click();", file_returns_btn)
            print("✅ Clicked 'FILE RETURNS' button")

            wait.until(EC.presence_of_element_located((By.NAME, "fin")))
            Select(driver.find_element(By.NAME, "fin")).select_by_visible_text(fy)
            Select(driver.find_element(By.NAME, "quarter")).select_by_visible_text(qtr)
            Select(driver.find_element(By.NAME, "mon")).select_by_visible_text(period)
            wait_overlay(driver)
            wait.until(EC.element_to_be_clickable(
                (By.XPATH, "//button[contains(text(), 'Search')]"))).click()
            wait.until(EC.element_to_be_clickable(
                (By.XPATH,
                 "//button[contains(text(), 'Download') and "
                 "@data-ng-click='downloadGSTR3Bpdf()']"))).click()
            time.sleep(3)
            wait_for_download_and_move(base_dir, gstr3b_dir, "GSTR-3B")

        ## 2. GSTR-1 ###########################################################
        if "gstr1" in tasks:
            time.sleep(3)
            wait.until(EC.element_to_be_clickable(
                (By.XPATH, "//a[normalize-space(text())='Dashboard']"))).click()
            wait_overlay(driver)

            file_returns_btn = wait.until(EC.presence_of_element_located((
                By.XPATH,
                "//a[.//span[contains(translate(normalize-space(text()),"
                " 'abcdefghijklmnopqrstuvwxyz', 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'),"
                " 'FILE RETURNS')]]"
            )))
            driver.execute_script("arguments[0].click();", file_returns_btn)
            print("✅ Clicked 'FILE RETURNS' button")
            wait_overlay(driver)

            wait.until(EC.presence_of_element_located((By.NAME, "fin")))
            Select(driver.find_element(By.NAME, "fin")).select_by_visible_text(fy)
            Select(driver.find_element(By.NAME, "quarter")).select_by_visible_text(qtr)
            Select(driver.find_element(By.NAME, "mon")).select_by_visible_text(period)
            wait_overlay(driver)
            wait.until(EC.element_to_be_clickable(
                (By.XPATH, "//button[contains(text(), 'Search')]"))).click()
            wait_overlay(driver)
            wait.until(EC.element_to_be_clickable((
                By.XPATH,
                "//p[contains(text(), 'Details of outward supplies of goods or services')]"
            ))).click()
            wait_overlay(driver)
            wait.until(EC.element_to_be_clickable((
                By.XPATH, "//button[span[normalize-space(text())='VIEW SUMMARY']]"
            ))).click()
            wait_overlay(driver)
            wait.until(EC.element_to_be_clickable((
                By.XPATH, "//button[span[normalize-space(text())='DOWNLOAD (PDF)']]"
            ))).click()
            time.sleep(3)
            wait_for_download_and_move(base_dir, gstr1_dir, "GSTR-1")
            time.sleep(3)

        ## 3. Electronic Cash Ledger ###########################################
        if "cash" in tasks:
            wait.until(EC.element_to_be_clickable((By.LINK_TEXT, "Services"))).click()
            wait_overlay(driver)
            wait.until(EC.element_to_be_clickable((By.LINK_TEXT, "Ledgers"))).click()
            wait_overlay(driver)
            wait.until(EC.element_to_be_clickable((By.LINK_TEXT, "Electronic Cash Ledger"))).click()
            wait_overlay(driver)
            wait.until(EC.element_to_be_clickable((
                By.XPATH,
                "//a[contains(text(),'Electronic Cash Ledger') and "
                "contains(@href,'/payment/auth/ledger/detailedledger')]"
            ))).click()
            wait_overlay(driver)

            driver.find_element(By.ID, "chlg_frdt").clear()
            driver.find_element(By.ID, "chlg_frdt").send_keys(from_dt.strftime("%d/%m/%Y"))
            driver.find_element(By.ID, "chlg_todt").clear()
            driver.find_element(By.ID, "chlg_todt").send_keys(to_dt.strftime("%d/%m/%Y"))

            wait.until(EC.element_to_be_clickable(
                (By.XPATH, "//button[contains(text(), 'GO')]"))).click()
            time.sleep(5)
            wait.until(EC.element_to_be_clickable(
                (By.XPATH, "//button[contains(text(), 'Save as Excel')]"))).click()
            time.sleep(3)
            wait_for_download_and_move(base_dir, cash_dir, "Cash Ledger")
            time.sleep(3)

        ## 4. Electronic Credit Ledger #########################################
        if "credit" in tasks:
            wait_overlay(driver)
            wait.until(EC.element_to_be_clickable((By.LINK_TEXT, "Services"))).click()
            wait_overlay(driver)
            wait.until(EC.element_to_be_clickable((By.LINK_TEXT, "Ledgers"))).click()
            wait_overlay(driver)
            wait.until(EC.element_to_be_clickable((By.LINK_TEXT, "Electronic Credit Ledger"))).click()
            wait_overlay(driver)
            wait.until(EC.element_to_be_clickable((
                By.XPATH,
                "//a[contains(text(),'Electronic Credit Ledger') and "
                "contains(@href,'/returns/auth/ledger/detailedledger')]"
            ))).click()
            wait_overlay(driver)

            driver.find_element(By.ID, "sumlg_frdt").clear()
            driver.find_element(By.ID, "sumlg_frdt").send_keys(from_dt.strftime("%d-%m-%Y"))
            driver.find_element(By.ID, "sumlg_todt").clear()
            driver.find_element(By.ID, "sumlg_todt").send_keys(to_dt.strftime("%d-%m-%Y"))

            wait.until(EC.element_to_be_clickable(
                (By.XPATH, "//button[contains(text(), 'GO')]"))).click()
            time.sleep(5)
            wait.until(EC.element_to_be_clickable(
                (By.XPATH, "//button[contains(text(), 'Save As Excel')]"))).click()
            time.sleep(5)
            wait_for_download_and_move(base_dir, credit_dir, "Credit Ledger")
            time.sleep(3)

        ## 5. Credit Reversal ###################################################
        if "reversal" in tasks:
            wait_overlay(driver)
            wait.until(EC.element_to_be_clickable((By.LINK_TEXT, "Services"))).click()
            wait_overlay(driver)
            wait.until(EC.element_to_be_clickable((By.LINK_TEXT, "Ledgers"))).click()
            reversal_link = wait.until(EC.presence_of_element_located((
                By.XPATH,
                "//a[contains(@href,'revreclaimstmt') and contains(text(),'Electronic Credit Reversal')]"
            )))
            driver.execute_script("arguments[0].click();", reversal_link)
            wait_overlay(driver)

            wait.until(EC.element_to_be_clickable((
                By.XPATH,
                "//a[contains(@href,'revreclaimdetledger') and contains(text(),'Electronic Credit Reversal')]"
            ))).click()
            wait_overlay(driver)

            driver.find_element(By.ID, "sumlg_frdt").clear()
            driver.find_element(By.ID, "sumlg_frdt").send_keys(from_dt.strftime("%d-%m-%Y"))
            driver.find_element(By.ID, "sumlg_todt").clear()
            driver.find_element(By.ID, "sumlg_todt").send_keys(to_dt.strftime("%d-%m-%Y"))

            wait.until(EC.element_to_be_clickable((
                By.XPATH,
                "//button[@data-ng-click='getrestmt()' and contains(text(), 'GO')]"
            ))).click()
            time.sleep(5)
            wait.until(EC.element_to_be_clickable((
                By.XPATH,
                "//button[@data-ng-click='downloadExcelForRclm()' and contains(text(), 'Save as Excel')]"
            ))).click()
            time.sleep(5)
            wait_for_download_and_move(base_dir, reversal_dir, "Reversal Statement")
            time.sleep(3)

    except Exception as e:
        print(f"❌ ERROR for {username}: {e}")

    finally:
        driver.quit()
        print(f"✅ Completed user {username}")
