import os
import re
import json
import base64
import logging
import random
import string
import requests
import mlflow
from datetime import datetime
from typing import Annotated, Literal
from typing_extensions import TypedDict
from dotenv import load_dotenv
from psycopg_pool import ConnectionPool

from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage, AIMessage, RemoveMessage
from langchain_core.tools import tool
from langchain_core.runnables.config import RunnableConfig
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langchain_huggingface import ChatHuggingFace, HuggingFaceEndpoint
from langchain_google_genai import ChatGoogleGenerativeAI as ChatGoogleGenAI
from langchain_groq import ChatGroq
from langgraph.prebuilt import ToolNode, tools_condition
from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.checkpoint.memory import MemorySaver
from supabase import create_client, Client
load_dotenv()

# logging.basicConfig(level=logging.DEBUG)

# ==========================================
# 1. INISIALISASI LLM 
# ==========================================
# LLM 1: Gemma (via Google GenAI) khusus untuk Pengecekan Intent
inten_endpoint = HuggingFaceEndpoint(
    repo_id="Goekdeniz-Guelmez/JOSIE-1.1-4B-Thinking:featherless-ai",
    task="text-generation",
    max_new_tokens=512,
    temperature=0.1, 
    huggingfacehub_api_token=os.getenv("HUGGINGFACEHUB_API_TOKEN_2")
)

llm_intent = ChatHuggingFace(llm=inten_endpoint) 

# LLM 2: Groq (Untuk Kasir, Komparasi, dan Summarizer agar lebih stabil)
kasir_endpoint = HuggingFaceEndpoint(
    repo_id="Qwen/Qwen2.5-7B-Instruct",
    task="text-generation",
    max_new_tokens=2048,
    temperature=0.1, 
    do_sample=False,
    huggingfacehub_api_token=os.getenv("HUGGINGFACEHUB_API_TOKEN")

)
llm_kasir = ChatHuggingFace(llm=kasir_endpoint)

# LLM 3: Google (Untuk Komparasi Visual)
vision_endpoint = HuggingFaceEndpoint(
    repo_id="google/gemma-4-26B-A4B-it",
    task="conversational", 
    max_new_tokens=1024,
    temperature=0.7,
    huggingfacehub_api_token=os.getenv("HUGGINGFACEHUB_API_TOKEN")
)
llm_komparasi = ChatHuggingFace(llm=vision_endpoint)

# LLM 4: Groq (Untuk Summarizer)
llm_summarizer = ChatGroq(model="llama-3.1-8b-instant", temperature=0.1)

# setup database
supabase_url = os.getenv("SUPABASE_URL")
supabase_key = os.getenv("SUPABASE_KEY")
supabase: Client = create_client(supabase_url, supabase_key)


# ==========================================
# 2. DEFINISI STATE
# ==========================================
class State(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]
    summary: str # Menyimpan rangkuman chat jika sudah lebih dari 13 pesan
    intent_kategori: str # Hasil dari node_intent ('kasir', 'komparasi', atau 'tidak_jelas')


# ==========================================
# 3. DEFINISI helper fuction dan tools
# ==========================================
# buat link pembayarang via xendit (bukan tools) ini fuction
def create_invoice(external_id:str, amount:int, description:str):
    auth_string = os.getenv("XENDIT_SECRET_KEY")
    auth_base64 = base64.b64encode(auth_string.encode('utf-8')).decode('utf-8')

    headers = {
        "Authorization": f"Basic {auth_base64}",
        "Content-Type": "application/json"
    }

    payload = {
        "external_id": external_id,
        "amount": amount,
        "description": description,
        "invoice_duration": 86400 // 4 # waktu berlaku pembayaran
    }

    xendit_res = requests.post("https://api.xendit.co/v2/invoices", json=payload, headers=headers)
    xendit_data = xendit_res.json()

    # Cek jika Xendit menolak request kita
    if xendit_res.status_code != 200:
        return "GAGAL: API Xendit bermasalah - {xendit_data.get('message', 'Unknown Error')}"

    # Ambil URL pembayarannya
    payment_link = xendit_data.get("invoice_url")
    return f"SUKSES: Transaksi dibuat. Link pembayaran: {payment_link}"


