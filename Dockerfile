# ---- Build Stage ----
    FROM golang:1.23 AS builder
    WORKDIR /app
    
    # Install build dependencies for CGO and glibc
    RUN apt-get update && apt-get install -y gcc libc6-dev
    
    COPY go.mod go.sum ./
    RUN go mod download
    
    COPY . .
    
    RUN CGO_ENABLED=1 GOOS=linux go build -o glimpsemain ./cmd/server/main.go
    
    # ---- Run Stage ----
    FROM debian:bookworm-slim
    
    RUN apt-get update && apt-get install -y ca-certificates && rm -rf /var/lib/apt/lists/*
    
    WORKDIR /app
    
    COPY --from=builder /app/glimpsemain ./glimpsemain
    COPY --from=builder /app/docs ./docs
    COPY --from=builder /app/internal/email/templates ./internal/email/templates
    COPY .env ./
    COPY glimpse-markets-firebase-adminsdk-fbsvc-503fbebcde.json ./
    
    EXPOSE 8383
    
    CMD ["./glimpsemain"]


    