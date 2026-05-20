import os
from dotenv import load_dotenv
from langchain_core.tools import tool
from langchain_core.messages import HumanMessage
from langchain_huggingface import HuggingFaceEndpoint, ChatHuggingFace

# 1. Load Environment Variables (Pastikan HUGGINGFACEHUB_API_TOKEN ada di .env)
load_dotenv()

# ==========================================
# 2. DEFINISIKAN TOOL DUMMY
# ==========================================
@tool
def process_transaction(product_id: str, quantity: int) -> str:
    """
    Gunakan tool ini HANYA ketika user secara eksplisit menyatakan ingin membeli produk.
    Fungsi ini akan mengecek stok dan memproses pembelian.
    """
    # Bagian ini hanya akan tereksekusi jika model berhasil memanggil tool
    print(f"\n[SYSTEM] 🛠️ Tool 'process_transaction' berhasil dipicu!")
    print(f"[SYSTEM] 📦 Product ID yang ditangkap : {product_id}")
    print(f"[SYSTEM] 🔢 Jumlah yang ditangkap     : {quantity}\n")
    return "SUKSES: Transaksi berhasil disimulasikan."

# ==========================================
# 3. INISIALISASI MODEL KASIR
# ==========================================
# Silakan ganti repo_id ini jika ingin menguji model lain
repo_id = "meta-llama/Llama-3.1-8B-Instruct"
# Alternatif yang sangat jago tool calling: "Qwen/Qwen2.5-7B-Instruct"

print(f"Mempersiapkan model {repo_id}...")
endpoint = HuggingFaceEndpoint(
    repo_id=repo_id,
    task="text-generation", 
    temperature=0.1, # Suhu dibuat rendah agar model fokus ke logika, bukan kreativitas
    max_new_tokens=512,
    do_sample=False,
)

chat_model = ChatHuggingFace(llm=endpoint)

# ==========================================
# 4. BIND TOOL KE MODEL
# ==========================================
# Di sinilah keajaiban terjadi, kita memberi tahu model bahwa dia punya "tangan"
kasir_agent = chat_model.bind_tools([process_transaction])

# ==========================================
# 5. PENGUJIAN SKENARIO
# ==========================================
print("\n--- MULAI PENGUJIAN TOOL CALLING ---")

# Simulasi percakapan di mana user meminta transaksi
user_input = "Halo, tadi saya sudah lihat perbandingannya. Saya memutuskan mau beli HP seri itu 2 buah ya. Kodenya hp-pro-2026."
print(f"User: \"{user_input}\"")

print("\nMenunggu respons model...")
response = kasir_agent.invoke([HumanMessage(content=user_input)])

# ==========================================
# 6. ANALISIS HASIL
# ==========================================
print("--- HASIL DARI MODEL ---")
if response.tool_calls:
    print("✅ STATUS: SUKSES!")
    print("Model berhasil memahami intent dan merakit JSON untuk memanggil tool.")
    print("Detail Tool Call dari Model:")
    for tc in response.tool_calls:
        print(f"  - Nama Fungsi : {tc['name']}")
        print(f"  - Parameter   : {tc['args']}")
else:
    print("❌ STATUS: GAGAL!")
    print("Model merespons dengan teks biasa dan TIDAK memanggil tool.")
    print(f"Respons Model: {response.content}")
    print("\nSaran: Coba ganti repo_id dengan model lain (seperti Qwen2.5-7B-Instruct).")