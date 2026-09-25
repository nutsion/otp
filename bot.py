import os
import re
import time
import requests
from bs4 import BeautifulSoup
from neonize.client import NewClient
from neonize.events import MessageEv, ConnectedEv
from neonize.utils import JID

from config import LOGIN_URL, OTP_URL, USERNAME, PASSWORD, DOWNLOAD_DIR

os.makedirs(DOWNLOAD_DIR, exist_ok=True)

client = NewClient("bot_otp_session")

# ============ WEB SESSION ============
web_session = requests.Session()
web_session.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/120.0.0.0 Safari/537.36",
    "Referer": LOGIN_URL,
})


def login_web() -> bool:
    """Login ke website target, simpan session"""
    try:
        # 1. GET halaman login (untuk ambil CSRF token kalau ada)
        r = web_session.get(LOGIN_URL, timeout=15)
        r.raise_for_status()

        # 2. Parse hidden input (CSRF, token, dsb.)
        soup = BeautifulSoup(r.text, "html.parser")
        payload = {
            # ⚠️ GANTI dengan name="" dari <input> di form login kamu
            "username": USERNAME,
            "password": PASSWORD,
        }
        # Auto-ambil hidden input
        for hidden in soup.find_all("input", {"type": "hidden"}):
            name = hidden.get("name")
            value = hidden.get("value", "")
            if name:
                payload[name] = value

        # 3. POST login
        r = web_session.post(LOGIN_URL, data=payload, timeout=15)
        r.raise_for_status()

        # 4. Cek berhasil login
        if "login" in r.url.lower() and "logout" not in r.text.lower():
            print("❌ Login gagal — cek username/password")
            return False

        print("✅ Login web berhasil")
        return True

    except Exception as e:
        print(f"❌ Error login: {e}")
        return False


def send_otp_request(nomor: str) -> dict:
    """
    Kirim request OTP untuk 1 nomor.
    Return: {"success": bool, "message": str}
    """
    try:
        # 1. GET halaman OTP (ambil CSRF & struktur form)
        r = web_session.get(OTP_URL, timeout=15)
        r.raise_for_status()

        soup = BeautifulSoup(r.text, "html.parser")
        payload = {
            # ⚠️ GANTI sesuai form di MySMSNumbers
            # Contoh umum: "msisdn", "phone", "number", "nomor"
            "msisdn": nomor,
            "phone": nomor,
            "number": nomor,
        }
        # Auto hidden input
        for hidden in soup.find_all("input", {"type": "hidden"}):
            name = hidden.get("name")
            value = hidden.get("value", "")
            if name:
                payload[name] = value

        # 2. POST ke endpoint OTP
        r = web_session.post(OTP_URL, data=payload, timeout=15)
        r.raise_for_status()

        # 3. Cek respon (⚠️ sesuaikan dengan respon site kamu)
        text_lower = r.text.lower()
        if any(k in text_lower for k in ["success", "berhasil", "sent", "terkirim"]):
            return {"success": True, "message": "OTP terkirim"}
        elif any(k in text_lower for k in ["error", "gagal", "failed", "invalid"]):
            return {"success": False, "message": "Gagal kirim OTP"}
        else:
            # Fallback: anggap sukses jika HTTP 200
            return {"success": True, "message": "Request OK (cek manual)"}

    except Exception as e:
        return {"success": False, "message": str(e)}


