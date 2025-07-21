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

# Log ayarları
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('OCPP-Sunucu')


# HTTP Sağlık Kontrol Sunucusu (8080 portunda)
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


def http_sunucu_baslat():
    server = HTTPServer(('0.0.0.0', 8080), HealthHandler)
    logger.info("HTTP Sağlık Kontrolü 8080 portunda çalışıyor")
    server.serve_forever()


# OCPP Şarj İstasyonu Sınıfı
class SarjIstasyonu(CP):
    @on(Action.BootNotification)
    async def boot_bildirimi(self, uretici, model, **kwargs):
        logger.info(f"Şarj istasyonu bağlandı: {uretici} - {model}")
        return call_result.BootNotificationPayload(
            current_time=datetime.utcnow().isoformat(),
            interval=10,
            status=RegistrationStatus.accepted
        )

    @on(Action.Heartbeat)
    async def kalp_atisi(self):
        return call_result.HeartbeatPayload(
            current_time=datetime.utcnow().isoformat()
        )


# WebSocket İstek İşleyici
async def istek_isleyici(path, istek_basliklari):
    """WebSocket öncesi sağlık kontrollerini yönetir"""
    if path == '/health' and istek_basliklari.get('Method') == 'HEAD':
        logger.debug("HEAD sağlık kontrolü alındı - HTTP 200 dönülüyor")
        return (200, [], b"OK")
    return None


# WebSocket Bağlantı Yöneticisi
async def baglanti_kabul(websocket, path):
    try:
        istasyon_id = path.strip('/')
        if not istasyon_id:
            logger.error("Geçersiz şarj istasyonu ID'si")
            await websocket.close()
            return

        istasyon = SarjIstasyonu(istasyon_id, websocket)
        logger.info(f"Yeni OCPP bağlantısı: {istasyon_id}")
        await istasyon.start()
    except websockets.exceptions.ConnectionClosed:
        logger.info(f"Bağlantı kapatıldı: {istasyon_id}")
    except Exception as e:
        logger.error(f"Bağlantı hatası: {e}")


async def ana():
    # WebSocket sunucusunu başlat
    ws_server = await websockets.serve(
        baglanti_kabul,
        '0.0.0.0',
        9000,
        subprotocols=['ocpp1.6'],
        process_request=istek_isleyici,
        ping_interval=None,
        ping_timeout=None
    )
    logger.info("OCPP 1.6 Sunucusu ws://0.0.0.0:9000 adresinde çalışıyor")
    await asyncio.Future()  # Sonsuza kadar çalış


if __name__ == '__main__':
    # HTTP sunucusunu ayrı bir thread'de başlat (Render sağlık kontrolleri için)
    http_thread = threading.Thread(target=http_sunucu_baslat)
    http_thread.daemon = True
    http_thread.start()

    # WebSocket sunucusunu başlat (OCPP bağlantıları için)
    try:
        asyncio.run(ana())
    except KeyboardInterrupt:
        logger.info("Sunucu kullanıcı tarafından durduruldu")
    except Exception as e:
        logger.error(f"Sunucu çöktü: {e}")