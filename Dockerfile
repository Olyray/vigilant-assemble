FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
# Generate synthetic data if not present
RUN python data/generate_data.py || true
# Expose Streamlit (8501) and MCP Server (8000)
EXPOSE 8501 8000
# Run MCP server by default; override with streamlit if needed
CMD ["python", "mcp_server.py"]
