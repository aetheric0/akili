# app/services/gemini.py

"""
Service module for interacting with Google's Gemini Generative AI API.
- Creates a chat session.
- Encapsulates API calls and error handling logic.
"""

import json
import requests
from typing import Optional
from config import settings

from google import genai
from google.genai.errors import APIError
from google.genai.chats import Chat
from google.genai import types

#Initialize the Gemini Client globally
client = genai.Client(api_key=settings.GOOGLE_GEMINI_API_KEY)
async_client = client.aio

# ⚠️  IN-MEMORY STORAGE (NOT FOR PRODUCTION!) ⚠️
# Remember to use Redis or a database in production for dedicated
# session service to store the history and make it available
# across multiple running server processes.

_CHAT_SESSIONS: dict[str, Chat] = {}
MODEL_NAME: str = "gemini-2.5-flash-lite"

# System Instruction/Context for AI model
system_context= """Generate a concise, easy-to-understand summary and then create
a 5-question multiple-choice quiz. Provide an answer key at the end.
\n\nTEXT:\n{extracted_text}"""


class GeniusService:
    """ 
    Handles all interactions with the Gemini API.
    """

    def get_or_create_chat_session(self, session_id: str) -> Chat:
        """
        Retrieves an existing chat session or creates a new one.
        """
        if session_id not in _CHAT_SESSIONS:
            # Start a new chat session using the model
            chat = async_client.chats.create(
                model=MODEL_NAME,
                config=types.GenerateContentConfig(
                    system_instruction=system_context
                )
            )
            _CHAT_SESSIONS[session_id] = chat
            print("Created new chat session for ID: {}".format(session_id))
            return chat

        return _CHAT_SESSIONS[session_id]

    async def get_chat_response(self, session_id: str, message: str) -> str:
        """
        Sends a message to the chat session and returns the model's response.
        The ChatSession object automatically includes the history.
        """
        try:
            # Get the session (or create it if it's the first message)
            chat = self.get_or_create_chat_session(session_id)

            # Use sendMessaage() which automatically manages the context
            response = await chat.send_message(message)

            # Optional: Add context window management here (truncation, summarization)

            return response.text

        except APIError as e:
            print("Gemini API Error: {}".format(e))
            return "Oops Akili encountered an error. Refresh and try again."

genius_service = GeniusService()

