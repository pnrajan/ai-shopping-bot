"""Personal Shopper FastAPI Application.

This module implements a FastAPI-based web service that provides an HTTP API
for a personal shopping assistant. The service is designed to handle chat
conversations where users can interact with an AI assistant to get shopping
recommendations, product information, and purchasing advice.

The application exposes REST endpoints that accept conversation data including
user messages, conversation history, and session identifiers. This allows for
maintaining context across multiple interactions within a shopping session.

Typical Usage Example:
    To run the application:
        python main.py

    The server will start on http://0.0.0.0:8000

    To send a chat request:
        POST /chat
        {
            "recent_turn": "I'm looking for a new laptop",
            "history": [
                {"role": "user", "message": "Hello"},
                {"role": "assistant", "message": "Hi! How can I help you shop today?"}
            ],
            "conversation_id": "session-123"
        }

Dependencies:
    - FastAPI: Modern web framework for building APIs
    - Pydantic: Data validation using Python type annotations
    - Uvicorn: ASGI server for running the FastAPI application

Author:
    Pankaj Rajan

Version:
    1.0.0
"""

from typing import Any

from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI(
    title="Personal Shopper API",
    description="A FastAPI service for personal shopping assistance",
    version="1.0.0"
)

class ChatRequest(BaseModel):
    """Request model for chat endpoint interactions.

    This Pydantic model defines the structure of incoming chat requests to the
    personal shopping assistant API. It ensures proper validation of request
    data and provides clear documentation for API consumers.

    The model captures the essential components needed for a conversational
    shopping assistant: the current user message, conversation context, and
    session tracking information.

    Attributes:
        recent_turn (str): The most recent user message or query in the conversation.
            This is the current input that the assistant should respond to.

            Examples:
                - "I need a new laptop for gaming"
                - "What's the best price for iPhone 15?"
                - "Show me winter jackets under $100"

        history (list[dict[str, Any]]): A chronological list of previous conversation
            turns including both user messages and assistant responses. Each entry
            should contain relevant metadata such as role, message content, timestamp,
            or any other contextual information.

            Example structure:
                [
                    {"role": "user", "message": "Hello", "timestamp": "2023-01-01T10:00:00Z"},
                    {"role": "assistant", "message": "Hi! How can I help?",
                     "timestamp": "2023-01-01T10:00:01Z"},
                    {"role": "user", "message": "I need shoes", "timestamp": "2023-01-01T10:00:30Z"}
                ]

        conversation_id (str): A unique identifier for the conversation session.
            This allows the system to track and maintain context across multiple
            API calls within the same shopping session. Should be consistent
            throughout the entire conversation.

            Examples:
                - "session-abc123"
                - "user-456-conv-789"
                - "shopping-session-2023-09-14-001"

    Note:
        All fields are required. Empty strings or empty lists may be provided
        for new conversations, but the fields must be present in the request.

    Raises:
        ValidationError: If any field is missing or has an invalid type.
    """
    recent_turn: str
    history: list[dict[str, Any]]
    conversation_id: str

@app.post("/chat")
async def chat_endpoint(request: ChatRequest):
    """Process chat interactions with the personal shopping assistant.

    This endpoint serves as the main interface for users to communicate with
    the personal shopping assistant. It receives user messages along with
    conversation context and returns appropriate responses to help users
    with their shopping needs.

    The endpoint is designed to be stateless - all necessary context should
    be provided in the request payload. This allows for easy scaling and
    load balancing across multiple server instances.

    Currently, this is a basic implementation that acknowledges receipt of
    messages. In a production environment, this would integrate with:
    - Natural language processing services
    - Product catalog APIs
    - Recommendation engines
    - User preference systems

    Args:
        request (ChatRequest): A validated request object containing:
            - recent_turn: The user's current message or query
            - history: Previous conversation exchanges for context
            - conversation_id: Session identifier for tracking

    Returns:
        dict[str, Any]: A JSON response containing:
            - message (str): Acknowledgment that the request was received
            - conversation_id (str): Echo of the provided conversation ID
            - recent_turn (str): Echo of the user's current message
            - history_length (int): Number of previous conversation turns

    Example:
        Request:
            POST /chat
            {
                "recent_turn": "I need a new laptop for video editing",
                "history": [
                    {"role": "user", "message": "Hello"},
                    {"role": "assistant", "message": "Hi! How can I help you shop today?"}
                ],
                "conversation_id": "session-12345"
            }

        Response:
            {
                "message": "Chat request received",
                "conversation_id": "session-12345",
                "recent_turn": "I need a new laptop for video editing",
                "history_length": 2
            }

    Raises:
        HTTPException: May raise various HTTP exceptions for invalid requests:
            - 400 Bad Request: If request validation fails
            - 422 Unprocessable Entity: If request format is invalid
            - 500 Internal Server Error: If server processing fails

    Note:
        This endpoint currently serves as a foundation for development.
        Future versions will include AI-powered response generation,
        product recommendations, and integration with e-commerce platforms.
    """
    return {
        "message": "Chat request received",
        "conversation_id": request.conversation_id,
        "recent_turn": request.recent_turn,
        "history_length": len(request.history)
    }

def main() -> None:
    """Start the Personal Shopper API server.

    This function serves as the entry point for running the FastAPI application
    using Uvicorn as the ASGI server. It configures the server to listen on
    all available network interfaces (0.0.0.0) on port 8000.

    The server will automatically reload when code changes are detected in
    development mode. For production deployment, additional configuration
    should be considered such as:
    - Using a production ASGI server like Gunicorn with Uvicorn workers
    - Configuring SSL/TLS certificates
    - Setting up proper logging and monitoring
    - Implementing rate limiting and security headers

    Server Configuration:
        - Host: 0.0.0.0 (accepts connections from any IP address)
        - Port: 8000 (HTTP)
        - Reload: Disabled (for production use, enable for development)

    Returns:
        None

    Note:
        This function will block until the server is stopped (Ctrl+C).
        In production, consider using a process manager like systemd
        or Docker to manage the application lifecycle.
    """
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)


if __name__ == "__main__":
    main()