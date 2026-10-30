"""Central MongoDB connection factory for new/refactored modules.

The legacy server currently creates the process-wide Motor client directly.
New code should import this module instead, so the remaining routers can be
migrated incrementally without duplicating pool/timeout configuration.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase


@dataclass(frozen=True)
class MongoSettings:
    uri: str
    database: str
    max_pool_size: int = 50
    min_pool_size: int = 5
    wait_queue_timeout_ms: int = 5_000
    server_selection_timeout_ms: int = 5_000
    connect_timeout_ms: int = 5_000
    socket_timeout_ms: int = 20_000

    @classmethod
    def from_env(cls) -> "MongoSettings":
        return cls(
            uri=os.environ["MONGO_URL"],
            database=os.environ["DB_NAME"],
            max_pool_size=max(5, int(os.environ.get("MONGO_MAX_POOL_SIZE", "50"))),
            min_pool_size=max(0, int(os.environ.get("MONGO_MIN_POOL_SIZE", "5"))),
            wait_queue_timeout_ms=max(500, int(os.environ.get("MONGO_WAIT_QUEUE_TIMEOUT_MS", "5000"))),
            server_selection_timeout_ms=max(500, int(os.environ.get("MONGO_SERVER_SELECTION_TIMEOUT_MS", "5000"))),
            connect_timeout_ms=max(500, int(os.environ.get("MONGO_CONNECT_TIMEOUT_MS", "5000"))),
            socket_timeout_ms=max(1000, int(os.environ.get("MONGO_SOCKET_TIMEOUT_MS", "20000"))),
        )


def create_motor_client(settings: Optional[MongoSettings] = None) -> AsyncIOMotorClient:
    cfg = settings or MongoSettings.from_env()
    return AsyncIOMotorClient(
        cfg.uri,
        maxPoolSize=cfg.max_pool_size,
        minPoolSize=min(cfg.min_pool_size, cfg.max_pool_size),
        waitQueueTimeoutMS=cfg.wait_queue_timeout_ms,
        serverSelectionTimeoutMS=cfg.server_selection_timeout_ms,
        connectTimeoutMS=cfg.connect_timeout_ms,
        socketTimeoutMS=cfg.socket_timeout_ms,
        retryReads=True,
        retryWrites=True,
    )


def get_database(client: AsyncIOMotorClient, settings: Optional[MongoSettings] = None) -> AsyncIOMotorDatabase:
    cfg = settings or MongoSettings.from_env()
    return client[cfg.database]
