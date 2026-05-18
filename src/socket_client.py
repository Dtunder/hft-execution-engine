import socket
import ssl
import selectors
import time
import json
import logging
import hmac
import hashlib
import struct
import os
import base64

logging.basicConfig(level=logging.INFO, format='%(asctime)s.%(msecs)03d - %(message)s', datefmt='%Y-%m-%d %H:%M:%S')

class FastExchangeConnection:
    """Low-allocation Python socket wrapper utilizing TCP_NODELAY."""
    __slots__ = ['exchange', 'host', 'port', 'sock', 'connected', 'last_heartbeat', 'latency_us', 'ssl_context', 'is_websocket']

    def __init__(self, exchange, host, port, is_websocket=False):
        self.exchange = exchange
        self.host = host
        self.port = port
        self.sock = None
        self.connected = False
        self.last_heartbeat = 0
        self.latency_us = 0.0
        self.ssl_context = ssl.create_default_context()
        self.is_websocket = is_websocket

    def connect(self):
        try:
            raw_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            raw_sock.setblocking(True)
            raw_sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            raw_sock.settimeout(2.0)

            self.sock = self.ssl_context.wrap_socket(raw_sock, server_hostname=self.host)
            self.sock.connect((self.host, self.port))
            self.sock.setblocking(False)

            self.connected = True
            logging.info(f"[CONNECT] Connected to {self.exchange} ({self.host}:{self.port}) with TLS")

            if self.is_websocket:
                self._ws_handshake()

            return True
        except Exception as e:
            logging.error(f"[ERROR] Failed to connect to {self.exchange}: {e}")
            self.connected = False
            return False

    def _ws_handshake(self):
        # Basic WebSocket Handshake
        path = "/ws-api/v3" if self.exchange == "Binance" else "/v5/trade"
        key = base64.b64encode(os.urandom(16)).decode('utf-8')
        handshake = (
            f"GET {path} HTTP/1.1\r\n"
            f"Host: {self.host}\r\n"
            f"Upgrade: websocket\r\n"
            f"Connection: Upgrade\r\n"
            f"Sec-WebSocket-Key: {key}\r\n"
            f"Sec-WebSocket-Version: 13\r\n\r\n"
        ).encode('utf-8')

        self.sock.setblocking(True)
        self.sock.sendall(handshake)
        resp = self.sock.recv(4096)
        self.sock.setblocking(False)
        if b"101 Switching Protocols" in resp:
            logging.info(f"[WS] Handshake successful for {self.exchange}")
        else:
            logging.error(f"[WS] Handshake failed for {self.exchange}: {resp[:100]}")
            self.connected = False

    def close(self):
        if self.sock:
            self.sock.close()
        self.connected = False
        self.sock = None

    def send_raw(self, data: memoryview):
        if not self.connected or not self.sock:
            return False
        total_sent = 0
        length = len(data)

        while total_sent < length:
            try:
                sent = self.sock.send(data[total_sent:])
                if sent == 0:
                    self.connected = False
                    return False
                total_sent += sent
            except (BlockingIOError, ssl.SSLWantWriteError):
                time.sleep(0.0001) # Yield briefly for backpressure
            except Exception as e:
                self.connected = False
                return False
        return True

    def send_ws_frame(self, payload: bytes):
        """Sends a masked WebSocket text frame."""
        length = len(payload)
        frame = bytearray()
        frame.append(0x81) # FIN + Text

        if length <= 125:
            frame.append(length | 0x80) # Masked
        elif length <= 65535:
            frame.append(126 | 0x80)
            frame.extend(struct.pack('>H', length))
        else:
            frame.append(127 | 0x80)
            frame.extend(struct.pack('>Q', length))

        masking_key = os.urandom(4)
        frame.extend(masking_key)

        masked_payload = bytearray(length)
        for i in range(length):
            masked_payload[i] = payload[i] ^ masking_key[i % 4]

        frame.extend(masked_payload)
        return self.send_raw(memoryview(frame))


