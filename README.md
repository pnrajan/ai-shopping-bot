# Personal Shopper API

[![CI](https://github.com/pankajrajan/personal-shopper/actions/workflows/ci.yml/badge.svg)](https://github.com/pankajrajan/personal-shopper/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

> **Status: early skeleton.** The `/chat` endpoint currently validates and echoes requests. AI responses, product search, and storage are not implemented yet. See [Roadmap](#roadmap).

A FastAPI-based web service that provides an HTTP API for a personal shopping assistant. The service handles chat conversations where users can interact with an AI assistant to get shopping recommendations and product information.

## Features

- RESTful API for shopping assistant interactions
- Conversation history tracking
- Session management with unique conversation IDs
- Fully documented API endpoints
- Request/response validation with Pydantic

## Prerequisites

- Python 3.9+
- pip (Python package installer)

## Local Setup

### 1. Clone the Repository

```bash
git clone https://github.com/pankajrajan/personal-shopper.git
cd personal-shopper
```

### 2. Create Virtual Environment (Recommended)

```bash
# Create virtual environment
python -m venv venv

# Activate virtual environment
# On macOS/Linux:
source venv/bin/activate

# On Windows:
venv\Scripts\activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Run the Application

```bash
python main.py
```

The server will start and be available at `http://localhost:8000`

### 5. Access API Documentation

Once the server is running, you can access:

- **Interactive API docs (Swagger UI)**: http://localhost:8000/docs
- **Alternative API docs (ReDoc)**: http://localhost:8000/redoc
- **OpenAPI schema**: http://localhost:8000/openapi.json

## API Usage

### Chat Endpoint

**POST** `/chat`

Send a message to the personal shopping assistant.

#### Request Body

```json
{
  "recent_turn": "I'm looking for a new laptop for gaming",
  "history": [
    {
      "role": "user",
      "message": "Hello",
      "timestamp": "2023-01-01T10:00:00Z"
    },
    {
      "role": "assistant",
      "message": "Hi! How can I help you shop today?",
      "timestamp": "2023-01-01T10:00:01Z"
    }
  ],
  "conversation_id": "session-123"
}
```

#### Response

```json
{
  "message": "Chat request received",
  "conversation_id": "session-123",
  "recent_turn": "I'm looking for a new laptop for gaming",
  "history_length": 2
}
```

## Example Usage

For runnable examples, see the [`examples/`](./examples/) folder:

- [`examples/curl_examples.sh`](./examples/curl_examples.sh) - curl requests
- [`examples/python_client.py`](./examples/python_client.py) - Python client with multi-turn history

### Quick Start Examples

#### Using curl

```bash
# Start a new conversation
curl -X POST "http://localhost:8000/chat" \
  -H "Content-Type: application/json" \
  -d '{
    "recent_turn": "I need help finding a good smartphone under $500",
    "history": [],
    "conversation_id": "session-001"
  }'
```

#### Using Python requests

```python
import requests

# API endpoint
url = "http://localhost:8000/chat"

# Request payload
payload = {
    "recent_turn": "What are the best wireless headphones for working out?",
    "history": [
        {"role": "user", "message": "Hello"},
        {"role": "assistant", "message": "Hi! How can I help you shop today?"}
    ],
    "conversation_id": "session-456"
}

# Send request
response = requests.post(url, json=payload)
print(response.json())
```

#### Using JavaScript/fetch

```javascript
const response = await fetch('http://localhost:8000/chat', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
  },
  body: JSON.stringify({
    recent_turn: "I'm looking for a winter jacket under $200",
    history: [],
    conversation_id: "session-789"
  })
});

const data = await response.json();
console.log(data);
```

> **💡 Tip:** Run the examples in the `examples/` folder to see more detailed implementations and use cases.

## Development

### Project Structure

```
personal-shopper/
├── .github/workflows/ci.yml   # Lint + tests on push/PR
├── examples/                  # Runnable client examples
│   ├── curl_examples.sh
│   └── python_client.py
├── tests/                     # pytest suite
├── main.py                    # FastAPI application
├── pyproject.toml             # Project metadata, ruff/pytest config
├── requirements.txt           # Runtime dependencies
├── requirements-dev.txt       # Dev dependencies
└── README.md
```

### Running Tests

```bash
pip install -r requirements-dev.txt
ruff check .
pytest
```

### Adding New Dependencies

1. Add the package to `requirements.txt`
2. Install with: `pip install -r requirements.txt`

### Code Style

The codebase follows Python best practices with:
- Type hints for function parameters and return values
- Comprehensive docstrings for all classes and functions
- Pydantic models for request/response validation

## API Reference

### ChatRequest Model

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `recent_turn` | string | Yes | The most recent user message |
| `history` | array | Yes | List of previous conversation turns |
| `conversation_id` | string | Yes | Unique session identifier |

### Chat Response

| Field | Type | Description |
|-------|------|-------------|
| `message` | string | Confirmation message |
| `conversation_id` | string | Echo of the session ID |
| `recent_turn` | string | Echo of the user's message |
| `history_length` | integer | Number of previous turns |

## Troubleshooting

### Common Issues

1. **Port already in use**: If port 8000 is occupied, you can specify a different port:
   ```bash
   uvicorn main:app --host 0.0.0.0 --port 8001
   ```

2. **Module not found**: Make sure you've activated your virtual environment and installed dependencies:
   ```bash
   source venv/bin/activate  # or venv\Scripts\activate on Windows
   pip install -r requirements.txt
   ```

3. **Permission errors**: On some systems, you might need to use `python3` instead of `python`:
   ```bash
   python3 main.py
   ```

## Roadmap

Planned next steps. Track progress and discuss in GitHub Issues.

- [ ] Add LLMPlanner component
- [ ] Add Executor to execute on the Plan and hook it with the Orchestrator (to be implemented)
- [ ] Connect SessionStorage
- [ ] Implement Cache to save results for 24 hours in Search Index as recommended by providers
- [ ] Implement Task DB to store tasks for cron execution for curation

## Future Enhancements

This is a foundational implementation. Future versions will include:

- AI-powered response generation
- Product catalog integration
- Recommendation engine
- User preference tracking
- E-commerce platform APIs
- Authentication and authorization
- Rate limiting and security features

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). All participants are expected to follow the [Code of Conduct](CODE_OF_CONDUCT.md).

## License

[MIT](LICENSE) © Pankaj Rajan
