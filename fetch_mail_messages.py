#!/usr/bin/env python3
"""
Fetch email messages using OAuth2 token via dongvanfb.net API
"""

import requests
import json
from datetime import datetime

def fetch_mail_messages(email, refresh_token, client_id):
    """
    Fetch all email messages using OAuth2 token

    Args:
        email: Email address
        refresh_token: OAuth2 refresh token
        client_id: OAuth2 client ID

    Returns:
        dict: API response containing messages
    """
    api_url = "https://tools.dongvanfb.net/api/get_messages_oauth2"

    payload = {
        "email": email,
        "refresh_token": refresh_token,
        "client_id": client_id
    }

    try:
        print(f"🔍 Fetching messages for: {email}")
        print(f"📡 Calling API: {api_url}")

        response = requests.post(api_url, json=payload, timeout=30)

        print(f"📊 Status Code: {response.status_code}")

        if response.status_code == 200:
            data = response.json()

            if data.get("status"):
                messages = data.get("messages", [])
                print(f"✅ Success! Found {len(messages)} messages\n")

                # Display messages
                for idx, msg in enumerate(messages, 1):
                    print(f"{'='*80}")
                    print(f"📧 Message #{idx}")
                    print(f"{'='*80}")
                    print(f"UID: {msg.get('uid')}")
                    print(f"Date: {msg.get('date')}")

                    # Parse sender
                    sender_info = msg.get('from', [])
                    if sender_info:
                        sender = sender_info[0] if isinstance(sender_info, list) else sender_info
                        print(f"From: {sender}")

                    print(f"Subject: {msg.get('subject')}")

                    # Verification code if exists
                    code = msg.get('code')
                    if code:
                        print(f"🎯 Verification Code: {code}")

                    # Message preview (first 200 chars)
                    message_content = msg.get('message', '')
                    if message_content:
                        # Remove HTML tags for preview
                        import re
                        preview = re.sub('<[^<]+?>', '', message_content)
                        preview = preview.strip()[:200]
                        print(f"\n📄 Preview: {preview}...")

                    print()

                return data
            else:
                print(f"⚠️  Status: false")
                print(f"Response: {json.dumps(data, indent=2, ensure_ascii=False)}")
                return data
        else:
            print(f"❌ Error: {response.status_code}")
            print(f"Response: {response.text}")
            return None

    except requests.exceptions.RequestException as e:
        print(f"❌ Request failed: {e}")
        return None

def save_messages_to_file(data, filename="messages.json"):
    """Save messages to JSON file"""
    try:
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        print(f"💾 Messages saved to: {filename}")
    except Exception as e:
        print(f"❌ Failed to save: {e}")

if __name__ == "__main__":
    # Credentials from user input
    EMAIL = "skyebettencourteaw1086@hotmail.com"
    REFRESH_TOKEN = "M.C521_BAY.0.U.-CtPwMqUZwogq2GKT6AxBVLI52H!tWLjEJFkAn0CfYm!swGHexo86*9aZ9GP0NKl9OVWZ4!c82DtLhALsgw7h2MuxI0dHCvCUGFLin9ZmzIaGI4NdQzsQW3VeoQoZRBR!WP1CjtMTh9*4sBTMH5PNv9N2HfkLh0ZnnHQwSKZOqXauHD8pzWlNm5PuSU*xEyvP588x5IDqulu46EaSdRV*jo1Ygp3HbF!BUaK3D7sWEWmH3*X*OPrkGpTUHow7AComWpkcjGQKOZJiWvhRZ!oY9o3IUEgksqHeatKT5KZpT0Q0FCIWATRFzGc6E!v!S*6RnvdueiY3aFgvN5HbFEZ9NUf1TKsO!n3kMENjChjgQYOuIOCgJVK9FkzOT6Fy11SWHA$$"
    CLIENT_ID = "9e5f94bc-e8a4-4e73-b8be-63364c29d753"

    result = fetch_mail_messages(EMAIL, REFRESH_TOKEN, CLIENT_ID)

    if result and result.get("status"):
        # Optionally save to file
        save_messages_to_file(result, "messages.json")

        # Extract all verification codes
        messages = result.get("messages", [])
        codes = [msg.get("code") for msg in messages if msg.get("code")]

        if codes:
            print(f"\n🎯 All Verification Codes Found:")
            for code in codes:
                print(f"  - {code}")
