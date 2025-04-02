import threading
import time
import sys
import os
from queue import Queue, Empty
from model import DVModel
from main import parse_command
import socket
import select
import fcntl

class NetworkNode:
    def __init__(self, node_id, port, initial_table, routing_delay, update_interval):
        """
        初始化网络节点：
          - node_id：节点标识符
          - port：本节点监听的端口
          - initial_table：初始邻居路由表（用于构造 DVModel）
          - routing_delay：延时后启动路由计算线程
          - update_interval：发送更新信息的时间间隔
        """
        self.node_id = node_id
        self.port = port
        self.routing_delay = routing_delay
        self.update_interval = update_interval
        
        # 初始化 UDP socket、设置为非阻塞模式
        self.setup(port)
        
        # 创建 DVModel 实例，并传入回调对象 self（本对象需要提供 info、on_broadcast、set_enabled 等方法）
        self.dv_model = DVModel(node_id, initial_table, self)
        self.model_lock = threading.Lock()
        # 命令队列，用于存储从输入中解析出的命令
        self.command_queue = Queue()
        # 输入队列，用于存放外部输入（例如用户输入）
        self.input_queue = Queue()
        self.running = True
        self.cache_lock = threading.Lock()
        # 用于缓存广播报文，形式为 (邻居字典, 报文字符串)
        self.cached = None
        # 创建三个线程：监听、发送和路由计算
        self.listen_thread = threading.Thread(target=self.listening_loop)
        self.send_thread = threading.Thread(target=self.sending_loop)
        self.calc_thread = threading.Thread(target=self.calc_loop)

    # 该方法可以用于外部推送输入数据到 input_queue
    def push_input(self, line):
        self.input_queue.put(line)
    
    def start(self):
        """启动所有线程"""
        self.listen_thread.start()
        self.send_thread.start()
        self.calc_thread.start()

    def stop(self):
        """停止节点运行，结束各个线程"""
        self.running = False
        self.input_queue.put("")
        self.listen_thread.join()
        self.send_thread.join()
        self.calc_thread.join()
    
    def listening_loop(self):
        """
        监听线程：
          - 从标准输入或 socket 中读取数据
          - 将读取到的行用 parse_command 解析后放入 command_queue
        """
        while self.running:
            try:
                line = self.readline()
                if not line:
                    continue
                # 注意：此处使用 sys.stderr.print 是错误的，
                # 正确做法可以使用 sys.stderr.write() 或 print(..., file=sys.stderr)
                # 此外，变量 node_id 未定义，应使用 self.node_id。
                sys.stderr.write(f"{self.node_id} {line}\n")
                sys.stderr.flush()
                result = parse_command(line)
                # 将解析出的命令加入队列；若队列已满时不阻塞
                self.command_queue.put(result, block=False)
            except Exception as e:
                # 这里建议至少打印异常信息，便于调试
                sys.stderr.write(f"Listening error: {e}\n")
                sys.stderr.flush()
                pass
    
    def sending_loop(self):
        """
        发送线程：
          - 定时检查缓存中是否存在广播报文
          - 若存在，则打印报文，并通过 UDP socket 将报文发送给各个邻居
        """
        while self.running:
            with self.cache_lock:
                if self.cached is not None:
                    m, message = self.cached
                    print(message)
                    # 向每个邻居的端口发送报文
                    for v in m.values():
                        self.send(v['port'], message)
            time.sleep(self.update_interval)
        
    def calc_loop(self):
        """
        路由计算线程：
          - 初始延时 routing_delay 后，计算并打印当前路由表，然后广播更新报文
          - 循环从 command_queue 中获取命令，执行后重新计算路由
        """
        time.sleep(self.routing_delay)
        self.dv_model._recalculate_routes()
        self.dv_model.print_routing_table()
        
        self.dv_model.broadcast()
        while self.running:
            try:
                # 非阻塞获取命令，超时 0.001 秒
                command = self.command_queue.get(timeout=0.001)
                if not command:
                    continue
                with self.model_lock:
                    # 每次处理命令前后均打印路由表（可能打印过于频繁，可根据需要调整）
                    self.dv_model.print_routing_table()
                    self.dv_model.run_command(command)
                    self.dv_model._recalculate_routes()
                    # 如果需要可再次广播更新信息，此处被注释掉
                    # self.dv_model.broadcast()
            except Empty:
                continue

    def set_enabled(self, value):
        """
        用于设置节点是否启用（例如在 FAIL/RECOVER 命令中调用）
        注意：当前未实现任何功能，建议根据需求更新 self.running 或其他状态。
        """
        # TODO: 实现 set_enabled 方法，根据 value 设置节点启用/停用状态
        pass                
            
    def setup(self, port):
        """
        设置 UDP socket：
          - 创建 socket，绑定到 ('localhost', port)
          - 设置为非阻塞模式
          - 同时将 sys.stdin 设置为非阻塞（仅适用于类 Unix 平台）
        """
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.socket.bind(('localhost', port))
        self.socket.setblocking(False)
        fcntl.fcntl(sys.stdin, fcntl.F_SETFL, os.O_NONBLOCK)

    def recv(self, port, n):
        """
        从 socket 接收数据（此方法暂未在本类中使用）
        """
        data, addr = self.socket.recvfrom(4096)
        return data.decode()
        
    def send(self, port, data):
        """
        通过 UDP socket 向 ('localhost', port) 发送 data 数据
        """
        self.socket.sendto(data.encode(), ('localhost', port))
    
    def readline(self):
        """
        尝试从 sys.stdin 或 UDP socket 中读取一行数据：
          - 使用 select 检测 sys.stdin 和 socket 是否有可读数据
          - 若 sys.stdin 可读，则返回其读取的数据
          - 否则若 socket 可读，则返回接收到的数据
          - 如果两者均没有数据，则从 input_queue 中取数据（若有）
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
        回调函数，用于打印信息并刷新标准输出
        """
        print(msg)
        sys.stdout.flush()
        
    def on_broadcast(self, message):
        """
        回调函数，在 DVModel 调用广播时被调用：
          - 打印广播消息
          - 将广播消息和当前邻居信息缓存
          - 向所有直接邻居发送广播消息
        """
        print(message)
        sys.stdout.flush()
        m = self.dv_model.get_neighbours()
        with self.cache_lock:
            self.cached = (m, message)
        for item, v in m.items():
            self.send(v['port'], message)
