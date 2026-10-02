"""Local Sonos native host. Python standard library + an installed FFmpeg binary."""
import collections
import ipaddress
import json
import os
import queue
import secrets
import select
import socket
import struct
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from xml.sax.saxutils import escape

ROOT = Path(__file__).resolve().parent
HTTP = urllib.request.build_opener(urllib.request.ProxyHandler({}))
CACHE = ROOT / "known-devices.json"


def interface_addresses():
    """Windows resolves the machine name to addresses on all active adapters."""
    addresses = set()
    for item in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET, socket.SOCK_DGRAM):
        try:
            addresses.add(local_ip(item[4][0]))
        except ValueError:
            pass
    return sorted(addresses)


def ssdp_discover(timeout=3.0):
    """Probe every adapter concurrently instead of relying on the multicast route."""
    sockets, found = [], set()
    targets = ("urn:schemas-upnp-org:device:ZonePlayer:1", "urn:schemas-upnp-org:device:MediaRenderer:1")
    try:
        for address in interface_addresses():
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            try:
                sock.bind((address, 0))
                sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_IF, socket.inet_aton(address))
                sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 2)
                sock.setblocking(False)
                for target in targets:
                    packet = ('M-SEARCH * HTTP/1.1\r\nHOST: 239.255.255.250:1900\r\nMAN: "ssdp:discover"\r\n'
                              'MX: 1\r\nST: {}\r\n\r\n').format(target).encode()
                    # Retry once: UDP discovery packets can be lost.
                    for _ in range(2):
                        sock.sendto(packet, ("239.255.255.250", 1900))
                sockets.append(sock)
            except OSError:
                sock.close()  # An adapter may disappear during enumeration.
        deadline = time.monotonic() + timeout
        while sockets and time.monotonic() < deadline:
            readable, _, _ = select.select(sockets, [], [], min(0.3, max(0, deadline - time.monotonic())))
            for sock in readable:
                try:
                    payload, address = sock.recvfrom(65536)
                    # MediaRenderer also returns TVs etc.; only probe Sonos responses.
                    if b"sonos" in payload.lower() or b"zoneplayer" in payload.lower():
                        found.add(local_ip(address[0]))
                except (OSError, ValueError):
                    continue
        return found
    finally:
        for sock in sockets:
            sock.close()


def known_devices():
    try:
        values = json.loads(CACHE.read_text(encoding="utf-8"))
        if not isinstance(values, list):
            return set()
        result = set()
        for value in values[:64]:
            try:
                result.add(local_ip(value))
            except (ValueError, TypeError):
                pass
        return result
    except (OSError, ValueError):
        return set()


def remember_devices(addresses):
    try:
        temporary = CACHE.with_suffix(".tmp")
        temporary.write_text(json.dumps(sorted(addresses)[:64]), encoding="utf-8")
        temporary.replace(CACHE)
    except OSError:
        pass  # Discovery still works when the installation directory is read-only.


def local_ip(value):
    address = ipaddress.IPv4Address(value)
    if not address.is_private or address.is_loopback or address.is_unspecified or address.is_multicast or address.is_link_local:
        raise ValueError("Bitte eine private IPv4-Adresse des Sonos-Geräts eingeben")
    return str(address)


def field(xml, name, default=""):
    for element in xml.iter():
        if element.tag.split("}")[-1] == name:
            return element.text or default
    return default


def soap(ip, service, action, **values):
    ip = local_ip(ip)
    paths = {"AVTransport": "MediaRenderer", "RenderingControl": "MediaRenderer", "GroupRenderingControl": "MediaRenderer", "ZoneGroupTopology": "ZoneGroupTopology"}
    service_type = "urn:schemas-upnp-org:service:" + service + ":1"
    content = "".join("<{0}>{1}</{0}>".format(key, escape(str(value))) for key, value in values.items())
    body = ('<?xml version="1.0"?><s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/" '
            's:encodingStyle="http://schemas.xmlsoap.org/soap/encoding/"><s:Body>'
            '<u:{0} xmlns:u="{1}">{2}</u:{0}></s:Body></s:Envelope>').format(action, service_type, content)
    path = "/{}/Control".format(service) if service == "ZoneGroupTopology" else "/{}/{}/Control".format(paths[service], service)
    request = urllib.request.Request("http://{}:1400{}".format(ip, path), data=body.encode(), headers={
        "Content-Type": 'text/xml; charset="utf-8"', "SOAPAction": '"{}#{}"'.format(service_type, action)
    })
    try:
        with HTTP.open(request, timeout=4) as response:
            return ET.fromstring(response.read(1024 * 1024))
    except urllib.error.HTTPError as error:
        detail = error.read(65536).decode("utf-8", "replace")
        raise RuntimeError("Sonos lehnt {} ab (HTTP {}). UPnP-Einstellung prüfen. {}".format(action, error.code, detail[-350:])) from error


