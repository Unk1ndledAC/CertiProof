# CertiProof Reproducible Artifact
# Build: docker build -t certiproof .
# Run:   docker run -it certiproof ./reproduce.sh

FROM python:3.12-slim

# System dependencies for plotting and Rocq compilation
RUN apt-get update && apt-get install -y --no-install-recommends \
    texlive-latex-base \
    texlive-latex-extra \
    texlive-fonts-recommended \
    texlive-science \
    && rm -rf /var/lib/apt/lists/*

# Python dependencies
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r /app/requirements.txt

# Copy source code
COPY src/ /app/src/
COPY experiments/ /app/experiments/
COPY run_*.py /app/
COPY verify_installation.py /app/

# Copy Rocq formalisation
COPY coq/ /app/coq/

# Copy paper source
COPY paper/ /app/paper/

# Copy reproduce script
COPY reproduce.sh /app/

WORKDIR /app
RUN chmod +x /app/reproduce.sh

CMD ["/bin/bash"]
