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

# HTTP Sağlık Kontrolü için
async def health_check(request):
    return web.Response(text="OK")

# OCPP ChargePoint sınıfı
class ChargePoint(CP):
    @on(Action.BootNotification)  # DÜZELTME: boot_notification -> BootNotification
    async def on_boot_notification(self, charge_point_vendor, charge_point_model, **kwargs):
        logger.info(f"Şarj istasyonu bağlandı: {charge_point_vendor} - {charge_point_model}")
        return call_result.BootNotificationPayload(
            current_time=datetime.utcnow().isoformat(),
            interval=10,
            status=RegistrationStatus.accepted
        )

    @on(Action.Heartbeat)
    async def on_heartbeat(self):
        logger.info("Heartbeat alındı")
        return call_result.HeartbeatPayload(
            current_time=datetime.utcnow().isoformat()
        )

    @on(Action.StatusNotification)
    async def on_status_notification(self, connector_id, status, error_code, **kwargs):
        logger.info(f"Durum güncellemesi - Konnektör {connector_id}: {status}")
        return call_result.StatusNotificationPayload()

# WebSocket bağlantı handler'ı
async def on_connect(websocket, path):
    try:
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
    # HTTP sunucu oluştur
    app = web.Application()
    app.router.add_get('/health', health_check)

    # HTTP sunucuyu başlat
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', 8080)
    await site.start()

    # WebSocket sunucuyu başlat
    ws_server = await websockets.serve(
        on_connect,
        '0.0.0.0',
        9000,
        subprotocols=['ocpp1.6']
    )

    logger.info("HTTP Sağlık Kontrolü: http://0.0.0.0:8080/health")
    logger.info("OCPP 1.6 Sunucusu çalışıyor... ws://0.0.0.0:9000")

    await asyncio.Future()  # Sonsuz döngü

if __name__ == '__main__':
    asyncio.run(main())