def device(ip):
    ip = local_ip(ip)
    with HTTP.open("http://{}:1400/xml/device_description.xml".format(ip), timeout=3) as response:
        xml = ET.fromstring(response.read(1024 * 1024))
    if "sonos" not in field(xml, "manufacturer").lower():
        raise ValueError("Unter dieser Adresse wurde kein Sonos gefunden")
    return {"ip": ip, "name": field(xml, "roomName", field(xml, "friendlyName", ip))}


def volume(ip, value=None):
    values = {"InstanceID": 0}
    if value is not None:
        if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= 100:
            raise ValueError("Lautstärke muss zwischen 0 und 100 liegen")
        soap(ip, "GroupRenderingControl", "SnapshotGroupVolume", **values)
        soap(ip, "GroupRenderingControl", "SetGroupVolume", DesiredVolume=value, **values)
        return value
    soap(ip, "GroupRenderingControl", "SnapshotGroupVolume", **values)
    return int(field(soap(ip, "GroupRenderingControl", "GetGroupVolume", **values), "CurrentVolume", "0"))


def topology(ip):
    xml = soap(ip, "ZoneGroupTopology", "GetZoneGroupState")
    return ET.fromstring(field(xml, "ZoneGroupState"))


def group_target(ip):
    # Always control the coordinator, preserving existing groups and stereo pairs.
    for group in topology(ip).iter("ZoneGroup"):
        members = list(group.iter("ZoneGroupMember"))
        if any(urllib.parse.urlparse(member.get("Location", "")).hostname == ip for member in members):
            coordinator = next((member for member in members if member.get("UUID") == group.get("Coordinator")), None)
            if coordinator is not None:
                return local_ip(urllib.parse.urlparse(coordinator.get("Location")).hostname)
    raise RuntimeError("Sonos-Gruppenkoordinator wurde nicht gefunden")


def discover(manual=""):
    if manual:
        ips = {local_ip(manual)}
    else:
        ips = ssdp_discover() | known_devices()
    result = {}
    verified = set()
    for ip in sorted(ips):
        if ip in verified:
            continue
        try:
            data = device(ip)
            groups = topology(ip)
            verified.add(ip)
            for group in groups.iter("ZoneGroup"):
                members = [member for member in group.findall("ZoneGroupMember") if member.get("Invisible") != "1"]
                coordinator = next((member for member in group.findall("ZoneGroupMember") if member.get("UUID") == group.get("Coordinator")), None)
                if coordinator is None:
                    continue
                target = local_ip(urllib.parse.urlparse(coordinator.get("Location", "")).hostname)
                names = [member.get("ZoneName", "Sonos") for member in members]
                result[target] = {"ip": target, "name": " + ".join(names) or data["name"], "volume": volume(target)}
                for member in group.iter("ZoneGroupMember"):
                    try:
                        verified.add(local_ip(urllib.parse.urlparse(member.get("Location", "")).hostname))
                    except (ValueError, TypeError):
                        pass
        except Exception:
            if manual:
                raise
    if result:
        remember_devices(verified)
    return sorted(result.values(), key=lambda item: item["name"].lower())


