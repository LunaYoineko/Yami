FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

WORKDIR /app

# キャッシュを活用して依存関係をインストール
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --frozen --no-install-project

# ソースコードのコピーとプロジェクトのインストール
COPY . /app
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen

# PATH を通しておく
ENV PATH="/app/.venv/bin:$PATH"

CMD ["python", "main.py"]