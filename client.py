import asyncio
import datetime
import logging
import ssl
import websockets
from ocpp.v16 import ChargePoint as CP
from ocpp.v16 import call

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('OCPP_Client')

class ChargePoint(CP):
    async def send_boot_notification(self):
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
        try:
            request = call.HeartbeatPayload()
            response = await self.call(request)
            logger.info(f"Heartbeat yanıtı: {response.current_time}")
            return response
        except Exception as e:
            logger.error(f"Heartbeat gönderim hatası: {str(e)}")
            return None

    async def simulate_charging(self):
        try:
            auth = await self.call(call.AuthorizePayload(id_tag="TEST_TAG_123"))
            if auth.id_tag_info["status"] != "Accepted":
                raise Exception("Yetkilendirme reddedildi")

            start_tx = await self.call(call.StartTransactionPayload(
                connector_id=1,
                id_tag="TEST_TAG_123",
                meter_start=0,
                timestamp=datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
            ))
            logger.info(f"Transaction başladı. ID: {start_tx.transaction_id}")

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

            await self.call(call.StopTransactionPayload(
                transaction_id=start_tx.transaction_id,
                meter_stop=5000,
                timestamp=datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
            ))
            logger.info("Transaction başarıyla durduruldu")

        except Exception as e:
            logger.error(f"Şarj simülasyonu hatası: {str(e)}")

async def main():
    render_url = "test-ocpp-16.onrender.com"  # Render'daki domain
    uri = f"wss://{render_url}/CP_1"

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
            if not await cp.send_boot_notification():
                raise Exception("BootNotification başarısız")
            asyncio.create_task(cp.send_heartbeat())
            await cp.simulate_charging()

    except Exception as e:
        logger.error(f"Bağlantı hatası: {str(e)}")

if __name__ == "__main__":
    asyncio.run(main())
