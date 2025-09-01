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



async def get_wallet_balance():
    """Get overall wallet balance"""
    print(f"[BALANCE] Getting overall wallet balance...")
    
    try:
        print(f"[BALANCE] Step 1: Ensuring wallet is loaded...")
        await ensure_wallet_loaded()
        print(f"[BALANCE] ✓ Wallet loaded successfully")
        
        print(f"[BALANCE] Step 2: Getting wallet balance...")
        balance = await rpc.call("getbalance")
        print(f"[BALANCE] ✓ Got balance: {balance}")
        
        # Parse the balance response
        confirmed_balance = balance.get("confirmed", "0")
        unconfirmed_balance = balance.get("unconfirmed", "0")
        
        # Convert to satoshis for consistency
        confirmed_sats = int(float(confirmed_balance) * 100000000)
        unconfirmed_sats = int(float(unconfirmed_balance) * 100000000)
        total_sats = confirmed_sats + unconfirmed_sats
        
        print(f"[BALANCE] ✓ Balance parsed successfully")
        print(f"[BALANCE]   Confirmed: {confirmed_sats} sats ({confirmed_balance} BTC)")
        print(f"[BALANCE]   Unconfirmed: {unconfirmed_sats} sats ({unconfirmed_balance} BTC)")
        print(f"[BALANCE]   Total: {total_sats} sats ({float(confirmed_balance) + float(unconfirmed_balance)} BTC)")
        
        return {
            "success": True,
            "balance": {
                "confirmed_btc": confirmed_balance,
                "unconfirmed_btc": unconfirmed_balance,
                "total_btc": str(float(confirmed_balance) + float(unconfirmed_balance)),
                "confirmed_sats": confirmed_sats,
                "unconfirmed_sats": unconfirmed_sats,
                "total_sats": total_sats
            },
            "message": "Wallet balance retrieved successfully"
        }
        
    except Exception as e:
        print(f"[BALANCE] ❌ Error getting wallet balance: {e}")
        print(f"[BALANCE] Error type: {type(e).__name__}")
        print(f"[BALANCE] Error details: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get wallet balance: {str(e)}"
        )

