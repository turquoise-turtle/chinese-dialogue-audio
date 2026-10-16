# Used by Hugging Face Spaces (Docker SDK). Render uses render.yaml instead.
FROM python:3.14-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=7860

# Spaces run containers as uid 1000.
RUN useradd --create-home --uid 1000 user
WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY --chown=user . .
USER user

EXPOSE 7860
CMD ["gunicorn", "app:app"]
