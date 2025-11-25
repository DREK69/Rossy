from fastapi import FastAPI, HTTPException, Header, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import create_engine, Column, Integer, String, DateTime, Boolean, Float, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime
from typing import Optional
from pathlib import Path
from pyrogram import Client
from contextlib import asynccontextmanager
import yt_dlp
import secrets
import os
import time
import random
import threading
import re
import ssl

ssl._create_default_https_context = ssl._create_unverified_context

DATABASE_URL = "sqlite:///./youtube_api.db"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

DOWNLOAD_DIR = Path("downloads")
DOWNLOAD_DIR.mkdir(exist_ok=True)

COOKIES_FILES = []
for i in range(1, 10):
    cookie_file = f"cookies{i}.txt"
    if Path(cookie_file).exists():
        COOKIES_FILES.append(cookie_file)

if not COOKIES_FILES:
    if Path("cookies.txt").exists():
        COOKIES_FILES = ["cookies.txt"]

API_ID = 25723056
API_HASH = "cbda56fac135e92b755e1243aefe9697"
BOT_TOKEN = "8382334407:AAEk62duH1YQ334X0NWJ5DBrhSnUME9SYUY"
STORAGE_CHANNEL = -1003420240384

bot = Client("youtube_api_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

cookie_last_used = {cookie: 0 for cookie in COOKIES_FILES}
cookie_lock = threading.Lock()

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    telegram_id = Column(String, unique=True, nullable=True)
    api_key = Column(String, unique=True, index=True)
    is_active = Column(Boolean, default=True)
    request_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)

class VideoCache(Base):
    __tablename__ = "video_cache"
    id = Column(Integer, primary_key=True, index=True)
    video_id = Column(String, unique=True, index=True)
    message_id = Column(Integer)
    title = Column(String)
    duration = Column(Integer)
    format_type = Column(String)
    file_path = Column(String)
    cached_at = Column(DateTime, default=datetime.utcnow)

class APILog(Base):
    __tablename__ = "api_logs"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer)
    video_id = Column(String)
    query = Column(Text)
    format_type = Column(String)
    response_time = Column(Float)
    success = Column(Boolean)
    error_msg = Column(Text, nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow)

Base.metadata.create_all(bind=engine)

@asynccontextmanager
async def lifespan(app: FastAPI):
    await bot.start()
    yield
    await bot.stop()

app = FastAPI(title="YouTube API with Telegram Storage", version="5.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def verify_api_key(api_key: str = Header(...)):
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.api_key == api_key, User.is_active == True).first()
        if not user:
            raise HTTPException(status_code=401, detail="Invalid API key")
        return user
    finally:
        db.close()

def get_available_cookie():
    with cookie_lock:
        now = time.time()
        available = []
        
        for cookie_path in COOKIES_FILES:
            if not Path(cookie_path).exists():
                continue
            last_used = cookie_last_used.get(cookie_path, 0)
            wait_time = now - last_used
            
            if wait_time >= 10:
                available.append(cookie_path)
        
        if not available:
            if not cookie_last_used:
                return None
            oldest = min(cookie_last_used.items(), key=lambda x: x[1])
            wait_needed = 10 - (now - oldest[1])
            if wait_needed > 0:
                time.sleep(wait_needed)
            return oldest[0]
        
        selected = random.choice(available)
        cookie_last_used[selected] = now
        return selected

def add_realistic_delay():
    delay = random.uniform(1, 3)
    time.sleep(delay)

def get_ydl_opts_audio(output_path, cookie_file=None):
    if not cookie_file:
        cookie_file = get_available_cookie()
    
    opts = {
        'format': 'bestaudio/best',
        'outtmpl': str(output_path.with_suffix('.%(ext)s')),
        'geo_bypass': True,
        'nocheckcertificate': True,
        'quiet': True,
        'no_warnings': True,
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
    }
    
    if cookie_file and Path(cookie_file).exists():
        opts['cookiefile'] = str(Path(cookie_file).absolute())
    
    return opts

def get_ydl_opts_video(output_path, cookie_file=None):
    if not cookie_file:
        cookie_file = get_available_cookie()
    
    opts = {
        'format': '(bestvideo[height<=?720][width<=?1280][ext=mp4])+(bestaudio[ext=m4a])',
        'outtmpl': str(output_path),
        'geo_bypass': True,
        'nocheckcertificate': True,
        'quiet': True,
        'no_warnings': True,
    }
    
    if cookie_file and Path(cookie_file).exists():
        opts['cookiefile'] = str(Path(cookie_file).absolute())
    
    return opts

