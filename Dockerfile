FROM python:3.12-slim

# Create user with UID 1000 (Hugging Face Spaces & cloud standards)
RUN useradd -m -u 1000 user
USER user
ENV HOME=/home/user \
    PATH=/home/user/.local/bin:$PATH

WORKDIR $HOME/app

# Install Python requirements
COPY --chown=user:user requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# Copy all project files (including pre-built frontend in app/frontend/out)
COPY --chown=user:user . .

ENV PORT=7860
EXPOSE 7860

CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-7860} --app-dir $HOME/app/app/backend"]
