"""
Bot Trade - DNSE Trading Service
Handles authentication, order placement, account management
"""
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field
from enum import Enum

import httpx

logger = logging.getLogger(__name__)


class OrderSide(str, Enum):
    """Order side."""
    BUY = "NB"   # Mua
    SELL = "NS"  # Bán


class OrderType(str, Enum):
    """Order type."""
    LO = "LO"    # Limit Order
    MP = "MP"    # Market Price
    ATO = "ATO"  # At The Open
    ATC = "ATC"  # At The Close
    MTL = "MTL"  # Market To Limit
    MOK = "MOK"  # Match Or Kill
    MAK = "MAK"  # Match And Kill


class OrderStatus(str, Enum):
    """Order status."""
    PENDING = "PENDING"
    FILLED = "FILLED"
    PARTIAL = "PARTIAL"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"


@dataclass
class Account:
    """Trading account."""
    id: str
    name: str = ""
    type: str = ""


@dataclass
class LoanPackage:
    """Loan package for margin trading."""
    id: int
    name: str
    type: str = ""


@dataclass
class AccountBalance:
    """Account balance information."""
    account_no: str
    cash_balance: float = 0.0
    buying_power: float = 0.0
    withdrawable: float = 0.0


@dataclass
class Order:
    """Order information."""
    id: str
    symbol: str
    side: OrderSide
    order_type: OrderType
    price: float
    quantity: int
    filled_quantity: int = 0
    status: str = ""
    account_no: str = ""
    created_at: Optional[datetime] = None


@dataclass
class TokenManager:
    """Manages JWT and Trading tokens."""
    jwt_token: Optional[str] = None
    jwt_expires: Optional[datetime] = None
    trading_token: Optional[str] = None
    trading_token_expires: Optional[datetime] = None
    
    def is_jwt_valid(self) -> bool:
        """Check if JWT token is still valid."""
        if not self.jwt_token or not self.jwt_expires:
            return False
        return datetime.now() < self.jwt_expires - timedelta(minutes=5)
    
    def is_trading_token_valid(self) -> bool:
        """Check if trading token is still valid."""
        if not self.trading_token or not self.trading_token_expires:
            return False
        return datetime.now() < self.trading_token_expires - timedelta(minutes=5)