def parse_tool_calls(text):
    tool_calls = []

    blocks = re.findall(r"<\|tool_call>(.*?)<tool_call\|>", text, re.DOTALL)
    pattern = r"call:(?:(\w+):)?(\w+)\{(.*?)\}"

    for i, block in enumerate(blocks):
        match = re.search(pattern, block)
        if not match:
            continue

        namespace, tool_name, args_str = match.groups()
        args = {}

        arg_pairs = re.findall(
            r"""(\w+)\s*:\s*(?:'([^']*)'|"([^"]*)"|([^,}\s]+))""",
            args_str
        )

        for key, sq, dq, uq in arg_pairs:
            args[key] = sq or dq or uq

        tool_calls.append({
            "id": f"call_{i}",
            "name": tool_name,
            "args": args,
            "type": "tool_call",
        })
    logging.info("tool calls: %s",tool_calls)
    return tool_calls


# import requests
import base64

def convert_image_to_base64(url: str) -> str:
    """Mengambil gambar dari URL localhost (FastAPI) dan mengubahnya ke Base64"""
    # Sedot gambar dari FastAPI Anda
    response = requests.get(url)
    response.raise_for_status() # Pastikan gambarnya ada (bukan 404)
    
    # Ubah ke Base64
    base64_str = base64.b64encode(response.content).decode("utf-8")
    
    # Ambil tipe file dari header respons (misal: image/jpeg)
    mime_type = response.headers.get('Content-Type', 'image/jpeg')
    
    return f"data:{mime_type};base64,{base64_str}"

#======
#definisi tools

@tool # tools proses transaksi
# @mlflow.trace(name="process_transaction")
def process_transaction(product_id: str, quantity: int, config: RunnableConfig) -> str:
    """
    Memproses pembelian, mengecek stok, menghitung total harga, 
    dan mencatatnya ke tabel transactions.
    """
    logging.info(f"tools process_transaction dipanggil dengan product_id={product_id} dan quantity={quantity}")

    # 1. Ambil user_id rahasia dari config
    user_id = config.get("configurable", {}).get("user_id")
    
    if not user_id:
        return "GAGAL: Sistem tidak menemukan ID User. Harap login terlebih dahulu."

    try:
        # 2. Cek stok dan harga dari tabel products
        res_product = supabase.table("products").select("stock", "price", "name").eq("id", product_id).execute()
        data_product = res_product.data

        if not data_product:
            return f"GAGAL: Produk dengan ID {product_id} tidak ditemukan di database."

        product_info = data_product[0]
        stok_saat_ini = product_info["stock"]
        harga_satuan = product_info["price"]

        # 3. Validasi Stok
        if stok_saat_ini < quantity:
            return f"GAGAL: Stok '{product_info['name']}' tidak cukup. Sisa stok hanya: {stok_saat_ini}."

        # 4. Hitung total harga & Generate kode pembayaran acak
        total_price = harga_satuan * quantity
        payment_code = "TRX-" + ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))

        # 5. Insert data ke tabel transactions (Sesuai skema ERD Anda)
        data_transaksi = {
            "user_id": user_id,
            "product_id": product_id,
            "quantity": quantity,
            "total_price": total_price,
            "payment_code": payment_code,
            "status": "PENDING" 
        }
        
        supabase.table("transactions").insert(data_transaksi).execute()

        # 6. Kurangi stok di tabel products
        stok_baru = stok_saat_ini - quantity
        supabase.table("products").update({"stock": stok_baru}).eq("id", product_id).execute()
        link_pembayaran = create_invoice(payment_code, total_price, f"Pembelian {quantity}x {product_info['name']} oleh {user_id}")

        return f"SUKSES: {link_pembayaran}"

    except Exception as e:
        return f"GAGAL terjadi kesalahan pada database: {str(e)}"

