FROM python:3.12-slim

WORKDIR /app

# Install python deps
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# Copy source
COPY src /app/src
# Default command (compose will override ports/env per node)
CMD ["python", "-m", "uvicorn", "src.node.server:app", "--host", "0.0.0.0", "--port", "8001"]
