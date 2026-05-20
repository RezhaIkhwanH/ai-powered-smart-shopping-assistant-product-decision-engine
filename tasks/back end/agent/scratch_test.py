import google.generativeai as genai
from dotenv import load_dotenv
load_dotenv()
# Ganti dengan API Key kamu
genai.configure(api_key="AIzaSyBGjKgJ_j2FFUpDzVTOpphu7_T0a05ntnY")

for m in genai.list_models():
        print(m.name)