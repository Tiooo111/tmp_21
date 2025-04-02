# network.py
import sys
import threading
import queue
import socket
import time

# 全局消息队列，供各线程共享
message_queue = queue.Queue()

class STDINListenerThread(threading.Thread):
    def __init__(self):
        super().__init__()
    def run(self):
        while True:
            try:
                line = sys.stdin.readline()
                if not line:
                    break
                line = line.strip()
                if line:
                    message_queue.put(("STDIN", line))
            except Exception as e:
                print("Error reading from STDIN:", e, flush=True)
                break

class ConnectionHandlerThread(threading.Thread):
    def __init__(self, conn, addr):
        super().__init__()
        self.conn = conn
        self.addr = addr
    def run(self):
        try:
            data = self.conn.recv(1024).decode()
            if data:
                data = data.strip()
                message_queue.put(("SOCKET", data))
            self.conn.close()
        except Exception as e:
            print("Error handling connection from", self.addr, ":", e, flush=True)

class SocketListenerThread(threading.Thread):
    def __init__(self, port):
        super().__init__()
        self.port = port
    def run(self):
        server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            server_sock.bind(('0.0.0.0', self.port))
            server_sock.listen(5)
        except Exception as e:
            print("Error setting up socket server:", e, flush=True)
            sys.exit(1)
        while True:
            try:
                conn, addr = server_sock.accept()
                handler = ConnectionHandlerThread(conn, addr)
                handler.start()
            except Exception as e:
                print("Error accepting connection:", e, flush=True)


class SendingThread(threading.Thread):
    def __init__(self, node_id, neighbors, update_interval):
        super().__init__()
        self.node_id = node_id
        self.neighbors = neighbors  # 格式：{'D': {'cost': 1.2, 'port': 6002}, ...}
        self.update_interval = update_interval

    def build_update_message(self):
        # 输出格式： "UPDATE <Node-ID> <Neighbour>:<Cost>:<Port>"，各邻居信息用空格分隔
        neighbor_entries = []
        for neigh_id, data in self.neighbors.items():
            neighbor_entries.append(f"{neigh_id}:{data['cost']}:{data['port']}")
        neighbor_str = " ".join(neighbor_entries)
        return f"UPDATE {self.node_id} {neighbor_str}"

    def run(self):
        while True:
            time.sleep(self.update_interval)
            update_message = self.build_update_message()
            print(update_message, flush=True)
            for neigh_id, data in self.neighbors.items():
                try:
                    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    s.connect(('127.0.0.1', data['port']))
                    s.sendall(update_message.encode())
                    s.close()
                except Exception as e:
                    print(f"Error sending update to {neigh_id} on port {data['port']}: {e}", flush=True)
