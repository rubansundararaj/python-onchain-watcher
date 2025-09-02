#!/bin/bash

# API Testing Commands for Python Onchain Watcher
# Copy and paste these commands one by one to test your endpoints

=== Python Onchain Watcher API Test Commands ==="
Make sure your server is running with: python main.py"
"

1. Health Check:"
curl -X GET \"http://localhost:8000/health\""
"

2. Create New Address:"
curl -X POST \"http://localhost:8000/addresses\""
"

3. Get Address Balance:"
curl -X GET http://localhost:8000/addresses/bc1q3ppsy7pwmhfwkudkaupv9rmnsc59al0smzctwf/balance"
"

4. Get Address UTXOs (all):"
curl -X GET http://localhost:8000/addresses/bc1q3ppsy7pwmhfwkudkaupv9rmnsc59al0smzctwf/utxos"
"

5. Get Address UTXOs (with confirmation filters):"
curl -X GET \"http://localhost:8000/addresses/bc1q3ppsy7pwmhfwkudkaupv9rmnsc59al0smzctwf/utxos?min_conf=1&max_conf=9999999\""
"

6. Get Address Transaction History:"
curl -X GET http://localhost:8000/addresses/bc1q3ppsy7pwmhfwkudkaupv9rmnsc59al0smzctwf/history"
"

7. Get Transaction Details:"
curl -X GET http://localhost:8000/transactions/abc123def456.../transaction"
"

8. Watch Address (default webhook):"
curl -X POST \"http://localhost:8000/watch\" \\"
  -H \"Content-Type: application/json\" \\"
  -d '{\"address\": \"bc1qxy2kgdygjrsqtzq2n0yrf2493p83kkfjhx0wlh\"}'"
"

9. Watch Address (custom webhook):"
curl -X POST \"http://localhost:8000/watch\" \\"
  -H \"Content-Type: application/json\" \\"
  -d '{\"address\": \"bc1qxy2kgdygjrsqtzq2n0yrf2493p83kkfjhx0wlh\", \"webhook\": \"https://your-webhook.com/endpoint\"}'"
"

10. List Watched Addresses:"
curl -X GET \"http://localhost:8000/watch\""
"

11. Transfer Bitcoin:"
curl -X POST \"http://localhost:8000/transfer\" \\"
  -H \"Content-Type: application/json\" \\"
  -d '{\"source_address\": \"bc1q3ppsy7pwmhfwkudkaupv9rmnsc59al0smzctwf\", \"destination_address\": \"1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa\", \"amount_sats\": 100000}'"
"

12. Transfer Bitcoin with Custom Fee Rate:"
curl -X POST \"http://localhost:8000/transfer\" \\"
  -H \"Content-Type: application/json\" \\"
  -d '{\"source_address\": \"bc1q3ppsy7pwmhfwkudkaupv9rmnsc59al0smzctwf\", \"destination_address\": \"1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa\", \"amount_sats\": 100000, \"fee_rate\": 5}'"
"

13. Get Overall Wallet Balance:"
curl -X GET \"http://localhost:8000/wallet/balance\""
"

14. Transfer 70% to Cold Storage:"
curl -X POST \"http://localhost:8000/cold-storage\" \\
  -H \"Content-Type: application/json\" \\
  -d '{\"cold_wallet_address\": \"bc1qgapvnn6vpyr37adaekxphyhrquqn386nzf2r6z\"}'"
"

15. Transfer 70% to Cold Storage with Custom Fee Rate:"
curl -X POST \"http://localhost:8000/cold-storage\" \\
  -H \"Content-Type: application/json\" \\
  -d '{\"cold_wallet_address\": \"bc1qgapvnn6vpyr37adaekxphyhrquqn386nzf2r6z\", \"fee_rate\": 5}'"
"

=== Example Bitcoin Addresses for Testing ==="
Testnet: tb1qw508d6qejxtdg4y5r3zarvary0c5xw7kv8f3t4"
Mainnet: bc1qw508d6qejxtdg4y5r3zarvary0c5xw7kv8f3t4"
"

=== Pretty Print JSON (if you have jq installed) ==="
Add | jq to any command, e.g.:"
curl -X GET \"http://localhost:8000/health\" | jq"
"

=== Notes ==="
- Replace port 8000 with your actual port if different"
- Replace example addresses with real Bitcoin addresses you want to monitor"
- Make sure your server is running (python main.py)"
- Check your environment variables are set correctly"
- The webhook endpoint needs to be accessible from your server"



