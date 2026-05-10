"""
database/mongodb.py — MongoDB connection and data-access helpers
"""

from motor.motor_asyncio import AsyncIOMotorClient
from config.config import Config
from helpers.logger import LOGGER

log = LOGGER(__name__)


class MongoDB:
    def __init__(self):
        self.client: AsyncIOMotorClient = None
        self.db = None

    async def connect(self):
        self.client = AsyncIOMotorClient(Config.MONGO_DB_URI)
        self.db = self.client[Config.DATABASE_NAME]
        # Ping to verify connection
        await self.client.admin.command("ping")
        log.info(f"🍃 Connected to MongoDB database: {Config.DATABASE_NAME}")

    async def close(self):
        if self.client:
            self.client.close()

    # ── Settings (per-chat) ───────────────────────────────────────────────

    async def get_chat_settings(self, chat_id: int) -> dict:
        doc = await self.db.chat_settings.find_one({"chat_id": chat_id})
        return doc or {}

    async def update_chat_settings(self, chat_id: int, data: dict):
        await self.db.chat_settings.update_one(
            {"chat_id": chat_id},
            {"$set": data},
            upsert=True,
        )

    # ── Always-on / 24-7 ─────────────────────────────────────────────────

    async def get_always_on(self, chat_id: int) -> bool:
        doc = await self.get_chat_settings(chat_id)
        return doc.get("always_on", Config.ALWAYS_ON_DEFAULT)

    async def set_always_on(self, chat_id: int, value: bool):
        await self.update_chat_settings(chat_id, {"always_on": value})

    # ── Play history / stats ──────────────────────────────────────────────

    async def log_play(self, chat_id: int, user_id: int, title: str):
        await self.db.play_logs.insert_one(
            {"chat_id": chat_id, "user_id": user_id, "title": title}
        )

    async def get_global_play_count(self) -> int:
        return await self.db.play_logs.count_documents({})

    async def get_top_tracks(self, limit: int = 10) -> list:
        pipeline = [
            {"$group": {"_id": "$title", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}},
            {"$limit": limit},
        ]
        cursor = self.db.play_logs.aggregate(pipeline)
        return await cursor.to_list(length=limit)

    # ── Block / ban ───────────────────────────────────────────────────────

    async def is_banned_user(self, user_id: int) -> bool:
        doc = await self.db.banned_users.find_one({"user_id": user_id})
        return doc is not None

    async def ban_user(self, user_id: int):
        await self.db.banned_users.update_one(
            {"user_id": user_id}, {"$set": {"user_id": user_id}}, upsert=True
        )

    async def unban_user(self, user_id: int):
        await self.db.banned_users.delete_one({"user_id": user_id})

    # ── Served chats / users counters ─────────────────────────────────────

    async def add_served_chat(self, chat_id: int):
        await self.db.served_chats.update_one(
            {"chat_id": chat_id}, {"$set": {"chat_id": chat_id}}, upsert=True
        )

    async def get_served_chats_count(self) -> int:
        return await self.db.served_chats.count_documents({})

    async def add_served_user(self, user_id: int):
        await self.db.served_users.update_one(
            {"user_id": user_id}, {"$set": {"user_id": user_id}}, upsert=True
        )

    async def get_served_users_count(self) -> int:
        return await self.db.served_users.count_documents({})


# Will be initialized in core/bot.py
db: MongoDB = None
