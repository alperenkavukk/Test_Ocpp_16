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
            charge_point_vendor="Python_Vendor",
            firmware_version="1.0.0"
        )
        try:
            response = await self.call(request)
            logger.info(f"BootNotification yanıtı: status={response.status}, interval={response.interval}")
            return response
        except Exception as e:
            logger.error(f"BootNotification hatası: {str(e)}")
            raise


async def main():
    # Render URL'si
    uri = "wss://test-ocpp-16.onrender.com/CP_1"

    # SSL ayarları (Render'ın otomatik sertifikaları için)
    ssl_context = ssl.create_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE

    try:
        async with websockets.connect(
                uri,
                subprotocols=["ocpp1.6"],
                ssl=ssl_context,
                extra_headers={
                    "Origin": "https://test-ocpp-16.onrender.com",
                    "Sec-WebSocket-Protocol": "ocpp1.6"
                },
                ping_interval=20,
                ping_timeout=20
        ) as ws:
            logger.info(f"Sunucuya bağlandı: {uri}")
            logger.info(f"Protokol: {ws.subprotocol}")

            cp = ChargePoint("CP_1", ws)
            await cp.send_boot_notification()

            # Bağlantıyı açık tut
            while True:
                await asyncio.sleep(10)

    except websockets.exceptions.InvalidHandshake as e:
        logger.error(f"Bağlantı hatası (InvalidHandshake): {str(e)}")
        logger.error("Muhtemelen OCPP protokolü anlaşması başarısız oldu")
    except websockets.exceptions.InvalidURI as e:
        logger.error(f"Geçersiz URI: {str(e)}")
    except Exception as e:
        logger.error(f"Beklenmeyen hata: {str(e)}")


if __name__ == "__main__":
    asyncio.run(main())