curl -u ruban:'InsaneElonTrump' \
  --data-binary '{"jsonrpc":"2.0","id":1,"method":"getaddresshistory","params":["bc1qrnrdpceunnkj6j8h9whw7n52uq8she4ne5n9y5"]}' \
  http://127.0.0.1:7777 | jq


curl -u ruban:'InsaneElonTrump' \
  --data-binary '{"jsonrpc":"2.0","id":1,"method":"gettransaction","params":["2f82fdcad6674704e0f6b752abdb6dbba7829e6043bf88d33104f3bb585600e8","bc1qrnrdpceunnkj6j8h9whw7n52uq8she4ne5n9y5"]}' \
  http://127.0.0.1:7777 | jq


curl -u ruban:'InsaneElonTrump' \
  --data-binary '{"jsonrpc":"2.0","id":1,"method":"load_wallet","params":[]}' \
  http://127.0.0.1:7777

curl -u ruban:'InsaneElonTrump' \
  --data-binary '{"jsonrpc":"2.0","id":1,"method":"load_wallet","params":[]}' \
  http://127.0.0.1:7777 | jq

# Transfer-related Electrum RPC commands
"
=== Transfer Testing Commands ==="
"

Get private key for address (required for transfers):"
curl -u ruban:'InsaneElonTrump' \
  --data-binary '{"jsonrpc":"2.0","id":1,"method":"getprivatekeys","params":["bc1qqysw3y94w3mq8huqxq4ggtzm8w4v5h0w8ypdet"]}' \
  http://127.0.0.1:7777 

Get address balance (check before transfer):"
curl -u ruban:'InsaneElonTrump' \
  --data-binary '{"jsonrpc":"2.0","id":1,"method":"getaddressbalance","params":["bc1qrnrdpceunnkj6j8h9whw7n52uq8she4ne5n9y5"]}' \
  http://127.0.0.1:7777 

Get overall wallet balance:"
curl -u ruban:'InsaneElonTrump' \
  --data-binary '{"jsonrpc":"2.0","id":1,"method":"getbalance"}' \
  http://127.0.0.1:7777 

Get address UTXOs (check available funds):"
curl -u ruban:'InsaneElonTrump' \
  --data-binary '{"jsonrpc":"2.0","id":1,"method":"getaddressunspent","params":["bc1qrnrdpceunnkj6j8h9whw7n52uq8she4ne5n9y5"]}' \
  http://127.0.0.1:7777 

