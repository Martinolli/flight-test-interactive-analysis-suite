# Frontend Dockerfile for FTIAS
# Node.js 20 with React + Vite

FROM node:20-alpine

# Set working directory
WORKDIR /app

# Install pnpm
RUN npm install -g pnpm

# Copy package files
COPY frontend/package*.json ./
COPY frontend/pnpm-lock.yaml* ./

# Install dependencies
RUN pnpm install

# Copy application code
COPY frontend/ .

# Expose port
EXPOSE 5173

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD wget --no-verbose --tries=1 --spider http://localhost:5173 || exit 1

# Run the development server
CMD ["pnpm", "dev", "--host", "0.0.0.0"]