async def transfer_bitcoin_to_cold_storage(fee_rate: Optional[int] = None):
    """Transfer 70% of wallet balance to cold storage address"""
    print(f"[COLD_STORAGE] Starting cold storage transfer to: {cold_wallet_address}")
    
    try:
        cold_wallet_address = "bc1q0pspp7zafe6qakrasugxsm49k2vfwa78xyvhnx"
        print(f"[COLD_STORAGE] Step 1: Ensuring wallet is loaded...")
        await ensure_wallet_loaded()
        print(f"[COLD_STORAGE] ✓ Wallet loaded successfully")
        
        print(f"[COLD_STORAGE] Step 2: Getting overall wallet balance...")
        # Get the overall wallet balance
        balance_response = await rpc.call("getbalance")
        print(f"[COLD_STORAGE] ✓ Got balance response: {balance_response}")
        
        # Parse the balance
        confirmed_balance = balance_response.get("confirmed", "0")
        unconfirmed_balance = balance_response.get("unconfirmed", "0")
        
        # Convert to satoshis
        confirmed_sats = int(float(confirmed_balance) * 100000000)
        unconfirmed_sats = int(float(unconfirmed_balance) * 100000000)
        total_sats = confirmed_sats + unconfirmed_sats
        
        print(f"[COLD_STORAGE] ✓ Balance parsed:")
        print(f"[COLD_STORAGE]   Confirmed: {confirmed_sats} sats ({confirmed_balance} BTC)")
        print(f"[COLD_STORAGE]   Unconfirmed: {unconfirmed_sats} sats ({unconfirmed_balance} BTC)")
        print(f"[COLD_STORAGE]   Total: {total_sats} sats")
        
        if total_sats == 0:
            print(f"[COLD_STORAGE] ❌ No funds available for transfer")
            raise HTTPException(
                status_code=400,
                detail="No funds available in wallet for cold storage transfer"
            )
        
        # Calculate 70% of total balance
        transfer_amount_sats = int(total_sats * 0.7)
        print(f"[COLD_STORAGE] Step 3: Calculating transfer amount...")
        print(f"[COLD_STORAGE] ✓ Transfer amount: {transfer_amount_sats} sats (70% of {total_sats} sats)")
        
        # Check if we have enough confirmed balance for the transfer
        if confirmed_sats < transfer_amount_sats:
            print(f"[COLD_STORAGE] ⚠️ Warning: Not enough confirmed balance for full transfer")
            print(f"[COLD_STORAGE]   Confirmed: {confirmed_sats} sats, Required: {transfer_amount_sats} sats")
            print(f"[COLD_STORAGE]   Using available confirmed balance instead")
            transfer_amount_sats = confirmed_sats
        
        if transfer_amount_sats < 1000:  # Minimum 1000 sats (dust threshold)
            print(f"[COLD_STORAGE] ❌ Transfer amount too small: {transfer_amount_sats} sats")
            raise HTTPException(
                status_code=400,
                detail=f"Transfer amount too small: {transfer_amount_sats} sats (minimum 1000 sats)"
            )
        
        print(f"[COLD_STORAGE] Step 4: Using payto method for transfer...")
        print(f"[COLD_STORAGE]   Destination: {cold_wallet_address}")
        print(f"[COLD_STORAGE]   Amount: {transfer_amount_sats} sats ({transfer_amount_sats / 100000000.0} BTC)")
        print(f"[COLD_STORAGE]   Fee rate: {fee_rate}")
        
        # Use payto method to create the transaction
        # Convert satoshis to BTC for payto
        amount_btc = transfer_amount_sats / 100000000.0
        
        try:
            # Create the transaction using payto
            if fee_rate:
                tx_hex = await rpc.call("payto", [cold_wallet_address, amount_btc, None, fee_rate])
                print(f"[COLD_STORAGE] ✓ payto successful with fee_rate {fee_rate}, got transaction hex: {tx_hex[:50]}...")
            else:
                tx_hex = await rpc.call("payto", [cold_wallet_address, amount_btc])
                print(f"[COLD_STORAGE] ✓ payto successful with default fee, got transaction hex: {tx_hex[:50]}...")
            
            print(f"[COLD_STORAGE] Step 5: Signing transaction...")
            # Sign the transaction
            signed_tx = await rpc.call("signtransaction", [tx_hex])
            print(f"[COLD_STORAGE] ✓ Transaction signed successfully")
            
            print(f"[COLD_STORAGE] Step 6: Broadcasting transaction...")
            # Broadcast the transaction
            txid = await rpc.call("broadcast", [signed_tx])
            print(f"[COLD_STORAGE] ✓ Transaction broadcast successfully! TXID: {txid}")
            
            print(f"[COLD_STORAGE] 🎉 Cold storage transfer completed successfully!")
            return {
                "success": True,
                "txid": txid,
                "cold_wallet_address": cold_wallet_address,
                "transfer_amount_sats": transfer_amount_sats,
                "transfer_amount_btc": amount_btc,
                "original_balance_sats": total_sats,
                "original_balance_btc": float(confirmed_balance) + float(unconfirmed_balance),
                "fee_rate": fee_rate,
                "message": f"Successfully transferred {transfer_amount_sats} sats ({amount_btc} BTC) to cold storage"
            }
            
        except Exception as payto_error:
            print(f"[COLD_STORAGE] ❌ payto method failed: {payto_error}")
            print(f"[COLD_STORAGE] Error type: {type(payto_error).__name__}")
            print(f"[COLD_STORAGE] Error details: {str(payto_error)}")
            
            # Fallback: Try paytomany method
            print(f"[COLD_STORAGE] Trying fallback with paytomany...")
            try:
                # Use paytomany with the cold wallet as destination
                paytomany_outputs = {
                    cold_wallet_address: amount_btc
                }
                
                if fee_rate:
                    tx_hex = await rpc.call("paytomany", [paytomany_outputs, None, fee_rate])
                    print(f"[COLD_STORAGE] ✓ paytomany successful with fee_rate {fee_rate}: {tx_hex[:50]}...")
                else:
                    tx_hex = await rpc.call("paytomany", [paytomany_outputs])
                    print(f"[COLD_STORAGE] ✓ paytomany successful with default fee: {tx_hex[:50]}...")
                
                # Broadcast directly (paytomany already signs)
                txid = await rpc.call("broadcast", [tx_hex])
                print(f"[COLD_STORAGE] ✓ Transaction broadcast successfully! TXID: {txid}")
                
                print(f"[COLD_STORAGE] 🎉 Cold storage transfer completed with paytomany!")
                return {
                    "success": True,
                    "txid": txid,
                    "cold_wallet_address": cold_wallet_address,
                    "transfer_amount_sats": transfer_amount_sats,
                    "transfer_amount_btc": amount_btc,
                    "original_balance_sats": total_sats,
                    "original_balance_btc": float(confirmed_balance) + float(unconfirmed_balance),
                    "fee_rate": fee_rate,
                    "message": f"Successfully transferred {transfer_amount_sats} sats ({amount_btc} BTC) to cold storage using paytomany"
                }
                
            except Exception as paytomany_error:
                print(f"[COLD_STORAGE] ❌ paytomany also failed: {paytomany_error}")
                raise HTTPException(
                    status_code=500,
                    detail=f"Both payto and paytomany methods failed. payto: {str(payto_error)}, paytomany: {str(paytomany_error)}"
                )
            
    except HTTPException:
        print(f"[COLD_STORAGE] ❌ HTTP Exception raised, re-raising...")
        raise
    except Exception as e:
        print(f"[COLD_STORAGE] ❌ Unexpected error: {e}")
        print(f"[COLD_STORAGE] Error type: {type(e).__name__}")
        print(f"[COLD_STORAGE] Error details: {str(e)}")
        raise HTTPException(
            status_code=500, 
            detail=f"Failed to transfer to cold storage: {str(e)}"
        )
