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

# Wallet loading lock to prevent race conditions
_wallet_loading_lock = asyncio.Lock()
_current_wallet = None

# Wallet configuration
DEPOSIT_WALLET_NAME = "default_wallet"  # Use existing default wallet as deposit wallet
WITHDRAWAL_WALLET_NAME = "withdraw_wallet_v2"

# ------------------- Operations -------------------
async def ensure_wallet_loaded(wallet_name: str):
    """Ensure the specified wallet is loaded - always unload current wallet and load requested one"""
    global _current_wallet
    
    # If the correct wallet is already loaded, return immediately
    if _current_wallet == wallet_name:
        print(f"[WALLET] Wallet '{wallet_name}' already loaded, skipping...")
        return
    
    # Use lock to prevent race conditions with multiple simultaneous calls
    async with _wallet_loading_lock:
        # Double-check after acquiring lock (another call might have loaded it)
        if _current_wallet == wallet_name:
            print(f"[WALLET] Wallet '{wallet_name}' loaded by another call, skipping...")
            return
            
        print(f"[WALLET] Loading wallet '{wallet_name}'...")
        try:
            # Always unload any currently loaded wallet first
            if _current_wallet:
                print(f"[WALLET] Unloading current wallet '{_current_wallet}'...")
                try:
                    await rpc.call("close_wallet", {})
                    print(f"[WALLET] ✓ Unloaded wallet '{_current_wallet}'")
                except Exception as unload_error:
                    print(f"[WALLET] ⚠️ Warning: Failed to unload wallet '{_current_wallet}': {unload_error}")
                    # Continue anyway, as the new wallet load might still work
            
            # Check if wallet file exists on disk
            import os
            wallet_file_path = f"/root/.electrum/wallets/{wallet_name}"
            wallet_exists_on_disk = os.path.exists(wallet_file_path)
            print(f"[WALLET] Wallet file exists on disk: {wallet_exists_on_disk} at {wallet_file_path}")
            
            # Create wallet if it doesn't exist on disk
            if not wallet_exists_on_disk:
                print(f"[WALLET] Wallet not found on disk, creating: {wallet_name}")
                
                if wallet_name == WITHDRAWAL_WALLET_NAME:
                    # Create withdrawal wallet with enhanced security
                    await create_secure_withdrawal_wallet()
                elif wallet_name == DEPOSIT_WALLET_NAME:
                    # This shouldn't happen - default wallet should always exist
                    print(f"[WALLET] ⚠️ Default wallet not found! This is unexpected.")
                    raise HTTPException(
                        status_code=500, 
                        detail=f"Default wallet ({DEPOSIT_WALLET_NAME}) not found. Please ensure Electrum is properly configured."
                    )
                else:
                    # Create regular wallet
                    await rpc.call("create", {"wallet_path": wallet_name})
                    print(f"[WALLET] ✓ Created wallet: {wallet_name}")
            else:
                print(f"[WALLET] ✓ Wallet '{wallet_name}' exists on disk, skipping creation")
            
            # Load the wallet
            print(f"[WALLET] Loading wallet: {wallet_name}")
            
            # For withdrawal wallet, we need to provide the password during load
            if wallet_name == WITHDRAWAL_WALLET_NAME:
                # Get the password from environment variable
                password = os.getenv(f"{WITHDRAWAL_WALLET_NAME.upper()}_PASSWORD")
                if not password:
                    print(f"[WALLET] ❌ No password found for withdrawal wallet in environment variables")
                    print(f"[WALLET] 🔍 Checking if wallet exists on disk...")
                    
                    # Check if wallet file exists on disk
                    wallet_file_path = f"/root/.electrum/wallets/{WITHDRAWAL_WALLET_NAME}"
                    if os.path.exists(wallet_file_path):
                        print(f"[WALLET] ⚠️ Wallet file exists but no password found!")
                        print(f"[WALLET] 💡 This means the wallet was created in a previous run but password was lost")
                        print(f"[WALLET] 🔧 Solution: Delete the existing wallet file and recreate it")
                        print(f"[WALLET] 🗑️ Deleting existing wallet file: {wallet_file_path}")
                        
                        try:
                            os.remove(wallet_file_path)
                            print(f"[WALLET] ✓ Deleted existing wallet file")
                            print(f"[WALLET] 🔄 Now creating new wallet with fresh password...")
                            
                            # Create a new wallet with a fresh password
                            await create_secure_withdrawal_wallet()
                            
                            # Get the new password
                            password = os.getenv(f"{WITHDRAWAL_WALLET_NAME.upper()}_PASSWORD")
                            if not password:
                                raise HTTPException(
                                    status_code=500, 
                                    detail="Failed to create new withdrawal wallet with password"
                                )
                        except Exception as delete_error:
                            print(f"[WALLET] ❌ Failed to delete existing wallet: {delete_error}")
                            raise HTTPException(
                                status_code=500, 
                                detail=f"Cannot load existing encrypted wallet without password. Please manually delete {wallet_file_path} and restart the application"
                            )
                    else:
                        print(f"[WALLET] 💡 Wallet doesn't exist on disk, will be created with new password")
                        # Wallet doesn't exist, create it
                        await create_secure_withdrawal_wallet()
                        password = os.getenv(f"{WITHDRAWAL_WALLET_NAME.upper()}_PASSWORD")
                        if not password:
                            raise HTTPException(
                                status_code=500, 
                                detail="Failed to create withdrawal wallet with password"
                            )
                
                print(f"[WALLET] Loading encrypted withdrawal wallet with password...")
                await rpc.call("load_wallet", {"wallet_path": wallet_name, "password": password})
            else:
                # For other wallets (like default_wallet), try without password first
                try:
                    await rpc.call("load_wallet", {"wallet_path": wallet_name, "password": None})
                except Exception as e:
                    if "InvalidPassword" in str(e):
                        print(f"[WALLET] ⚠️ Wallet requires password, but none provided for {wallet_name}")
                        raise HTTPException(
                            status_code=500, 
                            detail=f"Wallet {wallet_name} requires a password but none was provided"
                        )
                    else:
                        raise e
            
            print(f"[WALLET] ✓ Wallet loaded successfully")
            
            _current_wallet = wallet_name
            
        except Exception as e:
            print(f"[WALLET] ❌ Wallet management issue: {e}")
            raise

