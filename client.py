import asyncio
import websockets
from ocpp.v16 import ChargePoint as CP
from ocpp.v16 import call


async def test_charge_point():
    async with websockets.connect(
            'ws://localhost:9000/CP001',
            subprotocols=['ocpp1.6']
    ) as ws:
        cp = CP('CP001', ws)

        # BootNotification gönder
        boot_response = await cp.call(call.BootNotificationPayload(
            charge_point_vendor="VendorX",
            charge_point_model="ModelY"
        ))
        print("BootNotification Yanıtı:", boot_response)

        # Heartbeat gönder
        heartbeat_response = await cp.call(call.HeartbeatPayload())
        print("Heartbeat Yanıtı:", heartbeat_response)

        # StatusNotification gönder
        status_response = await cp.call(call.StatusNotificationPayload(
            connector_id=1,
            error_code="NoError",
            status="Available"
        ))
        print("StatusNotification Yanıtı:", status_response)


asyncio.run(test_charge_point())