class TradingService:
    """
    DNSE Trading Service.
    
    Handles:
    - Authentication (JWT + Trading Token)
    - Account management
    - Order placement and cancellation
    """
    
    BASE_URL = "https://api.dnse.com.vn"
    TOKEN_VALIDITY_HOURS = 8
    
    def __init__(
        self,
        username: str,
        password: str,
        account_no: Optional[str] = None
    ):
        self.username = username
        self.password = password
        self.account_no = account_no
        
        self.tokens = TokenManager()
        self.accounts: List[Account] = []
        self.loan_packages: List[LoanPackage] = []
        self.default_loan_package_id: Optional[int] = None
        
        self._client = httpx.AsyncClient(timeout=30.0)
    
    async def close(self):
        """Close HTTP client."""
        await self._client.aclose()
    
    # ============ Authentication ============
    
    async def login(self) -> bool:
        """
        Login to DNSE and get JWT token.
        
        Returns:
            True if login successful
        """
        try:
            response = await self._client.post(
                f"{self.BASE_URL}/auth-service/login",
                json={
                    "username": self.username,
                    "password": self.password
                }
            )
            response.raise_for_status()
            
            data = response.json()
            self.tokens.jwt_token = data.get("token")
            self.tokens.jwt_expires = datetime.now() + timedelta(hours=self.TOKEN_VALIDITY_HOURS)
            
            logger.info("DNSE login successful")
            return True
        
        except httpx.HTTPStatusError as e:
            logger.error(f"Login failed: {e.response.status_code} - {e.response.text}")
            return False
        except Exception as e:
            logger.error(f"Login error: {e}")
            return False
    
    async def request_email_otp(self) -> bool:
        """
        Request OTP to be sent via email.
        
        Returns:
            True if OTP sent successfully
        """
        if not self.tokens.is_jwt_valid():
            await self.login()
        
        try:
            response = await self._client.get(
                f"{self.BASE_URL}/auth-service/api/email-otp",
                headers=self._auth_headers()
            )
            response.raise_for_status()
            
            logger.info("OTP sent to email")
            return True
        
        except Exception as e:
            logger.error(f"Request OTP failed: {e}")
            return False
    
    async def get_trading_token(
        self,
        otp: Optional[str] = None,
        smart_otp: Optional[str] = None
    ) -> bool:
        """
        Exchange OTP for trading token.
        
        Args:
            otp: Email OTP code
            smart_otp: Smart OTP code from app
        
        Returns:
            True if trading token obtained
        """
        if not self.tokens.is_jwt_valid():
            await self.login()
        
        headers = self._auth_headers()
        
        if smart_otp:
            headers["smart-otp"] = smart_otp
        elif otp:
            headers["otp"] = otp
        else:
            logger.error("Must provide either otp or smart_otp")
            return False
        
        try:
            response = await self._client.post(
                f"{self.BASE_URL}/order-service/trading-token",
                headers=headers
            )
            response.raise_for_status()
            
            data = response.json()
            self.tokens.trading_token = data.get("tradingToken")
            self.tokens.trading_token_expires = datetime.now() + timedelta(hours=self.TOKEN_VALIDITY_HOURS)
            
            logger.info("Trading token obtained")
            return True
        
        except Exception as e:
            logger.error(f"Get trading token failed: {e}")
            return False
    
    # ============ Account Management ============
    
    async def get_accounts(self) -> List[Account]:
        """Get list of trading accounts."""
        if not self.tokens.is_jwt_valid():
            await self.login()
        
        try:
            response = await self._client.get(
                f"{self.BASE_URL}/order-service/accounts",
                headers=self._auth_headers()
            )
            response.raise_for_status()
            
            data = response.json()
            self.accounts = [
                Account(
                    id=acc.get("id", ""),
                    name=acc.get("name", ""),
                    type=acc.get("type", "")
                )
                for acc in data.get("accounts", [])
            ]
            
            # Set default account if not specified
            if not self.account_no and self.accounts:
                self.account_no = self.accounts[0].id
            
            logger.info(f"Found {len(self.accounts)} accounts")
            return self.accounts
        
        except Exception as e:
            logger.error(f"Get accounts failed: {e}")
            return []
    
    async def get_balance(self, account_no: Optional[str] = None) -> Optional[AccountBalance]:
        """Get account balance."""
        account_no = account_no or self.account_no
        if not account_no:
            logger.error("No account specified")
            return None
        
        if not self.tokens.is_jwt_valid():
            await self.login()
        
        try:
            response = await self._client.get(
                f"{self.BASE_URL}/order-service/account-balances/{account_no}",
                headers=self._auth_headers()
            )
            response.raise_for_status()
            
            data = response.json()
            return AccountBalance(
                account_no=account_no,
                cash_balance=float(data.get("cashBalance", 0)),
                buying_power=float(data.get("buyingPower", 0)),
                withdrawable=float(data.get("withdrawable", 0))
            )
        
        except Exception as e:
            logger.error(f"Get balance failed: {e}")
            return None
    
    async def get_loan_packages(self, account_no: Optional[str] = None) -> List[LoanPackage]:
        """Get loan packages for margin trading."""
        account_no = account_no or self.account_no
        if not account_no:
            return []
        
        if not self.tokens.is_jwt_valid():
            await self.login()
        
        try:
            response = await self._client.get(
                f"{self.BASE_URL}/order-service/v2/accounts/{account_no}/loan-packages",
                headers=self._auth_headers()
            )
            response.raise_for_status()
            
            data = response.json()
            self.loan_packages = [
                LoanPackage(
                    id=pkg.get("id", 0),
                    name=pkg.get("name", ""),
                    type=pkg.get("type", "")
                )
                for pkg in data.get("loanPackages", [])
            ]
            
            # Set default loan package
            if self.loan_packages:
                self.default_loan_package_id = self.loan_packages[0].id
            
            logger.info(f"Found {len(self.loan_packages)} loan packages")
            return self.loan_packages
        
        except Exception as e:
            logger.error(f"Get loan packages failed: {e}")
            return []
    
    async def get_buying_power(
        self,
        symbol: str,
        price: float,
        account_no: Optional[str] = None,
        loan_package_id: Optional[int] = None
    ) -> Optional[int]:
        """
        Get maximum quantity that can be bought.
        
        Returns:
            Maximum quantity or None if error
        """
        account_no = account_no or self.account_no
        loan_package_id = loan_package_id or self.default_loan_package_id
        
        if not account_no:
            return None
        
        if not self.tokens.is_jwt_valid():
            await self.login()
        
        try:
            params = {
                "symbol": symbol,
                "price": price
            }
            if loan_package_id:
                params["loanPackageId"] = loan_package_id
            
            response = await self._client.get(
                f"{self.BASE_URL}/order-service/accounts/{account_no}/ppse",
                params=params,
                headers=self._auth_headers()
            )
            response.raise_for_status()
            
            data = response.json()
            return int(data.get("qmax", 0))
        
        except Exception as e:
            logger.error(f"Get buying power failed: {e}")
            return None
    
    # ============ Order Management ============
    
    async def place_order(
        self,
        symbol: str,
        side: OrderSide,
        quantity: int,
        price: float,
        order_type: OrderType = OrderType.LO,
        account_no: Optional[str] = None,
        loan_package_id: Optional[int] = None
    ) -> Optional[Order]:
        """
        Place a new order.
        
        Args:
            symbol: Stock symbol
            side: Buy or Sell
            quantity: Number of shares
            price: Order price
            order_type: Order type (default: Limit Order)
            account_no: Account number
            loan_package_id: Loan package ID
        
        Returns:
            Order object if successful, None otherwise
        """
        account_no = account_no or self.account_no
        loan_package_id = loan_package_id or self.default_loan_package_id
        
        if not account_no:
            logger.error("No account specified")
            return None
        
        if not self.tokens.is_trading_token_valid():
            logger.error("Trading token not valid. Please authenticate with OTP first.")
            return None
        
        try:
            body = {
                "symbol": symbol.upper(),
                "side": side.value,
                "orderType": order_type.value,
                "price": int(price),
                "quantity": quantity,
                "accountNo": account_no
            }
            
            if loan_package_id:
                body["loanPackageId"] = loan_package_id
            
            response = await self._client.post(
                f"{self.BASE_URL}/order-service/v2/orders",
                json=body,
                headers=self._trading_headers()
            )
            response.raise_for_status()
            
            data = response.json()
            order = Order(
                id=str(data.get("id", "")),
                symbol=symbol.upper(),
                side=side,
                order_type=order_type,
                price=price,
                quantity=quantity,
                status=data.get("status", ""),
                account_no=account_no,
                created_at=datetime.now()
            )
            
            logger.info(f"Order placed: {order.id} {side.value} {quantity} {symbol} @ {price}")
            return order
        
        except httpx.HTTPStatusError as e:
            logger.error(f"Place order failed: {e.response.status_code} - {e.response.text}")
            return None
        except Exception as e:
            logger.error(f"Place order error: {e}")
            return None
    
    async def cancel_order(
        self,
        order_id: str,
        account_no: Optional[str] = None
    ) -> bool:
        """
        Cancel an existing order.
        
        Returns:
            True if cancellation successful
        """
        account_no = account_no or self.account_no
        
        if not account_no:
            logger.error("No account specified")
            return False
        
        if not self.tokens.is_trading_token_valid():
            logger.error("Trading token not valid")
            return False
        
        try:
            response = await self._client.delete(
                f"{self.BASE_URL}/order-service/v2/orders/{order_id}",
                params={"accountNo": account_no},
                headers=self._trading_headers()
            )
            response.raise_for_status()
            
            logger.info(f"Order cancelled: {order_id}")
            return True
        
        except Exception as e:
            logger.error(f"Cancel order failed: {e}")
            return False
    
    async def get_orders(
        self,
        account_no: Optional[str] = None
    ) -> List[Order]:
        """Get list of orders."""
        account_no = account_no or self.account_no
        
        if not account_no:
            return []
        
        if not self.tokens.is_jwt_valid():
            await self.login()
        
        try:
            response = await self._client.get(
                f"{self.BASE_URL}/order-service/v2/orders",
                params={"accountNo": account_no},
                headers=self._auth_headers()
            )
            response.raise_for_status()
            
            data = response.json()
            orders = []
            for o in data.get("orders", []):
                orders.append(Order(
                    id=str(o.get("id", "")),
                    symbol=o.get("symbol", ""),
                    side=OrderSide(o.get("side", "NB")),
                    order_type=OrderType(o.get("orderType", "LO")),
                    price=float(o.get("price", 0)),
                    quantity=int(o.get("quantity", 0)),
                    filled_quantity=int(o.get("filledQuantity", 0)),
                    status=o.get("status", ""),
                    account_no=account_no
                ))
            
            return orders
        
        except Exception as e:
            logger.error(f"Get orders failed: {e}")
            return []
    
    async def get_order(
        self,
        order_id: str,
        account_no: Optional[str] = None
    ) -> Optional[Order]:
        """Get order by ID."""
        account_no = account_no or self.account_no
        
        if not account_no:
            return None
        
        if not self.tokens.is_jwt_valid():
            await self.login()
        
        try:
            response = await self._client.get(
                f"{self.BASE_URL}/order-service/v2/orders/{order_id}",
                params={"accountNo": account_no},
                headers=self._auth_headers()
            )
            response.raise_for_status()
            
            o = response.json()
            return Order(
                id=str(o.get("id", "")),
                symbol=o.get("symbol", ""),
                side=OrderSide(o.get("side", "NB")),
                order_type=OrderType(o.get("orderType", "LO")),
                price=float(o.get("price", 0)),
                quantity=int(o.get("quantity", 0)),
                filled_quantity=int(o.get("filledQuantity", 0)),
                status=o.get("status", ""),
                account_no=account_no
            )
        
        except Exception as e:
            logger.error(f"Get order failed: {e}")
            return None
    
    async def get_positions(self, account_no: Optional[str] = None) -> List[Dict]:
        """Get current positions (deals)."""
        account_no = account_no or self.account_no
        
        if not account_no:
            return []
        
        if not self.tokens.is_jwt_valid():
            await self.login()
        
        try:
            response = await self._client.get(
                f"{self.BASE_URL}/deal-service/deals",
                params={"accountNo": account_no},
                headers=self._auth_headers()
            )
            response.raise_for_status()
            
            return response.json().get("deals", [])
        
        except Exception as e:
            logger.error(f"Get positions failed: {e}")
            return []
    
    # ============ Helper Methods ============
    
    def _auth_headers(self) -> Dict[str, str]:
        """Get headers with JWT token."""
        return {
            "Authorization": f"Bearer {self.tokens.jwt_token}",
            "Content-Type": "application/json"
        }
    
    def _trading_headers(self) -> Dict[str, str]:
        """Get headers with JWT + Trading token."""
        headers = self._auth_headers()
        headers["Trading-Token"] = self.tokens.trading_token or ""
        return headers
    
    async def initialize(self) -> bool:
        """
        Initialize trading service.
        
        Steps:
        1. Login
        2. Get accounts
        3. Get loan packages
        
        Returns:
            True if initialization successful
        """
        if not await self.login():
            return False
        
        await self.get_accounts()
        
        if self.account_no:
            await self.get_loan_packages()
        
        return True
