from aiohttp import web
import asyncio
import websockets
from datetime import datetime
from ocpp.routing import on
from ocpp.v16 import ChargePoint as CP
from ocpp.v16 import call_result
from ocpp.v16.enums import Action, RegistrationStatus


# HTTP Sağlık Kontrolü için
async def health_check(request):
    return web.Response(text="OK")


# OCPP ChargePoint sınıfı
class ChargePoint(CP):
    @on(Action.boot_notification)
    async def on_boot_notification(self, charge_point_vendor, charge_point_model, **kwargs):
        print(f"Şarj istasyonu bağlandı: {charge_point_vendor} - {charge_point_model}")
        return call_result.BootNotificationPayload(
            current_time=datetime.utcnow().isoformat(),
            interval=10,
            status=RegistrationStatus.accepted
        )

    # Diğer metodlar...


# WebSocket bağlantı handler'ı
async def on_connect(websocket, path):
    try:
        charge_point_id = path.strip('/')
        cp = ChargePoint(charge_point_id, websocket)
        print(f"Yeni bağlantı: {charge_point_id}")
        await cp.start()
    except Exception as e:
        print(f"Bağlantı hatası: {e}")


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

    print("HTTP Sağlık Kontrolü: http://0.0.0.0:8080/health")
    print("OCPP 1.6 Sunucusu çalışıyor... ws://0.0.0.0:9000")

    await asyncio.Future()  # Sonsuz döngü


if __name__ == '__main__':
    asyncio.run(main())