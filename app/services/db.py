# app/services/db.py

import redis.asyncio as redis # <-- Import the asyncio version of redis
import json
from typing import Any, Optional, List, Dict
from datetime import datetime, timedelta
from config import settings

# --- Initialize the Async Client ---
REDIS_CLIENT = redis.Redis.from_url(
    settings.REDIS_HOST,
    decode_responses=True
)

# Note: The global .ping() is removed as it would need to be awaited
# in an async context, which doesn't exist here.
# The service will check the connection on its first call.
print(f"✅ Redis Async Client configured for {settings.REDIS_HOST}")


class CacheService:
    def __init__(self, client: redis.Redis):
        self.client = client

    # ---------- Core JSON get/set ----------
    async def get(self, key: str) -> Optional[Any]:
        """Return parsed JSON object or None."""
        try:
            raw = await self.client.get(key) # <-- await
            if raw is None:
                return None
            return json.loads(raw)
        except (redis.exceptions.RedisError, json.JSONDecodeError) as e:
            print(f"[Redis:get] Error for key {key}: {e}")
            return None

    async def set(self, key: str, value: Any, ttl_seconds: Optional[int] = None) -> bool:
        """Set key to JSON-serialized value."""
        try:
            payload = json.dumps(value)
            if ttl_seconds is not None:
                await self.client.set(key, payload, ex=int(ttl_seconds)) # <-- await
            else:
                await self.client.set(key, payload) # <-- await
            return True
        except redis.exceptions.RedisError as e:
            print(f"[Redis:set] Error setting key {key}: {e}")
            return False

    # ---------- TTL utilities ----------
    async def expire(self, key: str, ttl_seconds: int) -> bool:
        try:
            return await self.client.expire(key, int(ttl_seconds)) # <-- await
        except redis.exceptions.RedisError as e:
            print(f"[Redis:expire] Error applying TTL to {key}: {e}")
            return False

    async def persist(self, key: str) -> bool:
        try:
            return await self.client.persist(key) # <-- await
        except redis.exceptions.RedisError as e:
            print(f"[Redis:persist] Error removing TTL on {key}: {e}")
            return False

    async def ttl(self, key: str) -> int:
        try:
            return await self.client.ttl(key) # <-- await
        except redis.exceptions.RedisError as e:
            print(f"[Redis:ttl] Error reading TTL for {key}: {e}")
            return -2

    # ---------- Policy-aware setter ----------
    async def set_with_policy(self, key: str, value: Any, tier: str) -> bool:
        try:
            if tier == "paid":
                return await self.set(key, value, ttl_seconds=None) # <-- await
            else:
                seven_days = 7 * 24 * 3600
                return await self.set(key, value, ttl_seconds=seven_days) # <-- await
        except Exception as e:
            print(f"[Redis:policy] Error setting {key} with tier {tier}: {e}")
            return False

    # ---------- Hash helpers ----------
    async def hset(self, key: str, mapping: Dict[str, Any]) -> bool:
        try:
            flat = {k: (v if isinstance(v, (str, int, float, bool)) else json.dumps(v)) for k, v in mapping.items()}
            await self.client.hset(key, mapping=flat) # <-- await
            return True
        except redis.exceptions.RedisError as e:
            print(f"[Redis:hset] Error on {key}: {e}")
            return False

    async def hgetall(self, key: str) -> Dict[str, str]:
        try:
            return await self.client.hgetall(key) or {} # <-- await
        except redis.exceptions.RedisError as e:
            print(f"[Redis:hgetall] Error on {key}: {e}")
            return {}

    async def hget(self, key: str, field: str) -> Optional[str]:
        try:
            return await self.client.hget(key, field) # <-- await
        except redis.exceptions.RedisError as e:
            print(f"[Redis:hget] Error on {key}:{field}: {e}")
            return None

    # ---------- Set helpers ----------
    async def sadd(self, key: str, *values: str) -> int:
        try:
            return int(await self.client.sadd(key, *values)) # <-- await
        except redis.exceptions.RedisError as e:
            print(f"[Redis:sadd] Error on {key}: {e}")
            return 0

    async def srem(self, key: str, value: str) -> int:
        try:
            return int(await self.client.srem(key, value)) # <-- await
        except redis.exceptions.RedisError as e:
            print(f"[Redis:srem] Error on {key}: {e}")
            return 0

    async def smembers(self, key: str) -> set:
        try:
            return set(await self.client.smembers(key) or set()) # <-- await
        except redis.exceptions.RedisError as e:
            print(f"[Redis:smembers] Error on {key}: {e}")
            return set()

    async def scard(self, key: str) -> int:
        try:
            return int(await self.client.scard(key)) # <-- await
        except redis.exceptions.RedisError as e:
            print(f"[Redis:scard] Error on {key}: {e}")
            return 0

    # ---------- Generic ----------
    async def delete(self, *keys: str) -> int:
        try:
            return int(await self.client.delete(*keys)) if keys else 0 # <-- await
        except redis.exceptions.RedisError as e:
            print(f"[Redis:delete] Error deleting keys: {e}")
            return 0

    async def exists(self, key: str) -> bool:
        try:
            return await self.client.exists(key) == 1 # <-- await
        except redis.exceptions.RedisError as e:
            print(f"[Redis:exists] Error checking {key}: {e}")
            return False

    async def sismember(self, key: str, value: str) -> bool:
            """Check if a value is a member of a set."""
            try:
                return await self.client.sismember(key, value)
            except redis.exceptions.RedisError as e:
                print(f"[Redis:sismember] Error on {key}: {e}")
                return False

    # ---------- Session & User helpers ----------
    async def add_session_for_user(self, user_id: str, session_id: str, session_data: Dict[str, Any], tier: str) -> bool:
        session_key = f"session:{session_id}"
        user_sessions_key = f"user:{user_id}:sessions"

        # Use a pipeline for atomicity
        pipe = self.client.pipeline()
        
        # Manually serialize data for the pipeline
        payload = json.dumps(session_data)
        if tier == "paid":
            pipe.set(session_key, payload, ex=None)
        else:
            pipe.set(session_key, payload, ex=int(timedelta(days=7).total_seconds()))
        
        pipe.sadd(user_sessions_key, session_id)
        
        try:
            await pipe.execute() # <-- await pipeline
            return True
        except redis.exceptions.RedisError as e:
            print(f"[CacheService] Error in add_session_for_user pipeline: {e}")
            return False

    async def remove_session_for_user(self, user_id: str, session_id: str) -> bool:
        session_key = f"session:{session_id}"
        user_sessions_key = f"user:{user_id}:sessions"
        
        pipe = self.client.pipeline()
        pipe.srem(user_sessions_key, session_id)
        pipe.delete(session_key)
        
        try:
            await pipe.execute() # <-- await pipeline
            return True
        except redis.exceptions.RedisError as e:
            return False

    async def list_user_sessions(self, user_id: str) -> List[str]:
        return list(await self.smembers(f"user:{user_id}:sessions")) # <-- await

    # ---------- Subscription helpers ----------
    async def set_user_profile(self, user_id: str, profile_data: Dict[str, Any]) -> bool:
        return await self.hset(f"user_stats:{user_id}", profile_data) # <-- await

    async def get_user_profile(self, user_id: str) -> Dict[str, str]:
        return await self.hgetall(f"user_stats:{user_id}") # <-- await

    # ---------- Bulk helpers ----------
    async def persist_user_sessions(self, user_id: str) -> None:
        sessions = await self.smembers(f"user:{user_id}:sessions") # <-- await
        pipe = self.client.pipeline()
        for s in sessions:
            pipe.persist(f"session:{s}")
        await pipe.execute() # <-- await

    async def expire_user_sessions(self, user_id: str, ttl_seconds: int) -> None:
        sessions = await self.smembers(f"user:{user_id}:sessions") # <-- await
        pipe = self.client.pipeline()
        for s in sessions:
            pipe.expire(f"session:{s}", ttl_seconds)
        await pipe.execute() # <-- await


# Instantiate the cache service for app usage
cache_service = CacheService(REDIS_CLIENT)

