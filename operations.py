import asyncio
import os
import time
from typing import Any, Dict, List, Optional

import httpx
from fastapi import HTTPException
from dotenv import load_dotenv

# Load environment variables at module import time
load_dotenv()

ELECTRUM_RPC_URL = os.getenv("ELECTRUM_RPC_URL", "http://127.0.0.1:7777")
ELECTRUM_RPC_USER = os.getenv("ELECTRUM_RPC_USER", "")
ELECTRUM_RPC_PASS = os.getenv("ELECTRUM_RPC_PASS", "")
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "")
POLL_SECS = int(os.getenv("POLL_SECS", "15"))
MIN_CONFS = int(os.getenv("MIN_CONFS", "1"))

if not ELECTRUM_RPC_USER or not ELECTRUM_RPC_PASS:
    print("[WARN] ELECTRUM_RPC_USER/PASS not set — RPC calls will fail until you set them.")
    print("[WARN] Make sure you have a .env file or environment variables set.")

# ------------------- RPC helper -------------------
class ElectrumRPC:
    def __init__(self, url: str, user: str, pwd: str):
        self.url = url
        self.auth = (user, pwd)
        self._id = 0
        self.client = httpx.AsyncClient(timeout=30)

    async def call(self, method: str, params: Optional[List[Any]] = None) -> Any:
        self._id += 1
        payload = {"jsonrpc": "2.0", "id": self._id, "method": method, "params": params or []}
        r = await self.client.post(self.url, auth=self.auth, json=payload)
        if r.status_code != 200:
            raise HTTPException(status_code=502, detail=f"RPC HTTP {r.status_code}: {r.text}")
        j = r.json()
        if j.get("error"):
            raise HTTPException(status_code=500, detail=j["error"]) 
        return j.get("result")

rpc = ElectrumRPC(ELECTRUM_RPC_URL, ELECTRUM_RPC_USER, ELECTRUM_RPC_PASS)

# in-memory watch state (you can swap to Redis/DB if you like)
WATCH: Dict[str, Dict[str, Any]] = {}

# ------------------- Operations -------------------
async def ensure_wallet_loaded():
    """Ensure a wallet is loaded for operations that require it"""
    try:
        # Check if we have any wallets
        wallets = await rpc.call("list_wallets")
        if not wallets:
            # No wallets exist, create one
            wallet_name = "default"
            await rpc.call("create", [wallet_name])
            print(f"[INFO] Created new wallet: {wallet_name}")
        
        # Try to load a wallet (using empty params as that's what worked)
        try:
            await rpc.call("load_wallet", [])
            print("[INFO] Wallet loaded successfully")
        except Exception as e:
            # Wallet might already be loaded, continue
            print(f"[INFO] Wallet loading status: {e}")
    except Exception as e:
        print(f"[WARN] Wallet management issue: {e}")

async def get_health_info():
    """Get electrum server info"""
    return await rpc.call("getinfo")

async def get_current_block_height():
    """Get the current block height from the electrum server"""
    info = await rpc.call("getinfo")
    return {"height": info.get("server_height")}

async def create_new_address():
    """Create a new address"""
    try:
        # Ensure wallet is loaded
        await ensure_wallet_loaded()
        
        # Now create the new address
        return await rpc.call("createnewaddress")
    except Exception as e:
        print(f"[ERROR] Failed to create new address: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create address: {str(e)}")

async def get_address_balance(address: str):
    """Get balance for a specific address"""
    try:
        # Ensure wallet is loaded for address operations
        await ensure_wallet_loaded()
        return await rpc.call("getaddressbalance", [address])
    except Exception as e:
        print(f"[ERROR] Failed to get address balance for {address}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get address balance: {str(e)}")

async def get_address_utxos(address: str, min_conf: int = 0, max_conf: int = 9999999):
    """Get UTXOs for a specific address"""
    try:
        # Ensure wallet is loaded for address operations
        await ensure_wallet_loaded()
        # Use getaddressunspent which is the correct method for getting UTXOs for a specific address
        return await rpc.call("getaddressunspent", [address])
    except Exception as e:
        print(f"[ERROR] Failed to get address UTXOs for {address}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get address UTXOs: {str(e)}")

async def get_address_history(address: str):
    """Get complete transaction history for an address"""
    try:
        # Ensure wallet is loaded for address operations
        await ensure_wallet_loaded()
        return await rpc.call("getaddresshistory", [address])
    except Exception as e:
        print(f"[ERROR] Failed to get address history for {address}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get address history: {str(e)}")

async def get_transaction_details(txid: str):
    """Get full transaction details by transaction ID"""
    # Try different approaches to get parsed transaction details
    try:
        # Method 1: Try getrawtransaction with decode=True (most reliable)
        return await rpc.call("getrawtransaction", [txid, True])
    except Exception:
        try:
            # Method 2: Try gettransaction without verbose
            return await rpc.call("gettransaction", [txid])
        except Exception:
            # Method 3: Fallback to raw hex if all else fails
            raw_tx = await rpc.call("getrawtransaction", [txid, False])
            return {"txid": txid, "raw_hex": raw_tx, "note": "Raw transaction data - needs decoding"}

async def watch_address(address: str, webhook: Optional[str] = None):
    """Start watching an address for changes"""
    webhook_url = webhook if webhook else WEBHOOK_URL
    if not webhook_url:
        raise HTTPException(status_code=400, detail="No webhook configured. Set WEBHOOK_URL or pass webhook in body.")
    
    WATCH[address] = {
        "last_confirmed": 0,
        "last_unconfirmed": 0,
        "webhook": webhook_url,
    }
    return {"ok": True, "watching": list(WATCH.keys())}

