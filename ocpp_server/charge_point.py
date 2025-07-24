from ocpp.routing import on
from ocpp.v16 import ChargePoint as BaseChargePoint
from ocpp.v16 import call_result, call
from ocpp.v16.enums import (
    AuthorizationStatus, ChargePointStatus,
    RegistrationStatus, ResetType,
    FirmwareStatus, DiagnosticsStatus
)
import logging
from datetime import datetime

logger = logging.getLogger("ocpp")


class ChargePoint(BaseChargePoint):
    def __init__(self, id, connection):
        super().__init__(id, connection)
        self.status = ChargePointStatus.unavailable
        self.last_heartbeat = None
        self._db = None

    async def set_db(self, db):
        self._db = db

    # Core OCPP Methods
    @on("BootNotification")
    async def on_boot_notification(self, charge_point_model, charge_point_vendor, **kwargs):
        current_time = datetime.utcnow()
        logger.info(f"BootNotification from {self.id}")

        if self._db:
            await self._db.add_boot_notification(
                self.id, charge_point_model, charge_point_vendor, current_time
            )

        return call_result.BootNotificationPayload(
            current_time=current_time.isoformat(),
            interval=30,
            status=RegistrationStatus.accepted
        )

    @on("Heartbeat")
    async def on_heartbeat(self):
        current_time = datetime.utcnow()
        self.last_heartbeat = current_time
        self.status = ChargePointStatus.available

        if self._db:
            await self._db.add_heartbeat(self.id, current_time)

        return call_result.HeartbeatPayload(
            current_time=current_time.isoformat()
        )

    @on("StatusNotification")
    async def on_status_notification(self, connector_id, error_code, status, **kwargs):
        logger.info(f"StatusNotification from {self.id}")

        if self._db:
            await self._db.add_status_notification(
                self.id, connector_id, status, error_code, kwargs.get("timestamp")
            )

        return call_result.StatusNotificationPayload()

    # Authorization
    @on("Authorize")
    async def on_authorize(self, id_tag, **kwargs):
        logger.info(f"Authorize from {self.id} for tag {id_tag}")
        return call_result.AuthorizePayload(
            id_tag_info={"status": AuthorizationStatus.accepted}
        )

    # Transactions
    @on("StartTransaction")
    async def on_start_transaction(self, connector_id, id_tag, meter_start, timestamp, **kwargs):
        logger.info(f"StartTransaction from {self.id}")

        if self._db:
            async with self._db._pool.acquire() as conn:
                transaction_id = await conn.fetchval("""
                                                     INSERT INTO transactions
                                                         (charge_point_id, connector_id, id_tag, start_value, start_time)
                                                     VALUES ($1, $2, $3, $4, $5) RETURNING id
                                                     """, self.id, connector_id, id_tag, meter_start, timestamp)

                return call_result.StartTransactionPayload(
                    transaction_id=transaction_id,
                    id_tag_info={"status": AuthorizationStatus.accepted}
                )

        return call_result.StartTransactionPayload(
            transaction_id=1,
            id_tag_info={"status": AuthorizationStatus.accepted}
        )

    @on("StopTransaction")
    async def on_stop_transaction(self, transaction_id, meter_stop, timestamp, **kwargs):
        logger.info(f"StopTransaction from {self.id}")

        if self._db:
            async with self._db._pool.acquire() as conn:
                await conn.execute("""
                                   UPDATE transactions
                                   SET stop_value = $1,
                                       stop_time  = $2
                                   WHERE id = $3
                                   """, meter_stop, timestamp, transaction_id)

        return call_result.StopTransactionPayload(
            id_tag_info={"status": AuthorizationStatus.accepted}
        )

    # Meter Values
    @on("MeterValues")
    async def on_meter_values(self, connector_id, meter_value, **kwargs):
        logger.info(f"MeterValues from {self.id}")
        return call_result.MeterValuesPayload()

    # Remote Commands
    @on("RemoteStartTransaction")
    async def on_remote_start_transaction(self, connector_id, id_tag, **kwargs):
        logger.info(f"RemoteStartTransaction from {self.id}")
        return call_result.RemoteStartTransactionPayload(
            status=RegistrationStatus.accepted
        )

    @on("RemoteStopTransaction")
    async def on_remote_stop_transaction(self, transaction_id, **kwargs):
        logger.info(f"RemoteStopTransaction from {self.id}")
        return call_result.RemoteStopTransactionPayload(
            status=RegistrationStatus.accepted
        )

    @on("Reset")
    async def on_reset(self, reset_type, **kwargs):
        logger.info(f"Reset from {self.id}")
        return call_result.ResetPayload(
            status=ResetType.hard if reset_type == ResetType.hard
            else ResetType.soft
        )

    # Firmware Management
    @on("FirmwareStatusNotification")
    async def on_firmware_status_notification(self, status, **kwargs):
        logger.info(f"FirmwareStatusNotification from {self.id}")
        return call_result.FirmwareStatusNotificationPayload()

    # Diagnostics
    @on("DiagnosticsStatusNotification")
    async def on_diagnostics_status_notification(self, status, **kwargs):
        logger.info(f"DiagnosticsStatusNotification from {self.id}")
        return call_result.DiagnosticsStatusNotificationPayload()

    # Data Transfer
    @on("DataTransfer")
    async def on_data_transfer(self, vendor_id, message_id, data, **kwargs):
        logger.info(f"DataTransfer from {self.id}")
        return call_result.DataTransferPayload(
            status="Accepted"
        )