import asyncio
import logging
import websockets
from ocpp.routing import on
from ocpp.v16 import ChargePoint as CP
from ocpp.v16 import call_result

logging.basicConfig(level=logging.INFO)


class ChargePoint(CP):
    @on("BootNotification")
    async def on_boot_notification(self, charge_point_model, charge_point_vendor, **kwargs):
        logging.info("BootNotification alındı.")
        return call_result.BootNotificationPayload(
            current_time="2025-07-21T12:00:00Z",
            interval=10,
            status="Accepted"
        )


async def on_connect(websocket, path):  # ✅ BU ŞEKİLDE OLMALI
    logging.info("Yeni bağlantı alındı.")
    cp_id = path.strip("/") or "unknown"  # ws://localhost:9000/CP_1 gibi bağlantı varsa CP_1 alınır
    cp = ChargePoint(cp_id, websocket)

    await cp.start()


async def main():
    server = await websockets.serve(
        on_connect,
        "0.0.0.0",
        9000,
        subprotocols=["ocpp1.6"]
    )

    logging.info("OCPP 1.6 Sunucusu çalışıyor... ws://0.0.0.0:9000")
    await server.wait_closed()


if __name__ == "__main__":
    asyncio.run(main())
