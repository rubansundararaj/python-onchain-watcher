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
#   POST   /withdraw                        -> withdraw bitcoin from withdrawal wallet
#   GET    /wallet/balance                  -> electrum.getbalance
#   POST   /deposit/address                 -> create new deposit address
#   GET    /deposit/balance                 -> get deposit wallet balance
#   GET    /withdraw/balance                -> get withdrawal wallet balance
#   POST   /withdraw/address                -> create new withdrawal address
#   POST   /withdraw/to-address             -> withdraw funds to specific address
#   POST   /withdraw/process                -> process withdrawal to cold storage
#   GET    /wallets/status                  -> get wallet status information
#   GET    /wallets/history                 -> get wallet transaction history
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
from datetime import timedelta
from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.middleware.cors import CORSMiddleware
import os
from dotenv import load_dotenv

# Load environment variables at module import time
load_dotenv()

from operations import (
    get_health_info,
    get_address_balance,
    get_address_utxos,
    get_address_history,
    get_wallet_history,
    get_transaction_details,
    watch_address,
    list_watched_addresses,
    watcher_loop,
    cleanup,
    get_current_block_height,
    startup,
    transfer_bitcoin_to_cold_storage,
    withdraw_bitcoin_to_address,
    get_wallet_balance,
    create_new_deposit_address,
    DEPOSIT_WALLET_NAME,
    WITHDRAWAL_WALLET_NAME
)
from models import WatchReq, TransferReq, WithdrawReq, LoginRequest, TokenResponse
from auth import authenticate_user, create_access_token, get_current_active_user, ACCESS_TOKEN_EXPIRE_MINUTES

app = FastAPI(title="Electrum RPC REST Wrapper", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# ------------------- Authentication Endpoints -------------------
@app.post("/login", response_model=TokenResponse)
async def login(login_data: LoginRequest):
    """Authenticate user and return JWT token"""
    user = authenticate_user(login_data.username, login_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user["username"]}, expires_delta=access_token_expires
    )
    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60
    )

# ------------------- Protected Endpoints -------------------
@app.get("/health")
async def health(current_user: dict = Depends(get_current_active_user)):
    """Get electrum server health info"""
    return await get_health_info()

@app.get("/block-height")
async def current_block_height(current_user: dict = Depends(get_current_active_user)):
    """Get the current block height from the electrum server"""
    return await get_current_block_height()

@app.post("/addresses")
async def create_address(current_user: dict = Depends(get_current_active_user)):
    """Create a new address"""
    addr = await create_new_deposit_address()
    return {"address": addr}

@app.get("/addresses/{address}/balance")
async def address_balance(address: str, current_user: dict = Depends(get_current_active_user)):
    """Get balance for a specific address"""
    bal = await get_address_balance(address)
    # returns {"confirmed": sats, "unconfirmed": sats}
    return bal

@app.get("/addresses/{address}/utxos")
async def address_utxos(address: str, min_conf: int = 0, max_conf: int = 9999999, current_user: dict = Depends(get_current_active_user)):
    """Get UTXOs for a specific address"""
    utxos = await get_address_utxos(address, min_conf, max_conf)
    return {"address": address, "utxos": utxos}

@app.get("/addresses/{address}/history")
async def address_history(address: str, current_user: dict = Depends(get_current_active_user)):
    """Get complete transaction history for an address"""
    history = await get_address_history(address)
    return {"address": address, "history": history}

@app.get("/transactions/{txid}")
async def transaction_details(txid: str, current_user: dict = Depends(get_current_active_user)):
    """Get full transaction details by transaction ID"""
    tx = await get_transaction_details(txid)
    return {"txid": txid, "transaction": tx}

@app.post("/watch")
async def watch_address_endpoint(req: WatchReq, current_user: dict = Depends(get_current_active_user)):
    """Start watching an address for changes"""
    webhook_url = str(req.webhook) if req.webhook else None
    return watch_address(req.address, webhook_url)

@app.get("/watch")
async def list_watch(current_user: dict = Depends(get_current_active_user)):
    """List all watched addresses"""
    return list_watched_addresses()

@app.post("/transfer")
async def transfer_bitcoin_endpoint(req: TransferReq, current_user: dict = Depends(get_current_active_user)):
    """Transfer Bitcoin from a source address to a destination address"""
    print(f"[ENDPOINT] /transfer called with request:")
    print(f"[ENDPOINT]   fee_rate: {req.fee_rate}")
    
    try:
        print(f"[ENDPOINT] Calling transfer_bitcoin function...")
        result = await transfer_bitcoin_to_cold_storage(
            req.fee_rate
        )
        print(f"[ENDPOINT] ✓ Transfer completed successfully, returning result")
        return result
    except Exception as e:
        print(f"[ENDPOINT] ❌ Error in transfer endpoint: {e}")
        print(f"[ENDPOINT] Error type: {type(e).__name__}")
        
        # Send Telegram notification for transfer endpoint errors
        try:
            from telegram_bot import send_telegram_error
            error_context = f"Transfer endpoint error - fee_rate: {req.fee_rate}"
            await send_telegram_error(str(e), error_context)
        except Exception as telegram_error:
            print(f"[ENDPOINT] ⚠️ Failed to send Telegram notification: {telegram_error}")
        
        raise

