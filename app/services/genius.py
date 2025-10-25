"""
Service module for interacting with Google's Gemini Generative AI API.
Includes Redis-based session persistence for context retention.
"""

import json
import re
from typing import Optional, Any, List
from config import settings
from google import genai
from google.genai.errors import APIError
from google.genai.chats import AsyncChat
from google.genai import types
from app.services.db import cache_service


# Initialize the Gemini Client globally
client = genai.Client(api_key=settings.GOOGLE_GEMINI_API_KEY)
async_client = client.aio

# Model used
MODEL_NAME: str = "gemini-2.5-flash-lite"

# System prompt template
SYSTEM_CONTEXT = """Generate a concise, easy-to-understand summary and then create
a 5-question multiple-choice quiz. Provide an answer key at the end.
\n\nTEXT:\n{extracted_text}"""

TTL_72_HOURS = 259200  # 3 days


# --- Helper Functions for History Serialization ---

def _serialize_history(history: List[types.Content]) -> List[dict]:
    """Convert a list of Gemini Content objects into JSON-serializable dicts."""
    serialized = []
    for content in history:
        try:
            serialized.append(json.loads(content.model_dump_json()))
        except AttributeError:
            serialized.append(json.loads(content.json()))
        except Exception as e:
            print(f"[ERROR] Failed to serialize content: {e}")
    return serialized


def _deserialize_history(history_dicts: List[dict]) -> List[types.Content]:
    """Convert a list of dicts back into Gemini Content objects."""
    if not history_dicts:
        return []
    deserialized = []
    for entry in history_dicts:
        if isinstance(entry, dict):
            deserialized.append(entry)
    return deserialized


# --- Core Service ---

class GeniusService:
    """
    Handles all interactions with Gemini API using Redis for persistent chat sessions.
    """

    async def get_or_create_chat_session(self, session_id: str, extracted_text: Optional[str] = None) -> AsyncChat:
        """
        Retrieves existing chat history from Redis or creates a new AsyncChat session.
        """
        try:
            history_dicts: Optional[Any] = await cache_service.get(session_id)
            initial_history: List[types.Content] = []
            chat_config: Optional[types.GenerateContentConfig] = None

            if history_dicts:
                try:
                    initial_history = _deserialize_history(history_dicts)
                    print(f"[INFO] Restored session {session_id} with {len(initial_history)} messages.")
                except Exception as e:
                    print(f"[WARN] Corrupted history for {session_id}, resetting. {e}")
                    await cache_service.delete(session_id)
                    initial_history = []

            if not initial_history:
                system_prompt = SYSTEM_CONTEXT.format(extracted_text=extracted_text or "")
                chat_config = types.GenerateContentConfig(system_instruction=system_prompt)
                print(f"[INFO] Created new chat session for {session_id}")

            chat: AsyncChat = async_client.chats.create(
                model=MODEL_NAME,
                history=initial_history,
                config=chat_config,
            )

            return chat

        except Exception as e:
            print(f"[ERROR] Failed to create or restore chat session: {e}")
            raise

    async def get_chat_response(self, session_id: str, message: str) -> str:
        """
        Sends user input to Gemini and stores updated history in Redis.
        """
        try:
            chat = await self.get_or_create_chat_session(session_id)

            # Send message
            response = await chat.send_message(message)

            # Update Redis with new history
            updated_history = chat.get_history()
            serialized = _serialize_history(updated_history)
            await cache_service.set(session_id, serialized, ttl_seconds=TTL_72_HOURS)
            print(f"[INFO] Saved session {session_id} with {len(updated_history)} messages.")

            # Extract text
            clean_text = self._extract_response_text(response)
            return clean_text

        except APIError as e:
            print(f"[API ERROR] Gemini request failed: {e}")
            return "⚠️ Gemini API request failed."
        except Exception as e:
            print(f"[ERROR] Gemini chat error: {e}")
            return f"Error: {e}"

    def _extract_response_text(self, response: Any) -> str:
        """
        Safely extract human-readable text from Gemini responses.
        """
        try:
            if hasattr(response, "text") and isinstance(response.text, str):
                return response.text.strip()

            elif hasattr(response, "candidates"):
                parts = []
                for candidate in response.candidates:
                    content = getattr(candidate, "content", None)
                    if content and hasattr(content, "parts"):
                        for part in content.parts:
                            if isinstance(part, dict):
                                text = part.get("text")
                                if text:
                                    parts.append(text)
                            elif hasattr(part, "text"):
                                parts.append(part.text)
                return "\n\n".join(parts).strip()

            return str(response)

        except Exception as e:
            print(f"[WARN] Failed to parse response: {e}")
            return str(response)

    async def generate_session_title(user_message: str, ai_response: str | None = None) -> str:
        """
        Generates a short, human-readable session title based on the first user message (and optionally AI response).
        """
        try:
            # Use the first sentence or keyword-like chunk
            text = user_message.strip()
            text = re.sub(r'[^\w\s]', '', text)  # remove punctuation
    
            if len(text.split()) <= 3:
                title = text.title()
            else:
                title = " ".join(text.split()[:5]).title()  # take first 5 words max
    
            if not title:
                title = "New Chat"
    
            # Optional enhancement: add emoji or prefix for personality
            # title = f"💬 {title}"
    
            return title[:60]  # safety truncate
    
        except Exception:
            return "Untitled Chat"


# Export singleton
genius_service = GeniusService()
