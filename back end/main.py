import os
import uvicorn
from datetime import datetime, timedelta
from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer
import logging
from pydantic import BaseModel, EmailStr
from supabase import create_client, Client
from passlib.context import CryptContext
from jose import JWTError, jwt
from typing import Dict, Any, Optional, List
import uuid
from fastapi import File, UploadFile, Form
from fastapi.staticfiles import StaticFiles
import shutil
from dotenv import load_dotenv
from agent.agent_on import inference_agent

logging.basicConfig(level=logging.DEBUG)
load_dotenv() 
  
# --- Konfigurasi ---
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
SECRET_KEY = os.getenv("SECRET_KEY")  # Ganti dengan string random yang kuat
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", 1440/2))  # Default 12 jam

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.mount("/img", StaticFiles(directory="public/img"), name="img")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
# Ganti dari "bcrypt" ke "bcrypt_sha256"
pwd_context = CryptContext(schemes=["bcrypt_sha256"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")

# --- Schemas ---
class UserRegister(BaseModel):
    username: str
    email: EmailStr
    password: str

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class room(BaseModel):
    title: str

class payment_webhook_data(BaseModel):
    external_id: str
    id: str
    amount: float
    status: str
    user_id: str
    description: Optional[str] = None

# --- Utility Functions ---
def get_password_hash(password):
    return pwd_context.hash(password)

def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


async def get_current_user(token: str = Depends(oauth2_scheme)):

    try:
        # 1. Decode JWT
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        user_id: str = payload.get("id")
        
        if email is None or user_id is None:
            raise HTTPException(status_code=401)
            
    except JWTError:
        # Jika token expired atau dimanipulasi
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "status": "error",
                "data": "Token tidak valid atau sudah kadaluwarsa",
                "codestatus": 401
            }
        )

    # Pastikan user dengan email tersebut benar-benar masih ada di DB
    response = supabase.table("users").select("*").eq("email", email).execute()
    user = response.data[0] if response.data else None

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "status": "error",
                "data": "User tidak ditemukan di sistem kami",
                "codestatus": 401
            }
        )
    
    return user 
# --- Routes ---

@app.post("/register",tags=["Authentication"])
async def register(user: UserRegister):
    # Cek user lama
    existing_user = supabase.table("users").select("email").eq("email", user.email).execute()
    if existing_user.data:
        return {
            "status": "error",
            "data": "Email sudah terdaftar",
            "codestatus": 400
        }

    print(user.password)
    new_user = {
        "username": user.username,
        "email": user.email,
        "password_hash": get_password_hash(user.password)
    }
    
    response = supabase.table("users").insert(new_user).execute()
    
    if not response.data:
        return {
            "status": "error",
            "data": "Gagal menyimpan data ke database",
            "codestatus": 500
        }
        
    return {
        "status": "success",
        "data": {"username": user.username, "email": user.email},
        "codestatus": 201
    }

@app.post("/login",tags=["Authentication"])
async def login(user_credentials: UserLogin):
    # Cari user
    response = supabase.table("users").select("*").eq("email", user_credentials.email).execute()
    user_data = response.data[0] if response.data else None

    if not user_data or not verify_password(user_credentials.password, user_data["password_hash"]):
        return {
            "status": "error",
            "data": "Email atau password salah",
            "codestatus": 401
        }

    # kalok bener Generate Token
    access_token = create_access_token(data={"sub": user_data["email"], "id": user_data["id"]})
    return {
        "status": "success",
        "data": {
            "access_token": access_token,
            "token_type": "bearer"
        },
        "codestatus": 200
    }

@app.post("/room",description="Create a new chat room for the authenticated user")
async def create_room(room : room, current_user: dict = Depends(get_current_user)):
    user_id = current_user["id"]
    new_room = {
        "title": room.title,
        "user_id": user_id
    }
    response = supabase.table("room_chats").insert(new_room).execute()
    if not response.data:
        return {
            "status": "error",
            "data": "Gagal membuat room",
            "codestatus": 500
        }
    return {
        "status": "success",
        "data": {
            "room_id": response.data[0]["id"],
            "title": room.title
        },
        "codestatus": 201
    }   

@app.get("/room",description="Get list of rooms created by the authenticated user")
async def create_room(current_user: dict = Depends(get_current_user)):
    user_id = current_user["id"]
    response = supabase.table("room_chats").select("*").eq("user_id", user_id).execute()
    if not response.data:
        return {
                "status": "error",
                "data": "Gagal mengambil room",
            "codestatus": 500
        }
    return {
        "status": "success",
        "data": response.data,
        "codestatus": 200
    }   


