#!/usr/bin/env python3
"""
Fetch email verification codes using OAuth2 token via dongvanfb.net API
"""

import requests
import json

def fetch_mail_codes(email, refresh_token, client_id, mail_type="all"):
    """
    Fetch verification codes from email using OAuth2 token

    Args:
        email: Email address
        refresh_token: OAuth2 refresh token
        client_id: OAuth2 client ID
        mail_type: Type of codes to fetch (all, facebook, instagram, etc.)

    Returns:
        dict: API response containing codes
    """
    api_url = "https://tools.dongvanfb.net/api/get_code_oauth2"

    payload = {
        "email": email,
        "refresh_token": refresh_token,
        "client_id": client_id,
        "type": mail_type
    }

    try:
        print(f"🔍 Fetching {mail_type} codes for: {email}")
        print(f"📡 Calling API: {api_url}")

        response = requests.post(api_url, json=payload, timeout=30)

        print(f"📊 Status Code: {response.status_code}")

        if response.status_code == 200:
            data = response.json()
            print(f"✅ Success!")
            print(f"\n📧 Response Data:")
            print(json.dumps(data, indent=2, ensure_ascii=False))
            return data
        else:
            print(f"❌ Error: {response.status_code}")
            print(f"Response: {response.text}")
            return None

    except requests.exceptions.RequestException as e:
        print(f"❌ Request failed: {e}")
        return None

if __name__ == "__main__":
    # Credentials from user input
    EMAIL = "skyebettencourteaw1086@hotmail.com"
    REFRESH_TOKEN = "M.C521_BAY.0.U.-CtPwMqUZwogq2GKT6AxBVLI52H!tWLjEJFkAn0CfYm!swGHexo86*9aZ9GP0NKl9OVWZ4!c82DtLhALsgw7h2MuxI0dHCvCUGFLin9ZmzIaGI4NdQzsQW3VeoQoZRBR!WP1CjtMTh9*4sBTMH5PNv9N2HfkLh0ZnnHQwSKZOqXauHD8pzWlNm5PuSU*xEyvP588x5IDqulu46EaSdRV*jo1Ygp3HbF!BUaK3D7sWEWmH3*X*OPrkGpTUHow7AComWpkcjGQKOZJiWvhRZ!oY9o3IUEgksqHeatKT5KZpT0Q0FCIWATRFzGc6E!v!S*6RnvdueiY3aFgvN5HbFEZ9NUf1TKsO!n3kMENjChjgQYOuIOCgJVK9FkzOT6Fy11SWHA$$"
    CLIENT_ID = "9e5f94bc-e8a4-4e73-b8be-63364c29d753"
    TYPE = "all"

    result = fetch_mail_codes(EMAIL, REFRESH_TOKEN, CLIENT_ID, TYPE)

    if result and result.get("status"):
        print(f"\n🎯 Verification Code: {result.get('code')}")
        if result.get('content'):
            print(f"📝 Content: {result.get('content')}")
        if result.get('date'):
            print(f"📅 Date: {result.get('date')}")
