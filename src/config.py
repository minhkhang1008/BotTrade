"""
Bot Trade - Configuration Management
"""
from pydantic import Field
from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # DNSE Configuration
    # Username: Email hoặc Số điện thoại hoặc Số lưu ký
    dnse_username: str = Field(default="", alias="DNSE_USERNAME")
    # Password: Mật khẩu DNSE
    dnse_password: str = Field(default="", alias="DNSE_PASSWORD")
    # MQTT WebSocket URL (theo doc DNSE: datafeed-lts-krx.dnse.com.vn:443/wss)
    dnse_mqtt_url: str = Field(
        default="wss://datafeed-lts-krx.dnse.com.vn/wss",
        alias="DNSE_MQTT_URL"
    )
    
    # Watchlist
    watchlist: str = Field(default="VNM,FPT,VIC", alias="WATCHLIST")
    
    # Timeframe
    timeframe: str = Field(default="1H", alias="TIMEFRAME")
    
    # Indicator Settings
    rsi_period: int = Field(default=14, alias="RSI_PERIOD")
    macd_fast: int = Field(default=12, alias="MACD_FAST")
    macd_slow: int = Field(default=26, alias="MACD_SLOW")
    macd_signal: int = Field(default=9, alias="MACD_SIGNAL")
    atr_period: int = Field(default=14, alias="ATR_PERIOD")
    
    # Zone & Risk Settings
    zone_width_atr_multiplier: float = Field(
        default=0.2,
        alias="ZONE_WIDTH_ATR_MULTIPLIER"
    )
    sl_buffer_atr_multiplier: float = Field(
        default=0.05,
        alias="SL_BUFFER_ATR_MULTIPLIER"
    )
    risk_reward_ratio: float = Field(default=2.0, alias="RISK_REWARD_RATIO")
    default_quantity: int = Field(default=100, alias="DEFAULT_QUANTITY")
    
    # Server Settings
    host: str = Field(default="0.0.0.0", alias="HOST")
    port: int = Field(default=8000, alias="PORT")
    
    # Database
    database_url: str = Field(
        default="sqlite+aiosqlite:///./bottrade.db",
        alias="DATABASE_URL"
    )
    
    # Auto-trade Settings
    auto_trade_enabled: bool = Field(default=False, alias="AUTO_TRADE_ENABLED")
    dnse_account_no: str = Field(default="", alias="DNSE_ACCOUNT_NO")
    
    # Backtest Settings
    backtest_initial_capital: float = Field(
        default=100_000_000,
        alias="BACKTEST_INITIAL_CAPITAL"
    )
    backtest_position_size_percent: float = Field(
        default=10.0,
        alias="BACKTEST_POSITION_SIZE_PERCENT"
    )
    
    @property
    def watchlist_symbols(self) -> List[str]:
        """Return watchlist as a list of symbols."""
        return [s.strip().upper() for s in self.watchlist.split(",") if s.strip()]
    
    @property
    def trading_configured(self) -> bool:
        """Check if trading is properly configured."""
        return bool(self.dnse_username and self.dnse_password and self.dnse_account_no)
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


# Global settings instance
settings = Settings()
