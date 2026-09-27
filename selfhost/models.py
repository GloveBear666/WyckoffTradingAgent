from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class AnalysisRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    exchange: Literal["okx", "binance", "bybit"] = "okx"
    symbol: str = Field(default="BTC/USDT", min_length=3, max_length=50)
    market: Literal["spot", "swap"] = "spot"
    timeframe: Literal["15m", "1h", "4h", "1d"] = "1d"
    limit: int = Field(default=320, ge=100, le=500)


class Message(BaseModel):
    model_config = ConfigDict(extra="forbid")
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=12000)


class ChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    messages: list[Message] = Field(min_length=1, max_length=20)
    context: AnalysisRequest = Field(default_factory=AnalysisRequest)
