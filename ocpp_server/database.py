import asyncpg
from datetime import datetime
import logging
from config import Config

logger = logging.getLogger("database")


class Database:
    _pool = None

    async def initialize(self):
        try:
            self._pool = await asyncpg.create_pool(
                host=Config.DB_HOST,
                port=Config.DB_PORT,
                database=Config.DB_NAME,
                user=Config.DB_USER,
                password=Config.DB_PASS,
                min_size=1,
                max_size=10
            )
            await self._create_tables()
            logger.info("Database initialized successfully")
        except Exception as e:
            logger.error(f"Database connection error: {str(e)}")
            raise

    async def _create_tables(self):
        async with self._pool.acquire() as conn:
            await conn.execute("""
                               CREATE TABLE IF NOT EXISTS charge_points (
                    id TEXT PRIMARY KEY,
                    status TEXT,
                    last_heartbeat TIMESTAMP,
                    config JSONB,
                    created_at TIMESTAMP DEFAULT NOW()
                );

                CREATE TABLE IF NOT EXISTS boot_notifications (
                    id SERIAL PRIMARY KEY,
                    charge_point_id TEXT REFERENCES charge_points(id),
                    model TEXT,
                    vendor TEXT,
                    timestamp TIMESTAMP,
                    created_at TIMESTAMP DEFAULT NOW()
                );

                CREATE TABLE IF NOT EXISTS heartbeats (
                    id SERIAL PRIMARY KEY,
                    charge_point_id TEXT REFERENCES charge_points(id),
                    timestamp TIMESTAMP,
                    created_at TIMESTAMP DEFAULT NOW()
                );

                CREATE TABLE IF NOT EXISTS status_notifications (
                    id SERIAL PRIMARY KEY,
                    charge_point_id TEXT REFERENCES charge_points(id),
                    connector_id INTEGER,
                    status TEXT,
                    error_code TEXT,
                    timestamp TIMESTAMP,
                    created_at TIMESTAMP DEFAULT NOW()
                );

                CREATE TABLE IF NOT EXISTS transactions (
                    id SERIAL PRIMARY KEY,
                    charge_point_id TEXT REFERENCES charge_points(id),
                    connector_id INTEGER,
                    id_tag TEXT,
                    start_value INTEGER,
                    stop_value INTEGER,
                    start_time TIMESTAMP,
                    stop_time TIMESTAMP,
                    created_at TIMESTAMP DEFAULT NOW()
                );
            """)

    # ChargePoint işlemleri
    async def get_charge_points(self):
        async with self._pool.acquire() as conn:
            return await conn.fetch("SELECT * FROM charge_points")

    async def get_charge_point(self, charge_point_id):
        async with self._pool.acquire() as conn:
            return await conn.fetchrow(
                "SELECT * FROM charge_points WHERE id = $1",
                charge_point_id
            )

    async def update_charge_point_config(self, charge_point_id, config):
        async with self._pool.acquire() as conn:
            await conn.execute(
                "UPDATE charge_points SET config = $1 WHERE id = $2",
                config, charge_point_id
            )

    # OCPP mesaj kayıtları
    async def add_boot_notification(self, charge_point_id, model, vendor, timestamp):
        async with self._pool.acquire() as conn:
            # Charge point kaydı yoksa oluştur
            await conn.execute("""
                               INSERT INTO charge_points (id, status)
                               VALUES ($1, 'Booted') ON CONFLICT (id) DO
                               UPDATE SET status = 'Booted'
                               """, charge_point_id)

            await conn.execute("""
                               INSERT INTO boot_notifications
                                   (charge_point_id, model, vendor, timestamp)
                               VALUES ($1, $2, $3, $4)
                               """, charge_point_id, model, vendor, timestamp)

    async def add_heartbeat(self, charge_point_id, timestamp):
        async with self._pool.acquire() as conn:
            await conn.execute("""
                               UPDATE charge_points
                               SET status         = 'Online',
                                   last_heartbeat = $1
                               WHERE id = $2
                               """, timestamp, charge_point_id)

            await conn.execute("""
                               INSERT INTO heartbeats (charge_point_id, timestamp)
                               VALUES ($1, $2)
                               """, charge_point_id, timestamp)

    async def add_status_notification(self, charge_point_id, connector_id, status, error_code, timestamp):
        async with self._pool.acquire() as conn:
            await conn.execute("""
                               INSERT INTO status_notifications
                                   (charge_point_id, connector_id, status, error_code, timestamp)
                               VALUES ($1, $2, $3, $4, $5)
                               """, charge_point_id, connector_id, status, error_code, timestamp)

            await conn.execute("""
                               UPDATE charge_points
                               SET status = $1
                               WHERE id = $2
                               """, status, charge_point_id)