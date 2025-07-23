import datetime
import logging
import os
import asyncpg

from ocpp.routing import on
from ocpp.v16 import ChargePoint as CP
from ocpp.v16 import call_result

logger = logging.getLogger("OCPP_Server")

async def connect_db():
    return await asyncpg.connect(
        host=os.environ.get("DB_HOST"),
        port=os.environ.get("DB_PORT", "5432"),
        user=os.environ.get("DB_USER"),
        password=os.environ.get("DB_PASS"),
        database=os.environ.get("DB_NAME")
    )

class ChargePoint(CP):
    def __init__(self, id, connection):
        super().__init__(id, connection)
        self.db = None

    async def start(self):
        logger.info(f"🔌 Yeni cihaz bağlandı - ID: {self.id}")
        self.db = await connect_db()
        try:
            await super().start()
        finally:
            await self.db.close()

    @on("BootNotification")
    async def on_boot_notification(self, charge_point_model, charge_point_vendor, **kwargs):
        logger.info(f"🔄 BootNotification - ID: {self.id}, Model: {charge_point_model}, Vendor: {charge_point_vendor}")
        await self.db.execute(
            """
            INSERT INTO boot_notifications (cp_id, model, vendor, timestamp)
            VALUES ($1, $2, $3, $4)
            """,
            self.id, charge_point_model, charge_point_vendor, datetime.datetime.utcnow()
        )
        return call_result.BootNotificationPayload(
            current_time=datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
            interval=30,
            status="Accepted"
        )

    @on("MeterValues")
    async def on_meter_values(self, connector_id, meter_value, **kwargs):
        logger.info(f"🔢 MeterValues - ID: {self.id}, Connector: {connector_id}, Samples: {len(meter_value)}")
        for mv in meter_value:
            timestamp = mv.get('timestamp')
            sampled = mv.get('sampledValue', [])
            for sample in sampled:
                value = sample.get("value")
                measurand = sample.get("measurand", "Energy.Active.Import.Register")
                unit = sample.get("unit", "Wh")
                await self.db.execute(
                    """
                    INSERT INTO meter_values (cp_id, connector_id, timestamp, measurand, value, unit)
                    VALUES ($1, $2, $3, $4, $5, $6)
                    """,
                    self.id, connector_id, timestamp, measurand, value, unit
                )
        return call_result.MeterValuesPayload()

    @on("StartTransaction")
    async def on_start_transaction(self, connector_id, id_tag, meter_start, timestamp, **kwargs):
        logger.info(f"⚡ StartTransaction - ID: {self.id}, Connector: {connector_id}, Tag: {id_tag}, MeterStart: {meter_start}")
        tx_id = 1234
        await self.db.execute(
            """
            INSERT INTO start_transactions (cp_id, transaction_id, connector_id, id_tag, meter_start, timestamp)
            VALUES ($1, $2, $3, $4, $5, $6)
            """,
            self.id, tx_id, connector_id, id_tag, meter_start, timestamp
        )
        return call_result.StartTransactionPayload(
            transaction_id=tx_id,
            id_tag_info={"status": "Accepted"}
        )

    @on("StopTransaction")
    async def on_stop_transaction(self, transaction_id, meter_stop, timestamp, **kwargs):
        logger.info(f"🛑 StopTransaction - ID: {self.id}, TxID: {transaction_id}, MeterStop: {meter_stop}")
        await self.db.execute(
            """
            INSERT INTO stop_transactions (cp_id, transaction_id, meter_stop, timestamp)
            VALUES ($1, $2, $3, $4)
            """,
            self.id, transaction_id, meter_stop, timestamp
        )
        return call_result.StopTransactionPayload(
            id_tag_info={"status": "Accepted"}
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
