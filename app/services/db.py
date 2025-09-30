import redis
import json
from typing import Any, Optional
from config import settings

"""
* Initialize Redis Client and Defines CacheService data structure
    - Reads connection details from environment variables (REDIS_HOST,
    REDIS_PORT).
    - decode_responses=True means Redis will return strings instead of
    bytes for key/values.
    - This is generally convenient but requires careful JSON error
    handling.
"""

REDIS_CLIENT = redis.Redis.from_url(
    settings.REDIS_HOST,
    decode_responses=True
)

# Simple check to ensure connection on startup
try:
    REDIS_CLIENT.ping()
    print("Successfully connected to Redis at: {}".format(
            settings.REDIS_HOST,
        ))
except redis.exceptions.ConnectionError as e:
    print("ERROR: Could not connect to Redis at {}: {}".format(
            settings.REDIS_HOST, e
        ))


class CacheService:
    """
    A service class to abstract Redis caching operations, handling
    automatic JSON serialization and deserialization for complex
    Python objects (dicts, lists).
    """
    def __init__(self, client: redis.Redis):
        self.client = client

    def get(self, key):
        """
        Retrieves a value from Redis and deserializes it from JSON.
        Returns the Python object if found, or None if key is missing
        or corrupted.
        """
        try:
            # client.get() returns a string because decode_responses=True
            cached_value_str: Optional[str] = self.client.get(key)

            if cached_value_str is None:
                # Cache miss
                print("REDIS: Cache Miss!")
                return None

            # Attempt to deserialize the JSON string back into a Python object
            data: Any = json.loads(cached_value_str)
            return data
        except redis.exceptions.RedisError as e:
            print("Redis operational error for key {}: {}".format(key, e))
        except json.JSONDecodeError as e:
            # Handles cases where the data stored is not valid JSON
            # (e.g., manually stored plain string or corrupted data).
            print(
                "Cache data corruption for key {}."
                " Failed to deserialize JSON: {}".format(key, e)
            )
            return None

    def set(self, key, value, ttl_seconds):
        """
        Serializes a Python object to JSON and stores it in Redis with an
        expiration (TTL). Uses 'EX' argument for expiration (equivalent 
        to SETEX command).
        """
        if ttl_seconds <= 0:
            print("TTL must be a positive integer.")
            return
        try:
            # Serializes the Python object (dict, list, etc.) into a JSON string
            json_string: str = json.dumps(value)

            # Stores the string. 'ex' sets the TTL in seconds
            # The client handles encoding the string to bytes before sending to Redis
            self.client.set(key, json_string, ex=ttl_seconds)

        except redis.exceptions.RedisError as e:
            print(
                "Redis operational error while setting key {}: {}".format(key,e)
            )

    def delete(self, key: str) -> int:
        """
        Deletes a key from Redis.
        Returns the number of keys removed (0 or 1).
        """
        try:
            return self.client.delete(key)
        except redis.exceptions.RedisError as e:
            print(
                "Redis operational error while deleting key {}: {}".format(key, e)
            )
            return 0

# Instantiate the service for use in application layer
cache_service = CacheService(REDIS_CLIENT)
