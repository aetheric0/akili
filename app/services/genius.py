# app/services/gemini.py

"""
Service module for interacting with Google's Gemini Generative AI API.
Encapsulates API calls and error handling logic.
"""

import json
import requests
from typing import Optional
from config import settings


def generate_content(prompt_text: str, model: str = "gemini-1.5-flash-latest") -> str:
    """
    Generate content using Google's Gemini API.

    Args:
        prompt_text (str): The text prompt to send to Gemini.
        model (str): The model to use. Defaults to "gemini-1.5-flash-latest".

    Returns:
        str: The generated text content, or an error message.
    """
    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{model}:generateContent?key={settings.GOOGLE_GEMINI_API_KEY}"
    )

    headers = {"Content-Type": "application/json"}
    data = {
        "contents": [{
            "parts": [{"text": prompt_text}]
        }]
    }

    try:
        response = requests.post(url, headers=headers, data=json.dumps(data), timeout=15)

        response.raise_for_status()  # raises HTTPError for 4xx/5xx
        result_json = response.json()

        return result_json['candidates'][0]['content']['parts'][0]['text']

    except requests.exceptions.Timeout:
        return "Error: Request to Gemini API timed out."

    except requests.exceptions.RequestException as e:
        return f"Error: Request failed - {str(e)}"

    except (KeyError, IndexError, ValueError):
        return "Error: Unexpected response format from Gemini API."
