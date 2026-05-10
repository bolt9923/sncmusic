"""
generate_session.py — Interactive Pyrogram string session generator
Run: python3 generate_session.py
"""

import asyncio
import sys

try:
    from pyrogram import Client
except ImportError:
    print("❌ Pyrogram is not installed. Run: pip install pyrogram TgCrypto")
    sys.exit(1)


async def generate():
    print("=" * 50)
    print("  TuneBot — String Session Generator")
    print("=" * 50)
    print("\nThis tool generates a Pyrogram string session")
    print("for your assistant account (NOT the bot account).\n")

    api_id = input("Enter your API_ID: ").strip()
    api_hash = input("Enter your API_HASH: ").strip()

    if not api_id.isdigit():
        print("❌ API_ID must be a number.")
        return

    print("\n📲 A login code will be sent to your Telegram account.")
    print("   Enter the phone number with country code (e.g. +1234567890)\n")

    async with Client(
        "session_generator",
        api_id=int(api_id),
        api_hash=api_hash,
    ) as app:
        session = await app.export_session_string()

    print("\n" + "=" * 50)
    print("✅  Your String Session:")
    print("=" * 50)
    print(session)
    print("=" * 50)
    print("\n⚠️  Keep this session string SECRET.")
    print("   Anyone with it can access your Telegram account.")
    print("\n📋  Add it to STRING_SESSIONS in your .env file.")


if __name__ == "__main__":
    asyncio.run(generate())
