"""
Bot Trade - Database Storage
SQLite storage for bars and signals
"""
import aiosqlite
import json
from datetime import datetime
from typing import List, Optional
from pathlib import Path
import logging

from ..core.models import Bar, Signal, SignalType, SignalStatus

logger = logging.getLogger(__name__)


class Database:
    """SQLite database for storing bars and signals."""
    
    def __init__(self, db_path: str = "bottrade.db"):
        self.db_path = db_path
        self._connection: Optional[aiosqlite.Connection] = None
    
    async def connect(self):
        """Connect to database and create tables."""
        self._connection = await aiosqlite.connect(self.db_path)
        await self._create_tables()
        logger.info(f"Connected to database: {self.db_path}")
    
    async def disconnect(self):
        """Close database connection."""
        if self._connection:
            await self._connection.close()
            self._connection = None
            logger.info("Disconnected from database")
    
    async def _create_tables(self):
        """Create required tables if not exist."""
        await self._connection.executescript("""
            CREATE TABLE IF NOT EXISTS bars (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                timeframe TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                open REAL NOT NULL,
                high REAL NOT NULL,
                low REAL NOT NULL,
                close REAL NOT NULL,
                volume REAL DEFAULT 0,
                UNIQUE(symbol, timeframe, timestamp)
            );
            
            CREATE INDEX IF NOT EXISTS idx_bars_symbol_time 
                ON bars(symbol, timeframe, timestamp);
            
            CREATE TABLE IF NOT EXISTS signals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                signal_type TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                entry REAL NOT NULL,
                stop_loss REAL NOT NULL,
                take_profit REAL NOT NULL,
                quantity INTEGER DEFAULT 1,
                status TEXT DEFAULT 'ACTIVE',
                reason TEXT,
                original_sl REAL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );
            
            CREATE INDEX IF NOT EXISTS idx_signals_symbol 
                ON signals(symbol);
            
            CREATE INDEX IF NOT EXISTS idx_signals_status 
                ON signals(status);
                
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            );
        """)
        await self._connection.commit()
    
    # ============ Bar Operations ============
    
    async def save_bar(self, bar: Bar) -> int:
        """Save or update a bar. Returns row ID."""
        async with self._connection.execute("""
            INSERT OR REPLACE INTO bars 
                (symbol, timeframe, timestamp, open, high, low, close, volume)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            bar.symbol,
            bar.timeframe,
            bar.timestamp.isoformat(),
            bar.open,
            bar.high,
            bar.low,
            bar.close,
            bar.volume
        )) as cursor:
            await self._connection.commit()
            return cursor.lastrowid
    
    async def save_bars(self, bars: List[Bar]):
        """Bulk save bars."""
        data = [
            (
                bar.symbol,
                bar.timeframe,
                bar.timestamp.isoformat(),
                bar.open,
                bar.high,
                bar.low,
                bar.close,
                bar.volume
            )
            for bar in bars
        ]
        await self._connection.executemany("""
            INSERT OR REPLACE INTO bars 
                (symbol, timeframe, timestamp, open, high, low, close, volume)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, data)
        await self._connection.commit()
    
    async def get_bars(
        self,
        symbol: str,
        timeframe: str = "1H",
        limit: int = 100
    ) -> List[Bar]:
        """Get recent bars for a symbol."""
        async with self._connection.execute("""
            SELECT symbol, timeframe, timestamp, open, high, low, close, volume
            FROM bars
            WHERE symbol = ? AND timeframe = ?
            ORDER BY timestamp DESC
            LIMIT ?
        """, (symbol, timeframe, limit)) as cursor:
            rows = await cursor.fetchall()
        
        bars = []
        for row in reversed(rows):  # Return in chronological order
            bars.append(Bar(
                symbol=row[0],
                timeframe=row[1],
                timestamp=datetime.fromisoformat(row[2]),
                open=row[3],
                high=row[4],
                low=row[5],
                close=row[6],
                volume=row[7]
            ))
        return bars
    
    async def get_latest_bar(
        self,
        symbol: str,
        timeframe: str = "1H"
    ) -> Optional[Bar]:
        """Get the most recent bar for a symbol."""
        bars = await self.get_bars(symbol, timeframe, limit=1)
        return bars[0] if bars else None
    
    # ============ Signal Operations ============
    
    async def save_signal(self, signal: Signal) -> int:
        """Save a signal. Returns signal ID."""
        async with self._connection.execute("""
            INSERT INTO signals 
                (symbol, signal_type, timestamp, entry, stop_loss, take_profit,
                 quantity, status, reason, original_sl)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            signal.symbol,
            signal.signal_type.value,
            signal.timestamp.isoformat(),
            signal.entry,
            signal.stop_loss,
            signal.take_profit,
            signal.quantity,
            signal.status.value,
            signal.reason,
            signal.original_sl
        )) as cursor:
            await self._connection.commit()
            signal.id = cursor.lastrowid
            return signal.id
    
    async def update_signal(self, signal: Signal):
        """Update an existing signal."""
        await self._connection.execute("""
            UPDATE signals
            SET status = ?, stop_loss = ?
            WHERE id = ?
        """, (signal.status.value, signal.stop_loss, signal.id))
        await self._connection.commit()
    
    async def get_signals(
        self,
        symbol: Optional[str] = None,
        status: Optional[SignalStatus] = None,
        limit: int = 50
    ) -> List[Signal]:
        """Get signals with optional filters."""
        query = "SELECT * FROM signals WHERE 1=1"
        params = []
        
        if symbol:
            query += " AND symbol = ?"
            params.append(symbol)
        
        if status:
            query += " AND status = ?"
            params.append(status.value)
        
        query += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)
        
        async with self._connection.execute(query, params) as cursor:
            rows = await cursor.fetchall()
        
        signals = []
        for row in rows:
            signals.append(Signal(
                id=row[0],
                symbol=row[1],
                signal_type=SignalType(row[2]),
                timestamp=datetime.fromisoformat(row[3]),
                entry=row[4],
                stop_loss=row[5],
                take_profit=row[6],
                quantity=row[7],
                status=SignalStatus(row[8]),
                reason=row[9] or "",
                original_sl=row[10] or row[5]
            ))
        return signals
    
    async def get_active_signals(self, symbol: Optional[str] = None) -> List[Signal]:
        """Get all active signals."""
        return await self.get_signals(
            symbol=symbol,
            status=SignalStatus.ACTIVE,
            limit=100
        )
    
    async def get_signal_by_id(self, signal_id: int) -> Optional[Signal]:
        """Get a signal by ID."""
        async with self._connection.execute(
            "SELECT * FROM signals WHERE id = ?",
            (signal_id,)
        ) as cursor:
            row = await cursor.fetchone()
        
        if not row:
            return None
        
        return Signal(
            id=row[0],
            symbol=row[1],
            signal_type=SignalType(row[2]),
            timestamp=datetime.fromisoformat(row[3]),
            entry=row[4],
            stop_loss=row[5],
            take_profit=row[6],
            quantity=row[7],
            status=SignalStatus(row[8]),
            reason=row[9] or "",
            original_sl=row[10] or row[5]
        )

    # ============ Settings Operations ============
    
    async def save_setting(self, key: str, value: str):
        """Save a setting to database."""
        await self._connection.execute("""
            INSERT OR REPLACE INTO settings (key, value, updated_at)
            VALUES (?, ?, ?)
        """, (key, value, datetime.now().isoformat()))
        await self._connection.commit()
    
    async def get_setting(self, key: str, default: str = None) -> Optional[str]:
        """Get a setting from database."""
        async with self._connection.execute(
            "SELECT value FROM settings WHERE key = ?",
            (key,)
        ) as cursor:
            row = await cursor.fetchone()
        return row[0] if row else default
    
    async def get_all_settings(self) -> dict:
        """Get all settings as a dictionary."""
        async with self._connection.execute(
            "SELECT key, value FROM settings"
        ) as cursor:
            rows = await cursor.fetchall()
        return {row[0]: row[1] for row in rows}


# Global database instance
db = Database()
