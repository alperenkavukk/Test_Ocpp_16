import asyncio
import websockets
from datetime import datetime
from ocpp.routing import on
from ocpp.v16 import ChargePoint as CP
from ocpp.v16 import call_result
from ocpp.v16.enums import Action, RegistrationStatus
from http.server import BaseHTTPRequestHandler, HTTPServer
import threading

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

def run_http_server():
    server = HTTPServer(('0.0.0.0', 8080), HealthHandler)
    print("HTTP Health Check running on port 8080")
    server.serve_forever()

# OCPP ChargePoint class
class ChargePoint(CP):
    @on(Action.BootNotification)  # Fixed: boot_notification -> BootNotification
    async def on_boot_notification(self, charge_point_vendor, charge_point_model, **kwargs):
        print(f"Charge station connected: {charge_point_vendor} - {charge_point_model}")
        return call_result.BootNotificationPayload(
            current_time=datetime.utcnow().isoformat(),
            interval=10,
            status=RegistrationStatus.accepted
        )

# WebSocket connection handler
async def on_connect(websocket, path):
    try:
        charge_point_id = path.strip('/')
        cp = ChargePoint(charge_point_id, websocket)
        print(f"New connection: {charge_point_id}")
        await cp.start()
    except Exception as e:
        print(f"Connection error: {e}")

async def main():
    # Start WebSocket server
    ws_server = await websockets.serve(
        on_connect,
        '0.0.0.0',
        9000,
        subprotocols=['ocpp1.6']
    )
    print("OCPP 1.6 Server running on ws://0.0.0.0:9000")
    await asyncio.Future()  # Run forever

if __name__ == '__main__':
    # Start HTTP server in a separate thread
    http_thread = threading.Thread(target=run_http_server)
    http_thread.daemon = True
    http_thread.start()

    # Start WebSocket server
    asyncio.run(main())