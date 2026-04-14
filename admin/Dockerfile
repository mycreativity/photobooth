FROM node:20-alpine

WORKDIR /app

# Install dependencies (cached layer)
COPY package.json package-lock.json ./
RUN npm ci

# Copy source (overridden by volume mount in dev)
COPY . .

# Dev mode: hot reload
EXPOSE 3000
CMD ["npm", "run", "dev"]
