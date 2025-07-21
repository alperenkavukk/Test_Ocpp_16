from aiohttp import web
import asyncio
import websockets
from datetime import datetime
from ocpp.routing import on
from ocpp.v16 import ChargePoint as CP
from ocpp.v16 import call_result
from ocpp.v16.enums import Action, RegistrationStatus, ChargePointStatus
import logging
import signal

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('OCPP-Server')


# HTTP Health Check
async def health_check(request):
    return web.Response(text="OK", status=200)


class ChargePoint(CP):
    def __init__(self, id, connection):
        super().__init__(id, connection)
        self.status = "disconnected"
        self.connectors = {}

    @on(Action.BootNotification)
    async def on_boot_notification(self, charge_point_vendor, charge_point_model, **kwargs):
        logger.info(f"Charge station connected: {charge_point_vendor} - {charge_point_model}")
        self.status = "connected"
        return call_result.BootNotificationPayload(
            current_time=datetime.utcnow().isoformat(),
            interval=300,  # 5 minutes
            status=RegistrationStatus.accepted
        )

    @on(Action.Heartbeat)
    async def on_heartbeat(self):
        logger.debug("Received heartbeat")
        return call_result.HeartbeatPayload(
            current_time=datetime.utcnow().isoformat()
        )

    @on(Action.StatusNotification)
    async def on_status_notification(self, connector_id, status, error_code, **kwargs):
        self.connectors[connector_id] = status
        logger.info(f"Connector {connector_id} status: {status}")
        return call_result.StatusNotificationPayload()

    @on(Action.Authorize)
    async def on_authorize(self, id_tag, **kwargs):
        logger.info(f"Authorization request for tag: {id_tag}")
        return call_result.AuthorizePayload(
            id_tag_info={"status": "Accepted"}
        )


async def on_connect(websocket, path):
    charge_point_id = path.strip('/')
    if not charge_point_id:
        logger.error("Invalid charge point ID")
        await websocket.close()
        return

    cp = ChargePoint(charge_point_id, websocket)
    logger.info(f"New connection: {charge_point_id}")

    try:
        await cp.start()
    except websockets.exceptions.ConnectionClosed:
        logger.info(f"Connection closed: {charge_point_id}")
    except Exception as e:
        logger.error(f"Error for {charge_point_id}: {str(e)}")


async def shutdown(signal, loop, ws_server, runner):
    logger.info("Shutting down server...")
    ws_server.close()
    await ws_server.wait_closed()
    await runner.cleanup()
    loop.stop()


async def main():
    loop = asyncio.get_running_loop()

    # Set up signal handlers
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(
            sig,
            lambda: asyncio.create_task(
                shutdown(sig, loop, ws_server, runner)
            )
        )

    # HTTP Server
    app = web.Application()
    app.router.add_get('/health', health_check)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', 8080)
    await site.start()

    # WebSocket Server
    ws_server = await websockets.serve(
        on_connect,
        '0.0.0.0',
        9000,
        subprotocols=['ocpp1.6'],
        ping_interval=None,
        ping_timeout=None
    )

    logger.info("HTTP Health Check: http://0.0.0.0:8080/health")
    logger.info("OCPP 1.6 Server running on ws://0.0.0.0:9000")

    await asyncio.Future()  # Run forever


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Server stopped by user")
    except Exception as e:
        logger.error(f"Server crashed: {str(e)}")