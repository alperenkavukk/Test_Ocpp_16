import asyncio
import logging
import datetime
import os
import websockets

from ocpp.routing import on
from ocpp.v16 import ChargePoint as CP
from ocpp.v16 import call_result

# 📒 Log yapılandırması
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("OCPP_Server")

# 🚘 Şarj Noktası Sınıfı
class ChargePoint(CP):

    async def start(self):
        logger.info(f"🔌 Yeni cihaz bağlandı - ID: {self.id}")
        try:
            await super().start()
        except websockets.exceptions.ConnectionClosedError:
            logger.warning(f"❌ Bağlantı kesildi - ID: {self.id}")
        except Exception as e:
            logger.error(f"⚠️ Hata oluştu - ID: {self.id}: {str(e)}")

    @on("BootNotification")
    async def on_boot_notification(self, charge_point_model, charge_point_vendor, **kwargs):
        logger.info(f"🔄 BootNotification - Model: {charge_point_model}, Vendor: {charge_point_vendor}")
        return call_result.BootNotificationPayload(
            current_time=datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
            interval=30,
            status="Accepted"
        )

    @on("Heartbeat")
    async def on_heartbeat(self):
        logger.info(f"💓 Heartbeat - Cihaz: {self.id}")
        return call_result.HeartbeatPayload(
            current_time=datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
        )

    @on("Authorize")
    async def on_authorize(self, id_tag):
        logger.info(f"🪪 Authorize - ID Tag: {id_tag}")
        return call_result.AuthorizePayload(
            id_tag_info={"status": "Accepted"}
        )

    @on("StartTransaction")
    async def on_start_transaction(self, connector_id, id_tag, meter_start, timestamp, **kwargs):
        logger.info(f"⚡ StartTransaction - Connector: {connector_id}, ID Tag: {id_tag}, Start Meter: {meter_start}")
        return call_result.StartTransactionPayload(
            transaction_id=1234,  # rastgele örnek ID
            id_tag_info={"status": "Accepted"}
        )

    @on("StopTransaction")
    async def on_stop_transaction(self, transaction_id, meter_stop, timestamp, **kwargs):
        logger.info(f"🛑 StopTransaction - Transaction ID: {transaction_id}, Stop Meter: {meter_stop}")
        return call_result.StopTransactionPayload(
            id_tag_info={"status": "Accepted"}
        )

    @on("StatusNotification")
    async def on_status_notification(self, connector_id, status, **kwargs):
        logger.info(f"📟 StatusNotification - Connector: {connector_id}, Status: {status}")
        return call_result.StatusNotificationPayload()

    @on("GetConfiguration")
    async def on_get_configuration(self, key=None):
        logger.info(f"⚙️ GetConfiguration - İstenen Ayarlar: {key}")
        return call_result.GetConfigurationPayload(
            configuration_key=[{
                "key": "HeartbeatInterval",
                "readonly": False,
                "value": "30"
            }],
            unknown_key=[]
        )

    @on("ChangeConfiguration")
    async def on_change_configuration(self, key, value):
        logger.info(f"🛠️ ChangeConfiguration - Ayar: {key}, Değer: {value}")
        return call_result.ChangeConfigurationPayload(status="Accepted")

    @on("Reset")
    async def on_reset(self, type):
        logger.info(f"♻️ Reset isteği alındı - Tip: {type}")
        return call_result.ResetPayload(status="Accepted")

    @on("MeterValues")
    async def on_meter_values(self, connector_id, meter_value, **kwargs):
        logger.info(f"🔢 MeterValues - Connector: {connector_id}")
        for entry in meter_value:
            timestamp = entry.get("timestamp")
            sampled_values = entry.get("sampledValue", [])
            for val in sampled_values:
                measurand = val.get("measurand", "Energy.Active.Import.Register")
                unit = val.get("unit", "Wh")
                value = val.get("value")
                logger.info(f"📊 Ölçüm: {measurand} = {value} {unit} @ {timestamp}")
        return call_result.MeterValuesPayload()
async def on_connect(websocket, path):
    try:
        charge_point_id = path.strip('/') or f"CP_{id(websocket)}"
        logger.info(f"🌐 Bağlantı - Path: {path}, Cihaz ID: {charge_point_id}")
        cp = ChargePoint(charge_point_id, websocket)
        await cp.start()
    except Exception as e:
        logger.error(f"⛔ Bağlantı hatası: {str(e)}")


async def main():
    port = int(os.environ.get("PORT", 8080))
    host = "0.0.0.0"

    server = await websockets.serve(
        on_connect,
        host=host,
        port=port,
        subprotocols=["ocpp1.6"],
        ping_interval=None
    )

    logger.info(f"✅ OCPP 1.6 Sunucusu çalışıyor: ws://{host}:{port}")
    logger.info("📡 WebSocket URL (prod): wss://<render-uygulama-adresi>")

    await server.wait_closed()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("🛑 Sunucu kapatılıyor...")
