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

## Configuration

Set these environment variables before running:

```bash
export ELECTRUM_RPC_URL=http://127.0.0.1:7777
export ELECTRUM_RPC_USER=your_username
export ELECTRUM_RPC_PASS='your_password'
export WEBHOOK_URL=https://example.com/webhook
export POLL_SECS=15
export MIN_CONFS=1
```

## Installation & Running

1. Install dependencies:
```bash
pip install fastapi uvicorn[standard] httpx pydantic
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