@tool #tools buat cari produk
# @mlflow.trace(name="search_products")
def search_products(query: str = "") -> str:
    """
    Mencari data produk di database toko.
    Jika query kosong (""), tool ini akan menampilkan daftar semua produk.
    Jika ada nama produk, tool ini akan mencari produk yang sesuai.
    gunakan untuk mencari produk yang tersedia.
    """
    logging.info(f"tools search_products dipanggil dengan query='{query}'")
    try:

        if query:
            # Mencari produk berdasarkan nama (ilike = case-insensitive, tidak peduli huruf besar/kecil)
            response = supabase.table("products").select("*").ilike("name", f"%{query}%").execute()
        else:
            # Jika user hanya bilang "Lihat menu" atau "Ada produk apa aja?"
            response = supabase.table("products").select("*").execute()
        
        data = response.data
        
        if not data: # jika data tidak ditemukan 
            return f"Tidak ada produk yang ditemukan untuk pencarian '{query}'."
        
        # 3. Memformat hasil JSON menjadi teks string agar AI gampang membacanya
        hasil_teks = "Hasil Pencarian Produk:\n"
        for item in data:
            # PENTING: Sesuaikan get() ini dengan nama-nama kolom di tabel Supabase Anda
            id_produk = item.get("id", "N/A")
            nama = item.get("name", "N/A")
            harga = item.get("price", 0)
            stok = item.get("stock", 0)
            deskripsi = item.get("description", "Tidak ada deskripsi.")
            spec = item.get("spec", "Tidak ada spesifikasi.")
            
            hasil_teks += f"- [ID: {id_produk}] {nama} | Harga: Rp{harga} | Stok Sisa: {stok} | Deskripsi: {deskripsi} | Spesifikasi: {spec}\n"
            
        return hasil_teks

    except Exception as e:
        return f"GAGAL mengambil data dari database: {str(e)}"


#==============
# setup agent untuk nodes
#=============

kasir_agent_llm = llm_kasir.bind_tools([process_transaction, search_products])
komparasi_agent_llm = llm_komparasi.bind_tools([search_products])

#================
# definisi promt untk agent
# note: ada indikasi promt nya bocor
#================

promt_sistem_intent = (
"""
tugas anda cuma kalsifikasikan intent penguna berdasarkan riwayat obrolan berikut ini. Kategori intent yang tersedia hanya 2 yaitu:
"kasir" untuk pembelian produk atau informasi produk yang dijual di toko
"komparasi" hanya untuk perbandingan produk.
Jawaban harus dalam format JSON dengan key "intent" dan value salah satu dari kategori tersebut. Contoh output yang benar:{{ "intent": "kasir" }}

riwayat obrolan:
{user_message}
"""
)

promt_sistem_perbandingan = (
    """
# PROMPT SISTEM PERBANDINGAN PRODUK

Anda adalah Asisten Komparasi Produk berbasis data yang objektif, akurat, dan sepenuhnya bergantung pada tool.

---

## ATURAN WAJIB (TIDAK BOLEH DILANGGAR)

1. Anda dilarang keras menggunakan pengetahuan internal (training data) untuk menjawab.
2. Satu-satunya sumber valid adalah:
- hasil tool `search_products`
- data yang diberikan secara eksplisit oleh user
3. Jika informasi tidak tersedia di tool atau user, Anda wajib menyatakan bahwa data tidak tersedia.
4. Dilarang membuat asumsi, perkiraan, atau melengkapi data yang tidak ada.
5. Semua jawaban harus berbasis data yang terverifikasi dari tool atau user.

---

## LOGIKA PENCARIAN PRODUK (WAJIB DIIKUTI)

### 1. Input hanya nama produk
- Jika user hanya memberikan nama produk, Anda WAJIB memanggil tool `search_products`.

### 2. Dua produk disebutkan
- Anda WAJIB melakukan 2 kali pemanggilan tool, masing-masing untuk satu produk.

### 3. Produk tidak ditemukan
Jika produk tidak ditemukan di database:
- Tampilkan pesan:  
**"Data produk tidak ditemukan di database"**
- Minta user memberikan spesifikasi atau data tambahan produk tersebut.

---

## PERILAKU AGENT

- Tidak boleh menambahkan informasi di luar hasil tool dan data user.
- Tidak boleh menggunakan pengetahuan internal dalam kondisi apa pun.
- Jika data tidak lengkap, tampilkan sebagai "tidak tersedia".
- Tetap objektif, netral, dan tidak memihak salah satu produk.
- Tidak boleh membuat kesimpulan tanpa data yang cukup.

---

## FORMAT OUTPUT (WAJIB MENGGUNAKAN MARKDOWN)

## [Judul Perbandingan Produk]

| Aspek | Produk A | Produk B |
|------|----------|----------|
| Nama Produk | ... | ... |
| Harga | ... | ... |
| Spesifikasi Utama | ... | ... |
| Kelebihan | ... | ... |
| Kekurangan | ... | ... |
| Fitur Tambahan | ... | ... |

---

### Kelebihan Masing-Masing

- Produk A: ...
- Produk B: ...

---

### Kekurangan Masing-Masing

- Produk A: ...
- Produk B: ...

---

### Kesimpulan dan Rekomendasi

Berikan rekomendasi yang tegas berdasarkan data:
- Produk mana yang lebih baik
- Untuk siapa produk tersebut lebih cocok
- Sertakan alasan yang sepenuhnya berdasarkan data dari tool

Jika data tidak cukup:
- Nyatakan bahwa perbandingan tidak dapat dilakukan secara valid karena data tidak lengkap.
    """
)

