from fastapi import APIRouter
from app.models.chat_models import ChatRequest, ChatResponse
from app.services.genius import genius_service

router = APIRouter(
    prefix="/chat",
    tags=["chat"],
)


@router.post("/", response_model=ChatResponse)
async def continue_chat(request: ChatRequest):
    """
    Endpoint to send a message and continue an ongoing
    conversation
    """
    # Call to the service layer to get the response
    ai_response = await genius_service.get_chat_response(
        session_id=request.session_id,
        message=request.message
    )

    # Return the structured response
    return ChatResponse(
        session_id = request.session_id,
        response=ai_response
    )
