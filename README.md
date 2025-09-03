# Python Onchain Watcher

A FastAPI wrapper around Electrum JSON-RPC that converts your curl calls into clean REST endpoints and adds a simple watcher that posts to a webhook when an address receives funds/confirmations.

## Project Structure

The project has been refactored for better organization and maintainability:

- **`main.py`** - Contains only FastAPI endpoints that call operations
- **`operations.py`** - Contains all business logic operations and RPC handling
- **`models.py`** - Contains Pydantic data models
- **`__init__.py`** - Makes the project a proper Python package

## Features

- **Health Check**: Get electrum server info
- **Address Management**: Create new addresses and get balances
- **UTXO Tracking**: Monitor unspent transaction outputs
- **Address Watching**: Set up webhooks for address balance changes
- **Background Monitoring**: Automatic polling and webhook notifications

## API Endpoints

- `GET /health` - Get electrum server health info
- `POST /addresses` - Create a new address
- `GET /addresses/{address}/balance` - Get balance for a specific address
- `GET /addresses/{address}/utxos` - Get UTXOs for a specific address
- `POST /watch` - Start watching an address for changes
- `GET /watch` - List all watched addresses
- `POST /transfer` - Transfer Bitcoin from a source address to a destination address
- `POST /cold-storage` - Transfer 70% of wallet balance to cold storage address
- `GET /wallet/balance` - Get overall wallet balance

## Transfer Endpoint

The `/transfer` endpoint allows you to transfer Bitcoin from an Electrum-generated address to any remote wallet address.

### Request Body

```json
{
  "source_address": "bc1q...",
  "destination_address": "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa",
  "amount_sats": 100000,
  "fee_rate": 5
}
```

### Parameters

- **`source_address`** (required): The Electrum-generated address to send Bitcoin from
- **`destination_address`** (required): The destination wallet address
- **`amount_sats`** (required): Amount to transfer in satoshis (1 BTC = 100,000,000 sats)
- **`fee_rate`** (optional): Fee rate in satoshis per byte. If not specified, Electrum will use default fee estimation

### Response

```json
{
  "success": true,
  "txid": "abc123...",
  "source_address": "bc1q...",
  "destination_address": "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa",
  "amount_sats": 100000,
  "fee_rate": 5,
  "message": "Transaction broadcast successfully"
}
```

### Example Usage

```bash
curl -X POST "http://localhost:8080/transfer" \
  -H "Content-Type: application/json" \
  -d '{
    "source_address": "bc1q...",
    "destination_address": "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa",
    "amount_sats": 100000
  }'
```

**Note**: The source address must have sufficient balance and the private key must be available in the Electrum wallet for signing the transaction.

## Cold Storage Endpoint

The `/cold-storage` endpoint automatically transfers 70% of the wallet's total balance to a specified cold storage address. This is useful for automated cold storage management.

### Request Body

```json
{
  "cold_wallet_address": "bc1q...",
  "fee_rate": 5
}
```

### Parameters

- **`cold_wallet_address`** (required): The cold storage wallet address to transfer funds to
- **`fee_rate`** (optional): Fee rate in satoshis per byte

### Response Format

```json
{
  "success": true,
  "txid": "abc123...",
  "cold_wallet_address": "bc1q...",
  "transfer_amount_sats": 38500,
  "transfer_amount_btc": 0.000385,
  "original_balance_sats": 55000,
  "original_balance_btc": 0.00055,
  "fee_rate": 5,
  "message": "Successfully transferred 38500 sats (0.000385 BTC) to cold storage"
}
```

### Example Usage

```bash
curl -X POST "http://localhost:8080/cold-storage" \
  -H "Content-Type: application/json" \
  -d '{
    "cold_wallet_address": "bc1qgapvnn6vpyr37adaekxphyhrquqn386nzf2r6z"
  }'
```

### Features

- **Automatic Balance Calculation**: Gets the current wallet balance and calculates 70%
- **Smart Balance Handling**: Uses confirmed balance if insufficient for full 70% transfer
- **Minimum Amount Check**: Ensures transfer amount is above dust threshold (1000 sats)
- **Fallback Methods**: Uses `payto` first, falls back to `paytomany` if needed
- **Comprehensive Logging**: Detailed logs for debugging and monitoring

## Wallet Balance Endpoint

The `/wallet/balance` endpoint provides the overall wallet balance including both confirmed and unconfirmed funds.

### Response Format

```json
{
  "success": true,
  "balance": {
    "confirmed_btc": "0.00005501",
    "unconfirmed_btc": "0.0",
    "total_btc": "0.00005501",
    "confirmed_sats": 5501,
    "unconfirmed_sats": 0,
    "total_sats": 5501
  },
  "message": "Wallet balance retrieved successfully"
}
```

### Example Usage

```bash
curl -X GET "http://localhost:8080/wallet/balance"
```

### Response Fields

- **`confirmed_btc`**: Confirmed balance in BTC (string format)
- **`unconfirmed_btc`**: Unconfirmed balance in BTC (string format)  
- **`total_btc`**: Total balance in BTC (string format)
- **`confirmed_sats`**: Confirmed balance in satoshis (integer)
- **`unconfirmed_sats`**: Unconfirmed balance in satoshis (integer)
- **`total_sats`**: Total balance in satoshis (integer)

## Authentication

All API endpoints (except `/login`) now require JWT authentication. 

### Login Endpoint

First, authenticate to get a JWT token:

```bash
curl -X POST "http://localhost:8080/login" \
  -H "Content-Type: application/json" \
  -d '{
    "username": "admin",
    "password": "admin123"
  }'
```

Response:
```json
{
  "access_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
  "token_type": "bearer",
  "expires_in": 1800
}
```

### Using the Token

Include the token in the Authorization header for all subsequent requests:

```bash
curl -X GET "http://localhost:8080/health" \
  -H "Authorization: Bearer eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9..."
```

## Configuration

Set these environment variables before running:

```bash
# Electrum RPC Configuration
export ELECTRUM_RPC_URL=http://127.0.0.1:7777
export ELECTRUM_RPC_USER=your_username
export ELECTRUM_RPC_PASS='your_password'

# Webhook Configuration
export WEBHOOK_URL=https://example.com/webhook
export POLL_SECS=15
export MIN_CONFS=1

# JWT Authentication Configuration
export JWT_SECRET_KEY=your-super-secret-jwt-key-change-this-in-production
export JWT_ACCESS_TOKEN_EXPIRE_MINUTES=30

# API Authentication Credentials
export API_USERNAME=admin
export API_PASSWORD=admin123

# App Configuration
export APP_HOST=0.0.0.0
export APP_PORT=8000
export APP_RELOAD=True
```

## Installation & Running

1. Install dependencies:
```bash
pip install fastapi uvicorn[standard] httpx pydantic python-jose[cryptography] passlib[bcrypt] python-multipart
```

2. Run the server:
```bash
uvicorn main:app --host 0.0.0.0 --port 8080 --reload
```

## Webhook Payloads

When an address receives funds, the webhook will receive:

```json
{
  "event": "payment",
  "address": "bc1...",
  "confirmed_sats": 12345,
  "unconfirmed_sats": 0,
  "utxos": [...],
  "height": 911015
}
```

## Development

The project follows a clean architecture pattern:
- **API Layer** (`main.py`): Handles HTTP requests and responses
- **Business Logic Layer** (`operations.py`): Contains all operations and RPC logic
- **Data Layer** (`models.py`): Defines data structures and validation

This separation makes the code more maintainable, testable, and easier to extend.
