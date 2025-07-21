import asyncio
import logging
import websockets
from ocpp.v16 import ChargePoint as CP
from ocpp.v16 import call

# Log ayarları
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)


class ChargePoint(CP):
    async def send_boot_notification(self):
        request = call.BootNotificationPayload(
            charge_point_model="Python_Model_V2",
            charge_point_vendor="Python_Vendor_Inc"
        )
        try:
            response = await self.call(request)
            logging.info(f"Sunucu yanıtı: Durum={response.status}, Interval={response.interval}")
        except Exception as e:
            logging.error(f"BootNotification hatası: {str(e)}")


async def main():
    # Local test için:
    # uri = "ws://localhost:9000/CP_1"

    # Render üzerindeki sunucu için:
    uri = "wss://test-ocpp-16.onrender.com/CP_1"

    try:
        async with websockets.connect(
                uri,
                subprotocols=["ocpp1.6"],
                ping_interval=None,
                # SSL doğrulamasını kapatmak için (sadece test amaçlı):
                # ssl=False
        ) as ws:
            cp = ChargePoint("CP_1", ws)
            await cp.send_boot_notification()

            # Diğer OCPP işlemleri için burada bekleyebilir
            while True:
                await asyncio.sleep(1)

    except websockets.exceptions.InvalidURI:
        logging.error("Geçersiz WebSocket URI")
    except websockets.exceptions.InvalidHandshake:
        logging.error("Bağlantı kurulamadı: OCPP 1.6 protokolü anlaşması başarısız")
    except Exception as e:
        logging.error(f"Beklenmeyen hata: {str(e)}")


if __name__ == "__main__":
    asyncio.run(main())