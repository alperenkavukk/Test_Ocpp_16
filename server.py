import asyncio
import logging
import datetime
import os
import websockets

from ocpp.routing import on
from ocpp.v16 import ChargePoint as CP
from ocpp.v16 import call_result

# 🔧 Log ayarları
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('OCPP_Server')


class ChargePoint(CP):
    async def start(self):
        logger.info(f"🔌 Yeni cihaz bağlandı - ID: {self.id}")
        try:
            await super().start()
        except websockets.exceptions.ConnectionClosedError as e:
            logger.warning(f"❌ Bağlantı koptu - ID: {self.id}, Sebep: {str(e)}")
        except Exception as e:
            logger.error(f"⚠️ Cihaz hatası - ID: {self.id}: {str(e)}")

    @on("BootNotification")
    async def on_boot_notification(self, charge_point_model, charge_point_vendor, **kwargs):
        logger.info(f"🔄 BootNotification - ID: {self.id}, Model: {charge_point_model}, Vendor: {charge_point_vendor}")
        return call_result.BootNotificationPayload(
            current_time=datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
            interval=30,
            status="Accepted"
        )

    @on("Heartbeat")
    async def on_heartbeat(self):
        logger.info(f"💓 Heartbeat - ID: {self.id}")
        return call_result.HeartbeatPayload(
            current_time=datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
        )

    @on("Authorize")
    async def on_authorize(self, id_tag):
        logger.info(f"🪪 Authorize - ID: {self.id}, Tag: {id_tag}")
        return call_result.AuthorizePayload(
            id_tag_info={"status": "Accepted"}
        )

    @on("StartTransaction")
    async def on_start_transaction(self, connector_id, id_tag, meter_start, timestamp, **kwargs):
        logger.info(f"⚡ StartTransaction - ID: {self.id}, Connector: {connector_id}, Tag: {id_tag}, MeterStart: {meter_start}")
        return call_result.StartTransactionPayload(
            transaction_id=1234,  # İstediğin ID’yi burada üret
            id_tag_info={"status": "Accepted"}
        )

    @on("StopTransaction")
    async def on_stop_transaction(self, transaction_id, meter_stop, timestamp, **kwargs):
        logger.info(f"🛑 StopTransaction - ID: {self.id}, TxID: {transaction_id}, MeterStop: {meter_stop}")
        return call_result.StopTransactionPayload(
            id_tag_info={"status": "Accepted"}
        )

    @on("StatusNotification")
    async def on_status_notification(self, connector_id, status, error_code=None, **kwargs):
        logger.info(f"📟 StatusNotification - ID: {self.id}, Connector: {connector_id}, Status: {status}, Error: {error_code}")
        return call_result.StatusNotificationPayload()

    @on("MeterValues")
    async def on_meter_values(self, connector_id, meter_value, **kwargs):
        # meter_value: list of dict'ler; her biri bir zaman ve ölçüm dizisi içerir
        logger.info(f"🔢 MeterValues - ID: {self.id}, Connector: {connector_id}, Samples: {len(meter_value)}")
        # Her örnekten ilk sample'ı logla
        first = meter_value[0]
        ts = first.get('timestamp')
        meas = first.get('measurands', [])
        logger.info(f"    ► İlk örnek: {ts}, measurands: {meas}")
        return call_result.MeterValuesPayload()

    @on("GetConfiguration")
    async def on_get_configuration(self, key=None):
        logger.info(f"⚙️ GetConfiguration - ID: {self.id}, Key: {key}")
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
        logger.info(f"🛠️ ChangeConfiguration - ID: {self.id}, Key: {key}, Value: {value}")
        return call_result.ChangeConfigurationPayload(status="Accepted")

    @on("Reset")
    async def on_reset(self, type):
        logger.info(f"♻️ Reset - ID: {self.id}, Type: {type}")
        return call_result.ResetPayload(status="Accepted")



async def on_connect(websocket, path):
    charge_point_id = path.strip("/") or f"CP_{id(websocket)}"
    logger.info(f"🌐 Yeni bağlantı isteği - Path: {path}, Atanan ID: {charge_point_id}")

    cp = ChargePoint(charge_point_id, websocket)
    await cp.start()


async def main():
    port = int(os.environ.get("PORT", 8080))
    host = "0.0.0.0"

    server = await websockets.serve(
        on_connect,
        host=host,
        port=port,
        subprotocols=["ocpp1.6"],
        ping_interval=20,
        ping_timeout=30
    )

    public_url = os.environ.get("RENDER_EXTERNAL_URL", "[render-url-bulunamadı]")
    logger.info(f"✅ OCPP 1.6 Sunucusu çalışıyor: ws://{host}:{port}")
    logger.info(f"🔗 WebSocket URL (prod): wss://{public_url}")

    await server.wait_closed()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("🛑 Sunucu kapatılıyor...")
