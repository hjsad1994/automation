#!/usr/bin/env python3
"""
Local proxy server that forwards to authenticated upstream proxy
Giải pháp cho vấn đề proxy authentication trong Chrome
"""

import socket
import threading
import requests
from urllib.parse import urlparse
import base64

class ProxyServer:
    def __init__(self, local_port, upstream_host, upstream_port, username, password):
        self.local_port = local_port
        self.upstream_host = upstream_host
        self.upstream_port = upstream_port
        self.username = username
        self.password = password
        self.upstream_proxy = f"http://{username}:{password}@{upstream_host}:{upstream_port}"
        self.server_socket = None
        self.running = False

    def start(self):
        """Khởi động proxy server"""
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_socket.bind(('127.0.0.1', self.local_port))
        self.server_socket.listen(50)
        self.running = True

        print(f"✓ Local proxy started on 127.0.0.1:{self.local_port}")
        print(f"  Forwarding to: {self.upstream_host}:{self.upstream_port}")

        while self.running:
            try:
                client_socket, addr = self.server_socket.accept()
                threading.Thread(target=self.handle_client, args=(client_socket,), daemon=True).start()
            except:
                break

    def handle_client(self, client_socket):
        """Xử lý request từ Chrome"""
        try:
            # Đọc request từ Chrome
            request = client_socket.recv(4096).decode('utf-8', errors='ignore')

            if not request:
                client_socket.close()
                return

            # Parse request
            lines = request.split('\r\n')
            if len(lines) == 0:
                client_socket.close()
                return

            first_line = lines[0]
            method, url, protocol = first_line.split(' ')

            # CONNECT method (for HTTPS)
            if method == 'CONNECT':
                # Gửi request qua upstream proxy với authentication
                upstream_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                upstream_socket.connect((self.upstream_host, int(self.upstream_port)))

                # Tạo CONNECT request với Proxy-Authorization
                auth_string = base64.b64encode(f"{self.username}:{self.password}".encode()).decode()
                connect_request = f"{first_line}\r\n"
                connect_request += f"Proxy-Authorization: Basic {auth_string}\r\n"
                connect_request += "\r\n"

                upstream_socket.sendall(connect_request.encode())
                response = upstream_socket.recv(4096)

                # Forward response về Chrome
                client_socket.sendall(response)

                # Nếu connection thành công, tunnel data
                if b'200' in response:
                    self.tunnel(client_socket, upstream_socket)
                else:
                    client_socket.close()
                    upstream_socket.close()

            else:
                # HTTP request - dùng requests library
                proxies = {
                    'http': self.upstream_proxy,
                    'https': self.upstream_proxy
                }

                # Parse headers
                headers = {}
                for line in lines[1:]:
                    if ': ' in line:
                        key, value = line.split(': ', 1)
                        headers[key] = value

                # Forward request
                response = requests.request(method, url, headers=headers, proxies=proxies, verify=False)

                # Send response back
                response_data = f"HTTP/1.1 {response.status_code} {response.reason}\r\n"
                for key, value in response.headers.items():
                    response_data += f"{key}: {value}\r\n"
                response_data += "\r\n"

                client_socket.sendall(response_data.encode())
                client_socket.sendall(response.content)
                client_socket.close()

        except Exception as e:
            print(f"Error handling client: {e}")
            try:
                client_socket.close()
            except:
                pass

    def tunnel(self, client_socket, upstream_socket):
        """Tunnel data giữa client và upstream"""
        def forward(source, destination):
            try:
                while True:
                    data = source.recv(4096)
                    if not data:
                        break
                    destination.sendall(data)
            except:
                pass
            finally:
                try:
                    source.close()
                    destination.close()
                except:
                    pass

        # Create two threads để forward data theo 2 chiều
        threading.Thread(target=forward, args=(client_socket, upstream_socket), daemon=True).start()
        threading.Thread(target=forward, args=(upstream_socket, client_socket), daemon=True).start()

    def stop(self):
        """Dừng proxy server"""
        self.running = False
        if self.server_socket:
            self.server_socket.close()
        print("✓ Proxy server stopped")

if __name__ == '__main__':
    # Test
    proxy = ProxyServer(
        local_port=8888,
        upstream_host="118.70.171.67",
        upstream_port=27608,
        username="KbdsYf",
        password="ffyDYM"
    )

    try:
        proxy.start()
    except KeyboardInterrupt:
        proxy.stop()
