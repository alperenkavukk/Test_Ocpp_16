import asyncio
import logging
import datetime
import os
import websockets
import asyncpg
from ocpp.routing import on
from ocpp.v16 import ChargePoint as CP
from ocpp.v16 import call_result

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('OCPP_Server')

db_pool = None  # Global havuz

class ChargePoint(CP):
    def __init__(self, id, connection):
        super().__init__(id, connection)
        self.db_pool = None

    async def set_db_pool(self, pool):
        self.db_pool = pool

    async def start(self):
        logger.info(f"🔌 Yeni cihaz bağlandı - ID: {self.id}")
        try:
            await super().start()
        except websockets.exceptions.ConnectionClosedError as e:
            logger.warning(f"❌ Bağlantı koptu - ID: {self.id}, Sebep: {str(e)}")
        except Exception as e:
            logger.error(f"⚠️ Cihaz hatası - ID: {self.id}: {str(e)}")

    @on("BootNotification")
    async def on_boot_notification(self, charge_point_model, charge_point_vendor, **kwargs):
        logger.info(f"🔄 BootNotification - ID: {self.id}, Model: {charge_point_model}, Vendor: {charge_point_vendor}")
        return call_result.BootNotificationPayload(
            current_time=datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
            interval=30,
            status="Accepted"
        )

    @on("Heartbeat")
    async def on_heartbeat(self):
        logger.info(f"💓 Heartbeat - ID: {self.id}")
        return call_result.HeartbeatPayload(
            current_time=datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
        )

    @on("Authorize")
    async def on_authorize(self, id_tag):
        logger.info(f"🪪 Authorize - ID: {self.id}, Tag: {id_tag}")
        try:
            if self.db_pool:
                async with self.db_pool.acquire() as conn:
                    user = await conn.fetchrow("SELECT * FROM users WHERE id_tag = $1", id_tag)
                    status = "Accepted" if user else "Invalid"
            else:
                status = "Accepted"
            return call_result.AuthorizePayload(id_tag_info={"status": status})
        except Exception as e:
            logger.error(f"⚠️ Authorize hatası - ID: {self.id}: {str(e)}")
            return call_result.AuthorizePayload(id_tag_info={"status": "Invalid"})

    @on("StartTransaction")
    async def on_start_transaction(self, connector_id, id_tag, meter_start, timestamp, **kwargs):
        logger.info(f"⚡ StartTransaction - ID: {self.id}, Connector: {connector_id}, Tag: {id_tag}, MeterStart: {meter_start}")
        try:
            tx_id = 1234
            if self.db_pool:
                async with self.db_pool.acquire() as conn:
                    tx_id = await conn.fetchval(
                        """INSERT INTO transactions (id_tag, connector_id, start_value, start_time)
                           VALUES($1, $2, $3, $4) RETURNING id""",
                        id_tag, connector_id, meter_start, timestamp
                    )
                    logger.info(f"💾 Transaction başlatıldı - TX ID: {tx_id}")
            return call_result.StartTransactionPayload(transaction_id=tx_id, id_tag_info={"status": "Accepted"})
        except Exception as e:
            logger.error(f"⚠️ StartTransaction hatası - ID: {self.id}: {str(e)}")
            return call_result.StartTransactionPayload(transaction_id=-1, id_tag_info={"status": "Invalid"})

    @on("StopTransaction")
    async def on_stop_transaction(self, transaction_id, meter_stop, timestamp, **kwargs):
        logger.info(f"🛑 StopTransaction - ID: {self.id}, TxID: {transaction_id}, MeterStop: {meter_stop}")
        try:
            if self.db_pool:
                async with self.db_pool.acquire() as conn:
                    await conn.execute(
                        """UPDATE transactions SET stop_value = $1, stop_time = $2,
                           total_energy = $1 - start_value WHERE id = $3""",
                        meter_stop, timestamp, transaction_id
                    )
                    logger.info(f"💾 Transaction durduruldu - TX ID: {transaction_id}")
            return call_result.StopTransactionPayload(id_tag_info={"status": "Accepted"})
        except Exception as e:
            logger.error(f"⚠️ StopTransaction hatası - ID: {self.id}: {str(e)}")
            return call_result.StopTransactionPayload(id_tag_info={"status": "Invalid"})

async def on_connect(websocket, path):
    charge_point_id = path.strip("/") or f"CP_{id(websocket)}"
    logger.info(f"🌐 Yeni bağlantı isteği - Path: {path}, Atanan ID: {charge_point_id}")
    cp = ChargePoint(charge_point_id, websocket)
    if 'db_pool' in globals():
        await cp.set_db_pool(db_pool)
    await cp.start()

async def create_db_pool():
    try:
        pool = await asyncpg.create_pool(
            user=os.getenv('DB_USER'),
            password=os.getenv('DB_PASSWORD', 'postgres'),
            database=os.getenv('DB_NAME', 'ocpp'),
            host=os.getenv('DB_HOST', 'localhost'),
            port=os.getenv('DB_PORT', '5432'),
            min_size=1, max_size=10
        )
        logger.info("✅ Veritabanı bağlantı havuzu oluşturuldu")
        return pool
    except Exception as e:
        logger.error(f"❌ Veritabanı bağlantı hatası: {str(e)}")
        return None

async def main():
    global db_pool
    db_pool = await create_db_pool()
    if db_pool:
        try:
            async with db_pool.acquire() as conn:
                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS users (
                        id SERIAL PRIMARY KEY,
                        id_tag VARCHAR(50) UNIQUE NOT NULL,
                        name VARCHAR(100),
                        created_at TIMESTAMP DEFAULT NOW()
                    );
                    CREATE TABLE IF NOT EXISTS transactions (
                        id SERIAL PRIMARY KEY,
                        id_tag VARCHAR(50) NOT NULL,
                        connector_id INTEGER NOT NULL,
                        start_value INTEGER NOT NULL,
                        stop_value INTEGER,
                        start_time TIMESTAMP NOT NULL,
                        stop_time TIMESTAMP,
                        total_energy INTEGER,
                        created_at TIMESTAMP DEFAULT NOW()
                    );
                """)
                logger.info("✅ Veritabanı tabloları kontrol edildi")
        except Exception as e:
            logger.error(f"⚠️ Veritabanı tablo oluşturma hatası: {str(e)}")

    server = await websockets.serve(
        on_connect,
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 8080)),
        subprotocols=["ocpp1.6"],
        ping_interval=20,
        ping_timeout=30
    )
    logger.info("✅ OCPP 1.6 Sunucusu çalışıyor")
    await server.wait_closed()

if __name__ == "__main__":
    asyncio.run(main())
