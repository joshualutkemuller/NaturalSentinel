# Stage 0: install dependencies (shared by dev and production)
FROM oven/bun:1 AS deps

WORKDIR /app

COPY package.json bun.lock /app/
COPY frontend/package.json /app/frontend/

WORKDIR /app/frontend

RUN bun install


# Stage 1: development — Vite dev server with HMR
FROM deps AS dev

COPY ./frontend /app/frontend

ARG VITE_API_URL
ENV VITE_API_URL=${VITE_API_URL}

EXPOSE 5173

CMD ["bun", "run", "dev", "--host", "0.0.0.0", "--port", "5173"]


# Stage 2: build the production bundle
FROM deps AS build

COPY ./frontend /app/frontend

ARG VITE_API_URL

RUN bun run build


# Stage 3: production — static files served by Nginx
FROM nginx:1

COPY --from=build /app/frontend/dist/ /usr/share/nginx/html

COPY ./frontend/nginx.conf /etc/nginx/conf.d/default.conf
COPY ./frontend/nginx-backend-not-found.conf /etc/nginx/extra-conf.d/backend-not-found.conf
