FROM python:3.12-slim-bookworm
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
RUN --mount=type=secret,id=extra_ca,target=/usr/local/share/ca-certificates/extra-ca.crt,required=false \
    update-ca-certificates \
    && sed -i 's|http://deb.debian.org|https://deb.debian.org|g' /etc/apt/sources.list.d/debian.sources \
    && apt-get update && apt-get install -y --no-install-recommends \
    git openssh-client procps libstdc++6 ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --shell /bin/bash --uid 1000 vscode \
    && mkdir -p /workspaces/dhd-ksnb && chown vscode:vscode /workspaces/dhd-ksnb
USER vscode
WORKDIR /workspaces/dhd-ksnb
