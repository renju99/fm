FROM odoo:19

# Install system dependencies for matplotlib and other Python packages
USER root

# Install system packages required for matplotlib and other dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        python3-pip \
        python3-dev \
        build-essential \
        libfreetype6-dev \
        libpng-dev \
        libjpeg-dev \
        && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
# Using --break-system-packages is safe in Docker containers
RUN pip3 install --no-cache-dir --break-system-packages \
    qrcode[pil] \
    Pillow \
    matplotlib

# Switch back to odoo user
USER odoo

