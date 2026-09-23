import time
import re
import hashlib
import json
import os
from playwright.sync_api import sync_playwright

# ============================================
# KONFIGURASI
# ============================================

BOT_TOKEN = "8578361582:AAHwuC8x9CmdEJB0_4KF6fJg7ctUIRm9lOY"
OWNER_ID = 8965979911
GROUP_ID = -5445996631

IVASMS_EMAIL = "alifvivo124@gmail.com"
IVASMS_PASSWORD = "nutsdev1"

POLL_INTERVAL = 60
TELEGRAM_API = "https://api.telegram.org"
CACHE_FILE = "otp_cache.json"


def send_telegram(chat_id, text):
    import requests
    url = f"{TELEGRAM_API}/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True
    }
    try:
        r = requests.post(url, json=payload, timeout=10)
        hasil = r.json()
        if not hasil.get("ok"):
            print(f"[ERROR] Gagal kirim ke {chat_id}: {hasil}")
        return hasil
    except Exception as e:
        print(f"[ERROR] Exception: {e}")
        return None


class IVASMSScraper:
    def __init__(self, email, password):
        self.email = email
        self.password = password
        self.playwright = None
        self.browser = None
        self.page = None
        self.logged_in = False

    def start(self):
        self.playwright = sync_playwright().start()
        self.browser = self.playwright.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-blink-features=AutomationControlled"
            ]
        )
        self.page = self.browser.new_page(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        print("[OK] Browser siap")

    def login(self):
        try:
            print("[INFO] Buka halaman login IVASMS...")
            self.page.goto("https://www.ivasms.com/login", timeout=60000)
            self.page.wait_for_timeout(8000)  # tunggu Cloudflare selesai

            # Cek apakah halaman login sudah kebuka
            content = self.page.content().lower()
            if "cloudflare" in content and "just a moment" in content:
                print("[WAIT] Cloudflare challenge, tunggu...")
                self.page.wait_for_timeout(10000)

            print("[INFO] Isi form login...")
            # Coba beberapa selector umum
            try:
                self.page.fill('input[name="email"]', self.email, timeout=10000)
            except:
                self.page.fill('input[type="email"]', self.email, timeout=10000)

            self.page.fill('input[name="password"]', self.password, timeout=10000)

            print("[INFO] Klik login...")
            self.page.click('button[type="submit"]', timeout=10000)
            self.page.wait_for_timeout(8000)

            # Cek login berhasil
            url_sekarang = self.page.url.lower()
            content_sekarang = self.page.content().lower()

            if "dashboard" in url_sekarang or "logout" in content_sekarang:
                self.logged_in = True
                print("[OK] Login IVASMS berhasil")
                return True

            print(f"[GAGAL] Login gagal. URL: {self.page.url}")
            return False
        except Exception as e:
            print(f"[ERROR] Login: {e}")
            return False

    def fetch_otps(self):
        if not self.logged_in:
            if not self.login():
                return []
        try:
            self.page.goto("https://www.ivasms.com/otp", timeout=30000)
            self.page.wait_for_timeout(3000)
            html = self.page.content()

            # Simpan HTML untuk debug
            with open("last_page.html", "w", encoding="utf-8") as f:
                f.write(html)

            otps = []
            pola = re.compile(r'(\+?\d{10,15})\D{0,50}?(\d{6})')
            for match in pola.finditer(html):
                otps.append({
                    "phone": match.group(1),
                    "otp": match.group(2)
                })
            return otps
        except Exception as e:
            print(f"[ERROR] Fetch OTP: {e}")
            return []

    def close(self):
        if self.browser:
            self.browser.close()
        if self.playwright:
            self.playwright.stop()


def load_cache():
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, "r") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def save_cache(cache):
    try:
        with open(CACHE_FILE, "w") as f:
            json.dump(cache, f)
    except Exception as e:
        print(f"[ERROR] Save cache: {e}")


def fingerprint(item):
    raw = f"{item['phone']}:{item['otp']}"
    return hashlib.md5(raw.encode()).hexdigest()


def main():
    print("=" * 40)
    print("BOT IVASMS OTP - START (Playwright)")
    print(f"Owner: {OWNER_ID}")
    print(f"Grup : {GROUP_ID}")
    print("=" * 40)

    scraper = IVASMSScraper(IVASMS_EMAIL, IVASMS_PASSWORD)
    scraper.start()
    cache = load_cache()

    print("[INFO] Kirim notif start...")
    send_telegram(OWNER_ID, "[BOT] Aktif (Playwright), mulai pantau OTP IVASMS")
    time.sleep(1)
    send_telegram(GROUP_ID, "[BOT] Aktif (Playwright), mulai pantau OTP IVASMS")

    while True:
        try:
            daftar = scraper.fetch_otps()
            print(f"[CEK] Dapat {len(daftar)} OTP")

            for item in daftar:
                fp = fingerprint(item)
                if fp in cache:
                    continue

                pesan = (
                    f"<b>OTP BARU</b>\n\n"
                    f"<b>Nomor:</b> <code>{item['phone']}</code>\n"
                    f"<b>OTP:</b> <code>{item['otp']}</code>\n"
                    f"<b>Waktu:</b> {time.strftime('%H:%M:%S')}"
                )

                send_telegram(OWNER_ID, pesan)
                time.sleep(1)
                send_telegram(GROUP_ID, pesan)

                cache[fp] = int(time.time())
                print(f"[KIRIM] OTP {item['otp']} - {item['phone']}")

            now = int(time.time())
            cache = {k: v for k, v in cache.items() if now - v < 1800}
            save_cache(cache)

        except Exception as e:
            print(f"[ERROR] Loop: {e}")

        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    main()
