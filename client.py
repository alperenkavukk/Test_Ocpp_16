import asyncio
import websockets
from ocpp.v16 import ChargePoint as CP
from ocpp.v16 import call


class ChargePoint(CP):
    async def send_boot_notification(self):
        request = call.BootNotificationPayload(
            charge_point_model="PythonModel",
            charge_point_vendor="PythonVendor"
        )
        response = await self.call(request)
        print(f"Sunucudan cevap: {response.status}, interval: {response.interval}")


async def main():
    uri = "ws://test-ocpp-16.onrender.com/CP_1"  # 🔁 kendi adresinle değiştir

    async with websockets.connect(
        uri,
        subprotocols=["ocpp1.6"]
    ) as ws:
        cp = ChargePoint("CP_1", ws)
        await cp.send_boot_notification()


if __name__ == "__main__":
    asyncio.run(main())
