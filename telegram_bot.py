import asyncio
import httpx
import os
from typing import Optional
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Telegram Bot configuration
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

async def send_telegram_error(error_message: str, context: str = ""):
    """Send error notification to Telegram"""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print(f"[TELEGRAM] ⚠️ Telegram bot not configured (missing token or chat_id)")
        return False
    
    try:
        import datetime
        current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        message = f"🚨 **Withdrawal Error**\n\n"
        message += f"**Context:** {context}\n\n"
        message += f"**Error:** {error_message}\n\n"
        message += f"**Time:** {current_time}"
        
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        data = {
            "chat_id": TELEGRAM_CHAT_ID,
            "text": message,
            "parse_mode": "Markdown"
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=data, timeout=10)
            if response.status_code == 200:
                print(f"[TELEGRAM] ✓ Error notification sent successfully")
                return True
            else:
                print(f"[TELEGRAM] ❌ Failed to send notification: {response.status_code}")
                return False
                
    except Exception as e:
        print(f"[TELEGRAM] ❌ Failed to send Telegram notification: {e}")
        return False

async def send_telegram_success(message: str, context: str = ""):
    """Send success notification to Telegram"""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print(f"[TELEGRAM] ⚠️ Telegram bot not configured (missing token or chat_id)")
        return False
    
    try:
        import datetime
        current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        telegram_message = f"✅ **Withdrawal Success**\n\n"
        telegram_message += f"**Context:** {context}\n\n"
        telegram_message += f"**Message:** {message}\n\n"
        telegram_message += f"**Time:** {current_time}"
        
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        data = {
            "chat_id": TELEGRAM_CHAT_ID,
            "text": telegram_message,
            "parse_mode": "Markdown"
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=data, timeout=10)
            if response.status_code == 200:
                print(f"[TELEGRAM] ✓ Success notification sent successfully")
                return True
            else:
                print(f"[TELEGRAM] ❌ Failed to send success notification: {response.status_code}")
                return False
                
    except Exception as e:
        print(f"[TELEGRAM] ❌ Failed to send Telegram success notification: {e}")
        return False

async def send_telegram_info(message: str, context: str = ""):
    """Send info notification to Telegram"""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print(f"[TELEGRAM] ⚠️ Telegram bot not configured (missing token or chat_id)")
        return False
    
    try:
        import datetime
        current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        telegram_message = f"ℹ️ **Info**\n\n"
        telegram_message += f"**Context:** {context}\n\n"
        telegram_message += f"**Message:** {message}\n\n"
        telegram_message += f"**Time:** {current_time}"
        
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        data = {
            "chat_id": TELEGRAM_CHAT_ID,
            "text": telegram_message,
            "parse_mode": "Markdown"
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=data, timeout=10)
            if response.status_code == 200:
                print(f"[TELEGRAM] ✓ Info notification sent successfully")
                return True
            else:
                print(f"[TELEGRAM] ❌ Failed to send info notification: {response.status_code}")
                return False
                
    except Exception as e:
        print(f"[TELEGRAM] ❌ Failed to send Telegram info notification: {e}")
        return False

def is_telegram_configured() -> bool:
    """Check if Telegram bot is properly configured"""
    return bool(TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID)
