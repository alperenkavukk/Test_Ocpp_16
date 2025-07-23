import asyncio
import logging
import ssl
import websockets
from ocpp.v16 import ChargePoint as CP
from ocpp.v16 import call

# Log ayarları
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('OCPP_Client')


class ChargePoint(CP):
    async def send_boot_notification(self):
        request = call.BootNotificationPayload(
            charge_point_model="Python_OCPP_Client",
            charge_point_vendor="Python_Vendor"
        )
        response = await self.call(request)
        logger.info(f"Sunucu yanıtı: {response.status}, interval: {response.interval}")


async def main():
    # Render URL'sini buraya girin
    render_url = "test-ocpp-16.onrender.com"  # SİZİN_URL'inizle değiştirin
    uri = f"wss://{render_url}/CP_1"

    # SSL ayarları (Render'ın otomatik sertifikaları için)
    ssl_context = ssl.create_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE

    try:
        async with websockets.connect(
                uri,
                subprotocols=["ocpp1.6"],
                ssl=ssl_context,
                extra_headers={"Origin": f"https://{render_url}"}
        ) as ws:
            logger.info(f"Sunucuya bağlandı: {uri}")
            cp = ChargePoint("CP_1", ws)
            await cp.send_boot_notification()

            # Bağlantıyı açık tut
            while True:
                await asyncio.sleep(10)

    except Exception as e:
        logger.error(f"Bağlantı hatası: {str(e)}")


if __name__ == "__main__":
    asyncio.run(main())