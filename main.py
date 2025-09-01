# main.py
# FastAPI wrapper around Electrum JSON-RPC
# Converts your curl calls into clean REST endpoints and adds a simple watcher
# that posts to a webhook when an address receives funds / confirmations.
#
# Endpoints:
#   GET    /health                          -> electrum.getinfo
#   GET    /block-height                    -> electrum.getinfo (server_height)
#   POST   /addresses                       -> electrum.createnewaddress
#   GET    /addresses/{address}/balance     -> electrum.getaddressbalance
#   GET    /addresses/{address}/utxos       -> electrum.listunspent (scoped)
#   POST   /watch                           -> start watching an address
#   GET    /watch                           -> list watched addresses
#   POST   /transfer                        -> transfer bitcoin between addresses
#   GET    /wallet/balance                  -> electrum.getbalance
#
# Webhook payloads:
#   { "event": "payment", "address": "bc1...", "confirmed_sats": 12345,
#     "unconfirmed_sats": 0, "utxos": [...], "height": 911015 }
#
# Config via ENV (set before running):
#   ELECTRUM_RPC_URL   (default: http://127.0.0.1:7777)
#   ELECTRUM_RPC_USER  (required)
#   ELECTRUM_RPC_PASS  (required)
#   WEBHOOK_URL        (optional but recommended)
#   POLL_SECS          (default 15)
#   MIN_CONFS          (default 1) confirmations to treat as confirmed
#
# Run locally (example using SSH tunnel):
#   ssh -N -L 7777:127.0.0.1:7777 root@REMOTE
#   export ELECTRUM_RPC_URL=http://127.0.0.1:7777
#   export ELECTRUM_RPC_USER=ruban
#   export ELECTRUM_RPC_PASS='YOUR_STRONG_PASSWORD'
#   export WEBHOOK_URL=https://example.com/webhook
#   pip install fastapi uvicorn[standard] httpx pydantic
#   uvicorn main:app --host 0.0.0.0 --port 8080 --reload


import asyncio
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import os
from dotenv import load_dotenv

# Load environment variables at module import time
load_dotenv()


from operations import (
    get_health_info,
    create_new_address,
    get_address_balance,
    get_address_utxos,
    get_address_history,
    get_transaction_details,
    watch_address,
    list_watched_addresses,
    watcher_loop,
    cleanup,
    get_current_block_height,
    startup,
    transfer_bitcoin_to_cold_storage,
    get_wallet_balance
)
from models import WatchReq, TransferReq

app = FastAPI(title="Electrum RPC REST Wrapper", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# ------------------- Endpoints -------------------
@app.get("/health")
async def health():
    """Get electrum server health info"""
    return await get_health_info()

@app.get("/block-height")
async def current_block_height():
    """Get the current block height from the electrum server"""
    return await get_current_block_height()

@app.post("/addresses")
async def create_address():
    """Create a new address"""
    addr = await create_new_address()
    return {"address": addr}

@app.get("/addresses/{address}/balance")
async def address_balance(address: str):
    """Get balance for a specific address"""
    bal = await get_address_balance(address)
    # returns {"confirmed": sats, "unconfirmed": sats}
    return bal

@app.get("/addresses/{address}/utxos")
async def address_utxos(address: str, min_conf: int = 0, max_conf: int = 9999999):
    """Get UTXOs for a specific address"""
    utxos = await get_address_utxos(address, min_conf, max_conf)
    return {"address": address, "utxos": utxos}

@app.get("/addresses/{address}/history")
async def address_history(address: str):
    """Get complete transaction history for an address"""
    history = await get_address_history(address)
    return {"address": address, "history": history}

@app.get("/transactions/{txid}")
async def transaction_details(txid: str):
    """Get full transaction details by transaction ID"""
    tx = await get_transaction_details(txid)
    return {"txid": txid, "transaction": tx}

@app.post("/watch")
async def watch_address_endpoint(req: WatchReq):
    """Start watching an address for changes"""
    webhook_url = str(req.webhook) if req.webhook else None
    return await watch_address(req.address, webhook_url)

@app.get("/watch")
async def list_watch():
    """List all watched addresses"""
    return await list_watched_addresses()

@app.post("/transfer")
async def transfer_bitcoin_endpoint(req: TransferReq):
    """Transfer Bitcoin from a source address to a destination address"""
    print(f"[ENDPOINT] /transfer called with request:")
    print(f"[ENDPOINT]   source_address: {req.source_address}")
    print(f"[ENDPOINT]   destination_address: {req.destination_address}")
    print(f"[ENDPOINT]   amount_sats: {req.amount_sats}")
    print(f"[ENDPOINT]   fee_rate: {req.fee_rate}")
    
    try:
        print(f"[ENDPOINT] Calling transfer_bitcoin function...")
        result = await transfer_bitcoin_to_cold_storage(
            req.destination_address,
            req.fee_rate
        )
        print(f"[ENDPOINT] ✓ Transfer completed successfully, returning result")
        return result
    except Exception as e:
        print(f"[ENDPOINT] ❌ Error in transfer endpoint: {e}")
        print(f"[ENDPOINT] Error type: {type(e).__name__}")
        raise


@app.get("/wallet/balance")
async def get_wallet_balance_endpoint():
    """Get overall wallet balance"""
    print(f"[ENDPOINT] /wallet/balance called")
    
    try:
        print(f"[ENDPOINT] Calling get_wallet_balance function...")
        result = await get_wallet_balance()
        print(f"[ENDPOINT] ✓ Wallet balance retrieved successfully, returning result")
        return result
    except Exception as e:
        print(f"[ENDPOINT] ❌ Error in wallet balance endpoint: {e}")
        print(f"[ENDPOINT] Error type: {type(e).__name__}")
        raise

# ------------------- Background watcher -------------------
@app.on_event("startup")
async def _startup():
    """Start the background watcher loop"""
    # Initialize wallet and other resources
    await startup()
    # Start the background watcher loop
    asyncio.create_task(watcher_loop())

@app.on_event("shutdown")
async def _shutdown():
    """Cleanup resources on shutdown"""
    await cleanup()

# ------------------- Server startup -------------------
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host=os.getenv("APP_HOST", "0.0.0.0"),
        port=int(os.getenv("APP_PORT", "8000")),
        reload=os.getenv("APP_RELOAD", "True").lower() == "true"
    )
