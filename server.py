import asyncio
import logging
import datetime
import os
import websockets
import asyncpg
from ocpp.routing import on
from ocpp.v16 import ChargePoint as CP
from ocpp.v16 import call_result

# 🔧 Gelişmiş Log Ayarları
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('ocpp_server.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('OCPP_Server')


class ChargePoint(CP):
    def __init__(self, id, connection):
        super().__init__(id, connection)
        self.db_pool = None
        self.is_active = True  # Yüksek erişilebilirlik için durum takibi

    async def set_db_pool(self, pool):
        """Veritabanı bağlantı havuzunu ayarlar"""
        self.db_pool = pool

    async def start(self):
        """Cihaz bağlantısını başlatır"""
        logger.info(f"🔌 Yeni cihaz bağlandı - ID: {self.id}")
        try:
            await super().start()
        except websockets.exceptions.ConnectionClosedError as e:
            logger.warning(f"❌ Bağlantı koptu - ID: {self.id}, Sebep: {str(e)}")
            self.is_active = False
        except Exception as e:
            logger.error(f"⚠️ Cihaz hatası - ID: {self.id}: {str(e)}")
            self.is_active = False

    @on("BootNotification")
    async def on_boot_notification(self, charge_point_model, charge_point_vendor, **kwargs):
        """Yüksek erişilebilirlik için standby mod kontrolü"""
        logger.info(f"🔄 BootNotification - ID: {self.id}")

        # Veritabanı bağlantısı kontrolü
        db_status = "Connected" if self.db_pool else "Disconnected"

        return call_result.BootNotificationPayload(
            current_time=datetime.datetime.utcnow().isoformat(),
            interval=30,
            status="Accepted",
            additional_info={
                "db_status": db_status,
                "ha_mode": "active" if self.is_active else "standby"
            }
        )

    # Diğer OCPP metodları (Authorize, StartTransaction vb.) önceki gibi kalacak
    # ...


async def create_ha_database_pool(primary_url, standby_url=None):
    """Yüksek erişilebilirlik için veritabanı bağlantı havuzu"""
    try:
        # Önce birincil veritabanına bağlanmayı dene
        pool = await asyncpg.create_pool(
            dsn=primary_url,
            min_size=2,
            max_size=10,
            timeout=5
        )
        logger.info("✅ Birincil veritabanına bağlandı")
        return pool
    except Exception as primary_error:
        if standby_url:
            logger.warning("⚠️ Birincil veritabanına bağlanılamadı, standby deneniyor...")
            try:
                pool = await asyncpg.create_pool(
                    dsn=standby_url,
                    min_size=1,
                    max_size=5,
                    timeout=10
                )
                logger.info("✅ Standby veritabanına bağlandı")
                return pool
            except Exception as standby_error:
                logger.error(f"❌ Tüm veritabanlarına bağlanılamadı: {standby_error}")
                return None
        else:
            logger.error(f"❌ Birincil veritabanına bağlanılamadı: {primary_error}")
            return None


async def main():
    """Ana uygulama - Yüksek erişilebilirlik desteği ile"""
    # Veritabanı URL'leri (Ortam değişkenlerinden al)
    primary_db = os.getenv('PRIMARY_DB_URL', 'postgres://user:pass@primary-host:5432/db')
    standby_db = os.getenv('STANDBY_DB_URL', None)  # Standby opsiyonel

    # HA veritabanı havuzu oluştur
    db_pool = await create_ha_database_pool(primary_db, standby_db)

    # WebSocket sunucusunu başlat
    server = await websockets.serve(
        on_connect,
        host="0.0.0.0",
        port=int(os.getenv("PORT", "8080")),
        subprotocols=["ocpp1.6"],
        ping_interval=20,
        ping_timeout=30,
        ssl=None  # SSL için uygun context eklenmeli
    )

    logger.info(f"🚀 OCPP 1.6 Sunucusu çalışıyor (HA modu)")
    await server.wait_closed()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("🛑 Sunucu kapatılıyor...")