async def create_secure_withdrawal_wallet():
    """Create a secure withdrawal wallet with proper permissions and encryption"""
    try:
        print(f"[SECURE_WALLET] Creating secure withdrawal wallet: {WITHDRAWAL_WALLET_NAME}")
        
        # Check if wallet already exists (both in memory and on disk)
        wallets = await rpc.call("list_wallets")
        wallet_names = [wallet.get('path', '').split('/')[-1] for wallet in wallets]
        
        # Also check if wallet file exists on disk
        import os
        wallet_file_path = f"/root/.electrum/wallets/{WITHDRAWAL_WALLET_NAME}"
        wallet_exists_on_disk = os.path.exists(wallet_file_path)
        
        if WITHDRAWAL_WALLET_NAME in wallet_names or wallet_exists_on_disk:
            print(f"[SECURE_WALLET] ✓ Withdrawal wallet already exists (in memory: {WITHDRAWAL_WALLET_NAME in wallet_names}, on disk: {wallet_exists_on_disk}), skipping creation")
            return True
        
        # Create wallet with encryption enabled
        wallet_path = f"/root/.electrum/wallets/{WITHDRAWAL_WALLET_NAME}"
        
        # Generate a strong password first
        import secrets
        import string
        password = ''.join(secrets.choice(string.ascii_letters + string.digits + "!@#$%^&*") for _ in range(32))
        
        # Create the wallet with encryption enabled
        print(f"[SECURE_WALLET] Creating encrypted wallet...")
        await rpc.call("create", {"wallet_path": WITHDRAWAL_WALLET_NAME, "password": password, "encrypt_file": True})
        
        # Set proper file permissions (readable only by owner)
        import os
        import stat
        
        # Make wallet file readable only by owner (600 permissions)
        os.chmod(wallet_path, stat.S_IRUSR | stat.S_IWUSR)
        print(f"[SECURE_WALLET] ✓ Set secure file permissions (600) for {wallet_path}")
        
        # Store password securely (in production, use proper secret management)
        # Store in both memory and .env file for persistence
        import os
        os.environ[f"{WITHDRAWAL_WALLET_NAME.upper()}_PASSWORD"] = password
        
        # Also store in .env file for persistence across restarts
        env_file_path = ".env"
        env_var_name = f"{WITHDRAWAL_WALLET_NAME.upper()}_PASSWORD"
        
        # Read existing .env file
        env_content = ""
        if os.path.exists(env_file_path):
            with open(env_file_path, 'r') as f:
                env_content = f.read()
        
        # Check if the variable already exists in .env
        if f"{env_var_name}=" not in env_content:
            # Add the password to .env file
            with open(env_file_path, 'a') as f:
                f.write(f"\n# Withdrawal wallet password\n{env_var_name}={password}\n")
            print(f"[SECURE_WALLET] ✓ Password stored in .env file: {env_var_name}")
        else:
            print(f"[SECURE_WALLET] ✓ Password already exists in .env file")
        
        print(f"[SECURE_WALLET] ✓ Created secure withdrawal wallet with encryption")
        print(f"[SECURE_WALLET] ⚠️  Password stored in environment variable: {WITHDRAWAL_WALLET_NAME.upper()}_PASSWORD")
        
        return True
        
    except Exception as e:
        print(f"[SECURE_WALLET] ❌ Failed to create secure withdrawal wallet: {e}")
        raise HTTPException(
            status_code=500, 
            detail=f"Failed to create secure withdrawal wallet: {str(e)}"
        )



