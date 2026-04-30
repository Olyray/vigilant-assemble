FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
# Generate synthetic data if not present
RUN python data/generate_data.py || true
# Expose Railway's default app port plus legacy compatibility ports.
EXPOSE 8080 8000 8501
# Run MCP server by default; override with streamlit if needed
CMD ["python", "mcp_server.py"]
