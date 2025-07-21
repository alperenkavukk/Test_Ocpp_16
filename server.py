import asyncio
import logging
import datetime
import ssl
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
        # Bağlantı bilgilerini logla
        logger.info(f"Yeni bağlantı: {websocket.remote_address}")
        logger.info(f"Headers: {websocket.request_headers}")

        charge_point_id = path.strip('/')
        if not charge_point_id:
            charge_point_id = f"CP_{websocket.id}"
            logger.warning(f"Charge Point ID belirtilmedi, otomatik atandı: {charge_point_id}")

        cp = ChargePoint(charge_point_id, websocket)
        await cp.start()
    except websockets.exceptions.ConnectionClosed:
        logger.info(f"Bağlantı kapatıldı: {charge_point_id}")
    except Exception as e:
        logger.error(f"Bağlantı hatası: {str(e)}")


async def main():
    # Render için SSL context oluştur
    ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ssl_context.minimum_version = ssl.TLSVersion.TLSv1_2
    ssl_context.set_ciphers('DEFAULT:@SECLEVEL=1')

    try:
        server = await websockets.serve(
            on_connect,
            host="0.0.0.0",
            port=9000,
            subprotocols=["ocpp1.6"],
            ssl=ssl_context,
            ping_interval=None,
            ping_timeout=None,
            reuse_port=True
        )

        logger.info("✅ OCPP 1.6 Sunucusu çalışıyor...")
        logger.info(f"wss://0.0.0.0:9000")
        logger.info(f"Desteklenen protokoller: {server.subprotocols}")

        await server.wait_closed()
    except Exception as e:
        logger.error(f"Sunucu hatası: {str(e)}")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Sunucu kapatılıyor...")