# app/services/db.py
#!/usr/bin/env python3
"""
Redis CacheService for Akili Study.

Provides:
- JSON-safe get/set
- TTL utilities (expire/persist)
- Policy-aware set_with_policy (free => 7d TTL, paid => persistent)
- Hash/Set helpers
- Session helpers (add/remove/count/list)
- Subscription helpers (set/get, is_active)
"""

import redis
import json
from typing import Any, Optional, List, Dict
from datetime import datetime, timedelta
from config import settings

REDIS_CLIENT = redis.Redis.from_url(
    settings.REDIS_HOST,
    decode_responses=True
)

# Quick connection check
try:
    REDIS_CLIENT.ping()
    print(f"✅ Connected to Redis at {settings.REDIS_HOST}")
except redis.exceptions.ConnectionError as e:
    print(f"❌ Could not connect to Redis at {settings.REDIS_HOST}: {e}")


class CacheService:
    def __init__(self, client: redis.Redis):
        self.client = client

    # ---------- Core JSON get/set ----------
    def get(self, key: str) -> Optional[Any]:
        """Return parsed JSON object or None."""
        try:
            raw = self.client.get(key)
            if raw is None:
                return None
            # raw is a string because decode_responses=True
            return json.loads(raw)
        except (redis.exceptions.RedisError, json.JSONDecodeError) as e:
            print(f"[Redis:get] Error for key {key}: {e}")
            return None

    def set(self, key: str, value: Any, ttl_seconds: Optional[int] = None) -> bool:
        """
        Set key to JSON-serialized value.
        ttl_seconds: optional TTL in seconds. If None -> no TTL.
        """
        try:
            payload = json.dumps(value)
            if ttl_seconds is not None:
                self.client.set(key, payload, ex=int(ttl_seconds))
            else:
                self.client.set(key, payload)
            return True
        except redis.exceptions.RedisError as e:
            print(f"[Redis:set] Error setting key {key}: {e}")
            return False

    # ---------- TTL utilities ----------
    def expire(self, key: str, ttl_seconds: int) -> bool:
        """Apply expiration (TTL) to an existing key."""
        try:
            return self.client.expire(key, int(ttl_seconds))
        except redis.exceptions.RedisError as e:
            print(f"[Redis:expire] Error applying TTL to {key}: {e}")
            return False

    def persist(self, key: str) -> bool:
        """Remove TTL from a key (make it persistent)."""
        try:
            return self.client.persist(key)
        except redis.exceptions.RedisError as e:
            print(f"[Redis:persist] Error removing TTL on {key}: {e}")
            return False

    def ttl(self, key: str) -> int:
        """Return TTL in seconds (-1 if persistent, -2 if not exists)."""
        try:
            return self.client.ttl(key)
        except redis.exceptions.RedisError as e:
            print(f"[Redis:ttl] Error reading TTL for {key}: {e}")
            return -2

    # ---------- Policy-aware setter ----------
    def set_with_policy(self, key: str, value: Any, tier: str) -> bool:
        """
        Set a key according to tier policy:
          - tier == "free" -> 7 days TTL
          - tier == "paid" -> persistent (no TTL)
          - any other -> treat as free
        NOTE: expired paid users are handled by application logic; if you
        want to preserve their history, treat them as "paid" here.
        """
        try:
            if tier == "paid":
                # Save permanently
                return self.set(key, value, ttl_seconds=None)
            else:
                # Free (or default) -> 7 days
                seven_days = 7 * 24 * 3600
                return self.set(key, value, ttl_seconds=seven_days)
        except Exception as e:
            print(f"[Redis:policy] Error setting {key} with tier {tier}: {e}")
            return False

    # ---------- Hash helpers ----------
    def hset(self, key: str, mapping: Dict[str, Any]) -> bool:
        """Set multiple fields in a hash. Serializes values to strings."""
        try:
            # Redis hset expects mapping of field->value as strings
            flat = {k: (v if isinstance(v, str) else json.dumps(v)) for k, v in mapping.items()}
            self.client.hset(key, mapping=flat)
            return True
        except redis.exceptions.RedisError as e:
            print(f"[Redis:hset] Error on {key}: {e}")
            return False

    def hgetall(self, key: str) -> Dict[str, str]:
        """Return all fields from a hash (strings)."""
        try:
            return self.client.hgetall(key) or {}
        except redis.exceptions.RedisError as e:
            print(f"[Redis:hgetall] Error on {key}: {e}")
            return {}

    def hget(self, key: str, field: str) -> Optional[str]:
        try:
            return self.client.hget(key, field)
        except redis.exceptions.RedisError as e:
            print(f"[Redis:hget] Error on {key}:{field}: {e}")
            return None

    # ---------- Set helpers ----------
    def sadd(self, key: str, value: str) -> int:
        try:
            return int(self.client.sadd(key, value))
        except redis.exceptions.RedisError as e:
            print(f"[Redis:sadd] Error on {key}: {e}")
            return 0

    def srem(self, key: str, value: str) -> int:
        try:
            return int(self.client.srem(key, value))
        except redis.exceptions.RedisError as e:
            print(f"[Redis:srem] Error on {key}: {e}")
            return 0

    def smembers(self, key: str) -> set:
        try:
            return set(self.client.smembers(key) or set())
        except redis.exceptions.RedisError as e:
            print(f"[Redis:smembers] Error on {key}: {e}")
            return set()

    def scard(self, key: str) -> int:
        try:
            return int(self.client.scard(key))
        except redis.exceptions.RedisError as e:
            print(f"[Redis:scard] Error on {key}: {e}")
            return 0

    # ---------- Generic ----------
    def delete(self, key: str) -> int:
        try:
            return int(self.client.delete(key))
        except redis.exceptions.RedisError as e:
            print(f"[Redis:delete] Error deleting {key}: {e}")
            return 0

    def exists(self, key: str) -> bool:
        try:
            return self.client.exists(key) == 1
        except redis.exceptions.RedisError as e:
            print(f"[Redis:exists] Error checking {key}: {e}")
            return False

    # ---------- Session & User helpers ----------
    def add_session_for_user(self, user_id: str, session_id: str, session_data: Optional[Dict[str, Any]] = None, tier: str = "free") -> bool:
        """
        Add session id to user's session set and (optionally) store session_data.
        session_data will be stored at key 'session:{session_id}' and policy applied.
        """
        session_key = f"session:{session_id}"
        user_sessions_key = f"user:{user_id}:sessions"

        if session_data is not None:
            ok = self.set_with_policy(session_key, session_data, tier=tier)
            if not ok:
                print(f"[CacheService] Warning: failed to write session data for {session_id}")
        self.sadd(user_sessions_key, session_id)
        return True

    def remove_session_for_user(self, user_id: str, session_id: str) -> bool:
        """Remove session id from user's set and delete session key."""
        session_key = f"session:{session_id}"
        user_sessions_key = f"user:{user_id}:sessions"
        self.srem(user_sessions_key, session_id)
        self.delete(session_key)
        return True

    def count_user_sessions(self, user_id: str) -> int:
        """Return number of active sessions tracked for a user."""
        return self.scard(f"user:{user_id}:sessions")

    def list_user_sessions(self, user_id: str) -> List[str]:
        """Return list of session IDs for a user."""
        return list(self.smembers(f"user:{user_id}:sessions"))

    # ---------- Subscription helpers ----------
    def set_user_subscription(self, user_id: str, tier: str = "paid", expiry_date: Optional[datetime] = None) -> bool:
        """
        Save subscription data under token:{guest_token}.
        expiry_date: datetime or None (if None and tier=='paid', you can choose to set a long expiry)
        """
        key = f"user:{user_id}"
        payload: Dict[str, str] = {"tier": tier}
        if expiry_date:
            payload["expiry_date"] = expiry_date.isoformat()
        payload["paid"] = "true" if tier == "paid" else "false"
        return self.hset(key, payload)

    def get_user_subscription(self, user_id: str) -> Dict[str, str]:
        return self.hgetall(f"user:{user_id}")

    def is_subscription_active(self, user_id: str) -> bool:
        """
        Returns True if the user has tier == 'paid' and expiry_date is in the future (or not provided).
        The application layer can implement grace periods; we keep this simple here.
        """
        data = self.get_user_subscription(user_id)
        if not data:
            return False
        tier = data.get("tier")
        if tier != "paid":
            return False
        expiry = data.get("expiry_date")
        if not expiry:
            # treat as active if expiry not set (e.g., long-lived paid account)
            return True
        try:
            expiry_dt = datetime.fromisoformat(expiry)
        except Exception:
            return False
        return datetime.utcnow() <= expiry_dt

    def set_user_profile(self, user_id: str, profile_data: Dict[str, Any]) -> bool:
        return self.hset(f"user_stats:{user_id}", profile_data)

    def get_user_profile(self, user_id: str) -> Dict[str, str]:
        return self.hgetall(f"user_stats:{user_id}")


    # ---------- Bulk helpers ----------
    def persist_user_sessions(self, user_id: str) -> None:
        """Remove TTL for all sessions of a user (make them permanent)."""
        sessions = self.smembers(f"user:{user_id}:sessions")
        for s in sessions:
            self.persist(f"session:{s}")

    def expire_user_sessions(self, user_id: str, ttl_seconds: int) -> None:
        """Apply TTL to all sessions of a user (useful to enforce expiry policy)."""
        sessions = self.smembers(f"user:{user_id}:sessions")
        for s in sessions:
            self.expire(f"session:{s}", ttl_seconds)


# Instantiate the cache service for app usage
cache_service = CacheService(REDIS_CLIENT)
