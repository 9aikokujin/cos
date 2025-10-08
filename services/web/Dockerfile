FROM node:20-alpine AS builder

WORKDIR /app

RUN apk add --no-cache python3 make g++

COPY package.json yarn.lock* ./

RUN yarn install --frozen-lockfile

COPY . .

RUN yarn add --dev @rollup/rollup-linux-x64-musl
RUN yarn add --dev @swc/core-linux-x64-musl

RUN yarn build

FROM node:20-alpine
RUN yarn global add serve
WORKDIR /app
COPY --from=builder /app/dist ./dist

CMD ["serve", "-s", "dist", "-l", "4444"]
