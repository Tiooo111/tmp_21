import threading
import time
import sys
import os
from queue import Queue, Empty
from model import DVModel
from command import parse_command
import socket
import select
import fcntl

class NetworkNode:
    def __init__(self, node_id, port, initial_table, routing_delay, update_interval):
        """
        初始化网络节点：
          - node_id：节点标识符
          - port：本节点监听端口
          - initial_table：初始邻居路由表
          - routing_delay：延时后启动路由计算线程
          - update_interval：发送更新报文的时间间隔
        """
        self.node_id = node_id
        self.port = port
        self.routing_delay = routing_delay
        self.update_interval = update_interval
        
        self.setup(port)
        
        self.dv_model = DVModel(node_id, initial_table, self)
        self.model_lock = threading.Lock()
        self.command_queue = Queue()
        self.input_queue = Queue()
        self.running = True
        self.cache_lock = threading.Lock()
        self.cached = None
        self.listen_thread = threading.Thread(target=self.listening_loop)
        self.send_thread = threading.Thread(target=self.sending_loop)
        self.calc_thread = threading.Thread(target=self.calc_loop)

    def push_input(self, line):
        self.input_queue.put(line)
    
    def start(self):
        self.listen_thread.start()
        self.send_thread.start()
        self.calc_thread.start()

    def stop(self):
        self.running = False
        self.input_queue.put("")
        self.listen_thread.join()
        self.send_thread.join()
        self.calc_thread.join()
    
    def listening_loop(self):
        """
        监听线程：从标准输入或 socket 中读取数据，
        使用 parse_command 解析后放入命令队列
        """
        while self.running:
            try:
                line = self.readline()
                if not line:
                    continue
                # 正确写法：使用 sys.stderr.write，并使用 self.node_id
                sys.stderr.write(f"{self.node_id} {line}\n")
                sys.stderr.flush()
                result = parse_command(line)
                self.command_queue.put(result, block=False)
            except Exception as e:
                sys.stderr.write(f"Listening error: {e}\n")
                sys.stderr.flush()
                continue
    
    def sending_loop(self):
        """
        发送线程：每隔 update_interval 检查缓存中的广播报文，
        打印并通过 socket 发送给所有直接邻居
        """
        while self.running:
            with self.cache_lock:
                if self.cached is not None:
                    m, message = self.cached
                    print(message)
                    for v in m.values():
                        self.send(v['port'], message)
            time.sleep(self.update_interval)
        
    def calc_loop(self):
        """
        路由计算线程：
          - 初始延时 routing_delay 后，计算路由并打印路由表、广播更新报文
          - 循环获取命令队列中的命令并处理后重新计算路由
        """
        time.sleep(self.routing_delay)
        self.dv_model._recalculate_routes()
        self.dv_model.print_routing_table()
        
        self.dv_model.broadcast()
        while self.running:
            try:
                command = self.command_queue.get(timeout=0.001)
                if not command:
                    continue
                with self.model_lock:
                    self.dv_model.print_routing_table()
                    self.dv_model.run_command(command)
                    self.dv_model._recalculate_routes()
            except Empty:
                continue

    def set_enabled(self, value):
        """
        设置节点的启用状态。
        例如：在 FAIL/RECOVER 命令中被调用，此处可扩展为修改 self.running 或其他状态
        """
        # 简单实现：如 value 为 False，则停止接收数据；实际可根据需要修改
        if not value:
            self.running = False
        else:
            self.running = True
                
    def setup(self, port):
        """
        设置 UDP socket，并将 sys.stdin 设置为非阻塞
        """
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.socket.bind(('localhost', port))
        self.socket.setblocking(False)
        fcntl.fcntl(sys.stdin, fcntl.F_SETFL, os.O_NONBLOCK)

    def send(self, port, data):
        """
        通过 UDP socket 向指定 ('localhost', port) 发送数据
        """
        self.socket.sendto(data.encode(), ('localhost', port))
    
    def readline(self):
        """
        尝试从 sys.stdin 或 socket 中读取一行数据，优先返回检测到的数据
        """
        readable, _, _ = select.select([sys.stdin, self.socket], [], [])
        
        if not readable:
            return self.input_queue.get() if not self.input_queue.empty() else ""
            
        for source in readable:
            if source == sys.stdin:
                return sys.stdin.readline().strip()
            else:
                data, addr = self.socket.recvfrom(4096)
                return data.decode().strip()

    def info(self, msg):
        """
        回调函数：输出信息并刷新标准输出
        """
        print(msg)
        sys.stdout.flush()
        
    def on_broadcast(self, message):
        """
        回调函数：在 DVModel 广播更新时调用，
        缓存当前邻居信息和广播报文，并向所有邻居发送消息
        """
        print(message)
        sys.stdout.flush()
        m = self.dv_model.get_neighbours()
        with self.cache_lock:
            self.cached = (m, message)
        for v in m.values():
            self.send(v['port'], message)