class ExecutionSocketClient:
    """Low-Latency Execution Socket Client with Epoll/Kqueue and Failover."""
    def __init__(self, use_websocket=False):
        self.selector = selectors.DefaultSelector()
        self.use_websocket = use_websocket
        self.connections = {
            "Binance": FastExchangeConnection("Binance", "ws-api.binance.com" if use_websocket else "api.binance.com", 443, is_websocket=use_websocket),
            "Bybit": FastExchangeConnection("Bybit", "stream.bybit.com" if use_websocket else "api.bybit.com", 443, is_websocket=use_websocket)
        }
        self.primary = "Binance"
        self.secondary = "Bybit"
        self.heartbeat_interval_ms = 500
        self.api_key = "DUMMY_API_KEY"
        self.api_secret = "DUMMY_API_SECRET"

        # Pre-allocated buffers to minimize allocations
        self._buffer = bytearray(8192)

    def initialize(self):
        for name, conn in self.connections.items():
            if conn.connect():
                self.selector.register(conn.sock, selectors.EVENT_READ, data=conn)

    def check_heartbeats(self):
        current_time = time.perf_counter()
        for name, conn in self.connections.items():
            if conn.connected:
                if current_time - conn.last_heartbeat > (self.heartbeat_interval_ms / 1000.0):
                    if self.use_websocket:
                        # WS Ping frame (Opcode 0x9)
                        ping_frame = bytearray([0x89, 0x80])
                        masking_key = os.urandom(4)
                        ping_frame.extend(masking_key)
                        conn.send_raw(memoryview(ping_frame))
                    else:
                        # REST Ping
                        endpoint = "/api/v3/ping" if name == "Binance" else "/v5/market/time"
                        req = f"GET {endpoint} HTTP/1.1\r\nHost: {conn.host}\r\nConnection: keep-alive\r\n\r\n".encode('utf-8')
                        conn.send_raw(memoryview(req))
                    conn.last_heartbeat = current_time
            else:
                logging.warning(f"[{name}] Disconnected. Attempting reconnect...")
                if conn.sock:
                    try:
                        self.selector.unregister(conn.sock)
                    except KeyError:
                        pass
                if conn.connect():
                    self.selector.register(conn.sock, selectors.EVENT_READ, data=conn)

    def trigger_failover(self):
        logging.warning(f"[FAILOVER] {self.primary} latency spike or disconnection detected. Switching to {self.secondary}.")
        self.primary, self.secondary = self.secondary, self.primary
        logging.info(f"[FAILOVER] New primary exchange: {self.primary}")

    def sign_request(self, exchange, payload, timestamp):
        if exchange == "Binance":
            query = f"symbol={payload['symbol']}&side={payload['side']}&type=MARKET&quantity={payload['qty']}&timestamp={timestamp}"
            sig = hmac.new(self.api_secret.encode('utf-8'), query.encode('utf-8'), hashlib.sha256).hexdigest()
            return query + f"&signature={sig}"
        else:
            payload_str = json.dumps(payload)
            sign_str = f"{timestamp}{self.api_key}5000{payload_str}"
            sig = hmac.new(self.api_secret.encode('utf-8'), sign_str.encode('utf-8'), hashlib.sha256).hexdigest()
            return payload_str, sig

    def _prepare_order_data(self, conn, order_payload):
        timestamp = str(int(time.time() * 1000))

        if self.use_websocket:
            if conn.exchange == "Binance":
                query_sig = self.sign_request("Binance", order_payload, timestamp)
                ws_req = {
                    "id": "1",
                    "method": "order.place",
                    "params": {
                        "apiKey": self.api_key,
                        "symbol": order_payload["symbol"],
                        "side": order_payload["side"],
                        "type": "MARKET",
                        "quantity": order_payload["qty"],
                        "timestamp": int(timestamp),
                        "signature": query_sig.split("signature=")[1]
                    }
                }
            else:
                payload_str, sig = self.sign_request("Bybit", order_payload, timestamp)
                ws_req = {
                    "req_id": "1",
                    "op": "order.create",
                    "args": [
                        {
                            "symbol": order_payload["symbol"],
                            "side": order_payload["side"],
                            "orderType": "Market",
                            "qty": str(order_payload["qty"])
                        }
                    ]
                }
            return json.dumps(ws_req).encode('utf-8')

        else: # REST
            if conn.exchange == "Binance":
                query_str = self.sign_request("Binance", order_payload, timestamp)
                endpoint = f"/api/v3/order?{query_str}"
                req = (
                    f"POST {endpoint} HTTP/1.1\r\n"
                    f"Host: {conn.host}\r\n"
                    f"X-MBX-APIKEY: {self.api_key}\r\n"
                    f"Connection: keep-alive\r\n\r\n"
                ).encode('utf-8')
            else:
                payload_str, sig = self.sign_request("Bybit", order_payload, timestamp)
                endpoint = "/v5/order/create"
                req = (
                    f"POST {endpoint} HTTP/1.1\r\n"
                    f"Host: {conn.host}\r\n"
                    f"X-BAPI-API-KEY: {self.api_key}\r\n"
                    f"X-BAPI-TIMESTAMP: {timestamp}\r\n"
                    f"X-BAPI-SIGN: {sig}\r\n"
                    f"X-BAPI-RECV-WINDOW: 5000\r\n"
                    f"Content-Type: application/json\r\n"
                    f"Content-Length: {len(payload_str)}\r\n"
                    f"Connection: keep-alive\r\n\r\n"
                    f"{payload_str}"
                ).encode('utf-8')
            return req

    def route_order(self, order_payload):
        primary_conn = self.connections[self.primary]

        if not primary_conn.connected or primary_conn.latency_us > 200000.0:
            self.trigger_failover()
            primary_conn = self.connections[self.primary]

        start_time = time.perf_counter()

        # Prepare Data
        data = self._prepare_order_data(primary_conn, order_payload)

        if self.use_websocket:
            success = primary_conn.send_ws_frame(data)
        else:
            # Copy to pre-allocated buffer
            length = len(data)
            self._buffer[:length] = data
            success = primary_conn.send_raw(memoryview(self._buffer)[:length])

        if not success:
            logging.error("[ROUTE] Primary failed to send. Immediate failover.")
            self.trigger_failover()
            primary_conn = self.connections[self.primary]

            data_sec = self._prepare_order_data(primary_conn, order_payload)
            if self.use_websocket:
                success = primary_conn.send_ws_frame(data_sec)
            else:
                length = len(data_sec)
                self._buffer[:length] = data_sec
                success = primary_conn.send_raw(memoryview(self._buffer)[:length])

        latency = (time.perf_counter() - start_time) * 1_000_000

        if success:
            logging.info(f"[ROUTE] Order sent via {self.primary} {'WS' if self.use_websocket else 'REST'}. Latency: {latency:.2f}us")
        else:
            logging.error("[ROUTE] Failed to route order via both exchanges.")

    def run_event_loop(self, iterations=100):
        try:
            for _ in range(iterations):
                events = self.selector.select(timeout=0.001)
                for key, mask in events:
                    conn = key.data
                    if mask & selectors.EVENT_READ:
                        try:
                            data = conn.sock.recv(8192)
                            if not data:
                                conn.connected = False
                            else:
                                conn.latency_us = (time.perf_counter() - conn.last_heartbeat) * 1_000_000
                        except ssl.SSLWantReadError:
                            pass
                        except BlockingIOError:
                            pass
                        except Exception:
                            conn.connected = False

                self.check_heartbeats()
                time.sleep(0.001)
        except KeyboardInterrupt:
            pass
        finally:
            for conn in self.connections.values():
                conn.close()
            self.selector.close()

if __name__ == "__main__":
    # Test REST
    client_rest = ExecutionSocketClient(use_websocket=False)
    client_rest.initialize()
    order = {"symbol": "BTCUSDT", "side": "BUY", "qty": 1.5}
    client_rest.route_order(order)
    client_rest.run_event_loop(20)

    # Test WS
    client_ws = ExecutionSocketClient(use_websocket=True)
    client_ws.initialize()
    client_ws.route_order(order)
    client_ws.run_event_loop(20)
