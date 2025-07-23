import asyncio
import logging
import os
import websockets

from client import ChargePoint  # client.py içinden alınıyor

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("OCPP_Server")

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
