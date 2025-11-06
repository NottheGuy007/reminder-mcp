FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY reminder_server.py .
COPY mcp_pipe.py .

ENV PYTHONUNBUFFERED=1

CMD ["python", "mcp_pipe.py"]
```

## File 5: `.env.example`
```
XIAOZHI_TOKEN=your_xiaozhi_token_here
MCP_SCRIPT=reminder_server.py
