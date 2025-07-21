import asyncio
import websockets
from datetime import datetime
from ocpp.routing import on
from ocpp.v16 import ChargePoint as CP
from ocpp.v16 import call_result
from ocpp.v16.enums import Action, RegistrationStatus

class ChargePoint(CP):
    @on(Action.BootNotification)
    async def on_boot_notification(self, charge_point_vendor, charge_point_model, **kwargs):
        print(f"Şarj istasyonu bağlandı: {charge_point_vendor} - {charge_point_model}")
        return call_result.BootNotificationPayload(
            current_time=datetime.utcnow().isoformat(),
            interval=10,
            status=RegistrationStatus.accepted
        )

    @on(Action.Heartbeat)
    async def on_heartbeat(self):
        print("Heartbeat alındı")
        return call_result.HeartbeatPayload(
            current_time=datetime.utcnow().isoformat()
        )

    @on(Action.StatusNotification)
    async def on_status_notification(self, connector_id, error_code, status, **kwargs):
        print(f"Durum güncellemesi: Connector {connector_id}, Durum: {status}, Hata: {error_code}")
        return call_result.StatusNotificationPayload()

async def on_connect(websocket, path):
    try:
        charge_point_id = path.strip('/')
        cp = ChargePoint(charge_point_id, websocket)
        print(f"Yeni bağlantı: {charge_point_id}")
        await cp.start()
    except Exception as e:
        print(f"Bağlantı hatası: {e}")

async def main():
    server = await websockets.serve(
        on_connect,
        '0.0.0.0',
        9000,
        subprotocols=['ocpp1.6']
    )
    print("OCPP 1.6 Sunucusu çalışıyor... ws://0.0.0.0:9000")
    await server.wait_closed()

if __name__ == '__main__':
    asyncio.run(main())