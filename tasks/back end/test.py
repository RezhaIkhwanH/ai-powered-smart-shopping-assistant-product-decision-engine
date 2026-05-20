
import requests
from dotenv import load_dotenv
import os
import base64
load_dotenv()
# ==========================================
        # 4. REQUEST KE XENDIT API (BIKIN INVOICE)
# ==========================================
# Xendit menggunakan Basic Auth dengan Secret Key (diencode ke Base64)
auth_string = os.getenv("XENDIT_SECRET_KEY")
auth_base64 = base64.b64encode(auth_string.encode('utf-8')).decode('utf-8')

headers = {
    "Authorization": f"Basic {auth_base64}",
    "Content-Type": "application/json"
}

payload = {
    "external_id": "TRX-1212wdassdss",
    "amount": 10000,
    "description": f"Pembelian {1}x sayur oleh jamal",
    "invoice_duration": 86400 # Link valid selama 24 jam
}

xendit_res = requests.post("https://api.xendit.co/v2/invoices", json=payload, headers=headers)
xendit_data = xendit_res.json()

# Cek jika Xendit menolak request kita
if xendit_res.status_code != 200:
    print("GAGAL: API Xendit bermasalah - {xendit_data.get('message', 'Unknown Error')}")

# Ambil URL pembayarannya
payment_link = xendit_data.get("invoice_url")

print(payment_link)