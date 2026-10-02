"""One bounded public HTTP snapshot. DNS is checked once, then the socket is pinned."""
from http.client import HTTPConnection, HTTPSConnection
import ipaddress
import queue
import socket
import threading
import time
from urllib.parse import urlsplit, urlunsplit, urljoin, quote

from .objects import MAX_BYTES


def normalize_url(url):
    if any(ord(c) < 33 or ord(c) == 127 for c in url):
        raise ValueError('Invalid URL characters')
    p = urlsplit(url)
    if p.scheme not in ('http', 'https') or not p.hostname or p.username or p.password:
        raise ValueError('Only HTTP(S) URLs without credentials are allowed')
    if p.port not in (None, 80 if p.scheme == 'http' else 443):
        raise ValueError('Only standard HTTP(S) ports are allowed')
    host = p.hostname.encode('idna').decode('ascii').lower()
    host = '[' + host + ']' if ':' in host else host
    return urlunsplit((p.scheme, host, quote(p.path or '/', safe='/:%@!$&\'()*+,;=-._~'),
                       quote(p.query, safe='=&/:?%+;,@!$\'()*-._~'), ''))


def public_addresses(host, port, timeout=5):
    result = queue.Queue()
    def resolve():
        try:
            result.put(socket.getaddrinfo(host, port, type=socket.SOCK_STREAM))
        except Exception as exc:
            result.put(exc)
    threading.Thread(target=resolve, daemon=True).start()
    try:
        addresses = result.get(timeout=timeout)
    except queue.Empty as exc:
        raise TimeoutError('DNS resolution timed out') from exc
    if isinstance(addresses, Exception):
        raise addresses
    if not addresses:
        raise ValueError('Host has no addresses')
    for _, _, _, _, address in addresses:
        ip = ipaddress.ip_address(address[0])
        if not ip.is_global or (ip.version == 6 and ip.ipv4_mapped and not ip.ipv4_mapped.is_global):
            raise ValueError('Private, loopback and link-local destinations are forbidden')
    return addresses


def fetch_snapshot(url, max_bytes=MAX_BYTES, timeout=30, max_redirects=3):
    deadline = time.monotonic() + timeout
    original = normalize_url(url)
    url = original
    for hop in range(max_redirects+1):
        p = urlsplit(url)
        port = 443 if p.scheme == 'https' else 80
        addresses = public_addresses(p.hostname, port, min(5, max(.01, deadline-time.monotonic())))
        family, kind, proto, _, address = addresses[0]
        def pinned_connect(*args, **kwargs):
            sock = socket.socket(family, kind, proto)
            try:
                sock.settimeout(max(.01, deadline-time.monotonic()))
                sock.connect(address)
                return sock
            except Exception:
                sock.close()
                raise
        connection = (HTTPSConnection if p.scheme == 'https' else HTTPConnection)(
            p.hostname, port, timeout=max(.01, deadline-time.monotonic()))
        connection._create_connection = pinned_connect
        try:
            connection.request('GET', urlunsplit(('', '', p.path, p.query, '')),
                               headers={'User-Agent': 'FinRAG-snapshot/1', 'Accept-Encoding': 'identity'})
            response = connection.getresponse()
            if response.status in (301, 302, 303, 307, 308):
                if hop == max_redirects or not response.getheader('Location'):
                    raise ValueError('Redirect limit or missing Location')
                url = normalize_url(urljoin(url, response.getheader('Location')))
                continue
            if response.status != 200:
                raise ValueError(f'Snapshot HTTP status {response.status}')
            media = response.getheader('Content-Type', '').split(';')[0].strip().lower()
            if media not in ('application/pdf', 'text/html', 'text/plain', 'text/markdown'):
                raise ValueError('Unsupported response media type')
            if response.getheader('Content-Encoding', 'identity').lower() != 'identity':
                raise ValueError('Compressed responses are not supported')
            if int(response.getheader('Content-Length', '0')) > max_bytes:
                raise ValueError('Snapshot exceeds byte limit')
            parts, size = [], 0
            while True:
                remaining = deadline-time.monotonic()
                if remaining <= 0:
                    raise TimeoutError('Snapshot deadline exceeded')
                if connection.sock:
                    connection.sock.settimeout(remaining)
                part = response.read1(min(65536, max_bytes+1-size))
                if not part:
                    break
                parts.append(part)
                size += len(part)
                if size > max_bytes:
                    raise ValueError('Snapshot exceeds byte limit')
            if not size:
                raise ValueError('Empty snapshot')
            from datetime import datetime, timezone
            return b''.join(parts), media, {'original_url': original, 'final_url': url,
                'fetched_at': datetime.now(timezone.utc).isoformat(),
                'etag': response.getheader('ETag'), 'last_modified': response.getheader('Last-Modified')}
        finally:
            connection.close()
    raise ValueError('Redirect limit')
