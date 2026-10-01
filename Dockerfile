FROM public.ecr.aws/docker/library/python:3.12-slim
ARG INSTALL_CHROME=false

RUN if [ "$INSTALL_CHROME" = "true" ]; then \
      apt-get update && apt-get install -y --no-install-recommends chromium chromium-driver \
      && rm -rf /var/lib/apt/lists/*; \
    fi

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir torch==2.3.1 --index-url https://download.pytorch.org/whl/cpu \
 && pip install --no-cache-dir -r requirements.txt

# Bake the embedding model into a fixed cache directory inside the image.
ENV HF_HOME=/app/.cache/huggingface
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('BAAI/bge-small-en-v1.5')"

# Fail the build if the model was not actually saved to the cache directory.
RUN python -c "import pathlib; p = pathlib.Path('/app/.cache/huggingface'); assert any(p.rglob('*bge-small-en-v1.5*')), 'embedding model missing from image cache'"

# At runtime, never download: fail loudly if the model is missing from the image.
ENV HF_HUB_OFFLINE=1

COPY src/ ./src/
ENV PYTHONPATH=/app/src
CMD ["python", "-m", "rjp.main"]