@app.post("/chat",description="inferece to agent AI")
async def save_chat(
    room_id: str = Form(...),
    content: str = Form(...),
    images: Optional[List[UploadFile]] = File(None),
    current_user: dict = Depends(get_current_user) # Proteksi endpoint
):
    

    image_urls = []
    img_paths = []

    # 2. Proses simpan gambar (jika ada file yang diupload)
    if images:
        for img in images:
            # Pastikan file tidak kosong
            if img.filename:
                # Ambil ekstensi file (misal: .jpg, .png)
                file_extension = img.filename.split(".")[-1]
                # Buat nama file unik pakai UUID biar tidak tertimpa
                unique_filename = f"{uuid.uuid4()}.{file_extension}"
                file_path = os.path.join("public/img", unique_filename)
                
                # Simpan file ke dalam folder 'img'
                with open(file_path, "wb") as buffer:
                    shutil.copyfileobj(img.file, buffer)
                
                # Simpan path url-nya (sesuaikan base url jika nanti sudah deploy)
                image_urls.append(f"http://127.0.0.1:8000/img/{unique_filename}")
                img_paths.append(file_path)  # Simpan path lokal untuk inference agent

    # 3. Siapkan data untuk dikirim ke Supabase
    chat_data = {
        "room_id": room_id,
        "role": "user", # karna dari user
        "content": content,
        # Jika tidak ada gambar, set null agar sesuai skema DB
        "image_urls": image_urls if len(image_urls) > 0 else None 
    }

    # 4. Insert ke Supabase
    try:
        # insert to hytory
        supabase.table("chat_histories").insert(chat_data).execute()
        # agent inference
        thread_id = current_user["id"]+"_"+room_id
        res_agent=inference_agent(user_query=content, thread_id=thread_id, user_id=current_user["id"], img_paths=img_paths) 

        #ai agent response simpan ke history juga
        chat_data_agent = {
        "room_id": room_id,
        "role": "assistant", # karna dari user
        "content": res_agent,
        # Jika tidak ada gambar, set null agar sesuai skema DB
        "image_urls": None 
        }

        supabase.table("chat_histories").insert(chat_data_agent).execute()
            
        return {
            "status": "success",
            "data": res_agent, # Kembalikan data chat yang berhasil disimpen
            "codestatus": 201
        }
    except Exception as e:
        return {
            "status": "error",
            "data": str(e),
            "codestatus": 500
        }
    

@app.get("/chat/{room_id}" ,description="Get chat history for a specific room")
async def get_chat_history(room_id: str, current_user: dict = Depends(get_current_user)):
    try:
        response = supabase.table("chat_histories").select("*").eq("room_id", room_id).execute()
        
        if response.data is None:
            raise Exception(response.error.message)
        
        return {
            "status": "success",
            "data": response.data,
            "codestatus": 200
        }
    except Exception as e:
        return {
            "status": "error",
            "data": str(e),
            "codestatus": 500
        }   


@app.get("/me")
async def get_profile(current_user: dict = Depends(get_current_user)):
    return {
        "status": "success",
        "data": {
            "email": current_user["email"],
            "user_id": current_user["id"] 
            },
            "codestatus": 200
        }


@app.post("/payment_webhook")
async def payment_webhook(data: payment_webhook_data):
    
    try: 
        supabase.table("transactions").update({
            "status": data.status}).eq("payment_code", data.external_id).execute()
        
        response = supabase.table("transactions").select("*").eq("payment_code", data.external_id).execute()

        if response.data is None:
            raise Exception(response.error.message)

        respponse = supabase.table("chat_histories").insert({
        "room_id": response.data[0]["room_id"],
        "role": "assistant", # karna dari user
        "content": f"Pembayaran dengan kode {data.external_id} sebesar {data.amount} telah {"berhasil" if data.status == "PAID" else "gagal"} dengan status {data.status}.",
        "image_urls": None 
        }).execute()

        if respponse.data is None:
            raise Exception(respponse.error.message)
        

        return {
            "status": "success",
            "data": "Webhook diterima dan transaksi diperbarui",
            "codestatus": 200
        }
    except Exception as e:
        return {
            "status": "error",
            "data": str(e),
            "codestatus": 500
        }


if __name__ == "__main__":
    uvicorn.run("main:app", host="localhost", port=8000, log_level="debug",workers=1)