# ============ HELPERS ============
def parse_numbers_from_txt(filepath: str) -> list:
    """Ambil nomor dari file .txt (1 nomor per baris, ignore komentar)"""
    numbers = []
    with open(filepath, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            # Normalisasi: buang spasi, +, -, ()
            clean = re.sub(r"[^\d]", "", line)
            if clean:
                numbers.append(clean)
    return numbers


def format_wa_number(nomor: str) -> str:
    """Normalisasi nomor ke format WhatsApp (628xxx)"""
    if nomor.startswith("0"):
        nomor = "62" + nomor[1:]
    elif nomor.startswith("8"):
        nomor = "62" + nomor
    return nomor


# ============ WHATSAPP EVENTS ============
@client.event(ConnectedEv)
def on_connected(client: NewClient, event: ConnectedEv):
    print("✅ Bot WhatsApp terhubung!")
    print("🔐 Login ke website target...")
    if login_web():
        print("🎉 Bot siap menerima file .txt")
    else:
        print("⚠️ Login web gagal — perintah akan error")


@client.event(MessageEv)
def on_message(client: NewClient, message: MessageEv):
    try:
        sender = message.Info.MessageSource.Sender.User
        chat_jid = JID(f"{sender}@s.whatsapp.net")

        # Cek dokumen (file)
        doc = message.Message.documentMessage
        if doc and doc.fileName and doc.fileName.lower().endswith(".txt"):
            handle_txt_upload(client, message, chat_jid, doc)
            return

        # Cek teks
        try:
            text = message.Message.conversation or \
                   message.Message.extendedTextMessage.text or ""
        except Exception:
            text = ""

        text = text.strip().lower()

        if text == "!help":
            client.send_message(chat_jid,
                "🤖 *BOT OTP*\n\n"
                "📌 *Cara pakai:*\n"
                "1. Kirim file `.txt` (1 nomor per baris)\n"
                "2. Bot otomatis login & kirim OTP ke semua nomor\n\n"
                "📌 *Perintah:*\n"
                "• `!login` — Login ulang ke web\n"
                "• `!help` — Bantuan ini\n\n"
                "📄 *Contoh isi file .txt:*\n"
                "```\n628123456789\n"
                "628987654321\n"
                "# baris diawali # di-skip\n```"
            )

        elif text == "!login":
            if login_web():
                client.send_message(chat_jid, "✅ Login web berhasil")
            else:
                client.send_message(chat_jid, "❌ Login web gagal")

    except Exception as e:
        print(f"❌ Handler error: {e}")


def handle_txt_upload(client, message, chat_jid, doc):
    """Proses file .txt yang di-upload"""
    try:
        # Download file dari WhatsApp
        filename = f"{int(time.time())}_{doc.fileName}"
        filepath = os.path.join(DOWNLOAD_DIR, filename)

        # Ambil URL media & download
        msg = client.download_media_with_path(message, filepath)
        print(f"📥 File tersimpan: {msg}")

        # Parse nomor
        numbers = parse_numbers_from_txt(msg)
        total = len(numbers)

        if total == 0:
            client.send_message(chat_jid, "❌ File kosong atau format salah")
            return

        client.send_message(chat_jid,
            f"📄 File diterima: *{doc.fileName}*\n"
            f"📊 Total nomor: *{total}*\n"
            f"⏳ Mulai proses OTP..."
        )

        sukses = 0
        gagal = 0
        gagal_list = []

        for i, nomor in enumerate(numbers, 1):
            wa_num = format_wa_number(nomor)
            result = send_otp_request(nomor)

            if result["success"]:
                sukses += 1
                print(f"[{i}/{total}] ✅ {nomor}")
            else:
                gagal += 1
                gagal_list.append(nomor)
                print(f"[{i}/{total}] ❌ {nomor} — {result['message']}")

            # Progress report tiap 10 nomor
            if i % 10 == 0:
                client.send_message(chat_jid,
                    f"📊 Progress: {i}/{total}\n"
                    f"✅ Sukses: {sukses}\n"
                    f"❌ Gagal: {gagal}"
                )

            time.sleep(1)  # delay anti rate-limit

        # Ringkasan akhir
        ringkasan = (
            f"✅ *SELESAI*\n\n"
            f"📊 Total: {total}\n"
            f"✅ Sukses: {sukses}\n"
            f"❌ Gagal: {gagal}"
        )
        if gagal_list and len(gagal_list) <= 20:
            ringkasan += "\n\n❌ *Gagal:*\n" + "\n".join(gagal_list[:20])

        client.send_message(chat_jid, ringkasan)

    except Exception as e:
        print(f"❌ Upload error: {e}")
        client.send_message(chat_jid, f"❌ Error proses file: {e}")


if __name__ == "__main__":
    print("🚀 Menjalankan bot OTP...")
    print("📱 Scan QR kalau belum login")
    client.connect()
