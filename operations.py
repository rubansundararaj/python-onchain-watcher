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
    print(f"[WALLET] Ensuring wallet is loaded...")
    try:
        # Check if we have any wallets
        print(f"[WALLET] Checking for existing wallets...")
        wallets = await rpc.call("list_wallets")
        print(f"[WALLET] Found wallets: {wallets}")
        
        if not wallets:
            # No wallets exist, create one
            wallet_name = "default"
            print(f"[WALLET] No wallets found, creating new wallet: {wallet_name}")
            await rpc.call("create", [wallet_name])
            print(f"[WALLET] ✓ Created new wallet: {wallet_name}")
        
        # Try to load a wallet (using empty params as that's what worked)
        try:
            print(f"[WALLET] Attempting to load wallet...")
            await rpc.call("load_wallet", [])
            print(f"[WALLET] ✓ Wallet loaded successfully")
        except Exception as e:
            # Wallet might already be loaded, continue
            print(f"[WALLET] ⚠️ Wallet loading status: {e}")
    except Exception as e:
        print(f"[WALLET] ❌ Wallet management issue: {e}")
        raise

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



async def transfer_bitcoin_to_cold_storage(source_address: str, destination_address: str, amount_sats: int, fee_rate: Optional[int] = None):
    """Transfer Bitcoin from a source address to a destination address"""
    print(f"[TRANSFER] Starting transfer: {source_address} -> {destination_address}, amount: {amount_sats} sats, fee_rate: {fee_rate}")
    
    try:  
        print(f"[TRANSFER] Step 1: Ensuring wallet is loaded...")
        # Ensure wallet is loaded
        await ensure_wallet_loaded()
        print(f"[TRANSFER] ✓ Wallet loaded successfully")
        
        print(f"[TRANSFER] Step 2: Getting UTXOs for source address {source_address}...")
        # Get UTXOs for the source address
        utxos = await rpc.call("getaddressunspent", [source_address])
        print(f"[TRANSFER] ✓ Got UTXOs: {len(utxos) if utxos else 0} UTXOs found")
        
        if not utxos:
            print(f"[TRANSFER] ❌ No UTXOs found for source address {source_address}")
            raise HTTPException(status_code=400, detail=f"No UTXOs found for source address {source_address}")
        
        print(f"[TRANSFER] Step 3: Calculating total available balance...")
        # Calculate total available balance
        total_available = sum(utxo.get("value", 0) for utxo in utxos)
        print(f"[TRANSFER] ✓ Total available: {total_available} sats")
        
        if total_available < amount_sats:
            print(f"[TRANSFER] ❌ Insufficient balance. Available: {total_available} sats, requested: {amount_sats} sats")
            raise HTTPException(
                status_code=400, 
                detail=f"Insufficient balance. Available: {total_available} sats, requested: {amount_sats} sats"
            )
        
        print(f"[TRANSFER] Step 4: Getting private key for source address...")
        # Get the private key for the source address (required for signing)
        try:
            await rpc.call("getprivatekeys", [source_address])
            print(f"[TRANSFER] ✓ Private key retrieved successfully")
        except Exception as e:
            print(f"[TRANSFER] ❌ Failed to get private key for source address: {e}")
            raise HTTPException(
                status_code=500, 
                detail=f"Failed to get private key for source address: {str(e)}"
            )
        
        print(f"[TRANSFER] Step 5: Attempting transaction creation with payto method...")
        # Create a raw transaction
        # We'll use the 'payto' method which is more straightforward for simple transfers
        try:
            # Use payto method which handles the transaction creation
            print(f"[TRANSFER] Calling payto with: dest={destination_address}, amount={amount_sats/100000000.0} BTC, source={source_address}")
            tx_hex = await rpc.call("payto", [
                destination_address, 
                amount_sats / 100000000.0,  # Convert satoshis to BTC
                source_address,  # Specify the source address
                None,  # fee (set to None)
                fee_rate if fee_rate else None  # feerate (satoshis per byte)
            ])
            print(f"[TRANSFER] ✓ payto successful, got transaction hex: {tx_hex[:50]}...")
            
            print(f"[TRANSFER] Step 6: Signing transaction...")
            # Sign the transaction
            signed_tx = await rpc.call("signtransaction", [tx_hex])
            print(f"[TRANSFER] ✓ Transaction signed successfully")
            
            print(f"[TRANSFER] Step 7: Broadcasting transaction...")
            # Broadcast the transaction
            txid = await rpc.call("broadcast", [signed_tx])
            print(f"[TRANSFER] ✓ Transaction broadcast successfully! TXID: {txid}")
            
            print(f"[TRANSFER] 🎉 Transfer completed successfully!")
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
            print(f"[TRANSFER] ⚠️ payto method failed: {e}")
            raise HTTPException(
                status_code=500, 
                detail=f"payto method failed: {str(e)}"
            )
            
            # Fallback to manual transaction building if payto fails
            #print(f"[TRANSFER] Building inputs from {len(utxos)} UTXOs...")
            # Manual transaction building approach
            # This is more complex but gives us more control
            # inputs = []
            # for i, utxo in enumerate(utxos):
            #     input_data = {
            #         "txid": utxo.get("txid"),
            #         "vout": utxo.get("tx_pos", 0),
            #         "address": source_address
            #     }
            #     inputs.append(input_data)
            #     print(f"[TRANSFER] Input {i}: txid={utxo.get('txid')[:16]}..., vout={utxo.get('tx_pos', 0)}, amount={utxo.get('amount')} sats")
            
            # print(f"[TRANSFER] Creating outputs...")
            # # Create outputs
            # outputs = [
            #     {
            #         "address": destination_address,
            #         "value": amount_sats / 100000000.0  # Convert to BTC
            #     }
            # ]
            # print(f"[TRANSFER] Output 1: {destination_address} = {amount_sats} sats")
            
            # # Calculate change (if any)
            # change_amount = total_available - amount_sats
            # if change_amount > 546:  # Dust threshold
            #     outputs.append({
            #         "address": source_address,
            #         "value": change_amount / 100000000.0
            #     })
            #     print(f"[TRANSFER] Output 2 (change): {source_address} = {change_amount} sats")
            # else:
            #     print(f"[TRANSFER] No change output (amount {change_amount} sats is below dust threshold)")
            
            # print(f"[TRANSFER] Step 6b: Creating raw transaction...")
            # # Create raw transaction
            # raw_tx = await rpc.call("createrawtransaction", [inputs, outputs])
            # print(f"[TRANSFER] ✓ Raw transaction created: {raw_tx[:50]}...")
            
            # print(f"[TRANSFER] Step 7b: Signing raw transaction...")
            # # Sign the transaction
            # signed_tx = await rpc.call("signrawtransaction", [raw_tx])
            # print(f"[TRANSFER] ✓ Raw transaction signed, complete: {signed_tx.get('complete', False)}")
            
            # if not signed_tx.get("complete", False):
            #     print(f"[TRANSFER] ❌ Failed to sign transaction completely")
            #     print(f"[TRANSFER] Signing errors: {signed_tx.get('errors', [])}")
            #     raise HTTPException(
            #         status_code=500, 
            #         detail="Failed to sign transaction completely"
            #     )
            
            # print(f"[TRANSFER] Step 8b: Broadcasting signed transaction...")
            # # Broadcast the transaction
            # txid = await rpc.call("broadcast", [signed_tx.get("hex")])
            # print(f"[TRANSFER] ✓ Transaction broadcast successfully! TXID: {txid}")
            
            # print(f"[TRANSFER] 🎉 Transfer completed successfully (manual method)!")
            # return {
            #     "success": True,
            #     "txid": txid,
            #     "source_address": source_address,
            #     "destination_address": destination_address,
            #     "amount_sats": amount_sats,
            #     "fee_rate": fee_rate,
            #     "message": "Transaction broadcast successfully (manual method)"
            # }
            
    except HTTPException:
        print(f"[TRANSFER] ❌ HTTP Exception raised, re-raising...")
        raise
    except Exception as e:
        print(f"[TRANSFER] ❌ Unexpected error: {e}")
        print(f"[TRANSFER] Error type: {type(e).__name__}")
        print(f"[TRANSFER] Error details: {str(e)}")
        raise HTTPException(
            status_code=500, 
            detail=f"Failed to transfer Bitcoin: {str(e)}"
        )
