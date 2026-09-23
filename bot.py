import requests
import time
import re
import hashlib
import json
import os

# ============================================
# KONFIGURASI - GANTI BAGIAN INI
# ============================================

# Token BARU dari @BotFather (revoke token lama dulu!)
BOT_TOKEN = "8578361582:AAHwuC8x9CmdEJB0_4KF6fJg7ctUIRm9lOY"

# ID Telegram kamu (owner)
OWNER_ID = 8965979911

# ID Grup Telegram
GROUP_ID = -5445996631

# Akun IVASMS kamu
IVASMS_EMAIL = "alifvivo124@gmail.com"
IVASMS_PASSWORD = "ixizpop9988@"

# Interval cek OTP (detik) - jangan di bawah 15
POLL_INTERVAL = 30

# Alamat API Telegram
TELEGRAM_API = "https://api.telegram.org"

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
        self.session.headers.update({"User-Agent": "Mozilla/5.0"})
        self.logged_in = False

    def login(self):
        try:
            self.session.get("https://ivasms.com/", timeout=15)
            data = {
                "email": self.email,
                "password": self.password,
                "remember": "on"
            }
            resp = self.session.post(
                "https://ivasms.com/login",
                data=data,
                timeout=15,
                allow_redirects=True
            )
            if "logout" in resp.text.lower() or "dashboard" in resp.url.lower():
                self.logged_in = True
                print("[OK] Login IVASMS berhasil")
                return True
            print("[GAGAL] Login gagal, cek email/password")
            return False
        except Exception as e:
            print(f"[ERROR] Login: {e}")
            return False

    def fetch_otps(self):
        if not self.logged_in:
            if not self.login():
                return []
        try:
            resp = self.session.get("https://ivasms.com/otp", timeout=15)
            html = resp.text
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
    print("BOT IVASMS OTP - START")
    print(f"Owner: {OWNER_ID}")
    print(f"Grup : {GROUP_ID}")
    print("=" * 40)

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
