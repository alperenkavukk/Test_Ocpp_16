import asyncio
import websockets
from datetime import datetime
from ocpp.routing import on
from ocpp.v16 import ChargePoint as CP
from ocpp.v16 import call_result
from ocpp.v16.enums import Action, RegistrationStatus
from http.server import BaseHTTPRequestHandler, HTTPServer
import threading
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('OCPP-Server')


# HTTP Health Check Server
class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/health':
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"OK")
        else:
            self.send_response(404)
            self.end_headers()

    def do_HEAD(self):
        if self.path == '/health':
            self.send_response(200)
            self.end_headers()
        else:
            self.send_response(404)
            self.end_headers()


def run_http_server():
    server = HTTPServer(('0.0.0.0', 8080), HealthHandler)
    logger.info("HTTP Health Check running on port 8080")
    server.serve_forever()


# OCPP ChargePoint class
class ChargePoint(CP):
    @on(Action.BootNotification)
    async def on_boot_notification(self, charge_point_vendor, charge_point_model, **kwargs):
        logger.info(f"Charge station connected: {charge_point_vendor} - {charge_point_model}")
        return call_result.BootNotificationPayload(
            current_time=datetime.utcnow().isoformat(),
            interval=10,
            status=RegistrationStatus.accepted
        )


# Custom WebSocket request processor
async def process_request(path, headers):
    """Handle health checks before WebSocket upgrade"""
    if path == '/health' and headers.get('Method') == 'HEAD':
        logger.debug("Received HEAD health check")
        return (200, [], b"OK")
    return None


# WebSocket connection handler
async def on_connect(websocket, path):
    try:
        charge_point_id = path.strip('/')
        if not charge_point_id:
            logger.error("Invalid charge point ID")
            await websocket.close()
            return

        cp = ChargePoint(charge_point_id, websocket)
        logger.info(f"New connection: {charge_point_id}")
        await cp.start()
    except websockets.exceptions.ConnectionClosed:
        logger.info(f"Connection closed: {charge_point_id}")
    except Exception as e:
        logger.error(f"Connection error: {e}")


async def main():
    # Start WebSocket server with custom request processor
    ws_server = await websockets.serve(
        on_connect,
        '0.0.0.0',
        9000,
        subprotocols=['ocpp1.6'],
        process_request=process_request
    )
    logger.info("OCPP 1.6 Server running on ws://0.0.0.0:9000")
    await asyncio.Future()  # Run forever


if __name__ == '__main__':
    # Start HTTP server in a separate thread
    http_thread = threading.Thread(target=run_http_server)
    http_thread.daemon = True
    http_thread.start()

    # Start WebSocket server
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Server stopped by user")
    except Exception as e:
        logger.error(f"Server crashed: {e}")