#!/bin/bash

# API Testing Commands for Python Onchain Watcher
# This script actually EXECUTES the commands instead of just displaying them

echo "=== Python Onchain Watcher API Test Commands ==="
echo "Make sure your server is running with: python main.py"
echo ""

# 1. Health Check
curl -X GET "http://localhost:8000/health"

# 2. Create New Address
curl -X POST "http://localhost:8000/addresses"

# 3. Get Address Balance
curl -X GET "http://localhost:8000/addresses/bc1q3ppsy7pwmhfwkudkaupv9rmnsc59al0smzctwf/balance"

# 4. Get Address UTXOs (all)
curl -X GET "http://localhost:8000/addresses/bc1q3ppsy7pwmhfwkudkaupv9rmnsc59al0smzctwf/utxos"

# 5. Get Address UTXOs (with confirmation filters)
curl -X GET "http://localhost:8000/addresses/bc1q3ppsy7pwmhfwkudkaupv9rmnsc59al0smzctwf/utxos?min_conf=1&max_conf=9999999"

# 6. Get Address Transaction History
curl -X GET "http://localhost:8000/addresses/bc1q3ppsy7pwmhfwkudkaupv9rmnsc59al0smzctwf/history"

# 7. Get Transaction Details
curl -X GET "http://localhost:8000/transactions/abc123def456.../transaction"

# 8. Watch Address (default webhook)
curl -X POST "http://localhost:8000/watch" \
  -H "Content-Type: application/json" \
  -d '{"address": "bc1qxy2kgdygjrsqtzq2n0yrf2493p83kkfjhx0wlh"}'

# 9. Watch Address (custom webhook)
curl -X POST "http://localhost:8000/watch" \
  -H "Content-Type: application/json" \
  -d '{"address": "bc1qxy2kgdygjrsqtzq2n0yrf2493p83kkfjhx0wlh", "webhook": "https://your-webhook.com/endpoint"}'

# 10. List Watched Addresses
curl -X GET "http://localhost:8000/watch"

# 11. Transfer Bitcoin
curl -X POST "http://localhost:8000/transfer" \
  -H "Content-Type: application/json" \
  -d '{"source_address": "bc1q3ppsy7pwmhfwkudkaupv9rmnsc59al0smzctwf", "destination_address": "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa", "amount_sats": 100000}'

# 12. Transfer Bitcoin with Custom Fee Rate
curl -X POST "http://localhost:8000/transfer" \
  -H "Content-Type: application/json" \
  -d '{"source_address": "bc1q3ppsy7pwmhfwkudkaupv9rmnsc59al0smzctwf", "destination_address": "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa", "amount_sats": 100000, "fee_rate": 5}'

# Direct Electrum RPC commands
curl -u ruban:'InsaneElonTrump' \
  --data-binary '{"jsonrpc":"2.0","id":1,"method":"getaddresshistory","params":["bc1qrnrdpceunnkj6j8h9whw7n52uq8she4ne5n9y5"]}' \
  http://127.0.0.1:7777

curl -u ruban:'InsaneElonTrump' \
  --data-binary '{"jsonrpc":"2.0","id":1,"method":"gettransaction","params":["2f82fdcad6674704e0f6b752abdb6dbba7829e6043bf88d33104f3bb585600e8","bc1qrnrdpceunnkj6j8h9whw7n52uq8she4ne5n9y5"]}' \
  http://127.0.0.1:7777

curl -u ruban:'InsaneElonTrump' \
  --data-binary '{"jsonrpc":"2.0","id":1,"method":"load_wallet","params":["default"]}' \
  http://127.0.0.1:7777

curl -u ruban:'InsaneElonTrump' \
  --data-binary '{"jsonrpc":"2.0","id":1,"method":"load_wallet","params":[]}' \
  http://127.0.0.1:7777

# Transfer-related Electrum RPC commands
curl -u ruban:'InsaneElonTrump' \
  --data-binary '{"jsonrpc":"2.0","id":1,"method":"getprivatekeys","params":["bc1q3ppsy7pwmhfwkudkaupv9rmnsc59al0smzctwf"]}' \
  http://127.0.0.1:7777

curl -u ruban:'InsaneElonTrump' \
  --data-binary '{"jsonrpc":"2.0","id":1,"method":"getaddressbalance","params":["bc1q3ppsy7pwmhfwkudkaupv9rmnsc59al0smzctwf"]}' \
  http://127.0.0.1:7777

curl -u ruban:'InsaneElonTrump' \
  --data-binary '{"jsonrpc":"2.0","id":1,"method":"getaddressunspent","params":["bc1q3ppsy7pwmhfwkudkaupv9rmnsc59al0smzctwf"]}' \
  http://127.0.0.1:7777

curl -u ruban:'InsaneElonTrump' \
  --data-binary '{"jsonrpc":"2.0","id":1,"method":"payto","params":["1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa", 0.001, "bc1q3ppsy7pwmhfwkudkaupv9rmnsc59al0smzctwf"]}' \
  http://127.0.0.1:7777