@app.post("/withdraw-on-chain")
async def withdraw_bitcoin_endpoint(req: WithdrawReq, current_user: dict = Depends(get_current_active_user)):
    """Withdraw Bitcoin from withdrawal wallet to a specific address"""
    print(f"[ENDPOINT] /withdraw called with request:")
    print(f"[ENDPOINT]   recipient_address: {req.recipient_address}")
    print(f"[ENDPOINT]   amount_sats: {req.amount_sats}")
    print(f"[ENDPOINT]   fee_rate: {req.fee_rate}")
    
    try:
        print(f"[ENDPOINT] Calling withdraw_bitcoin_to_address function...")
        result = await withdraw_bitcoin_to_address(
            req.recipient_address,
            req.amount_sats,
            req.fee_rate
        )
        print(f"[ENDPOINT] ✓ Withdrawal completed successfully, returning result")
        return result
    except Exception as e:
        print(f"[ENDPOINT] ❌ Error in withdraw endpoint: {e}")
        print(f"[ENDPOINT] Error type: {type(e).__name__}")
        
        # Send Telegram notification for endpoint errors
        try:
            from telegram_bot import send_telegram_error
            error_context = f"Withdraw endpoint error - {req.recipient_address}, {req.amount_sats} sats"
            await send_telegram_error(str(e), error_context)
        except Exception as telegram_error:
            print(f"[ENDPOINT] ⚠️ Failed to send Telegram notification: {telegram_error}")
        
        raise


@app.get("/wallet/balance")
async def get_wallet_balance_endpoint(current_user: dict = Depends(get_current_active_user)):
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

# ------------------- Deposit Wallet Endpoints -------------------
@app.post("/deposit/address")
async def create_deposit_address(current_user: dict = Depends(get_current_active_user)):
    """Create a new deposit address for users to send funds to"""
    print(f"[ENDPOINT] /deposit/address called")
    
    try:
        print(f"[ENDPOINT] Calling create_new_deposit_address function...")
        address = await create_new_deposit_address()
        print(f"[ENDPOINT] ✓ Deposit address created successfully: {address}")
        return {"address": address, "wallet": DEPOSIT_WALLET_NAME}
    except Exception as e:
        print(f"[ENDPOINT] ❌ Error in deposit address endpoint: {e}")
        print(f"[ENDPOINT] Error type: {type(e).__name__}")
        raise

@app.get("/deposit/balance")
async def get_deposit_balance(current_user: dict = Depends(get_current_active_user)):
    """Get deposit wallet balance"""
    print(f"[ENDPOINT] /deposit/balance called")
    
    try:
        print(f"[ENDPOINT] Calling get_wallet_balance function for deposit wallet...")
        result = await get_wallet_balance("deposit")
        print(f"[ENDPOINT] ✓ Deposit wallet balance retrieved successfully")
        return {"wallet": DEPOSIT_WALLET_NAME, "balance": result}
    except Exception as e:
        print(f"[ENDPOINT] ❌ Error in deposit balance endpoint: {e}")
        print(f"[ENDPOINT] Error type: {type(e).__name__}")
        raise

# ------------------- Withdrawal Wallet Endpoints -------------------
@app.get("/withdraw/balance")
async def get_withdrawal_balance(current_user: dict = Depends(get_current_active_user)):
    """Get withdrawal wallet balance"""
    print(f"[ENDPOINT] /withdraw/balance called")
    
    try:
        print(f"[ENDPOINT] Calling get_wallet_balance function for withdrawal wallet...")
        result = await get_wallet_balance("withdrawal")
        print(f"[ENDPOINT] ✓ Withdrawal wallet balance retrieved successfully")
        return {"wallet": WITHDRAWAL_WALLET_NAME, "balance": result}
    except Exception as e:
        print(f"[ENDPOINT] ❌ Error in withdrawal balance endpoint: {e}")
        print(f"[ENDPOINT] Error type: {type(e).__name__}")
        raise



@app.post("/withdraw/address")
async def create_withdrawal_address(current_user: dict = Depends(get_current_active_user)):
    """Create a new withdrawal address for users to receive funds"""
    print(f"[ENDPOINT] /withdraw/address called")
    
    try:
        print(f"[ENDPOINT] Calling create_new_deposit_address function for withdrawal wallet...")
        # We can reuse the same function but ensure it uses the withdrawal wallet
        from operations import ensure_wallet_loaded, rpc
        await ensure_wallet_loaded(WITHDRAWAL_WALLET_NAME)
        address = await rpc.call("createnewaddress", {})
        print(f"[ENDPOINT] ✓ Withdrawal address created successfully: {address}")
        return {"address": address, "wallet": WITHDRAWAL_WALLET_NAME}
    except Exception as e:
        print(f"[ENDPOINT] ❌ Error in withdrawal address endpoint: {e}")
        print(f"[ENDPOINT] Error type: {type(e).__name__}")
        raise