promt_sistem_kasir = (
    """
Anda adalah Kasir AI yang ramah, profesional, dan berbasis data.

Anda hanya boleh menggunakan data dari tool `search_products` dan `process_transaction`.
Dilarang menggunakan pengetahuan internal dalam bentuk apa pun.

---

## ATURAN UTAMA (WAJIB DIIKUTI)

1. Semua informasi produk harus berasal dari `search_products`.
2. Dilarang menebak harga, stok, atau ID produk.
3. Jika data tidak ditemukan, nyatakan produk tidak tersedia.
4. Jika user tidak menyebutkan nama produk secara jelas, Anda wajib meminta klarifikasi.
5. Default quantity pembelian adalah 1 jika user tidak menyebutkan jumlah.
6. Tidak boleh memanggil `process_transaction` sebelum data produk lengkap dan dikonfirmasi user.

---

## KEMAMPUAN ANDA

### 1. Pencarian Produk
Gunakan `search_products` untuk:
- Menampilkan semua produk (query = "")
- Mencari produk berdasarkan nama
- Mengambil detail lengkap produk (harga, stok, id)

Jika user menanyakan:
- "produk apa saja yang dijual"
→ tampilkan semua produk secara ringkas

Jika user menanyakan jenis produk tanpa nama spesifik:
→ tolak dengan sopan dan minta nama produk yang jelas

Contoh:
"Silakan sebutkan nama produk yang ingin Anda cari agar saya bisa membantu dengan tepat."

---

### 2. Informasi Produk
Saat produk ditemukan:
- tampilkan nama produk
- harga
- stok
- deskripsi singkat (jika ada dari tool)

---

### 3. Proses Pembelian

Jika user ingin membeli produk:

Langkah wajib:

#### Step 1 - Cari Produk
Gunakan `search_products` untuk mendapatkan data lengkap.

#### Step 2 - Validasi Data
Pastikan tersedia:
- product_id
- harga
- stok

Jika tidak lengkap → cari ulang dengan tool.

#### Step 3 - Tentukan Quantity
- Jika user tidak menyebutkan jumlah → default = 1

#### Step 4 - Konfirmasi ke User
Tampilkan ringkasan:

- Nama produk
- Quantity
- Harga satuan
- Total harga
- Product ID

Tanyakan:
"Apakah Anda ingin melanjutkan transaksi?"

---

### 4. Eksekusi Transaksi

Jika user menyetujui:
- gunakan `process_transaction` dengan:
- product_id
- quantity

Setelah berhasil:
- kirimkan link pembayaran kepada user

---

### 5. Produk Tidak Tersedia

Jika produk tidak ditemukan:
- katakan: "Produk tidak tersedia di toko"
- jelaskan kemungkinan:
- stok habis
- tidak dijual
- sarankan user mencari produk lain

---

## PERILAKU AGENT

- Selalu ramah, singkat, dan jelas
- Tidak boleh mengarang data
- Tidak boleh melanjutkan transaksi tanpa konfirmasi user
- Tidak boleh memproses transaksi jika data tidak valid
"""
)