def reset_wallet_state():
    """Reset wallet loading state (useful for testing or if wallet needs to be reloaded)"""
    global _current_wallet
    _current_wallet = None
    print("[WALLET] Wallet state reset - next calls will reload wallet")

async def get_health_info():
    """Get electrum server info"""
    return await rpc.call("getinfo")

async def get_current_block_height():
    """Get the current block height from the electrum server"""
    info = await rpc.call("getinfo")
    return {"height": info.get("server_height")}

async def create_new_deposit_address():
    """Create a new deposit address for users to send funds to"""
    try:
        # Ensure deposit wallet is loaded
        await ensure_wallet_loaded(DEPOSIT_WALLET_NAME)
        
        # Now create the new address in the deposit wallet
        return await rpc.call("createnewaddress")
    except Exception as e:
        print(f"[ERROR] Failed to create new deposit address: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create deposit address: {str(e)}")

async def get_address_balance(address: str):
    """Get balance for a specific address (works with any wallet)"""
    try:
        # For address balance, we can use either wallet since it's just querying the blockchain
        # But we need at least one wallet loaded
        await ensure_wallet_loaded(DEPOSIT_WALLET_NAME)
        return await rpc.call("getaddressbalance", [address])
    except Exception as e:
        print(f"[ERROR] Failed to get address balance for {address}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get address balance: {str(e)}")

async def get_address_utxos(address: str, min_conf: int = 0, max_conf: int = 9999999):
    """Get UTXOs for a specific address"""
    try:
        # Ensure wallet is loaded for address operations
        await ensure_wallet_loaded(DEPOSIT_WALLET_NAME)
        # Use getaddressunspent which is the correct method for getting UTXOs for a specific address
        return await rpc.call("getaddressunspent", [address])
    except Exception as e:
        print(f"[ERROR] Failed to get address UTXOs for {address}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get address UTXOs: {str(e)}")

async def get_address_history(address: str):
    """Get complete transaction history for an address"""
    try:
        # Ensure wallet is loaded for address operations
        await ensure_wallet_loaded(DEPOSIT_WALLET_NAME)
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

def watch_address(address: str, webhook: Optional[str] = None):
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

def list_watched_addresses():
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
        await ensure_wallet_loaded(DEPOSIT_WALLET_NAME)
        print("[INFO] Wallet initialization completed")
    except Exception as e:
        print(f"[WARN] Wallet initialization failed: {e}")



async def get_wallet_balance(wallet_type: str = "deposit"):
    """Get overall wallet balance for specified wallet type"""
    print(f"[BALANCE] Getting {wallet_type} wallet balance...")
    
    try:
        wallet_name = DEPOSIT_WALLET_NAME if wallet_type == "deposit" else WITHDRAWAL_WALLET_NAME
        print(f"[BALANCE] Step 1: Ensuring {wallet_type} wallet is loaded...")
        await ensure_wallet_loaded(wallet_name)
        print(f"[BALANCE] ✓ {wallet_type} wallet loaded successfully")
        
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

