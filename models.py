from typing import Optional
from pydantic import BaseModel, HttpUrl, Field

class WatchReq(BaseModel):
    address: str
    webhook: Optional[HttpUrl] = None  # override default

class TransferReq(BaseModel):
    source_address: str = Field(..., description="Source address (Electrum-generated address to send from)")
    amount_sats: int = Field(..., gt=0, description="Amount to transfer in satoshis")
    fee_rate: Optional[int] = Field(None, gt=0, description="Fee rate in satoshis per byte (optional)")