Test payto method (Electrum's built-in transfer):"
curl -u ruban:'InsaneElonTrump' \
  --data-binary '{"jsonrpc":"2.0","id":1,"method":"payto","params":["bc1qgapvnn6vpyr37adaekxphyhrquqn386nzf2r6z", 0.00001]}' \
  http://127.0.0.1:7777



  curl -u ruban:'InsaneElonTrump' \
  --data-binary '{"jsonrpc":"2.0","id":1,"method":"payto","params":["bc1qy4lhny44e7vh3g9dszs9r3kkuftfqq8nhpxfne", 0.00001, "bc1qqysw3y94w3mq8huqxq4ggtzm8w4v5h0w8ypdet"]}' \
  http://127.0.0.1:7777

# Manual Transaction Building Commands
echo ""
echo "=== Manual Transaction Building Commands ==="
echo ""

echo "1. Get UTXOs from specific address:"
curl -u ruban:'InsaneElonTrump' \
 --data-binary '{"jsonrpc":"2.0","id":1"method":"getaddressunspent","params":["bc1qqysw3y94w3mq8huqxq4ggtzm8w4v5h0w8ypdet\"]}' \\"
 http://127.0.0.1:7777

echo "2. Create raw transaction:"
echo "curl -u ruban:'InsaneElonTrump' \\"
echo "  --data-binary '{"jsonrpc":"2.0","id":1,"method":"createrawtransaction","params":[[{"txid":"abc123...","vout":0}],[{"bc1qy4lhny44e7vh3g9dszs9r3kkuftfqq8nhpxfne":0.00001}]]}' \"
echo "  http://127.0.0.1:7777"
echo ""

echo "3. Sign raw transaction:"
echo "curl -u ruban:'InsaneElonTrump' \\"
echo "  --data-binary '{\"jsonrpc\":\"2.0\",\"id\":1,\"method\":\"signrawtransaction\",\"params\":[\"raw_tx_hex_here\"]}' \\"
echo "  http://127.0.0.1:7777"
echo ""

echo "4. Broadcast signed transaction:"
echo "curl -u ruban:'InsaneElonTrump' \\"
echo "  --data-binary '{\"jsonrpc\":\"2.0\",\"id\":1,\"method\":\"broadcast\",\"params\":[\"signed_tx_hex_here\"]}' \\"
echo "  http://127.0.0.1:7777"
echo ""

echo "5. Test createrawtransaction with real data:"
echo "curl -u ruban:'InsaneElonTrump' \\"
echo "  --data-binary '{\"jsonrpc\":\"2.0\",\"id\":1,\"method\":\"createrawtransaction\",\"params\":[[{\"txid\":\"REPLACE_WITH_REAL_TXID\",\"vout\":0}],[{\"bc1qy4lhny44e7vh3g9dszs9r3kkuftfqq8nhpxfne\":0.00001}]]}' \\"
echo "  http://127.0.0.1:7777"
echo ""

echo "6. Test the complete manual flow:"
echo "curl -X POST http://localhost:8000/transfer \\"
echo "  -H \"Content-Type: application/json\" \\"
echo "  -d '{\"source_address\":\"bc1qqysw3y94w3mq8huqxq4ggtzm8w4v5h0w8ypdet\",\"destination_address\":\"bc1qy4lhny44e7vh3g9dszs9r3kkuftfqq8nhpxfne\",\"amount_sats\":1000}'"
echo ""

echo "7d. Test with just the basic transaction (no change):"
echo "curl -u ruban:'InsaneElonTrump' \\"
echo "  --data-binary '{\"jsonrpc\":\"2.0\",\"id\":1,\"method\":\"createrawtransaction\",\"params\":[[{\"txid\":\"bee52c6957e3276702ad2a9290b26fd5844821b216156d9c1608a82cb0c7ad0e\",\"vout\":1}],{\"bc1qy4lhny44e7vh3g9dszs9r3kkuftfqq8nhpxfne\":1e-05}]}' \\"
echo "  http://127.0.0.1:7777"
echo ""

echo "8. Check what RPC methods are available in Electrum:"
echo "curl -u ruban:'InsaneElonTrump' \\"
echo "  --data-binary '{\"jsonrpc\":\"2.0\",\"id\":1,\"method\":\"help\"}' \\"
echo "  http://127.0.0.1:7777"
echo ""

echo "9. Test alternative transaction creation methods:"
echo ""

echo "9a. Try paytomany (Electrum's preferred method):"
echo "curl -u ruban:'InsaneElonTrump' \\"
echo "  --data-binary '{\"jsonrpc\":\"2.0\",\"id\":1,\"method\":\"paytomany\",\"params\":[{\"bc1qy4lhny44e7vh3g9dszs9r3kkuftfqq8nhpxfne\":1e-05,\"bc1qqysw3y94w3mq8huqxq4ggtzm8w4v5h0w8ypdet\":4e-05}]}' \\"
echo "  http://127.0.0.1:7777"
echo ""

echo "9b. Try payto with specific source (if supported):"
echo "curl -u ruban:'InsaneElonTrump' \\"
echo "  --data-binary '{\"jsonrpc\":\"2.0\",\"id\":1,\"method\":\"payto\",\"params\":[\"bc1qy4lhny44e7vh3g9dszs9r3kkuftfqq8nhpxfne\",1e-05]}' \\"
echo "  http://127.0.0.1:7777"
echo ""

echo "9c. Check if we can freeze specific addresses to control spending:"
echo "curl -u ruban:'InsaneElonTrump' \\"
echo "  --data-binary '{\"jsonrpc\":\"2.0\",\"id\":1,\"method\":\"freeze\",\"params\":[\"bc1qqysw3y94w3mq8huqxq4ggtzm8w4v5h0w8ypdet\"]}' \\"
echo "  http://127.0.0.1:7777"
echo ""

echo "9d. Unfreeze the address:"
echo "curl -u ruban:'InsaneElonTrump' \\"
echo "  --data-binary '{\"jsonrpc\":\"2.0\",\"id\":1,\"method\":\"freeze\",\"params\":[\"bc1qqysw3y94w3mq8huqxq4ggtzm8w4v5h0w8ypdet\"]}' \\"
echo "  http://127.0.0.1:7777"
echo ""



echo ""
echo "=== NEW WITHDRAW ENDPOINT ==="
echo "Withdraw from withdrawal wallet with balance check:"
curl -X POST http://localhost:8000/withdraw \
  -H "Content-Type: application/json" \
  -d '{"recipient_address": "bc1qy4lhny44e7vh3g9dszs9r3kkuftfqq8nhpxfne", "amount_sats": 1000, "fee_rate": 2}'
echo ""
