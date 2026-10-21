FROM node:24-bookworm-slim AS dashboard
RUN corepack enable && corepack prepare pnpm@10.11.0 --activate
WORKDIR /web
COPY apps/dashboard/package.json apps/dashboard/pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile
COPY apps/dashboard/ ./
RUN pnpm build

FROM python:3.12-slim-bookworm
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY pyproject.toml alembic.ini ./
COPY services/api/ services/api/
COPY db/migrations/ db/migrations/
COPY infra/nginx.conf infra/nginx.conf
RUN pip install --no-cache-dir . && useradd --create-home --uid 10001 nebula
COPY --from=dashboard /web/dist /app/apps/dashboard/dist
USER nebula
EXPOSE 8080
CMD ["uvicorn", "nebula.api:app", "--host", "0.0.0.0", "--port", "8080", "--no-proxy-headers"]
