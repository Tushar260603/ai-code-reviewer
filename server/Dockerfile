# ==============================================================================
# server/Dockerfile
# Node 20 alpine base, installs deps, runs Express
# ==============================================================================

FROM node:20-alpine

# Set environment variables
ENV NODE_ENV=production \
    PORT=5000

# Install curl for health check
RUN apk add --no-cache curl

# Set working directory
WORKDIR /app

# Copy package manifests and install dependencies
COPY package*.json ./
RUN npm install --omit=dev

# Copy application source code
COPY . .

# Expose Express service port
EXPOSE 5000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:5000/health || exit 1

# Run Express server
CMD ["node", "src/index.js"]