async def withdraw_bitcoin_to_address(recipient_address: str, amount_sats: int, fee_rate: Optional[int] = None):
    """Withdraw Bitcoin from withdrawal wallet to a specific address"""
    print(f"[WITHDRAW] Starting withdrawal: {recipient_address}, amount: {amount_sats} sats, fee_rate: {fee_rate}")
    
    try:
        # Step 1: Ensure withdrawal wallet is loaded
        print(f"[WITHDRAW] Step 1: Ensuring withdrawal wallet is loaded...")
        await ensure_wallet_loaded(WITHDRAWAL_WALLET_NAME)
        print(f"[WITHDRAW] ✓ Withdrawal wallet loaded successfully")
        
        # Step 2: Check wallet balance
        print(f"[WITHDRAW] Step 2: Checking withdrawal wallet balance...")
        balance_result = await rpc.call("getbalance")
        print(f"[WITHDRAW] Raw balance result: {balance_result}")
        
        # Handle different balance formats
        if isinstance(balance_result, dict):
            confirmed_balance = balance_result.get("confirmed", 0)
            # If confirmed balance is a string (like "0.00002"), convert it
            if isinstance(confirmed_balance, str):
                total_balance = float(confirmed_balance)
                # Convert BTC to satoshis (multiply by 100,000,000)
                total_balance = int(total_balance * 100000000)
            else:
                total_balance = int(confirmed_balance) if confirmed_balance else 0
        elif isinstance(balance_result, str):
            # If balance is returned as string like "0.00002 sats", extract the number
            import re
            balance_match = re.search(r'(\d+\.?\d*)', balance_result)
            if balance_match:
                total_balance = float(balance_match.group(1))
                # Convert to satoshis if it's in BTC
                if 'btc' in balance_result.lower() or total_balance < 1:
                    total_balance = int(total_balance * 100000000)  # Convert BTC to sats
                else:
                    total_balance = int(total_balance)
            else:
                total_balance = 0
        else:
            total_balance = int(balance_result) if balance_result else 0
            
        print(f"[WITHDRAW] ✓ Current balance: {total_balance} sats")
        
        # Step 3: Calculate required amount (amount + estimated fee)
        estimated_fee = 300  # Conservative estimate in sats
        required_amount = amount_sats + estimated_fee
        print(f"[WITHDRAW] Step 3: Calculating required amount...")
        print(f"[WITHDRAW] Amount to send: {amount_sats} sats")
        print(f"[WITHDRAW] Estimated fee: {estimated_fee} sats")
        print(f"[WITHDRAW] Required total: {required_amount} sats")
        
        # Step 4: Check if we have enough balance
        print(f"[WITHDRAW] Step 4: Checking sufficient balance...")
        print(f"[WITHDRAW] Available: {total_balance} sats (type: {type(total_balance)})")
        print(f"[WITHDRAW] Required: {required_amount} sats (type: {type(required_amount)})")
        
        if total_balance < required_amount:
            print(f"[WITHDRAW] ❌ Insufficient balance!")
            print(f"[WITHDRAW] Shortfall: {required_amount - total_balance} sats")
            raise HTTPException(
                status_code=400,
                detail=f"Insufficient balance. Available: {total_balance} sats, Required: {required_amount} sats"
            )
        
        print(f"[WITHDRAW] ✓ Sufficient balance available")
        
        # Step 5: Create and send transaction
        print(f"[WITHDRAW] Step 4: Creating transaction...")
        
        # Use payto method for transaction creation
        if fee_rate:
            print(f"[WITHDRAW] Using fee rate: {fee_rate} sats/byte")
            result = await rpc.call("payto", {
                "destination": recipient_address,
                "amount": amount_sats,
                "fee": None,
                "feerate": fee_rate
            })
        else:
            print(f"[WITHDRAW] Using default fee rate")
            result = await rpc.call("payto", {
                "destination": recipient_address,
                "amount": amount_sats,
                "fee": None,
                "feerate": None
            })
        
        print(f"[WITHDRAW] ✓ Transaction created successfully")
        
        # Step 6: Sign the transaction
        print(f"[WITHDRAW] Step 5: Signing transaction...")
        signed_result = await rpc.call("signtransaction", {"tx": result})
        print(f"[WITHDRAW] ✓ Transaction signed successfully")
        
        # Step 7: Broadcast the transaction
        print(f"[WITHDRAW] Step 6: Broadcasting transaction...")
        broadcast_result = await rpc.call("broadcast", {"tx": signed_result})
        tx_id = broadcast_result
        print(f"[WITHDRAW] ✓ Transaction broadcasted successfully")
        print(f"[WITHDRAW] Transaction ID: {tx_id}")
        
        # Step 8: Return success response
        return {
            "success": True,
            "transaction_id": tx_id,
            "recipient_address": recipient_address,
            "amount_sats": amount_sats,
            "fee_rate": fee_rate,
            "message": f"Successfully sent {amount_sats} sats to {recipient_address}"
        }
        
    except Exception as e:
        print(f"[WITHDRAW] ❌ Unexpected error: {e}")
        print(f"[WITHDRAW] Error type: {type(e).__name__}")
        print(f"[WITHDRAW] Error details: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to withdraw Bitcoin: {str(e)}"
        )

async def transfer_bitcoin_to_cold_storage(fee_rate: Optional[int] = None):
    """Transfer 70% of withdrawal wallet balance to cold storage address"""
    try:
        cold_wallet_address = "bc1q0pspp7zafe6qakrasugxsm49k2vfwa78xyvhnx"
        print(f"[COLD_STORAGE] Step 1: Ensuring withdrawal wallet is loaded...")
        await ensure_wallet_loaded(WITHDRAWAL_WALLET_NAME)
        print(f"[COLD_STORAGE] ✓ Withdrawal wallet loaded successfully")
        
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
