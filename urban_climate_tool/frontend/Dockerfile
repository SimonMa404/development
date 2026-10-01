FROM node:20-alpine

WORKDIR /app

ENV PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1 \
    NEXT_TELEMETRY_DISABLED=1

COPY package*.json ./
RUN npm install --ignore-scripts

COPY . .

RUN npm run build

EXPOSE 3000

CMD ["npm", "run", "start"]