# ==========================================
# 4. DEFINISI NODES 
# ==========================================
# @mlflow.trace(name="node_intent")
def node_intent(state: State):
    """Mendeteksi apakah user ingin belanja (kasir) atau membandingkan produk menggunakan konteks."""
    
    # 1. Ambil 5 pesan terakhir 
    batas_pesan = 5
    pesan_konteks = state["messages"][-batas_pesan:]
    
    # 2. Ekstrak dan susun history obrolan (Aman untuk Multimodal)
    teks_konteks = "\n"
    for msg in pesan_konteks:
        content = msg.content
        teks_murni = ""

        if not msg.type in ['human', 'ai']:\
            continue # skip pesan yang bukan human atau ai (misal system, tool_call, dll)
        
        # Ekstrak teks murni dari masing-masing pesan
        if isinstance(content, str):
            if msg.type in ['ai']:
                content = re.sub(r'\|.*\|', '', content)
                content = re.sub(r'[-]{3,}', '', content) # Hapus garis pembatas tabel ---

                # Hapus baris kosong yang berlebihan dan strip leading/trailing whitespace
                content = re.sub(r'\n\s*\n+', '\n', content)
                content = content.strip()
            teks_murni = content
        elif isinstance(content, list):
            for item in content:
                if item.get("type") == "text":
                    teks_murni += item.get("text", "")
        
        # Gabungkan tipe (human/ai) dengan teksnya
        teks_konteks += f"{msg.type}: {teks_murni}\n"
    
    # 3. Masukkan riwayat obrolan ke dalam prompt format Anda
    sistem_prompt = mlflow.genai.load_prompt("prompts:/intent_promt_sistem@latest")
    human_message = sistem_prompt.format(user_message=teks_konteks)
    
    # 4. Invoke LLM Intent
    hasil = llm_intent.invoke([HumanMessage(content=human_message)])
    raw_text = hasil.content
    
    # 5. REGEX CLEANER & JSON Parser
    cleaned_json = re.sub(r'```(?:json)?|```', '', raw_text, flags=re.IGNORECASE).strip()
    
    try:
        data = json.loads(cleaned_json)
        kategori = data.get("intent", "komparasi")
    except json.JSONDecodeError:
        kategori = "komparasi" 
        
    return {"intent_kategori": kategori}

# @mlflow.trace(name="node_komparasi")
#node comparasi atau perbandigan
def node_komparasi(state: State):
    promt_sistem=mlflow.genai.load_prompt("prompts:/komparasi_promt_sistem@latest")
    messages = [SystemMessage(content=promt_sistem.template)]

    if state.get("summary"):
        messages.append(SystemMessage(content=f"Rangkuman Obrolan Sebelumnya: {state['summary']}"))

    messages += state["messages"]

    response = llm_komparasi.invoke(messages)
    raw_text = response.content if hasattr(response, "content") else str(response)

    tool_calls = parse_tool_calls(raw_text)
    cleaned_text = re.sub(
        r"<\|tool_call>.*?<tool_call\|>",
        "",
        raw_text,
        flags=re.DOTALL
    ).strip()

    fixed_message = AIMessage(
        content=cleaned_text or "",
        tool_calls=tool_calls
    )
    logging.info("raw text dari LLM komparasi: %s", raw_text)
    logging.info("isi tool calls node komparasi: %s", tool_calls)
    logging.info("message node komparasi: %s", fixed_message)
    return {"messages": [fixed_message]}

# @mlflow.trace(name="node_kasir")
def node_kasir(state: State):
    promt_sistem=mlflow.genai.load_prompt("prompts:/kasir_promt_sistem@latest")
    messages = [SystemMessage(content=promt_sistem.template)] 

    if state.get("summary"):
        messages.append(SystemMessage(content=f"Rangkuman Obrolan Sebelumnya: {state['summary']}"))
        
    messages += state["messages"]
    response = kasir_agent_llm.invoke(messages)
    return {"messages": [response]}


# @mlflow.trace(name="node_summarize")
def node_summarize(state: State):
    """Terpicu jika pesan > 13. Merangkum pesan lama, menyisakan 10 pesan terbaru."""
    pesan = state["messages"]
    summary_lama = state.get("summary", "")
    
    batas_buffer = 11 
    pesan_untuk_dirangkum = pesan[:-batas_buffer] 
    
    prompt_summary = (
        f"Rangkuman lama: {summary_lama}\n\n"
        "Tambahkan intisari dari pesan baru ini ke dalam rangkuman tersebut secara singkat:\n"
        + "\n".join([f"{m.type}: {m.content}" for m in pesan_untuk_dirangkum if m.type in ['human', 'ai']])
    )
    
    hasil_summary = llm_summarizer.invoke([HumanMessage(content=prompt_summary)])
    
    # Hapus pesan yang sudah dirangkum dari memori database
    delete_actions = [RemoveMessage(id=m.id) for m in pesan_untuk_dirangkum]
    
    return {"summary": hasil_summary.content, "messages": delete_actions}