class Server(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True


class Session:
    def __init__(self, ip, ffmpeg, origin, notify):
        self.ip = group_target(local_ip(ip))
        self.origin, self.notify = origin, notify
        self.token = secrets.token_urlsafe(32)
        self.path = "/stream/" + secrets.token_urlsafe(24) + ".mp3"
        self.running = True
        self.ready = threading.Event()
        self.lock, self.control_lock, self.write_lock = threading.Lock(), threading.Lock(), threading.Lock()
        self.clients = set()
        self.recent = collections.deque(maxlen=8)
        self.last_audio = time.monotonic()
        self.error_tail = collections.deque(maxlen=10)
        self.process = subprocess.Popen([
            str(ffmpeg), "-hide_banner", "-loglevel", "error", "-probesize", "32", "-analyzeduration", "0", "-f", "s16le", "-ar", "48000", "-ac", "2", "-i", "pipe:0",
            "-c:a", "libmp3lame", "-b:a", "192k", "-ar", "48000", "-write_xing", "0", "-id3v2_version", "0",
            "-flush_packets", "1", "-f", "mp3", "pipe:1"
        ], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        session = self

        class Handler(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def log_message(self, *args):
                pass

            def reply(self, status):
                self.send_response(status)
                self.send_header("Content-Length", "0")
                self.send_header("Connection", "close")
                if self.headers.get("Origin") == session.origin:
                    self.send_header("Access-Control-Allow-Origin", session.origin)
                    self.send_header("Access-Control-Allow-Headers", "Content-Type, X-Session-Token")
                    self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
                self.end_headers()
                self.close_connection = True

            def upload_allowed(self):
                return self.client_address[0] == "127.0.0.1" and self.headers.get("Origin") == session.origin and self.path == "/pcm"

            def do_OPTIONS(self):
                self.reply(204 if self.upload_allowed() else 403)

            def do_POST(self):
                self.connection.settimeout(5)
                try:
                    length = int(self.headers.get("Content-Length", "0"))
                    if not 0 < length <= 192000:
                        self.reply(400)
                        return
                    # Drain bounded request bodies before rejecting them. Closing with unread
                    # bytes can reset the connection on Windows and hide the HTTP status.
                    data = self.rfile.read(length)
                    if not self.upload_allowed() or not secrets.compare_digest(self.headers.get("X-Session-Token", ""), session.token):
                        self.reply(403)
                        return
                    if length % 4:
                        self.reply(400)
                        return
                    if len(data) != length or not session.running:
                        self.reply(410)
                        return
                    with session.write_lock:
                        session.process.stdin.write(data)
                        session.process.stdin.flush()
                    session.last_audio = time.monotonic()
                    self.reply(204)
                except (OSError, ValueError):
                    self.reply(503)

            def do_GET(self):
                if self.path != session.path or self.client_address[0] != session.ip or not session.running:
                    self.reply(404)
                    return
                self.connection.settimeout(5)
                client = queue.Queue(maxsize=64)
                with session.lock:
                    for chunk in session.recent:
                        client.put_nowait(chunk)
                    session.clients.add(client)
                try:
                    self.send_response(200)
                    self.send_header("Content-Type", "audio/mpeg")
                    self.send_header("Cache-Control", "no-store")
                    self.send_header("Connection", "close")
                    self.end_headers()
                    while session.running:
                        try:
                            chunk = client.get(timeout=1)
                        except queue.Empty:
                            continue
                        if chunk is None:
                            break
                        self.wfile.write(chunk)
                        self.wfile.flush()
                except OSError:
                    pass
                finally:
                    with session.lock:
                        session.clients.discard(client)
                    self.close_connection = True

            def do_HEAD(self):
                if self.path != session.path or self.client_address[0] != session.ip or not session.running:
                    self.reply(404)
                    return
                self.send_response(200)
                self.send_header("Content-Type", "audio/mpeg")
                self.send_header("Cache-Control", "no-store")
                self.send_header("Connection", "close")
                self.end_headers()
                self.close_connection = True

        try:
            self.server = Server(("0.0.0.0", 0), Handler)
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
                sock.connect((self.ip, 1400))
                address = sock.getsockname()[0]
            self.uri = "x-rincon-mp3radio://{}:{}{}".format(address, self.server.server_port, self.path)
            for target in (self.server.serve_forever, self.read_mp3, self.read_errors, self.play, self.watchdog):
                threading.Thread(target=target, daemon=True).start()
        except Exception:
            self.running = False
            self.process.kill()
            self.process.wait()
            raise

    def connection(self):
        return {"upload": "http://127.0.0.1:{}/pcm".format(self.server.server_port), "token": self.token}

    def read_errors(self):
        for line in self.process.stderr:
            self.error_tail.append(line.decode("utf-8", "replace").strip())

    def read_mp3(self):
        while self.running:
            chunk = self.process.stdout.read1(4096)
            if not chunk:
                if self.running:
                    self.notify(error="FFmpeg beendet: " + " ".join(self.error_tail))
                break
            with self.lock:
                self.recent.append(chunk)
                for client in list(self.clients):
                    try:
                        client.put_nowait(chunk)
                    except queue.Full:
                        self.clients.discard(client)
                        while not client.empty():
                            try:
                                client.get_nowait()
                            except queue.Empty:
                                break
                        client.put_nowait(None)
            self.ready.set()

    def play(self):
        if not self.ready.wait(12):
            if self.running:
                self.notify(error="Kein Audiosignal vom Browser empfangen")
            return
        try:
            with self.control_lock:
                if not self.running:
                    return
                soap(self.ip, "AVTransport", "SetAVTransportURI", InstanceID=0, CurrentURI=self.uri, CurrentURIMetaData="")
                soap(self.ip, "AVTransport", "Play", InstanceID=0, Speed=1)
            self.notify(status="Übertragung läuft")
        except Exception as error:
            if self.running:
                self.notify(error=str(error))

    def watchdog(self):
        while self.running:
            time.sleep(1)
            if time.monotonic() - self.last_audio > 15:
                self.notify(error="Audioverbindung zum Browser abgebrochen")
                return

    def close(self):
        if not self.running:
            return
        self.running = False
        self.ready.set()
        with self.control_lock:
            try:
                current = field(soap(self.ip, "AVTransport", "GetMediaInfo", InstanceID=0), "CurrentURI")
                # Do not stop music started by another controller in the meantime.
                if current == self.uri:
                    soap(self.ip, "AVTransport", "Stop", InstanceID=0)
            except Exception:
                pass
        self.process.kill()
        self.process.wait(timeout=5)
        self.server.shutdown()
        self.server.server_close()
        for pipe in (self.process.stdin, self.process.stdout, self.process.stderr):
            pipe.close()


def read_message(stream):
    header = stream.read(4)
    if not header:
        return None
    if len(header) != 4:
        raise ValueError("Unvollständiger Nachrichtenkopf")
    size = struct.unpack("<I", header)[0]
    if not 0 < size <= 65536:
        raise ValueError("Ungültige Nachrichtengröße")
    body = stream.read(size)
    if len(body) != size:
        raise ValueError("Unvollständige Nachricht")
    return json.loads(body)


def main():
    if os.name == "nt":
        import msvcrt
        msvcrt.setmode(sys.stdin.fileno(), os.O_BINARY)
        msvcrt.setmode(sys.stdout.fileno(), os.O_BINARY)
    config = json.loads((ROOT / "config.json").read_text(encoding="utf-8-sig"))
    origin = config["origin"]
    if len(sys.argv) < 2 or sys.argv[1].rstrip("/") != origin.rstrip("/"):
        raise ValueError("Nicht erlaubte Erweiterung")
    output_lock = threading.Lock()

    def emit(message):
        data = json.dumps(message, ensure_ascii=False).encode("utf-8")
        with output_lock:
            sys.stdout.buffer.write(struct.pack("<I", len(data)) + data)
            sys.stdout.buffer.flush()

    def notify(**event):
        emit({"event": True, **event})

    session = None
    try:
        while True:
            request = read_message(sys.stdin.buffer)
            if request is None:
                break
            try:
                kind = request["type"]
                if kind == "discover":
                    result = discover(request.get("ip", ""))
                elif kind == "volume":
                    result = volume(local_ip(request["ip"]), request["volume"])
                elif kind == "start":
                    if session:
                        raise ValueError("Übertragung läuft bereits")
                    session = Session(request["ip"], ROOT / "ffmpeg.exe", origin, notify)
                    result = session.connection()
                elif kind == "stop":
                    if session:
                        session.close()
                        session = None
                    result = True
                elif kind == "ping":
                    result = {"version": "0.1.0"}
                else:
                    raise ValueError("Unbekannter Befehl")
                emit({"id": request["id"], "result": result})
            except Exception as error:
                emit({"id": request.get("id"), "error": str(error)})
    finally:
        if session:
            session.close()


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(str(error), file=sys.stderr)
        sys.exit(1)