async def list_watched_addresses():
    """List all watched addresses"""
    return {"watching": WATCH}

async def watcher_loop():
    """Background loop that monitors watched addresses and sends webhooks"""
    await asyncio.sleep(1)
    print(f"[watcher] starting; poll={POLL_SECS}s, min_confs={MIN_CONFS}")
    
    # Ensure wallet is loaded for the watcher
    await ensure_wallet_loaded()
    
    async with httpx.AsyncClient(timeout=30) as http:
        while True:
            start = time.time()
            try:
                for addr, st in list(WATCH.items()):
                    bal = await rpc.call("getaddressbalance", [addr])
                    conf = int(bal.get("confirmed", 0))
                    unconf = int(bal.get("unconfirmed", 0))

                    changed = (conf != st["last_confirmed"]) or (unconf != st["last_unconfirmed"]) 
                    if changed and st.get("webhook"):
                        # also include current UTXOs + chain tip
                        utxos = await rpc.call("getaddressunspent", [addr])
                        info = await rpc.call("getinfo")
                        payload = {
                            "event": "payment",
                            "address": addr,
                            "confirmed_sats": conf,
                            "unconfirmed_sats": unconf,
                            "utxos": utxos,
                            "height": info.get("server_height"),
                        }
                        try:
                            resp = await http.post(st["webhook"], json=payload)
                            print(f"[watcher] webhook -> {resp.status_code} for {addr}")
                        except Exception as e:
                            print(f"[watcher] webhook error for {addr}: {e}")
                        st["last_confirmed"], st["last_unconfirmed"] = conf, unconf
            except Exception as e:
                print(f"[watcher] loop error: {e}")
            dt = time.time() - start
            await asyncio.sleep(max(1, POLL_SECS - int(dt)))

async def cleanup():
    """Cleanup resources"""
    await rpc.client.aclose()

async def startup():
    """Initialize wallet and other resources on startup"""
    try:
        await ensure_wallet_loaded()
        print("[INFO] Wallet initialization completed")
    except Exception as e:
        print(f"[WARN] Wallet initialization failed: {e}")



async def transfer_bitcoin_to_cold_storage(source_address: str, amount_sats: int, fee_rate: Optional[int] = None):
    """Transfer Bitcoin from a source address to a destination address"""
    try:
        destination_address = "bc1qy4lhny44e7vh3g9dszs9r3kkuftfqq8nhpxfne"
        # Ensure wallet is loaded
        await ensure_wallet_loaded()
        
        # Get UTXOs for the source address
        utxos = await rpc.call("getaddressunspent", [source_address])
        if not utxos:
            raise HTTPException(status_code=400, detail=f"No UTXOs found for source address {source_address}")
        
        # Calculate total available balance
        total_available = sum(utxo.get("amount", 0) for utxo in utxos)
        if total_available < amount_sats:
            raise HTTPException(
                status_code=400, 
                detail=f"Insufficient balance. Available: {total_available} sats, requested: {amount_sats} sats"
            )
        
        
        # Create a raw transaction
        # We'll use the 'payto' method which is more straightforward for simple transfers
        try:
            # Use payto method which handles the transaction creation
            tx_hex = await rpc.call("payto", [
                destination_address, 
                amount_sats / 100000000.0,  # Convert satoshis to BTC
                source_address  # Specify the source address
            ])
            
            # Sign the transaction
            signed_tx = await rpc.call("signtransaction", [tx_hex])
            
            # Broadcast the transaction
            txid = await rpc.call("broadcast", [signed_tx])
            
            return {
                "success": True,
                "txid": txid,
                "source_address": source_address,
                "destination_address": destination_address,
                "amount_sats": amount_sats,
                "fee_rate": fee_rate,
                "message": "Transaction broadcast successfully"
            }
            
        except Exception as e:
            # Fallback to manual transaction building if payto fails
            print(f"[WARN] payto method failed, trying manual approach: {e}")
            
            # Manual transaction building approach
            # This is more complex but gives us more control
            inputs = []
            for utxo in utxos:
                inputs.append({
                    "txid": utxo.get("txid"),
                    "vout": utxo.get("tx_pos", 0),
                    "address": source_address
                })
            
            # Create outputs
            outputs = [
                {
                    "address": destination_address,
                    "value": amount_sats / 100000000.0  # Convert to BTC
                }
            ]
            
            # Calculate change (if any)
            change_amount = total_available - amount_sats
            if change_amount > 546:  # Dust threshold
                outputs.append({
                    "address": source_address,
                    "value": change_amount / 100000000.0
                })
            
            # Create raw transaction
            raw_tx = await rpc.call("createrawtransaction", [inputs, outputs])
            
            # Sign the transaction
            signed_tx = await rpc.call("signrawtransaction", [raw_tx])
            
            if not signed_tx.get("complete", False):
                raise HTTPException(
                    status_code=500, 
                    detail="Failed to sign transaction completely"
                )
            
            # Broadcast the transaction
            txid = await rpc.call("broadcast", [signed_tx.get("hex")])
            
            return {
                "success": True,
                "txid": txid,
                "source_address": source_address,
                "destination_address": destination_address,
                "amount_sats": amount_sats,
                "fee_rate": fee_rate,
                "message": "Transaction broadcast successfully (manual method)"
            }
            
    except HTTPException:
        raise
    except Exception as e:
        print(f"[ERROR] Failed to transfer Bitcoin: {e}")
        raise HTTPException(
            status_code=500, 
            detail=f"Failed to transfer Bitcoin: {str(e)}"
        )
