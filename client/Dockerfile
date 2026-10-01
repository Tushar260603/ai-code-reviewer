# ==============================================================================
# client/Dockerfile
# Multi-stage build: Vite / frontend build, serve with Nginx
# ==============================================================================

# ------------------------------------------------------------------------------
# Stage 1: Build stage
# ------------------------------------------------------------------------------
FROM node:20-alpine AS build

WORKDIR /app

# Build arguments for frontend API configuration
ARG NEXT_PUBLIC_API_URL=http://localhost:5000
ARG VITE_API_URL=http://localhost:5000
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL \
    VITE_API_URL=$VITE_API_URL

# Install dependencies
COPY package*.json ./
RUN npm install

# Copy application source code
COPY . .

# Run production build (Vite / Next.js static build)
RUN npm run build

# Ensure dist directory exists for Nginx serving (supports both Vite and Next.js export)
RUN if [ -d "out" ] && [ ! -d "dist" ]; then cp -r out dist; fi

# ------------------------------------------------------------------------------
# Stage 2: Production serve stage
# ------------------------------------------------------------------------------
FROM nginx:alpine

# Copy custom Nginx configuration for SPA routing
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Copy compiled static assets from build stage to Nginx html directory
COPY --from=build /app/dist /usr/share/nginx/html

# Expose HTTP port 80 and client port 3000
EXPOSE 80
EXPOSE 3000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD wget -q --spider http://localhost:80/ || wget -q --spider http://localhost:3000/ || exit 1

# Start Nginx in foreground
CMD ["nginx", "-g", "daemon off;"]
