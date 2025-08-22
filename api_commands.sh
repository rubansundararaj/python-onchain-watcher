#!/bin/bash

# API Testing Commands for Python Onchain Watcher
# Copy and paste these commands one by one to test your endpoints

echo "=== Python Onchain Watcher API Test Commands ==="
echo "Make sure your server is running with: python main.py"
echo ""

echo "1. Health Check:"
echo "curl -X GET \"http://localhost:8000/health\""
echo ""

echo "2. Create New Address:"
echo "curl -X POST \"http://localhost:8000/addresses\""
echo ""

echo "3. Get Address Balance:"
echo "curl -X GET http://localhost:8000/addresses/bc1q3ppsy7pwmhfwkudkaupv9rmnsc59al0smzctwf/balance"
echo ""

echo "4. Get Address UTXOs (all):"
echo "curl -X GET http://localhost:8000/addresses/bc1q3ppsy7pwmhfwkudkaupv9rmnsc59al0smzctwf/utxos"
echo ""

echo "5. Get Address UTXOs (with confirmation filters):"
echo "curl -X GET \"http://localhost:8000/addresses/bc1q3ppsy7pwmhfwkudkaupv9rmnsc59al0smzctwf/utxos?min_conf=1&max_conf=9999999\""
echo ""

echo "6. Watch Address (default webhook):"
echo "curl -X POST \"http://localhost:8000/watch\" \\"
echo "  -H \"Content-Type: application/json\" \\"
echo "  -d '{\"address\": \"bc1qxy2kgdygjrsqtzq2n0yrf2493p83kkfjhx0wlh\"}'"
echo ""

echo "7. Watch Address (custom webhook):"
echo "curl -X POST \"http://localhost:8000/watch\" \\"
echo "  -H \"Content-Type: application/json\" \\"
echo "  -d '{\"address\": \"bc1qxy2kgdygjrsqtzq2n0yrf2493p83kkfjhx0wlh\", \"webhook\": \"https://your-webhook.com/endpoint\"}'"
echo ""

echo "8. List Watched Addresses:"
echo "curl -X GET \"http://localhost:8000/watch\""
echo ""

echo "=== Example Bitcoin Addresses for Testing ==="
echo "Testnet: tb1qw508d6qejxtdg4y5r3zarvary0c5xw7kv8f3t4"
echo "Mainnet: bc1qw508d6qejxtdg4y5r3zarvary0c5xw7kv8f3t4"
echo ""

echo "=== Pretty Print JSON (if you have jq installed) ==="
echo "Add | jq to any command, e.g.:"
echo "curl -X GET \"http://localhost:8000/health\" | jq"
echo ""

echo "=== Notes ==="
echo "- Replace port 8000 with your actual port if different"
echo "- Replace example addresses with real Bitcoin addresses you want to monitor"
echo "- Make sure your server is running (python main.py)"
echo "- Check your environment variables are set correctly"
echo "- The webhook endpoint needs to be accessible from your server"