@app.post("/withdraw/to-address")
async def withdraw_to_address(request: dict, current_user: dict = Depends(get_current_active_user)):
    """Withdraw funds from withdrawal wallet to a specific address"""
    print(f"[ENDPOINT] /withdraw/to-address called")
    
    try:
        destination_address = request.get("address")
        amount_sats = request.get("amount_sats")
        fee_rate = request.get("fee_rate", 2)
        
        if not destination_address:
            raise HTTPException(status_code=400, detail="Missing 'address' parameter")
        if not amount_sats:
            raise HTTPException(status_code=400, detail="Missing 'amount_sats' parameter")
        
        print(f"[ENDPOINT] Withdrawing {amount_sats} sats to {destination_address} with fee_rate {fee_rate}")
        
        # Ensure withdrawal wallet is loaded
        from operations import ensure_wallet_loaded, rpc
        await ensure_wallet_loaded(WITHDRAWAL_WALLET_NAME)
        
        # Use payto method for withdrawal
        result = await rpc.call("payto", {
            "destination": destination_address,
            "amount": amount_sats / 100000000,  # Convert sats to BTC
            "feerate": fee_rate
        })
        
        print(f"[ENDPOINT] ✓ Withdrawal transaction created successfully")
        return {
            "wallet": WITHDRAWAL_WALLET_NAME,
            "destination": destination_address,
            "amount_sats": amount_sats,
            "fee_rate": fee_rate,
            "transaction": result
        }
    except Exception as e:
        print(f"[ENDPOINT] ❌ Error in withdraw to address endpoint: {e}")
        print(f"[ENDPOINT] Error type: {type(e).__name__}")
        raise

@app.post("/withdraw/process")
async def process_withdrawal(current_user: dict = Depends(get_current_active_user)):
    """Process withdrawal to cold storage (70% of withdrawal wallet balance)"""
    print(f"[ENDPOINT] /withdraw/process called")
    
    try:
        print(f"[ENDPOINT] Calling transfer_bitcoin_to_cold_storage function...")
        result = await transfer_bitcoin_to_cold_storage()
        print(f"[ENDPOINT] ✓ Withdrawal processed successfully")
        return {"wallet": WITHDRAWAL_WALLET_NAME, "result": result}
    except Exception as e:
        print(f"[ENDPOINT] ❌ Error in withdrawal process endpoint: {e}")
        print(f"[ENDPOINT] Error type: {type(e).__name__}")
        raise

# ------------------- Wallet Management Endpoints -------------------
@app.get("/wallets/status")
async def get_wallets_status(current_user: dict = Depends(get_current_active_user)):
    """Get status of both deposit and withdrawal wallets"""
    print(f"[ENDPOINT] /wallets/status called")
    
    try:
        from operations import rpc
        wallets = await rpc.call("list_wallets")
        
        status = {
            "deposit_wallet": {
                "name": DEPOSIT_WALLET_NAME,
                "exists": DEPOSIT_WALLET_NAME in wallets,
                "path": f"/root/.electrum/wallets/{DEPOSIT_WALLET_NAME}"
            },
            "withdrawal_wallet": {
                "name": WITHDRAWAL_WALLET_NAME,
                "exists": WITHDRAWAL_WALLET_NAME in wallets,
                "path": f"/root/.electrum/wallets/{WITHDRAWAL_WALLET_NAME}",
                "encrypted": bool(os.environ.get("WITHDRAW_WALLET_V2_PASSWORD"))
            }
        }
        
        print(f"[ENDPOINT] ✓ Wallet status retrieved successfully")
        return status
    except Exception as e:
        print(f"[ENDPOINT] ❌ Error in wallet status endpoint: {e}")
        print(f"[ENDPOINT] Error type: {type(e).__name__}")
        raise

@app.get("/wallets/history")
async def get_wallets_history(wallet_type: str = "deposit", current_user: dict = Depends(get_current_active_user)):
    """Get transaction history for a wallet (deposit or withdrawal)"""
    print(f"[ENDPOINT] /wallets/history called with wallet_type: {wallet_type}")
    
    try:
        print(f"[ENDPOINT] Calling get_wallet_history function...")
        result = await get_wallet_history(wallet_type)
        print(f"[ENDPOINT] ✓ Wallet history retrieved successfully")
        return result
    except Exception as e:
        print(f"[ENDPOINT] ❌ Error in wallet history endpoint: {e}")
        print(f"[ENDPOINT] Error type: {type(e).__name__}")
        raise

# ------------------- Background watcher -------------------
@app.on_event("startup")
async def _startup():
    """Start the background watcher loop"""
    # Initialize wallet and other resources
    await startup()
    # Start the background watcher loop
    watcher_task = asyncio.create_task(watcher_loop())
    # Store the task to prevent garbage collection
    app.state.watcher_task = watcher_task

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
