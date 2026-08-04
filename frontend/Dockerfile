FROM node:22-alpine AS base

ENV PNPM_HOME=/pnpm
ENV PATH="$PNPM_HOME:$PATH"
RUN corepack enable && corepack prepare pnpm@9.15.4 --activate
WORKDIR /app
COPY package.json pnpm-lock.yaml ./

FROM base AS development
RUN pnpm install --frozen-lockfile
COPY . .
CMD ["pnpm", "dev", "--host", "0.0.0.0"]

FROM base AS build
ARG VITE_REVIEWER_CONTEXT_ENABLED=false
ENV VITE_REVIEWER_CONTEXT_ENABLED=$VITE_REVIEWER_CONTEXT_ENABLED
ARG VITE_GOOGLE_MAPS_BROWSER_API_KEY=
ENV VITE_GOOGLE_MAPS_BROWSER_API_KEY=$VITE_GOOGLE_MAPS_BROWSER_API_KEY
RUN pnpm install --frozen-lockfile
COPY . .
RUN pnpm build

FROM nginx:1.30.4-alpine AS production
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