def search_youtube(query):
    add_realistic_delay()
    
    try:
        cookie_file = get_available_cookie()
        
        ydl_opts = {
            'quiet': True,
            'extract_flat': True,
            'nocheckcertificate': True,
        }
        
        if cookie_file and Path(cookie_file).exists():
            ydl_opts['cookiefile'] = str(Path(cookie_file).absolute())
        
        search_url = f"ytsearch5:{query}"
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            result = ydl.extract_info(search_url, download=False)
            
            if result and 'entries' in result:
                videos = []
                for video in result['entries']:
                    if video:
                        videos.append({
                            'video_id': video.get('id'),
                            'title': video.get('title', 'Unknown'),
                            'duration': video.get('duration', 0),
                            'channel': video.get('channel', 'Unknown'),
                            'thumbnail': video.get('thumbnail', ''),
                            'url': f"https://www.youtube.com/watch?v={video.get('id')}"
                        })
                return videos
        
        return []
        
    except Exception as e:
        raise Exception(f"Search error: {str(e)}")

async def upload_to_telegram(file_path, title, duration, format_type):
    try:
        async with bot:
            if format_type == 'audio':
                msg = await bot.send_audio(
                    STORAGE_CHANNEL,
                    str(file_path),
                    title=title[:100] if title else "Audio",
                    duration=int(duration) if duration else 0
                )
            else:
                msg = await bot.send_video(
                    STORAGE_CHANNEL,
                    str(file_path),
                    caption=title[:1000] if title else "Video",
                    duration=int(duration) if duration else 0
                )
            return msg.id
    except Exception as e:
        raise Exception(f"Telegram upload error: {e}")

async def get_from_telegram(message_id):
    try:
        async with bot:
            msg = await bot.get_messages(STORAGE_CHANNEL, message_id)
            if msg.audio:
                file = msg.audio
            elif msg.video:
                file = msg.video
            else:
                return None
            
            return {
                'file_id': file.file_id,
                'file_name': getattr(file, 'file_name', 'download'),
                'file_size': file.file_size,
                'duration': getattr(file, 'duration', 0)
            }
    except:
        return None

@app.get("/")
async def root():
    cookies_found = len(COOKIES_FILES)
    return {
        "status": "active",
        "version": "5.0",
        "yt_dlp_version": "2025.11.12",
        "cookies_loaded": cookies_found,
        "features": ["Audio Download", "Video Download", "Telegram Storage", "Smart Caching"],
        "endpoints": {
            "register": "POST /register?username=<n>",
            "search": "GET /api/search?query=<song>",
            "download": "GET /api/youtube?query=<song>&format=<audio/video>",
            "video": "GET /api/youtube?video_id=<id>&format=<audio/video>",
            "stats": "GET /api/stats"
        }
    }

@app.post("/register")
async def register(username: str, telegram_id: Optional[str] = None):
    db = SessionLocal()
    try:
        if db.query(User).filter(User.username == username).first():
            raise HTTPException(status_code=400, detail="Username exists")
        
        api_key = secrets.token_urlsafe(32)
        user = User(username=username, telegram_id=telegram_id, api_key=api_key)
        db.add(user)
        db.commit()
        db.refresh(user)
        
        return {
            "success": True,
            "username": user.username,
            "api_key": user.api_key,
            "message": "Registration successful"
        }
    finally:
        db.close()

@app.get("/api/search")
async def search_videos(
    query: str,
    artist: Optional[str] = None,
    max_results: int = Query(default=5, le=20),
    api_key: str = Header(...)
):
    user = verify_api_key(api_key)
    db = SessionLocal()
    start_time = time.time()
    
    try:
        search_query = f"{artist} {query}" if artist else query
        results = search_youtube(search_query)
        
        user.request_count += 1
        response_time = time.time() - start_time
        
        log = APILog(
            user_id=user.id,
            video_id='search',
            query=search_query,
            format_type='search',
            response_time=response_time,
            success=True
        )
        db.add(log)
        db.commit()
        
        return {
            "success": True,
            "query": search_query,
            "results": results[:max_results],
            "count": len(results[:max_results])
        }
        
    except Exception as e:
        response_time = time.time() - start_time
        log = APILog(
            user_id=user.id,
            video_id='search',
            query=query,
            format_type='search',
            response_time=response_time,
            success=False,
            error_msg=str(e)
        )
        db.add(log)
        db.commit()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()

