from typing import Optional
from pydantic import BaseModel, HttpUrl

class WatchReq(BaseModel):
    address: str
    webhook: Optional[HttpUrl] = None  # override default
