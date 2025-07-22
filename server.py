import asyncio
import logging
import datetime
import os
import websockets

from ocpp.routing import on
from ocpp.v16 import ChargePoint as CP
from ocpp.v16 import call_result

# 🔧 Log ayarları
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('OCPP_Server')


class ChargePoint(CP):
    async def start(self):
        logger.info(f"🔌 Yeni cihaz bağlandı - ID: {self.id}")
        try:
            await super().start()
        except websockets.exceptions.ConnectionClosed:
            logger.info(f"❌ Cihaz bağlantısı kesildi - ID: {self.id}")
        except Exception as e:
            logger.error(f"⚠️ Cihaz hatası - ID: {self.id}: {str(e)}")

    @on("BootNotification")
    async def on_boot_notification(self, charge_point_model, charge_point_vendor, **kwargs):
        logger.info(
            f"🔄 BootNotification alındı - Cihaz: {self.id}, Model: {charge_point_model}, Vendor: {charge_point_vendor}"
        )
        return call_result.BootNotificationPayload(
            current_time=datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
            interval=30,
            status="Accepted"
        )

    @on("Heartbeat")
    async def on_heartbeat(self):
        logger.info(f"💓 Heartbeat alındı - Cihaz: {self.id}")
        return call_result.HeartbeatPayload(
            current_time=datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
        )


async def on_connect(websocket, path):
    try:
        charge_point_id = path.strip('/') or f"CP_{id(websocket)}"
        logger.info(f"🌐 Yeni bağlantı isteği - Path: {path}, Atanan ID: {charge_point_id}")

        cp = ChargePoint(charge_point_id, websocket)
        await cp.start()
    except Exception as e:
        logger.error(f"⛔ Bağlantı hatası: {str(e)}")


async def main():
    # Render platformunun atadığı PORT değişkeni
    port = int(os.environ.get("PORT", 8080))
    host = "0.0.0.0"

    server = await websockets.serve(
        on_connect,
        host=host,
        port=port,
        subprotocols=["ocpp1.6"],
        ping_interval=None
    )

    logger.info(f"✅ OCPP 1.6 Sunucusu çalışıyor: ws://{host}:{port}")
    logger.info(f"🔗 WebSocket URL (prod): wss://[your-render-app].onrender.com")

    await server.wait_closed()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("🛑 Sunucu kapatılıyor...")
