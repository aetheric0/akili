# app/services/gemini.py

"""
* Service module for interacting with Google's Gemini Generative AI API.
    - Now uses Redis to store and restore chat history for persistent
    sessions.
    - Encapsulates API calls and error handling logic.
"""

import json
import requests
from typing import Optional, Any
from config import settings

# GOOGLE GEN_AI IMPORTS
from google import genai
from google.genai.errors import APIError
from google.genai.chats import AsyncChat
from google.genai import types

# Import Cache Service (REDIS)
from app.services.db import cache_service

#Initialize the Gemini Client globally
client = genai.Client(api_key=settings.GOOGLE_GEMINI_API_KEY)
async_client = client.aio

# GEN_AI model
MODEL_NAME: str = "gemini-2.5-flash-lite"

# System Instruction/Context for AI model
system_context= """Generate a concise, easy-to-understand summary and then create
a 5-question multiple-choice quiz. Provide an answer key at the end.
\n\nTEXT:\n{extracted_text}"""


# --- Helper FUnctions for History Serialization ---

def _serialize_history(history: list[types.Content]) -> list[dict]:
    """
    Converts a list of Gemini Content objects into JSON-serializable dictionaries.
    """
    serialized_list = []
    for content in history:
        try:
            json_string = content.model_dump_json()
            serialized_list.append(json.loads(json_string))
        except AttributeError:
            try:
                # Fallback to Pydantic V1/older SDK
                json_string = content.json()
                serialized_list.append(json.loads(json_string))
            except Exception as e:
                # 3. If both fail, something is fundamentally wrong with the object structure
                print(f"Serialization Error: Content object failed both model_dump() and dict(): {e}")
                raise RuntimeError(f"Failed to deeply serialize Content object using Pydantic methods: {e}")
        except Exception as e:
            # Catch all other exceptions during serialization
            print(f"Serialization Error on content object: {e}")
            raise RuntimeError(f"Failed to deeply serialize Content object: {e}")
        
    return serialized_list
        

def _deserialize_history(history_dicts: list[dict]) -> list[types.Content]:
    """
    Converts a list of dictionaries back into Gemini Content objects.
    """
    deserialized_list = []
    for content_dict in history_dicts:
        try:
            deserialized_list.append(content_dict)
        except Exception as e:
            raise ValueError(f"Failed to deserialize dict {content_dict} into types.Content. Internal error: {e}") from e
    return deserialized_list
    
# --- Genius Service Implementation

class GeniusService:
    """ 
    Handles all interactions with the Gemini API, utilizing Redis for persistent
    chat sessions
    """

    async def get_or_create_chat_session(self, session_id: str) -> AsyncChat:
        """
        Retrieves an existing chat history from Redis and re-initializes the AsyncChat
        object, or creates a new session if no history is found.
        """
        # Attempt to retrieve history from Redis
        # cache_service.get returns a Python object (list of dicts) or None
        history_dicts: Optional[Any] = cache_service.get(session_id)

        initial_history: list[types.Content] = []
        chat_config: Optional[types.GenerateContentConfig] = None

        if history_dicts:
            try:
                # If found, deserialize the dicts back into types.Content objects
                initial_history = _deserialize_history(history_dicts)
                print(
                    "Restored chat session for ID: {} with "
                    "{} history parts.".format(session_id, len(initial_history))
                )
            except Exception as e:
                # Handle case where Redis data is corrupted or malformed
                print(
                    "⚠️  WARNING: Failed to deserialize chat history for "
                    "{}. Starting new session. Error: {}".format(session_id, e)
                )
                cache_service.delete(session_id)    # Clear bad cache entry
        if not initial_history:
            # Only apply the system_context on a brand new session.
            chat_config = types.GenerateContentConfig(
                system_instruction=system_context
            )
            print("Created new chat session for ID: {}".format(session_id))
        # Create chat session (either new or restored)
        # ⚠️  WARNING: Avoid mixing synchronous and asynchronous access to this
        # file to prevent race conditions and unpredictable behavior. Choose one
        # mode and use it consistently throughout the application. The base code
        # of this project uses asynchronous calls through Gemini's chat sessions'
        # genai.Client.aio()
        chat: AsyncChat = async_client.chats.create(
            model=MODEL_NAME,
            history=initial_history,
            config=chat_config
        )


        return chat

    async def get_chat_response(self, session_id: str, message: str) -> str:
        """
        Sends a message to the chat session, gets the model's response,
        and saves the *updated* history back to Redis.
        """
        try:
            # Get the session (or create/restore it)
            chat: AsyncChat = await self.get_or_create_chat_session(session_id)

            # Sends the message
            response = await chat.send_message(message)

            # Get the *updated* history after the model's response
            # The history now includes the user message and the model's response
            updated_history: list[types.Content] = chat.get_history()

            # Serialize and save the history back to Redis
            serialized_history = _serialize_history(updated_history)

            # TTL: 72 Hours
            TTL_72_HOURS = 259200
            cache_service.set(session_id, serialized_history, ttl_seconds=TTL_72_HOURS)

            print(
                "Saved {} history parts to Redis for {}.".format(
                    len(updated_history),
                    session_id
                )
            )

            return response.text

        except APIError as e:
            print("Gemini API Error: {}".format(e))
            return "Oops Akili encountered an error. Refresh and try again."

genius_service = GeniusService()

