import time
import os
import re
import requests
import json
import gspread
import asyncio
import cv2
import easyocr
import feedparser
import yt_dlp
from telethon import TelegramClient, events
from telethon.sessions import StringSession
from google.oauth2.service_account import Credentials
from ntscraper import Nitter

# --- Config ---
START_TIME = time.time()
MAX_RUN_TIME = 19800 
MY_CHAT_ID = int(os.getenv("MY_CHAT_ID"))
READER = easyocr.Reader(['en'], gpu=False) 
PROCESSED_VIDEOS = set()
BLACKLIST = ["GIVEAWAY", "GRAPHICS", "AIRDROPS", "BINANCE", "CHANNELS", "REGISTER", "DOWNLOAD", "DAILYNEW"]

def find_binance_code(text):
    if not text: return []
    found = re.findall(r'\b[A-Z0-9]{8}\b', text.upper())
    return [c for c in found if c not in BLACKLIST and any(char.isdigit() for char in c)]

# Video Scan with Timeout
async def scan_video_content(video_url):
    video_file = f"vid_{int(time.time())}.mp4"
    codes_found = set()
    
    ydl_opts = {
        'format': 'best[height<=360]',
        'outtmpl': video_file,
        'cookiefile': 'cookies.txt',
        'quiet': True,
        'no_warnings': True,
        'socket_timeout': 30, # ၃၀ စက္ကန့်အတွင်း မရရင် ကျော်မယ်
    }
    
    try:
        # YouTube Download ကို ၅ မိနစ်ထက် ပိုမကြာအောင် ကန့်သတ်မယ်
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([video_url])
        
        if os.path.exists(video_file):
            cap = cv2.VideoCapture(video_file)
            fps = cap.get(cv2.CAP_PROP_FPS) or 24
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            interval = int(fps * 3)
            for frame_no in range(0, total_frames, interval):
                cap.set(cv2.CAP_PROP_POS_FRAMES, frame_no)
                success, frame = cap.read()
                if not success: break
                for (_, text, _) in READER.readtext(frame):
                    codes_found.update(find_binance_code(text))
            cap.release()
    except Exception as e:
        print(f"⚠️ YT Scan Skipped: {e}")
    finally:
        if os.path.exists(video_file): os.remove(video_file)
            
    return codes_found

def get_sheet():
    try:
        creds_json = json.loads(os.getenv("GOOGLE_SHEETS_JSON"))
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = Credentials.from_service_account_info(creds_json, scopes=scope)
        gc = gspread.authorize(creds)
        return gc.open_by_url("https://docs.google.com/spreadsheets/d/1ZDHya5Gep3kvVyQqgdRlJIgquP7pYZv9ZSW7hV2YTyE/edit").sheet1
    except: return None

async def main():
    user_client = TelegramClient(StringSession(os.getenv("TG_STRING_SESSION")), 
                                 int(os.getenv("TG_API_ID")), os.getenv("TG_API_HASH"))
    bot_client = TelegramClient('bot', int(os.getenv("TG_API_ID")), os.getenv("TG_API_HASH"))

    await user_client.start()
    await bot_client.start(bot_token=os.getenv("BOT_TOKEN"))
    print("🚀 Bot v3.9 (Robust Mode) Started!")

    while True:
        if time.time() - START_TIME > MAX_RUN_TIME: break
        
        sheet = get_sheet()
        if not sheet: 
            await asyncio.sleep(60)
            continue
        
        records = sheet.get_all_records()

        # --- ၁။ X (Twitter) Section ကို အရင်လုပ်မယ် ---
        print("🐦 Checking X (Twitter)...")
        x_links = [r['Link'] for r in records if r['Type'].upper() == 'X']
        if x_links:
            try:
                scraper = Nitter()
                for link in x_links:
                    user = link.strip().split('/')[-1].split('?')[0]
                    # အလုပ်လုပ်နေတဲ့ Nitter instance ကို ရှာဖွေပြီး scan ဖတ်မယ်
                    tweets = scraper.get_tweets(user, mode='user', number=3)
                    if tweets and 'tweets' in tweets:
                        for t in tweets['tweets']:
                            codes = find_binance_code(t['text'])
                            for c in set(codes):
                                await bot_client.send_message(MY_CHAT_ID, f"🐦 **X Code:** `{c}`\n👤 From: {user}")
                                print(f"✨ Found on X: {c}")
            except Exception as e:
                print(f"⚠️ X Error: {e}")

        # --- ၂။ YouTube Section ကို နောက်မှလုပ်မယ် ---
        print("📺 Checking YouTube RSS...")
        yt_links = [r['Link'] for r in records if r['Type'].upper() == 'YT']
        for rss_url in yt_links:
            try:
                feed = feedparser.parse(rss_url)
                for entry in feed.entries:
                    v_id = entry.yt_videoid if 'yt_videoid' in entry else entry.link
                    if v_id in PROCESSED_VIDEOS: continue
                    
                    found_codes = await scan_video_content(entry.link)
                    if found_codes:
                        for c in found_codes:
                            await bot_client.send_message(MY_CHAT_ID, f"📺 **YouTube Code:** `{c}`\n🔗 {entry.link}")
                    PROCESSED_VIDEOS.add(v_id)
            except: pass

        print("😴 Sleeping for 10 minutes...")
        await asyncio.sleep(600)

if __name__ == "__main__":
    asyncio.run(main())
