# Alternative to the Render blueprint: run anywhere that takes a container
# (Fly.io, Railway, a VPS, Google Cloud Run, etc.).
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY trello_mcp_server.py .

# Most hosts inject PORT; default to 8000 for plain `docker run`.
ENV PORT=8000
EXPOSE 8000

CMD ["python", "trello_mcp_server.py"]