# ==========================================
# 5. ROUTER LOGIC
# ==========================================
def route_setelah_intent(state: State) -> Literal["node_kasir", "node_komparasi"]:
    """Routing berdasarkan hasil deteksi intent."""
    if state["intent_kategori"] == "kasir":
        return "node_kasir"
    return "node_komparasi"

def route_setelah_tools(state: State) -> Literal["node_kasir", "node_komparasi"]:
    """Mengembalikan alur ke agent yang memanggil tool berdasarkan intent."""
    if state["intent_kategori"] == "kasir":
        return "node_kasir"
    return "node_komparasi"

def route_memory(state: State) -> Literal["node_summarize", END]:
    """Routing ke summarizer jika pesan melebihi batas."""
    if len(state["messages"]) > 13:
        return "node_summarize"
    return END

# ==========================================
# 6. MEMBANGUN GRAPH
# ==========================================
builder = StateGraph(State)

# --- Daftarkan semua Node ---
builder.add_node("node_intent", node_intent)
builder.add_node("node_komparasi", node_komparasi)
builder.add_node("node_kasir", node_kasir)
builder.add_node("tools", ToolNode([process_transaction, search_products]))
builder.add_node("node_summarize", node_summarize)
# Node cek_memori: dummy passthrough sebagai titik masuk route_memory
builder.add_node("cek_memori", lambda state: state)

# --- Daftarkan semua Edge ---

# Mulai dari intent detector
builder.add_edge(START, "node_intent")
builder.add_conditional_edges("node_intent", route_setelah_intent)

# Kasir: pakai tools_condition dari LangGraph prebuilt
# tools_condition otomatis cek apakah last_message punya tool_calls:
#   -> jika YA  : lanjut ke node "tools"
#   -> jika TIDAK: lanjut ke END (kita override ke "cek_memori")
builder.add_conditional_edges(
    "node_kasir",
    tools_condition,
    {
        "tools": "tools",   # ada tool_calls -> eksekusi tool
        END: "cek_memori",  # tidak ada tool_calls -> cek memori
    }
)
builder.add_conditional_edges("tools", route_setelah_tools)  # setelah tool selesai, kembali ke kasir

# Komparasi: juga pakai tools_condition (karena bind search_products)
builder.add_conditional_edges(
    "node_komparasi",
    tools_condition,
    {
        "tools": "tools",   # ada tool_calls -> eksekusi tool
        END: "cek_memori",  # tidak ada tool_calls -> cek memori
    }
)

# Setelah semua agent selesai, cek apakah perlu summarize=============================
builder.add_conditional_edges("cek_memori", route_memory)
builder.add_edge("node_summarize", END)

# ==========================================
# 7. KONEKSI KE SUPABASE & COMPILE
# ==========================================
DB_URI = os.getenv("SUPABASE_DB_URI")

connection_kwargs = {
    "autocommit": True,
    "prepare_threshold": None,
}

# ==========================================
# 8. EVALUASI MLFLOW — mlflow.genai.evaluate()
# ==========================================

# Dataset evaluasi: format bawaan mlflow.genai.evaluate()
# "inputs"       → diteruskan ke predict_fn sebagai keyword arguments
# "expectations" → diteruskan ke setiap @scorer sebagai parameter expectations
EVAL_TEST_CASES = [
    {
        "inputs": {
            "user_query": "Bandingkan Poco X6 Pro dengan Realme GT Neo 5, pilih mana yang lebih bagus",
            # "thread_id": "test_case_01"
        },
        "expectations": {
            "expected_node": "node_komparasi",
            "expected_tool": "search_products",
        },
    },
    {
        "inputs": {
            "user_query": "Saya mau beli Xiaomi Redmi Note 13 sekarang 1 unit",
            # "thread_id": "test_case_02"
        },
        "expectations": {
            "expected_node": "node_kasir",
            "expected_tool": "search_products",
        },
    },
    {
        "inputs": {
            "user_query": "Tolong sebutkan semua produk yang dijual di toko ini dan jelaskan secara singkat",
            # "thread_id": "test_case_03"
        },
        "expectations": {
            "expected_node": "node_kasir",
            "expected_tool": "search_products",
        },
    },
]

