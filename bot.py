import time
import re
import hashlib
import json
import os
import requests
import urllib.parse

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
FLARESOLVERR_URL = "http://localhost:8191/v1"
CACHE_FILE = "otp_cache.json"


def send_telegram(chat_id, text):
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
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        })
        self.logged_in = False

    def flaresolverr_get(self, url):
        """Request ke URL via FlareSolverr (bypass Cloudflare)"""
        payload = {
            "cmd": "request.get",
            "url": url,
            "maxTimeout": 60000
        }
        try:
            r = requests.post(FLARESOLVERR_URL, json=payload, timeout=90)
            data = r.json()
            if data.get("status") == "ok":
                solution = data["solution"]
                # Update cookies dari FlareSolverr
                for cookie in solution.get("cookies", []):
                    self.session.cookies.set(
                        cookie["name"],
                        cookie["value"],
                        domain=cookie.get("domain", ".ivasms.com")
                    )
                return solution.get("response", "")
            else:
                print(f"[ERROR] FlareSolverr: {data.get('message')}")
                return ""
        except Exception as e:
            print(f"[ERROR] FlareSolverr: {e}")
            return ""

    def login(self):
        try:
            print("[INFO] Buka halaman login via FlareSolverr...")
            html = self.flaresolverr_get("https://www.ivasms.com/login")

            if not html or "cloudflare" in html.lower() and "just a moment" in html.lower():
                print("[GAGAL] Masih kena Cloudflare")
                return False

            print("[OK] Halaman login kebuka, length:", len(html))

            # Cari CSRF token di form
            csrf = ""
            csrf_match = re.search(r'name="_token"\s+value="([^"]+)"', html)
            if csrf_match:
                csrf = csrf_match.group(1)
                print(f"[INFO] CSRF token ditemukan")

            # Cari nama field
            email_field = "email"
            if 'name="username"' in html:
                email_field = "username"

            # Submit login via requests (pakai cookies dari FlareSolverr)
            data = {
                email_field: self.email,
                "password": self.password,
                "_token": csrf,
                "remember": "on"
            }

            login_url = "https://www.ivasms.com/login"
            r = self.session.post(login_url, data=data, timeout=30, allow_redirects=True)

            if "logout" in r.text.lower() or "dashboard" in r.url.lower():
                self.logged_in = True
                print("[OK] Login IVASMS berhasil")
                return True

            print(f"[GAGAL] Login gagal. URL akhir: {r.url}")
            with open("login_fail.html", "w", encoding="utf-8") as f:
                f.write(r.text)
            return False
        except Exception as e:
            print(f"[ERROR] Login: {e}")
            return False

    def fetch_otps(self):
        if not self.logged_in:
            if not self.login():
                return []
        try:
            print("[INFO] Ambil halaman OTP via FlareSolverr...")
            html = self.flaresolverr_get("https://www.ivasms.com/otp")

            if not html:
                return []

            with open("otp_page.html", "w", encoding="utf-8") as f:
                f.write(html)

            otps = []
            pola = re.compile(r'(\+?\d{10,15})\D{0,50}?(\d{4,8})')
            for match in pola.finditer(html):
                otps.append({
                    "phone": match.group(1),
                    "otp": match.group(2)
                })
            return otps
        except Exception as e:
            print(f"[ERROR] Fetch OTP: {e}")
            return []


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
    print("BOT IVASMS OTP - START (FlareSolverr)")
    print(f"Owner: {OWNER_ID}")
    print(f"Grup : {GROUP_ID}")
    print("=" * 40)

    # Test FlareSolverr dulu
    try:
        r = requests.get("http://localhost:8191/", timeout=5)
        print("[OK] FlareSolverr aktif")
    except Exception as e:
        print(f"[ERROR] FlareSolverr tidak jalan: {e}")
        print("[INFO] Jalankan dulu: docker run -d --name flaresolverr -p 8191:8191 ghcr.io/flaresolverr/flaresolverr")
        return

    scraper = IVASMSScraper(IVASMS_EMAIL, IVASMS_PASSWORD)
    cache = load_cache()

    print("[INFO] Kirim notif start...")
    send_telegram(OWNER_ID, "[BOT] Aktif, mulai pantau OTP IVASMS")
    time.sleep(1)
    send_telegram(GROUP_ID, "[BOT] Aktif, mulai pantau OTP IVASMS")

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
