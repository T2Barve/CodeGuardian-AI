# ==============================================================================
# CodeGuardian AI — Frontend Dashboard Multi-Stage Dockerfile
# Production-Hardened Nginx Server (CIS Docker Benchmark Compliant)
# ==============================================================================

# Stage 1: Build Application
FROM node:20-alpine AS builder

LABEL maintainer="CodeGuardian AI Team <devops@codeguardian.ai>"
LABEL stage="builder"

WORKDIR /app

# Cache package dependencies
COPY package.json package-lock.json* ./
RUN npm ci || npm install

# Build static bundle
COPY . .
RUN npm run build

# Stage 2: Production Web Server
FROM nginx:1.27-alpine AS runner

LABEL maintainer="CodeGuardian AI Team <devops@codeguardian.ai>"
LABEL description="CodeGuardian AI React Dashboard Web Server"
LABEL version="1.0.0"

# Remove default nginx configurations and static files
RUN rm -rf /etc/nginx/conf.d/* /etc/nginx/nginx.conf /usr/share/nginx/html/*

# Copy custom enterprise Nginx configuration
COPY nginx.conf /etc/nginx/nginx.conf

# Copy production static assets from builder stage
COPY --from=builder /app/dist /usr/share/nginx/html

# Expose HTTP port
EXPOSE 5173

# Healthcheck verifying Nginx availability
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD wget --quiet --tries=1 --spider http://localhost:5173/nginx-health || exit 1

# Start Nginx in foreground mode
CMD ["nginx", "-g", "daemon off;"]
