import asyncio
import logging
import websockets
from datetime import datetime
from ocpp.v16 import ChargePoint as CP
from ocpp.v16.enums import Action, RegistrationStatus
from ocpp.v16 import call_result
from ocpp.routing import on

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ocpp")


class ChargePoint(CP):
    @on(Action.BootNotification)
    async def on_boot_notification(self, charge_point_vendor, charge_point_model, **kwargs):
        logger.info(f"Şarj istasyonu bağlandı: {charge_point_vendor} - {charge_point_model}")
        return call_result.BootNotificationPayload(
            current_time=datetime.utcnow().isoformat(),
            interval=10,
            status=RegistrationStatus.accepted
        )

    @on(Action.Heartbeat)
    async def on_heartbeat(self):
        logger.info("Heartbeat alındı.")
        return call_result.HeartbeatPayload(current_time=datetime.utcnow().isoformat())

    @on(Action.StatusNotification)
    async def on_status_notification(self, connector_id, error_code, status, **kwargs):
        logger.info(f"Durum güncellemesi: Connector {connector_id}, Durum: {status}, Hata: {error_code}")
        return call_result.StatusNotificationPayload()


async def on_connect(websocket, path):
    charge_point_id = path.strip("/")
    cp = ChargePoint(charge_point_id, websocket)
    logger.info(f"Yeni bağlantı geldi: {charge_point_id}")
    try:
        await cp.start()
    except Exception as e:
        logger.exception(f"Bağlantı sırasında hata: {e}")


async def main():
    server = await websockets.serve(
        on_connect,
        host="0.0.0.0",
        port=9000,
        subprotocols=["ocpp1.6"]
    )
    logger.info("OCPP 1.6 Sunucusu çalışıyor... ws://0.0.0.0:9000")
    await server.wait_closed()


if __name__ == '__main__':
    asyncio.run(main())
