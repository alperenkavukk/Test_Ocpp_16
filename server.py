from aiohttp import web
import asyncio
import websockets
from datetime import datetime
from ocpp.routing import on
from ocpp.v16 import ChargePoint as CP
from ocpp.v16 import call_result
from ocpp.v16.enums import Action, RegistrationStatus
import logging

# Log ayarları
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('OCPP-Server')


# HTTP Sağlık Kontrolü
async def health_check(request):
    return web.Response(text="OK", status=200)


class ChargePoint(CP):
    def __init__(self, id, connection):
        super().__init__(id, connection)
        self.status = "disconnected"

    @on(Action.BootNotification)
    async def on_boot_notification(self, charge_point_vendor, charge_point_model, **kwargs):
        logger.info(f"Şarj istasyonu bağlandı: {charge_point_vendor} - {charge_point_model}")
        self.status = "connected"
        return call_result.BootNotificationPayload(
            current_time=datetime.utcnow().isoformat(),
            interval=300,
            status=RegistrationStatus.accepted
        )

    @on(Action.Heartbeat)
    async def on_heartbeat(self):
        return call_result.HeartbeatPayload(
            current_time=datetime.utcnow().isoformat()
        )


async def ws_handler(websocket, path):
    """HEAD isteklerini ele alan özel WebSocket handler"""
    try:
        # Önce bir HTTP isteği bekleyelim
        request_headers = await websocket.recv()

        # Eğer bu bir HEAD isteği ise (Render health check)
        if request_headers.startswith('HEAD'):
            logger.debug("HEAD isteği alındı (health check), 200 döndürülüyor")
            await websocket.send("HTTP/1.1 200 OK\r\n\r\n")
            await websocket.close()
            return

        # Normal WebSocket bağlantısı
        charge_point_id = path.strip('/')
        if not charge_point_id:
            logger.error("Geçersiz şarj istasyonu ID'si")
            await websocket.close()
            return

        cp = ChargePoint(charge_point_id, websocket)
        logger.info(f"Yeni bağlantı: {charge_point_id}")
        await cp.start()

    except websockets.exceptions.ConnectionClosed:
        logger.info(f"Bağlantı kapatıldı: {charge_point_id}")
    except Exception as e:
        logger.error(f"Bağlantı hatası: {str(e)}")


async def main():
    # HTTP sunucu
    app = web.Application()
    app.router.add_get('/health', health_check)
    app.router.add_head('/health', health_check)  # HEAD isteklerini de kabul et

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', 8080)
    await site.start()

    # WebSocket sunucu
    ws_server = await websockets.serve(
        ws_handler,  # Özel handler kullanıyoruz
        '0.0.0.0',
        9000,
        subprotocols=['ocpp1.6'],
        # Render'ın health check'leri için ek ayarlar
        process_request=handle_health_check,
        ping_interval=None,
        ping_timeout=None
    )

    logger.info("HTTP Sağlık Kontrolü: http://0.0.0.0:8080/health")
    logger.info("OCPP 1.6 Sunucusu çalışıyor... ws://0.0.0.0:9000")

    await asyncio.Future()  # Sonsuz döngü


async def handle_health_check(path, headers):
    """Render'ın HEAD isteklerini işle"""
    if path == '/health' and headers.get('method') == 'HEAD':
        logger.debug("HEAD health check isteği alındı")
        return ('HTTP/1.1 200 OK\r\n\r\n', [])
    return None


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Sunucu kapatılıyor...")
    except Exception as e:
        logger.error(f"Sunucu hatası: {str(e)}")