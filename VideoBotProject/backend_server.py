import asyncio
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from yt_dlp import YoutubeDL
import os
import json
from pydantic import BaseModel
from typing import Dict

app = FastAPI()

# --- إضافة CORS للسماح للوحة التحكم بالوصول ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- ملفات وإعدادات ---
CONFIG_FILE = "config.json"
DOWNLOADS_DIR = "temp_videos"
if not os.path.exists(DOWNLOADS_DIR):
    os.makedirs(DOWNLOADS_DIR)

# --- دوال مساعدة للإعدادات ---
def get_config():
    if not os.path.exists(CONFIG_FILE):
        default_config = { "default": "https://www.google.com", "720p": "", "1080p": "" }
        set_config(default_config)
        return default_config
    with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)

def set_config(config_data):
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(config_data, f, indent=4, ensure_ascii=False)

# --- نقاط الوصول (Endpoints) للوحة التحكم ---
@app.get("/get_ads_config")
async def get_ads_config():
    return get_config()

@app.post("/set_ads_config")
async def set_ads_config(payload: Dict[str, str]):
    try:
        set_config(payload)
        return {"message": "تم تحديث الإعدادات بنجاح!"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"فشل تحديث الإعدادات: {e}")

# --- نقطة وصول لصفحة الإعلان مع عداد ---
@app.get("/show_ad_page", response_class=HTMLResponse)
async def show_ad_page(feature: str):
    config = get_config()
    ad_url = config.get(feature) or config.get("default", "https://google.com")
    html_content = f"""
    <!DOCTYPE html><html lang="ar" dir="rtl"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"><title>عرض الإعلان</title><script src="https://cdn.tailwindcss.com"></script></head><body class="bg-gray-900 text-white flex flex-col items-center justify-center h-screen font-sans p-4"><div class="text-center"><h1 id="timer-message" class="text-2xl font-bold text-yellow-400 mb-4">يجب الانتظار <span id="countdown">30</span> ثانية للمتابعة...</h1><p id="success-message" class="text-xl font-bold text-green-400 hidden">✅ شكراً لك! يمكنك الآن إغلاق هذه النافذة والعودة إلى البوت للضغط على زر المتابعة.</p></div><div class="w-full max-w-lg h-3/5 my-8 border-4 border-gray-700 rounded-lg overflow-hidden bg-gray-800"><iframe src="{ad_url}" class="w-full h-full" frameborder="0"></iframe></div><script>let seconds = 30;const countdownElement = document.getElementById('countdown');const timerMessage = document.getElementById('timer-message');const successMessage = document.getElementById('success-message');const interval = setInterval(() => {{seconds--;countdownElement.textContent = seconds;if (seconds <= 0) {{clearInterval(interval);timerMessage.classList.add('hidden');successMessage.classList.remove('hidden');}}}}, 1000);</script></body></html>
    """
    return HTMLResponse(content=html_content)

# --- نقاط الوصول (Endpoints) للبوت ---
@app.get("/get_info")
async def get_video_info(url: str):
    try:
        ydl_opts = {'quiet': True, 'skip_download': True}
        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            formats = []
            for f in info.get('formats', []):
                if f.get('vcodec') != 'none' and f.get('acodec') != 'none' and f.get('ext') == 'mp4':
                    formats.append({
                        'format_id': f.get('format_id'), 'resolution': f.get('format_note'),
                        'filesize': f.get('filesize') or f.get('filesize_approx'), 'ext': f.get('ext')
                    })
            return {"title": info.get('title'), "formats": formats}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/download")
async def download_video(url: str, format_id: str):
    try:
        output_template = os.path.join(DOWNLOADS_DIR, f'%(id)s_{format_id}.%(ext)s')
        ydl_opts = {'format': format_id, 'outtmpl': output_template, 'quiet': True}
        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)
        if os.path.exists(filename):
            return {"file_path": filename}
        else:
            raise HTTPException(status_code=500, detail="Failed to download video file.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