@app.get("/api/youtube")
async def download_youtube(
    query: Optional[str] = None,
    format: str = "audio",
    video_id: Optional[str] = None,
    api_key: str = Header(...)
):
    user = verify_api_key(api_key)
    db = SessionLocal()
    start_time = time.time()
    
    try:
        if format not in ['audio', 'video']:
            raise HTTPException(status_code=400, detail="Format must be 'audio' or 'video'")
        
        if not query and not video_id:
            raise HTTPException(status_code=400, detail="Either 'query' or 'video_id' is required")
        
        if video_id:
            url = f"https://www.youtube.com/watch?v={video_id}"
            vid_id = video_id
            title = None
            duration = 0
        else:
            if not query.startswith('http'):
                search_results = search_youtube(query)
                if not search_results:
                    raise HTTPException(status_code=404, detail="No results found")
                
                url = search_results[0]['url']
                vid_id = search_results[0]['video_id']
                title = search_results[0]['title']
                duration = search_results[0]['duration']
            else:
                url = query
                video_id_match = re.search(r'(?:v=|/)([0-9A-Za-z_-]{11}).*', url)
                if not video_id_match:
                    raise HTTPException(status_code=400, detail="Invalid URL")
                vid_id = video_id_match.group(1)
                title = "Video"
                duration = 0
        
        cache_key = f"{vid_id}_{format}"
        cached = db.query(VideoCache).filter(VideoCache.video_id == cache_key).first()
        
        if cached:
            file_info = await get_from_telegram(cached.message_id)
            if file_info:
                user.request_count += 1
                response_time = time.time() - start_time
                
                log = APILog(
                    user_id=user.id,
                    video_id=vid_id,
                    query=query or video_id,
                    format_type=format,
                    response_time=response_time,
                    success=True
                )
                db.add(log)
                db.commit()
                
                return {
                    "success": True,
                    "title": cached.title,
                    "video_id": vid_id,
                    "format": format,
                    "duration": cached.duration,
                    "file_id": file_info['file_id'],
                    "file_size": file_info['file_size'],
                    "cached": True,
                    "telegram_file": True
                }
        
        ext = 'mp3' if format == 'audio' else 'mp4'
        output_path = DOWNLOAD_DIR / f"{vid_id}.{ext}"
        
        if output_path.exists():
            os.remove(output_path)
        
        add_realistic_delay()
        
        if format == 'audio':
            ydl_opts = get_ydl_opts_audio(output_path)
        else:
            ydl_opts = get_ydl_opts_video(output_path)
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            if not title:
                title = info.get('title', 'Unknown')
                duration = info.get('duration', 0)
        
        downloaded_files = list(DOWNLOAD_DIR.glob(f"{vid_id}.*"))
        if not downloaded_files:
            raise Exception("Download failed")
        
        actual_file = downloaded_files[0]
        
        message_id = await upload_to_telegram(str(actual_file), title, duration, format)
        
        cache_entry = VideoCache(
            video_id=cache_key,
            message_id=message_id,
            title=title,
            duration=duration,
            format_type=format,
            file_path=str(actual_file)
        )
        db.add(cache_entry)
        
        try:
            actual_file.unlink()
        except:
            pass
        
        user.request_count += 1
        response_time = time.time() - start_time
        
        log = APILog(
            user_id=user.id,
            video_id=vid_id,
            query=query or video_id,
            format_type=format,
            response_time=response_time,
            success=True
        )
        db.add(log)
        db.commit()
        
        file_info = await get_from_telegram(message_id)
        
        return {
            "success": True,
            "title": title,
            "video_id": vid_id,
            "format": format,
            "duration": duration,
            "file_id": file_info['file_id'] if file_info else None,
            "file_size": file_info['file_size'] if file_info else None,
            "cached": False,
            "telegram_file": True
        }
        
    except Exception as e:
        response_time = time.time() - start_time
        log = APILog(
            user_id=user.id,
            video_id=video_id or 'unknown',
            query=query or video_id or 'unknown',
            format_type=format,
            response_time=response_time,
            success=False,
            error_msg=str(e)
        )
        db.add(log)
        db.commit()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()

@app.get("/api/stats")
async def get_stats(api_key: str = Header(...)):
    user = verify_api_key(api_key)
    db = SessionLocal()
    
    try:
        total = db.query(APILog).filter(APILog.user_id == user.id).count()
        success = db.query(APILog).filter(APILog.user_id == user.id, APILog.success == True).count()
        cached_files = db.query(VideoCache).count()
        
        return {
            "username": user.username,
            "total_requests": total,
            "successful_requests": success,
            "failed_requests": total - success,
            "cached_files": cached_files,
            "member_since": user.created_at
        }
    finally:
        db.close()

@app.get("/health")
async def health():
    cookies_status = {}
    for cookie_path in COOKIES_FILES:
        path = Path(cookie_path)
        if path.exists():
            age_hours = (time.time() - path.stat().st_mtime) / 3600
            last_used = cookie_last_used.get(cookie_path, 0)
            time_since_use = time.time() - last_used if last_used > 0 else 999
            cookies_status[path.name] = {
                'exists': True,
                'age_hours': round(age_hours, 2),
                'last_used_seconds_ago': round(time_since_use, 1),
                'readable': os.access(path, os.R_OK)
            }
        else:
            cookies_status[path.name] = {'exists': False}
    
    db = SessionLocal()
    cached_count = db.query(VideoCache).count()
    db.close()
    
    return {
        'status': 'ok',
        'yt_dlp_version': '2025.11.12',
        'cookies': cookies_status,
        'cookies_count': len(COOKIES_FILES),
        'cached_files': cached_count,
        'storage': 'telegram'
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
