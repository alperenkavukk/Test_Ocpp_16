import asyncio
import logging
import datetime
import ssl
import os
import websockets
from ocpp.routing import on
from ocpp.v16 import ChargePoint as CP
from ocpp.v16 import call_result

# Log ayarları
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('OCPP_Server')


class ChargePoint(CP):
    @on("BootNotification")
    async def on_boot_notification(self, charge_point_model, charge_point_vendor, **kwargs):
        logger.info(f"BootNotification alındı: {charge_point_model} - {charge_point_vendor}")
        return call_result.BootNotificationPayload(
            current_time=datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
            interval=30,
            status="Accepted"
        )


async def on_connect(websocket, path):
    try:
        charge_point_id = path.strip('/') or f"CP_{websocket.id}"
        logger.info(f"Yeni bağlantı: {charge_point_id}")

        cp = ChargePoint(charge_point_id, websocket)
        await cp.start()
    except Exception as e:
        logger.error(f"Bağlantı hatası: {str(e)}")


async def main():
    # Render'ın atadığı portu al (PORT environment variable)
    port = int(os.environ.get("PORT", 9000))
    host = os.environ.get("HOST", "0.0.0.0")

    # SSL context (Render'da otomatik yönetiliyor)
    ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)

    server = await websockets.serve(
        on_connect,
        host=host,
        port=port,
        subprotocols=["ocpp1.6"],
        ssl=ssl_context,
        ping_interval=None
    )

    logger.info(f"✅ OCPP 1.6 Sunucusu çalışıyor... {host}:{port}")
    logger.info(f"WebSocket URL: wss://[YOUR_RENDER_URL].onrender.com")

    await server.wait_closed()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Sunucu kapatılıyor...")