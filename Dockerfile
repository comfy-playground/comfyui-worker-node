FROM pytorch/pytorch:2.5.1-cuda12.4-cudnn9-runtime

ENV DEBIAN_FRONTEND=noninteractive
ENV PIP_NO_CACHE_DIR=1

# System dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    aria2 \
    git \
    wget \
    curl \
    build-essential \
    g++ \
    libgl1 \
    libglib2.0-0 \
    libsm6 \
    libxrender1 \
    libxext6 \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Install ComfyUI
WORKDIR /app
ARG COMFYUI_REF=6f7cd7fceaaf60d2669b554936394a7412c6fde5
RUN git clone https://github.com/comfyanonymous/ComfyUI.git /app/ComfyUI && \
    cd /app/ComfyUI && \
    git checkout "${COMFYUI_REF}"

WORKDIR /app/ComfyUI
RUN pip install -r requirements.txt

# Install custom nodes

# Gateway-owned deterministic multi-seed noise node. This remains a small,
# dependency-free custom node so ComfyUI core stays unmodified.
COPY custom_nodes/ComfyUI-Gateway-Batch \
    /app/ComfyUI/custom_nodes/ComfyUI-Gateway-Batch

# 1. ControlNet Auxiliary Preprocessors (OpenPose etc.)
RUN git clone https://github.com/Fannovel16/comfyui_controlnet_aux.git \
    /app/ComfyUI/custom_nodes/comfyui_controlnet_aux && \
    cd /app/ComfyUI/custom_nodes/comfyui_controlnet_aux && \
    pip install -r requirements.txt

# 2. IP-Adapter Plus
RUN git clone https://github.com/cubiq/ComfyUI_IPAdapter_plus.git \
    /app/ComfyUI/custom_nodes/ComfyUI_IPAdapter_plus

# 3. LoRA Manager (dynamic multi-LoRA stack used by AstrBot)
ARG COMFYUI_LORA_MANAGER_REF=186ef4da786a039ee2a429508c93f5bffaedf1e3
COPY patches/comfyui-lora-manager-aria2-resume-queue.patch /tmp/
RUN git clone https://github.com/willmiao/ComfyUI-Lora-Manager.git \
    /app/ComfyUI/custom_nodes/ComfyUI-Lora-Manager && \
    cd /app/ComfyUI/custom_nodes/ComfyUI-Lora-Manager && \
    git checkout "${COMFYUI_LORA_MANAGER_REF}" && \
    git apply /tmp/comfyui-lora-manager-aria2-resume-queue.patch && \
    pip install -r requirements.txt

# 4. Anima-2.9B compatibility patch. The 2.9B model has 40 transformer
# blocks, while the current core detector assumes the original 28-block
# Anima architecture. Pin the patch so image rebuilds stay reproducible.
ARG COMFYUI_ANIMA_29B_REF=2de99f23e31ccf75d1a0f3d04c16ac5cfcd320e6
RUN git clone https://github.com/gazingstars123/ComfyUI-Anima-2.9B.git \
    /app/ComfyUI/custom_nodes/ComfyUI-Anima-2.9B && \
    cd /app/ComfyUI/custom_nodes/ComfyUI-Anima-2.9B && \
    git checkout "${COMFYUI_ANIMA_29B_REF}"

# Expose port
EXPOSE 8188

# ComfyUI startup: listen on all interfaces, enable preview
CMD ["python", "main.py", "--listen", "0.0.0.0", "--port", "8188", "--preview-method", "auto", "--lowvram"]
