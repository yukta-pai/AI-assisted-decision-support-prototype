FROM python:3.12-slim

# System dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies first (layer caching)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy project
COPY . .

# Generate synthetic dataset at build time
RUN python src/data_generator.py

# Streamlit config
RUN mkdir -p /root/.streamlit
RUN echo '[server]\nheadless = true\nport = 8501\nenableCORS = false\n[theme]\nbase = "dark"' \
    > /root/.streamlit/config.toml

EXPOSE 8501

HEALTHCHECK CMD curl --fail http://localhost:8501/_stcore/health || exit 1

CMD ["streamlit", "run", "app/main.py", "--server.address=0.0.0.0"]
