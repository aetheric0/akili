# Akili AI Assistant

[![Profile Logo](https://i.postimg.cc/HxhdwkPg/Gemini-Generated-Image-73szv2>

Akili is an intelligent, dual-mode study companion designed to turn passive
reading into an active, gamified learning experience. It provides instant va>
through a familiar chat interface while offering powerful, specialized tools>
deep study.

## Main Technologies
- FastAPI
- Google Gemini Flash and Smart Models

## Dependencies
- Refer to the `requirements.txt` file

## Setup

### Option 1: Run Locally (Manual Setup)
Before running the app ensure you follow the instructions below to configure
your environment to run the app service.

### Environment Setup
- **PYDANTIC IS REQUIRED**, You should be fine if you install our
    requirements.txt file as it is included.
- Setup *Environment Variables* in a .env file:
    - APP_ENV: Set to development or production based on environment
    - APP_PORT
    - SUPABASE_URL: For real users authentication via email
    - SUPABASE_KEY: Secret key for email authentication
    - MAX_FILE_SIZE: Maximum file size that can be uploaded
    - REDIS_HOST: Your redis db URL
    - UI_HOST: The frontend client
    - PAYSTACK_SECRET_KEY: For Paystack payment integration
    - GOOGLE_GEMINI_API_KEY: API Key for AI model access

#### Local Run Commands
```bash
# Clone repository
git clone https://github.com/yourusername/akili-ai-assistant.git
cd akili-ai-assistant

# Create virtual environment
python -m venv venv
source venv/bin/activate  # (Windows: venv\Scripts\activate)

# Install dependencies
pip install -r requirements.txt

# Run the app
uvicorn app.main:app --reload --port 8000
```
### Option 2: Run with Docker (Recommended for Easy Setup)
 > 🔒 **Private Access**: Contact the maintainer to be added to the Docker registry
    for access to the private image.
