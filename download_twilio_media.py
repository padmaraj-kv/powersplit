#!/usr/bin/env python3
"""
Script to download media files from Twilio webhook messages
Uses basic authentication with Twilio credentials
"""

import requests
import os
from datetime import datetime
from urllib.parse import urlparse
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Twilio credentials from environment variables
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")

if not TWILIO_ACCOUNT_SID or not TWILIO_AUTH_TOKEN:
    raise ValueError("TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN must be set in environment variables or .env file")

# Media URLs from the webhook messages
MEDIA_URLS = [
    {
        "url": "https://api.twilio.com/2010-04-01/Accounts/ACd195d7913a39e869ac436d25f3057b18/Messages/MM4051e9f3a46292627027cc90b6d2064b/Media/ME73f08d35dd229cb6fc65498832408461",
        "type": "image",
        "content_type": "image/jpeg",
        "message_id": "MM4051e9f3a46292627027cc90b6d2064b"
    },
    {
        "url": "https://api.twilio.com/2010-04-01/Accounts/ACd195d7913a39e869ac436d25f3057b18/Messages/MM7718be3a0e03c05829bdf9ca90ce98b9/Media/ME6a4ac467f5002b7457f01ed41dc09459",
        "type": "audio",
        "content_type": "audio/ogg",
        "message_id": "MM7718be3a0e03c05829bdf9ca90ce98b9"
    }
]

def download_media_file(media_info):
    """Download a media file from Twilio"""
    url = media_info["url"]
    media_type = media_info["type"]
    content_type = media_info["content_type"]
    message_id = media_info["message_id"]
    
    print(f"Downloading {media_type} file from message {message_id}...")
    print(f"URL: {url}")
    
    try:
        # Make authenticated request to Twilio
        response = requests.get(
            url,
            auth=(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN),
            timeout=30
        )
        
        if response.status_code == 200:
            # Determine file extension based on content type
            if content_type == "image/jpeg":
                extension = ".jpg"
            elif content_type == "audio/ogg":
                extension = ".ogg"
            else:
                extension = ".bin"  # fallback
            
            # Create filename with timestamp and message ID
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"twilio_{media_type}_{timestamp}_{message_id[-8:]}{extension}"
            
            # Create media directory if it doesn't exist
            media_dir = "downloaded_media"
            os.makedirs(media_dir, exist_ok=True)
            
            # Full file path
            file_path = os.path.join(media_dir, filename)
            
            # Save file to disk
            with open(file_path, "wb") as f:
                f.write(response.content)
            
            file_size = len(response.content)
            print(f"✅ Successfully downloaded {media_type} file:")
            print(f"   File: {file_path}")
            print(f"   Size: {file_size:,} bytes")
            print(f"   Content-Type: {content_type}")
            print()
            
            return file_path
            
        else:
            print(f"❌ Failed to download {media_type} file:")
            print(f"   Status Code: {response.status_code}")
            print(f"   Response: {response.text}")
            print()
            return None
            
    except requests.exceptions.RequestException as e:
        print(f"❌ Error downloading {media_type} file: {e}")
        print()
        return None

def main():
    """Download all media files"""
    print("🔽 Starting Twilio Media Download")
    print("=" * 50)
    print(f"Account SID: {TWILIO_ACCOUNT_SID}")
    print(f"Number of files to download: {len(MEDIA_URLS)}")
    print()
    
    downloaded_files = []
    
    for i, media_info in enumerate(MEDIA_URLS, 1):
        print(f"[{i}/{len(MEDIA_URLS)}] Processing {media_info['type']} file...")
        file_path = download_media_file(media_info)
        
        if file_path:
            downloaded_files.append(file_path)
    
    print("=" * 50)
    print("📋 Download Summary:")
    print(f"   Total files attempted: {len(MEDIA_URLS)}")
    print(f"   Successfully downloaded: {len(downloaded_files)}")
    
    if downloaded_files:
        print("\n📁 Downloaded files:")
        for file_path in downloaded_files:
            abs_path = os.path.abspath(file_path)
            print(f"   • {abs_path}")
    
    print("\n✨ Download process completed!")

if __name__ == "__main__":
    main()