EVAL_SCENARIOS =[
    {
        "inputs": {
            "user_query": "mana yang lebih bagus dari kedua hp ini?",
            "image_url": [
            "http://127.0.0.1:8000/img/2d3b6ba9-a554-4243-9595-64855be7dec5.webp",
            "http://127.0.0.1:8000/img/d501073c-c43e-45d5-8a6b-edd985eecbce.webp"
        ],
        },
        "expectations": {
            "expected_node": "node_komparasi",
            # "expected_tool": "search_products",
        },
    },
    {
        "inputs": {
            "user_query": "kalok yang paling bagus dari sisi buat main game berat gitu yang mana",
        },
        "expectations": {
            "expected_node": "node_komparasi",
            # "expected_tool": "search_products",
        },
    },
    {
        "inputs": {
            "user_query": "ok saya mau beli yang itu dong 1 unit",
        },
        "expectations": {
            "expected_node": "node_kasir",
            "expected_tool": "search_products",
        },
    },
]


def run_evaluasi_mlflow(app_eval):
    from mlflow.entities import Feedback
    from mlflow.genai import scorer
    from mlflow.genai.scorers import Guidelines

    id_trace = datetime.now().strftime("%Y%m%d-%H%M%S")

    # Aktifkan auto-tracing LangChain/LangGraph agar span setiap node & tool terekam
    # mlflow.set_system_metrics_sampling_interval(1)
    # mlflow.set_tracking_uri("http://localhost:5000")
    mlflow.langchain.autolog()
    mlflow.tracing.enable()
    mlflow.set_experiment("capstone-agent-evaluation")

    # ── predict_fn: dipanggil mlflow.genai.evaluate() untuk setiap baris data ──
    # @mlflow.trace
    def predict_fn(user_query: str, image_url: list = None) -> str:
        config = {
            "configurable": {
                "user_id": "a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11",
                "thread_id": id_trace,
            }
        }
        if image_url:
            image_messages = []
            for img_url in image_url:
                image_base64 = convert_image_to_base64(img_url)
                image_messages.append({"type": "image_url", "image_url": {"url": image_base64}})
            hasil = app_eval.invoke(
            {"messages": [HumanMessage(content=[
                {"type": "text", "text": user_query},
                *image_messages
            ])]},
            config=config,
        )

        else:
            hasil = app_eval.invoke(
            {"messages": [HumanMessage(content=user_query)]},
            config=config,
        )
        
        return hasil["messages"][-1].content
    
    
    # ── Juri 1: Route Accuracy — cek apakah node yang benar dieksekusi ──────
    @scorer
    def juri_rute(trace, expectations) -> Feedback:
        expected_node = expectations.get("expected_node", "")
        span_names = [span.name for span in trace.data.spans]
        if expected_node in span_names:
            return Feedback(
                value=1.0,
                rationale=f"LULUS: Node '{expected_node}' ditemukan dalam trace.",
            )
        return Feedback(
            value=0.0,
            rationale=f"GAGAL: '{expected_node}' tidak ditemukan. Spans aktif: {span_names}",
        )

    # ── Juri 2: Tool Call Accuracy — cek apakah tool yang benar dipanggil ───
    @scorer
    def juri_tool(trace, expectations) -> Feedback:
        expected_tool = expectations.get("expected_tool", "")
        span_names = [span.name for span in trace.data.spans]
        if expected_tool in span_names:
            return Feedback(
                value=1.0,
                rationale=f"LULUS: Tool '{expected_tool}' dipanggil dalam trace.",
            )
        return Feedback(
            value=0.0,
            rationale=f"GAGAL: '{expected_tool}' tidak dipanggil. Spans aktif: {span_names}",
        )
 
    # ── Juri 3: Answer Relevancy — MLflow Guidelines (LLM-as-Judge) ─────────
    juri_relevancy = Guidelines(
        name="skor_relevansi_jawaban",
        guidelines=(
            "Semua jawaban WAJIB menggunakan Bahasa Indonesia yang baik dan jelas. "
            "Semua jawaban WAJIB ditulis dalam format Markdown yang rapi. "
            "Jawaban HARUS langsung, relevan, dan akurat sesuai pertanyaan pengguna. "
            "Jika pengguna menanyakan produk yang tersedia, jawaban HARUS menampilkan daftar produk yang relevan. "
            "Jika pengguna ingin membeli produk, jawaban HARUS membantu proses pembelian "
            "dan menyediakan tautan pembayaran jika tersedia. "
            "Jika pengguna meminta perbandingan produk, jawaban WAJIB menyertakan tabel perbandingan dalam format Markdown "
            "serta rekomendasi yang jelas. "
            "Jawaban yang tidak relevan, tidak menjawab pertanyaan, tidak menggunakan Bahasa Indonesia, "
            "atau tidak menggunakan format Markdown harus mendapatkan skor rendah."
        ),
        model="groq:/llama-3.1-8b-instant",
    )

    # ── Jalankan evaluasi dengan mlflow.genai.evaluate() ────────────────────
    run_name = f"evaluasi-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
    print(f"\n🔬 Memulai mlflow.genai.evaluate() — run: '{run_name}'")

    with mlflow.start_run(run_name=run_name):
        result = mlflow.genai.evaluate(
            data=EVAL_SCENARIOS,
            predict_fn=predict_fn,
            # scorers=[juri_rute, juri_tool, juri_relevancy],
            scorers=[juri_rute, juri_tool],
        )

    print("✅ Selesai! Buka: mlflow ui  →  http://127.0.0.1:5000")
    return result




