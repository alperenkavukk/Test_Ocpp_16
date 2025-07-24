import asyncio
import datetime
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
        """Sunucuya boot bildirimi gönderir"""
        try:
            request = call.BootNotificationPayload(
                charge_point_model="Python_OCPP_Client",
                charge_point_vendor="Python_Vendor"
            )
            response = await self.call(request)
            logger.info(f"Sunucu yanıtı: {response.status}, interval: {response.interval}")
            return response
        except Exception as e:
            logger.error(f"BootNotification gönderim hatası: {str(e)}")
            return None

    async def send_heartbeat(self):
        """Düzenli heartbeat gönderir"""
        try:
            request = call.HeartbeatPayload()
            response = await self.call(request)
            logger.info(f"Heartbeat yanıtı: {response.current_time}")
            return response
        except Exception as e:
            logger.error(f"Heartbeat gönderim hatası: {str(e)}")
            return None

    async def simulate_charging(self):
        """Şarj işlemi simülasyonu"""
        try:
            # 1. Yetkilendirme
            auth = await self.call(call.AuthorizePayload(id_tag="TEST_TAG_123"))
            if auth.id_tag_info["status"] != "Accepted":
                raise Exception("Yetkilendirme reddedildi")

            # 2. Transaction başlat
            start_tx = await self.call(call.StartTransactionPayload(
                connector_id=1,
                id_tag="TEST_TAG_123",
                meter_start=0,
                timestamp=datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
            ))

            logger.info(f"Transaction başladı. ID: {start_tx.transaction_id}")

            # 3. Şarj simülasyonu (5 adet meter value gönder)
            for i in range(1, 6):
                await asyncio.sleep(5)
                await self.call(call.MeterValuesPayload(
                    connector_id=1,
                    meter_value=[{
                        "timestamp": datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
                        "sampledValue": [{
                            "value": str(i * 1000),
                            "measurand": "Energy.Active.Import.Register",
                            "unit": "Wh"
                        }]
                    }]
                ))
                logger.info(f"Meter value gönderildi: {i * 1000} Wh")

            # 4. Transaction durdur
            await self.call(call.StopTransactionPayload(
                transaction_id=start_tx.transaction_id,
                meter_stop=5000,
                timestamp=datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
            ))
            logger.info("Transaction başarıyla durduruldu")

        except Exception as e:
            logger.error(f"Şarj simülasyonu hatası: {str(e)}")


async def main():
    # Render URL'sini buraya girin
    render_url = "test-ocpp-16.onrender.com"  # SİZİN_URL'inizle değiştirin
    uri = f"wss://{render_url}/CP_1"

    # SSL ayarları (Production'da sertifika doğrulama aktif olmalı)
    ssl_context = ssl.create_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE  # Development için, production'da değiştirin

    try:
        async with websockets.connect(
                uri,
                subprotocols=["ocpp1.6"],
                ssl=ssl_context,
                extra_headers={"Origin": f"https://{render_url}"}
        ) as ws:
            logger.info(f"Sunucuya bağlandı: {uri}")
            cp = ChargePoint("CP_1", ws)

            # Boot bildirimi gönder
            if not await cp.send_boot_notification():
                raise Exception("BootNotification başarısız")

            # Heartbeat döngüsü
            asyncio.create_task(cp.start_heartbeat(interval=30))

            # Şarj simülasyonu başlat
            await cp.simulate_charging()

    except Exception as e:
        logger.error(f"Bağlantı hatası: {str(e)}")


if __name__ == "__main__":
    asyncio.run(main())