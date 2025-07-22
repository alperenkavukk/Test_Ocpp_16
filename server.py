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
        except websockets.exceptions.ConnectionClosedError as e:
            logger.warning(f"❌ Bağlantı koptu - ID: {self.id}, Sebep: {str(e)}")
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
    charge_point_id = path.strip("/") or f"CP_{id(websocket)}"
    logger.info(f"🌐 Yeni bağlantı isteği - Path: {path}, Atanan ID: {charge_point_id}")

    cp = ChargePoint(charge_point_id, websocket)
    await cp.start()


async def main():
    port = int(os.environ.get("PORT", 8080))
    host = "0.0.0.0"

    server = await websockets.serve(
        on_connect,
        host=host,
        port=port,
        subprotocols=["ocpp1.6"],
        ping_interval=20,
        ping_timeout=30
    )

    public_url = os.environ.get("RENDER_EXTERNAL_URL", "[render-url-bulunamadı]")
    logger.info(f"✅ OCPP 1.6 Sunucusu çalışıyor: ws://{host}:{port}")
    logger.info(f"🔗 WebSocket URL (prod): wss://{public_url}")

    await server.wait_closed()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("🛑 Sunucu kapatılıyor...")
