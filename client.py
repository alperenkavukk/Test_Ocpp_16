import asyncio
import logging
import ssl
import websockets
from ocpp.v16 import ChargePoint as CP
from ocpp.v16 import call

# Gelişmiş Loglama
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('ocpp_client.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('OCPP_Client')


class ChargePoint(CP):
    def __init__(self, id, connection):
        super().__init__(id, connection)
        self.connection_status = "disconnected"
        self.failover_urls = [
            "wss://primary-ocpp-server.example.com",
            "wss://standby-ocpp-server.example.com"
        ]

    async def connect_with_failover(self):
        """Yüksek erişilebilirlik için bağlantı yönetimi"""
        for url in self.failover_urls:
            try:
                ssl_context = ssl.create_default_context()
                ssl_context.check_hostname = False
                ssl_context.verify_mode = ssl.CERT_NONE

                connection = await websockets.connect(
                    f"{url}/CP_{self.id}",
                    subprotocols=["ocpp1.6"],
                    ssl=ssl_context
                )
                self.connection_status = "connected"
                logger.info(f"✅ Başarıyla bağlandı: {url}")
                return connection
            except Exception as e:
                logger.warning(f"⚠️ Bağlantı hatası ({url}): {str(e)}")
                continue

        raise ConnectionError("Tüm sunuculara bağlanılamadı")

    async def start(self):
        """HA destekli istemci başlatma"""
        try:
            ws = await self.connect_with_failover()
            self._connection = ws

            # Boot bildirimi gönder
            response = await self.send_boot_notification()
            if not response or response.status != "Accepted":
                raise Exception("BootNotification reddedildi")

            # Heartbeat döngüsü başlat
            asyncio.create_task(self.heartbeat_loop())

        except Exception as e:
            logger.error(f"❌ İstemci başlatma hatası: {str(e)}")
            self.connection_status = "failed"


async def main():
    """HA destekli istemci"""
    cp = ChargePoint("CP_1", None)
    await cp.start()

    # İstemciyi çalışır durumda tut
    while cp.connection_status == "connected":
        await asyncio.sleep(5)


if __name__ == "__main__":
    asyncio.run(main())