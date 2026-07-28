# --- Base image: a lightweight Python 3.12 environment ---
# "slim" means it's a smaller version of the official image (less bloat,
# faster builds/downloads) but still has everything Python needs.
FROM python:3.12-slim

# --- System-level dependencies ---
# OpenCV and MediaPipe need a few OS libraries (for image/video codecs and
# graphics) that aren't installed in the slim image by default.
# Without these, "import cv2" or "import mediapipe" would crash inside the container.
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender1 \
    && rm -rf /var/lib/apt/lists/*

# --- Set the working directory inside the container ---
# All following commands (COPY, RUN, CMD) run relative to this folder.
WORKDIR /app

# --- Install Python dependencies FIRST, before copying the rest of the code ---
# This is a deliberate ordering trick: Docker caches each step. If only your
# code changes (not requirements.txt), Docker reuses the cached "pip install"
# layer instead of redoing it — much faster rebuilds.
COPY requirements.txt .
RUN pip install --no-cache-dir --retries 10 --timeout 100 -r requirements.txt

# --- Now copy the rest of the project files into the container ---
COPY . .

# --- Document which port the app listens on ---
# This doesn't actually publish the port (that happens with `docker run -p`),
# it's just metadata/documentation for anyone reading this file.
EXPOSE 5000

# --- The command that runs when the container starts ---
# Uses gunicorn (production server) instead of Flask's dev server.
# IMPORTANT: explicitly wrapped in `sh -c` so $PORT always gets substituted
# by a real shell at runtime. Platforms like Railway/Render assign their own
# dynamic port via the PORT environment variable - without this, $PORT can
# end up passed as a literal, un-substituted string, causing a crash.
CMD ["sh", "-c", "gunicorn app:app --bind 0.0.0.0:${PORT:-5000} --workers 1 --threads 4 --timeout 120"]