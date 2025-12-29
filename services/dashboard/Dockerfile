FROM node:20-slim AS builder

WORKDIR /build

# Copy package files and JSX components
COPY package.json vite.config.js ./
COPY components/ ./components/

# Install dependencies and build
RUN npm install && npm run build

FROM python:3.12-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY app/ ./app/
COPY templates/ ./templates/
COPY static/ ./static/

# Copy built components from builder stage
COPY --from=builder /build/static/dist/ ./static/dist/

# Expose port
EXPOSE 8080

# Run the application
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]