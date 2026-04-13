FROM node:20-slim AS base

WORKDIR /app

# Install dependencies
COPY package.json package-lock.json* ./
RUN npm ci

# Copy source
COPY . .

# Build
RUN npm run build

EXPOSE 3000

CMD ["npm", "start"]
