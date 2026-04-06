FROM nvidia/cuda:12.0.0-cudnn8-devel-ubuntu22.04

# Core dependencies for Python and basic libraries
RUN apt-get update && apt-get install -y --no-install-recommends \
    wget git curl libglib2.0-0 libsm6 libxext6 libxrender-dev ffmpeg \
    python3.10 python3.10-venv python3-pip python3.10-dev build-essential \
    && rm -rf /var/lib/apt/lists/*

# Setup virtual environment
RUN python3.10 -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

WORKDIR /app

# Install standard dependencies and torch
COPY requirements.txt /app/
RUN pip install --no-cache-dir --upgrade pip setuptools wheel
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install torch==2.5.0 torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121
RUN pip install ninja psutil packaging
RUN pip install flash_attn==2.8.0.post2 --no-build-isolation

# For production, clone VITA-EPFL SVI repo and setup
RUN git clone --depth=1 https://github.com/vita-epfl/Stable-Video-Infinity /app/svi
RUN cd /app/svi && pip install setuptools==69.5.1 && pip install -e . --no-build-isolation

# Add handler script
COPY handler.py /app/handler.py

CMD ["python", "-u", "/app/handler.py"]
# trigger action
