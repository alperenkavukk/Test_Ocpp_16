import asyncio
import logging
import datetime
from datetime import datetime  # timestamp parse için
import os
import websockets
import asyncpg
from ocpp.routing import on
from ocpp.v16 import ChargePoint as CP
from ocpp.v16 import call_result

# 📋 Log formatı
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("OCPP_Server")

db_pool = None  # Global veritabanı havuzu


class ChargePoint(CP):
    def __init__(self, id, connection):
        super().__init__(id, connection)
        self.db_pool = None

    async def set_db_pool(self, pool):
        self.db_pool = pool

    async def start(self):
        port = int(os.environ.get("PORT", 8080))
        server = await websockets.serve(
            self.on_connect,
            "0.0.0.0",
            port,
            subprotocols=['ocpp1.6']
        )
        logger.info(f"OCPP server started on ws://0.0.0.0:{port}")

    @on("BootNotification")
    async def on_boot_notification(self, charge_point_model, charge_point_vendor, **kwargs):
        current_time = datetime.utcnow()
        logger.info(f"🔄 BootNotification - ID: {self.id}, Model: {charge_point_model}, Vendor: {charge_point_vendor}")

        if self.db_pool:
            try:
                async with self.db_pool.acquire() as conn:
                    await conn.execute("""
                        INSERT INTO boot_notifications (cp_id, model, vendor, timestamp)
                        VALUES ($1, $2, $3, $4)
                    """, self.id, charge_point_model, charge_point_vendor, current_time)
            except Exception as e:
                logger.error(f"⚠️ BootNotification DB kaydı hatası - ID: {self.id}: {str(e)}")

        return call_result.BootNotificationPayload(
            current_time=current_time.strftime("%Y-%m-%dT%H:%M:%SZ"),
            interval=30,
            status="Accepted"
        )

    @on("Heartbeat")
    async def on_heartbeat(self):
        current_time = datetime.utcnow()
        logger.info(f"💓 Heartbeat - ID: {self.id}")

        if self.db_pool:
            try:
                async with self.db_pool.acquire() as conn:
                    await conn.execute("""
                        INSERT INTO heartbeats (cp_id, timestamp)
                        VALUES ($1, $2)
                    """, self.id, current_time)
            except Exception as e:
                logger.error(f"⚠️ Heartbeat DB kaydı hatası - ID: {self.id}: {str(e)}")

        return call_result.HeartbeatPayload(
            current_time=current_time.strftime("%Y-%m-%dT%H:%M:%SZ")
        )

    @on("Authorize")
    async def on_authorize(self, id_tag):
        logger.info(f"🪪 Authorize - ID: {self.id}, Tag: {id_tag}")
        status = "Invalid"
        try:
            if self.db_pool:
                async with self.db_pool.acquire() as conn:
                    user = await conn.fetchrow("SELECT * FROM users WHERE id_tag = $1", id_tag)
                    status = "Accepted" if user else "Invalid"
                    await conn.execute("""
                        INSERT INTO authorizations (cp_id, id_tag, status, timestamp)
                        VALUES ($1, $2, $3, NOW())
                    """, self.id, id_tag, status)
            else:
                status = "Accepted"
        except Exception as e:
            logger.error(f"⚠️ Authorize hatası - ID: {self.id}: {str(e)}")
            status = "Invalid"

        return call_result.AuthorizePayload(id_tag_info={"status": status})

    @on("StartTransaction")
    async def on_start_transaction(self, connector_id, id_tag, meter_start, timestamp, **kwargs):
        logger.info(f"⚡ StartTransaction - ID: {self.id}, Connector: {connector_id}, Tag: {id_tag}, MeterStart: {meter_start}")
        try:
            tx_id = 1234
            if self.db_pool:
                async with self.db_pool.acquire() as conn:
                    tx_id = await conn.fetchval("""
                        INSERT INTO transactions (id_tag, connector_id, start_value, start_time)
                        VALUES ($1, $2, $3, $4) RETURNING id
                    """, id_tag, connector_id, meter_start, timestamp)
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
                    await conn.execute("""
                        UPDATE transactions
                        SET stop_value = $1,
                            stop_time = $2,
                            total_energy = $1 - start_value
                        WHERE id = $3
                    """, meter_stop, timestamp, transaction_id)
                    logger.info(f"💾 Transaction durduruldu - TX ID: {transaction_id}")
            return call_result.StopTransactionPayload(id_tag_info={"status": "Accepted"})
        except Exception as e:
            logger.error(f"⚠️ StopTransaction hatası - ID: {self.id}: {str(e)}")
            return call_result.StopTransactionPayload(id_tag_info={"status": "Invalid"})

    @on("StatusNotification")
    async def on_status_notification(self, connectorId, errorCode, status, **kwargs):
        timestamp_str = kwargs.get("timestamp")
        vendor_id = kwargs.get("vendorId")
        logger.info(f"📥 StatusNotification - ID: {self.id}, Connector: {connectorId}, Status: {status}, Error: {errorCode}")

        timestamp = None
        if timestamp_str:
            try:
                timestamp = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
            except Exception as e:
                logger.warning(f"⚠️ Timestamp parse hatası: {timestamp_str} - {e}")

        try:
            if self.db_pool:
                async with self.db_pool.acquire() as conn:
                    await conn.execute("""
                        INSERT INTO status_notifications (cp_id, connector_id, status, error_code, timestamp, vendor_id)
                        VALUES ($1, $2, $3, $4, $5, $6)
                    """, self.id, connectorId, status, errorCode, timestamp, vendor_id)
            return call_result.StatusNotificationPayload()
        except Exception as e:
            logger.error(f"⚠️ StatusNotification hatası - ID: {self.id}: {str(e)}")
            return call_result.StatusNotificationPayload()

    # ----- EKLEMELER -----

    @on("MeterValues")
    async def on_meter_values(self, connector_id, meter_value, **kwargs):
        timestamp_str = kwargs.get("timestamp")
        logger.info(f"🔢 MeterValues - ID: {self.id}, Connector: {connector_id}, MeterValue: {meter_value}")

        timestamp = None
        if timestamp_str:
            try:
                timestamp = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
            except Exception as e:
                logger.warning(f"⚠️ MeterValues timestamp parse hatası: {timestamp_str} - {e}")

        try:
            if self.db_pool:
                async with self.db_pool.acquire() as conn:
                    # meter_value genelde array şeklinde gelir, JSON olarak kaydetmek pratik
                    await conn.execute("""
                        INSERT INTO meter_values (cp_id, connector_id, meter_value, timestamp)
                        VALUES ($1, $2, $3, $4)
                    """, self.id, connector_id, str(meter_value), timestamp)
            return call_result.MeterValuesPayload()
        except Exception as e:
            logger.error(f"⚠️ MeterValues DB kaydı hatası - ID: {self.id}: {str(e)}")
            return call_result.MeterValuesPayload()

    @on("FirmwareStatusNotification")
    async def on_firmware_status_notification(self, status, **kwargs):
        logger.info(f"📦 FirmwareStatusNotification - ID: {self.id}, Status: {status}")
        try:
            if self.db_pool:
                async with self.db_pool.acquire() as conn:
                    await conn.execute("""
                        INSERT INTO firmware_status_notifications (cp_id, status, timestamp)
                        VALUES ($1, $2, NOW())
                    """, self.id, status)
            return call_result.FirmwareStatusNotificationPayload()
        except Exception as e:
            logger.error(f"⚠️ FirmwareStatusNotification DB kaydı hatası - ID: {self.id}: {str(e)}")
            return call_result.FirmwareStatusNotificationPayload()

    @on("DiagnosticsStatusNotification")
    async def on_diagnostics_status_notification(self, status, **kwargs):
        logger.info(f"🛠 DiagnosticsStatusNotification - ID: {self.id}, Status: {status}")
        try:
            if self.db_pool:
                async with self.db_pool.acquire() as conn:
                    await conn.execute("""
                        INSERT INTO diagnostics_status_notifications (cp_id, status, timestamp)
                        VALUES ($1, $2, NOW())
                    """, self.id, status)
            return call_result.DiagnosticsStatusNotificationPayload()
        except Exception as e:
            logger.error(f"⚠️ DiagnosticsStatusNotification DB kaydı hatası - ID: {self.id}: {str(e)}")
            return call_result.DiagnosticsStatusNotificationPayload()

    @on("RemoteStartTransaction")
    async def on_remote_start_transaction(self, connector_id, id_tag, **kwargs):
        logger.info(f"▶ RemoteStartTransaction - ID: {self.id}, Connector: {connector_id}, Tag: {id_tag}")
        # Bu komut serverdan charge point'e gönderilir, burada payload döner
        # Uygulamanda gerekli ise transaction başlatma işlemi yapabilirsin
        return call_result.RemoteStartTransactionPayload(status="Accepted")

    @on("RemoteStopTransaction")
    async def on_remote_stop_transaction(self, transaction_id, **kwargs):
        logger.info(f"⏹ RemoteStopTransaction - ID: {self.id}, Transaction ID: {transaction_id}")
        # Uygulamanda gerekli ise transaction durdurma işlemi yapabilirsin
        return call_result.RemoteStopTransactionPayload(status="Accepted")

    @on("ReserveNow")
    async def on_reserve_now(self, connector_id, expiry_date, id_tag, **kwargs):
        logger.info(f"📅 ReserveNow - ID: {self.id}, Connector: {connector_id}, Tag: {id_tag}, Expiry: {expiry_date}")
        # Rezervasyon işlemini burada kaydet veya onayla
        # Basit örnek: her zaman kabul
        return call_result.ReserveNowPayload(status="Accepted")

    @on("CancelReservation")
    async def on_cancel_reservation(self, reservation_id, **kwargs):
        logger.info(f"❌ CancelReservation - ID: {self.id}, Reservation ID: {reservation_id}")
        # Rezervasyon iptali işlemini burada yap
        # Basit örnek: her zaman kabul
        return call_result.CancelReservationPayload(status="Accepted")


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
            user=os.getenv("DB_USER"),
            password=os.getenv("DB_PASS"),
            database=os.getenv("DB_NAME"),
            host=os.getenv("DB_HOST"),
            port=os.getenv("DB_PORT"),
            min_size=1,
            max_size=10
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

                    CREATE TABLE IF NOT EXISTS status_notifications (
                        id SERIAL PRIMARY KEY,
                        cp_id TEXT NOT NULL,
                        connector_id INTEGER,
                        status TEXT,
                        error_code TEXT,
                        vendor_id TEXT,
                        timestamp TIMESTAMP,
                        created_at TIMESTAMP DEFAULT NOW()
                    );

                    CREATE TABLE IF NOT EXISTS boot_notifications (
                        id SERIAL PRIMARY KEY,
                        cp_id TEXT NOT NULL,
                        model TEXT,
                        vendor TEXT,
                        timestamp TIMESTAMP,
                        created_at TIMESTAMP DEFAULT NOW()
                    );

                    CREATE TABLE IF NOT EXISTS heartbeats (
                        id SERIAL PRIMARY KEY,
                        cp_id TEXT NOT NULL,
                        timestamp TIMESTAMP,
                        created_at TIMESTAMP DEFAULT NOW()
                    );

                    CREATE TABLE IF NOT EXISTS authorizations (
                        id SERIAL PRIMARY KEY,
                        cp_id TEXT NOT NULL,
                        id_tag VARCHAR(50),
                        status TEXT,
                        timestamp TIMESTAMP,
                        created_at TIMESTAMP DEFAULT NOW()
                    );

                    CREATE TABLE IF NOT EXISTS meter_values (
                        id SERIAL PRIMARY KEY,
                        cp_id TEXT NOT NULL,
                        connector_id INTEGER,
                        meter_value TEXT,
                        timestamp TIMESTAMP,
                        created_at TIMESTAMP DEFAULT NOW()
                    );

                    CREATE TABLE IF NOT EXISTS firmware_status_notifications (
                        id SERIAL PRIMARY KEY,
                        cp_id TEXT NOT NULL,
                        status TEXT,
                        timestamp TIMESTAMP DEFAULT NOW(),
                        created_at TIMESTAMP DEFAULT NOW()
                    );

                    CREATE TABLE IF NOT EXISTS diagnostics_status_notifications (
                        id SERIAL PRIMARY KEY,
                        cp_id TEXT NOT NULL,
                        status TEXT,
                        timestamp TIMESTAMP DEFAULT NOW(),
                        created_at TIMESTAMP DEFAULT NOW()
                    );

                    CREATE TABLE IF NOT EXISTS reservations (
                        id SERIAL PRIMARY KEY,
                        cp_id TEXT NOT NULL,
                        connector_id INTEGER,
                        id_tag VARCHAR(50),
                        expiry_date TIMESTAMP,
                        status TEXT,
                        created_at TIMESTAMP DEFAULT NOW()
                    );
                """)
                logger.info("✅ Veritabanı tabloları hazır")
        except Exception as e:
            logger.error(f"⚠️ Tablo oluşturma hatası: {str(e)}")

    server = await websockets.serve(
        on_connect,
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 8080)),
        subprotocols=["ocpp1.6"],
        ping_interval=20,
        ping_timeout=30
    )
    logger.info("✅ OCPP 1.6 Sunucusu dinlemede...")
    await server.wait_closed()


if __name__ == "__main__":
    asyncio.run(main())
