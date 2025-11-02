from concurrent.futures import ThreadPoolExecutor
import ssl
import mimetypes
import importlib
import os
import signal
import socket
import io
import sys
import selectors
import hashlib
from email.utils import formatdate


def grim_reaper(signum, frame):
    while True:
        try:
            pid, status = os.waitpid(
                -1,          # Wait for any child process
                 os.WNOHANG  # Do not block and return EWOULDBLOCK error
            )
            print(
                'Child {pid} terminated with status {status}'
                '\n'.format(pid=pid, status=status)
            )
        except OSError:
            return

        if pid == 0:
            return


class WSGIServer(object):

    address_family = socket.AF_INET
    socket_type = socket.SOCK_STREAM
    request_queue_size = 1024

    def __init__(self, server_address):
        sock = socket.socket(
            self.address_family,
            self.socket_type
        )
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind(server_address)

        # 👇 Store SSL context for later use in accept()
        self.context = None
        if server_address[1] == 8443:
            self.context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            self.context.load_cert_chain(certfile="cert.pem", keyfile="key.pem")

        sock.listen(self.request_queue_size)
        self.listen_socket = sock
        host, port = sock.getsockname()[:2]

        self.server_name = socket.getfqdn(host)
        self.server_port = port
        self.selector = selectors.DefaultSelector()
        self.selector.register(self.listen_socket, selectors.EVENT_READ, self.accept)
        self.headers_set = []

    def set_app(self, application):
        self.application = application

    def accept(self, server_sock):
        try:
            client_sock, addr = server_sock.accept()
            print(f"Accepted connection from {addr}")
            if self.context:
                try:
                    client_sock = self.context.wrap_socket(client_sock, server_side=True)
                except ssl.SSLError as e:
                    print(f"SSL handshake failed: {e}")
                    client_sock.close()
                    return

            client_sock.setblocking(False)

            # 🔐 Make sure the fd is not already registered
            try:
                self.selector.register(client_sock, selectors.EVENT_READ, self.read)
            except KeyError:
                print("FD already registered, unregistering first...")
                self.selector.unregister(client_sock)
                self.selector.register(client_sock, selectors.EVENT_READ, self.read)

        except Exception as e:
            print(f"Exception in accept(): {e}")

    def read(self, client_sock):
        try:
            request_data = client_sock.recv(1024)
            if not request_data:
                raise ConnectionResetError("Client closed the connection")

            self.client_connection = client_sock
            self.request_data = request_data
            self.handle_one_request()

        except Exception as e:
            print(f"Error reading from socket: {e}")

        finally:
            try:
                if client_sock.fileno() != -1:
                    self.selector.unregister(client_sock)
            except Exception as ex:
                print(f"Failed to unregister socket: {ex}")

            try:
                client_sock.close()
            except Exception as ex:
                print(f"Failed to close socket: {ex}")



    def serve_forever(self):
        print("Server is running (non-blocking with selectors)...")
        while True:
            events = self.selector.select(timeout=None)
            for key, mask in events:
                callback = key.data
                callback(key.fileobj)

    def handle_one_request(self):
        request_data = self.request_data
        print(''.join(
            '< {line}\n'.format(line=line)
            for line in request_data.splitlines()
        ))
        try:
            request_text = request_data.decode('utf-8')
            request_line = request_text.splitlines()[0]
            method, path, _ = request_line.split()
            self.request_method = method
            self.path = path
            self.is_head = (method == "HEAD")
            self.if_modified_since = None
            self.if_none_match = None
            self.range_header = None
            for line in request_text.splitlines()[1:]:
                if line.startswith("If-Modified-Since:"):
                    self.if_modified_since = line.split(":", 1)[1].strip()
                elif line.startswith("If-None-Match:"):
                    self.if_none_match = line.split(":", 1)[1].strip()
                elif line.startswith("Range:"):
                    self.range_header = line.split(":", 1)[1].strip()
        except Exception as e:
            print("Failed to parse request:", e)
            self.client_connection.close()
            self.selector.unregister(self.client_connection)
            return

        if path.startswith('/static/'):
            filepath = path.lstrip('/')
            full_path = os.path.abspath(filepath)
            static_root = os.path.abspath('static')
            if not full_path.startswith(static_root):
                self.send_404()
                return
            if not os.path.exists(full_path):
                self.send_404()
                return
            if os.path.isdir(full_path):
                full_path = os.path.join(full_path, 'index.html')
                if not os.path.exists(full_path):
                    self.send_404()
                    return            
            with open(full_path, 'rb') as f:
                content = f.read()
            
            last_modified = formatdate(os.path.getmtime(full_path), usegmt=True)
            etag = '"' + hashlib.md5(content).hexdigest() + '"'
            if (self.if_none_match and self.if_none_match.strip('"') == etag.strip('"')) or \
               (self.if_modified_since and self.if_modified_since == last_modified):
                self.send_304()
                return
            self.send_static_response(content, full_path)
            return

        env = self.get_environ()
        result = self.application(env, self.start_response)
        self.finish_response(result)


    def send_static_response(self, content, filepath):
        mime_type, _ = mimetypes.guess_type(filepath)
        if not mime_type:
            mime_type = "application/octet-stream"

        last_modified = formatdate(os.path.getmtime(filepath), usegmt=True)
        etag = hashlib.md5(content).hexdigest()
        headers = []

        status_line = "HTTP/1.1 200 OK"
        body = content
        content_range_header = ""

        if self.range_header:
            try:
                range_val = self.range_header.replace("bytes=", "")
                start_str, end_str = range_val.split("-")
                start = int(start_str)
                end = int(end_str) if end_str else len(content) - 1
                if start > end or start >= len(content):
                    raise ValueError("Invalid range")

                body = content[start:end+1]
                status_line = "HTTP/1.1 206 Partial Content"
                content_range_header = f"Content-Range: bytes {start}-{end}/{len(content)}"
            except Exception as e:
                print("Invalid Range header:", e)
                self.send_404()
                return

        headers.append(f"{status_line}")
        headers.append(f"Content-Type: {mime_type}")
        headers.append(f"Content-Length: {len(body)}")
        headers.append(f"Last-Modified: {last_modified}")
        headers.append(f'ETag: "{etag}"')
        headers.append(f"Connection: close")
        if content_range_header:
            headers.append(content_range_header)
        headers.append("")  # blank line before body
        headers.append("")

        response = "\r\n".join(headers).encode("utf-8")

        if self.is_head:
            self.client_connection.sendall(response)
        else:
            self.client_connection.sendall(response + body)

        self.client_connection.close()
        self.selector.unregister(self.client_connection)

        
    def send_404(self):
        
        response = (
            "HTTP/1.1 404 Not Found\r\n"
            "Content-Type: text/plain\r\n"
            "Connection: close\r\n"
            "\r\n"
            "404 - File not found"
        ).encode("utf-8")

        self.client_connection.sendall(response)
        self.client_connection.close()
        self.selector.unregister(self.client_connection)


    def send_304(self):
        response = (
            "HTTP/1.1 304 Not Modified\r\n"
            "Connection: close\r\n"
            "\r\n"
        ).encode("utf-8")

        self.client_connection.sendall(response)
        self.client_connection.close()
        self.selector.unregister(self.client_connection)


    def get_environ(self):
        env = {}

        env['wsgi.version']      = (1, 0)
        env['wsgi.url_scheme']   = 'http'
        env['wsgi.input']        = io.StringIO(self.request_data.decode('utf-8'))
        env['wsgi.errors']       = sys.stderr
        env['wsgi.multithread']  = False
        env['wsgi.multiprocess'] = False
        env['wsgi.run_once']     = False
        env['REQUEST_METHOD']    = self.request_method    # GET
        env['PATH_INFO']         = self.path              # /hello
        env['SERVER_NAME']       = self.server_name       # localhost
        env['SERVER_PORT']       = str(self.server_port)  # 8888
        return env

    def start_response(self, status, response_headers, exc_info=None):
        # Add necessary server headers
        server_headers = [
            ('Date', formatdate(usegmt=True)),
            ('Server', 'WSGIServer 0.2'),
        ]
        self.headers_set = [status, response_headers + server_headers]

    def finish_response(self, result):
        try:
            status, response_headers = self.headers_set
            response = 'HTTP/1.1 {status}\r\n'.format(status=status)
            for header in response_headers:
                response += '{0}: {1}\r\n'.format(*header)
            response += '\r\n'
            response_bytes = response.encode('utf-8')

            for data in result:
                response_bytes += data

            print(''.join(
                '> {line}\n'.format(line=line)
                for line in response_bytes.decode('utf-8').splitlines()
            ))

            self.client_connection.sendall(response_bytes)
        finally:
            self.client_connection.close()


SERVER_ADDRESS = (HOST, PORT) = '', 8443  # HTTPS port


def make_server(server_address, application):
    signal.signal(signal.SIGCHLD, grim_reaper)
    server = WSGIServer(server_address)
    server.set_app(application)
    return server


if __name__ == '__main__':
    if len(sys.argv) < 2:
        sys.exit('Provide a WSGI application object as module:callable')
    app_path = sys.argv[1]
    module, application = app_path.split(':')
    module = importlib.import_module(module)
    application = getattr(module, application)
    httpd = make_server(SERVER_ADDRESS, application)
    print('WSGIServer: Serving HTTP on port {port} ...\n'.format(port=PORT))
    httpd.serve_forever()