if __name__ != "__main__":
    from mlflow.entities import Feedback
    from mlflow.genai import scorer
    from mlflow.genai.scorers import Guidelines
    mlflow.langchain.autolog()
    mlflow.tracing.enable()
    mlflow.set_experiment("capstone-agent-evaluation")

    @scorer
    def juri_rute(trace, expectations) -> Feedback:
        expected_node = expectations.get("expected_node", "")
        span_names = [span.name for span in trace.data.spans]
        if expected_node in span_names:
            return Feedback(
                value=1.0,
                rationale=f"LULUS: Node '{expected_node}' ditemukan dalam trace.",
            )
        return Feedback(
            value=0.0,
            rationale=f"GAGAL: '{expected_node}' tidak ditemukan. Spans aktif: {span_names}",
        )
     
    def inference_agent(user_query: str,thread_id: str, user_id = str , image_url: list = None  ) -> str:
            response_agent = None
            with ConnectionPool(conninfo=DB_URI, kwargs=connection_kwargs) as pool:
                checkpointer = PostgresSaver(pool)
                checkpointer.setup()
                agent = builder.compile(checkpointer=checkpointer)
                
                config = {
                    "configurable": {
                        "user_id": user_id,
                        "thread_id": thread_id,
                    }
                }

                def predict_fn(user_query: str, image_url: list = None) -> str:
                    if image_url:
                        image_messages = []
                        for img_url in image_url:
                            image_base64 = convert_image_to_base64(img_url)
                            image_messages.append({"type": "image_url", "image_url": {"url": image_base64}})
                        hasil = agent.invoke(
                        {"messages": [HumanMessage(content=[
                            {"type": "text", "text": user_query},
                            *image_messages
                        ])]},
                        config=config,
                    )

                    else:
                        hasil = agent.invoke(
                        {"messages": [HumanMessage(content=user_query)]},
                        config=config,
                    )

                    nonlocal response_agent
                    response_agent = hasil["messages"][-1].content
                    return hasil["messages"][-1].content

                run_name = f"evaluasi-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
                print(f"\n🔬 Memulai mlflow.genai.evaluate() — run: '{run_name}'")

                with mlflow.start_run(run_name=run_name):
                    result = mlflow.genai.evaluate(
                        data=[{
                                "inputs": {
                                    "user_query": user_query,
                                    "image_url": image_url
                                    },
                                "expectations": {
                                    "expected_node": "node_komparasi",
                                 }
                                }],
                        predict_fn=predict_fn,
                        scorers=[juri_rute],
                    )
                print (result)
            return response_agent
                        

    __all__ = [inference_agent]
