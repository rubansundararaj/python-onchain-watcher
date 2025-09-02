from typing import Optional
from pydantic import BaseModel, HttpUrl, Field

class WatchReq(BaseModel):
    address: str
    webhook: Optional[HttpUrl] = None  # override default

class TransferReq(BaseModel):
    fee_rate: Optional[int] = Field(None, gt=0, description="Fee rate in satoshis per byte (optional)")

class WithdrawReq(BaseModel):
    recipient_address: str = Field(..., description="Bitcoin address to send funds to")
    amount_sats: int = Field(..., gt=0, description="Amount to send in satoshis")
    fee_rate: Optional[int] = Field(None, gt=0, description="Fee rate in satoshis per byte (optional)")
