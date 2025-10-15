"""
实时浏览器操作后端API
使用Flask + WebSocket实现与前端的实时通信
集成browser-use的屏幕录制功能
"""

import asyncio
import os
import sys
import json
import threading
import time
import logging
import sqlite3
from datetime import datetime
from tkinter.constants import TRUE
from typing import Optional, Dict, Any, List
from flask import Flask, request, jsonify
from flask_socketio import SocketIO, emit
from flask_cors import CORS

# 添加browser-use路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from dotenv import load_dotenv
from browser_use import Agent, ChatGoogle, BrowserProfile
from browser_use.browser.profile import ProxySettings
from realtime_screen_watchdog import RealtimeScreenWatchdog
from realtime_api import realtime_bp

load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = 'live_browser_demo_secret'
CORS(app, origins="*")
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

# 注册实时API蓝图
app.register_blueprint(realtime_bp)

# 全局变量
current_agent: Optional[Agent] = None
agent_task: Optional[asyncio.Task] = None
browser_session_active = False
recording_path = None

# API数据库路径 - 固定在backend目录下
API_DB_PATH = os.path.join(os.path.dirname(__file__), 'api_data.db')

# Google API配置
api_key = os.getenv('GOOGLE_API_KEY')
if not api_key:
    print("警告: GOOGLE_API_KEY未设置，请在.env文件中配置")

# 创建LLM实例，添加更好的错误处理
def create_llm():
    """
    创建Google LLM实例，包含错误处理和重试机制
    """
    if not api_key:
        return None
    
    try:
        # 使用更稳定的模型版本，移除不支持的参数
        llm = ChatGoogle(
            model='gemini-2.5-pro',  # 使用更稳定的版本
            api_key=api_key,
        )
        return llm
    except Exception as e:
        print(f"创建LLM失败: {e}")
        return None

llm = create_llm()


class BrowserController:
    """浏览器控制器，管理browser-use agent的生命周期"""
    
    def __init__(self):
        self.agent = None
        self.loop = None
        self.thread = None
        self.is_running = False
        self.realtime_watchdog = None
        
    def create_agent(self, task: str, website_url: str, traversal_depth: int = 3) -> Agent:
        """创建browser-use agent"""
        try:
            # 检查LLM是否可用
            if not llm:
                raise ValueError("LLM未正确初始化，请检查GOOGLE_API_KEY配置")
            
            # 设置代理绕过规则，确保localhost不经过代理
            # os.environ['NO_PROXY'] = 'localhost,127.0.0.1,::1'

            # 创建代理配置对象
            proxy_settings = ProxySettings(server='http://127.0.0.1:8080')

            # 创建浏览器配置 - 参考stable_website_traversal.py，但暂时不使用代理
            browser_profile = BrowserProfile(
                headless=True,  # 非无头模式，便于调试和实时显示
                disable_security=True,
                minimum_wait_page_load_time=3.0,  # 页面加载最小等待时间
                wait_between_actions=1.0,  # 动作间等待时间
                screen_recording=False,  # 禁用内置录制，使用实时捕获
                screen_recording_fps=2,
                screen_recording_path=None,
                proxy=proxy_settings,
            )
            
            # 构建详细的任务描述，参考stable_website_traversal.py
            detailed_task = f"""**网站系统遍历任务 - 确定性执行模式**

**目标网站**: {website_url}

**执行策略**:
1. **初始化阶段**:
   - 访问主页并等待完全加载（至少3秒）
   - 截图记录初始状态
   - 识别主要导航区域和功能模块

2. **系统性遍历规则**:
   - 采用**广度优先**策略：先完成同级别所有链接，再进入下级
   - 每个页面停留时间：最少5秒，确保页面完全加载
   - 按照**从左到右、从上到下**的顺序点击链接
   - 遍历深度限制：{traversal_depth}级

3. **交互行为规范**:
   - 每次点击前先滚动确保元素可见
   - 点击后等待页面响应（2-3秒）
   - 如遇到表单，填写测试数据，謹慎提交
   - 遇到弹窗或模态框，先关闭再继续
   - 避免下载文件或外部链接

4. **记录要求**:
   - 为每个访问的页面创建PageSection记录
   - 记录页面标题、URL、深度级别
   - 记录所有交互动作和结果
   - 标记遍历策略类型

5. **异常处理**:
   - 遇到404或错误页面，返回上级继续
   - 页面加载超时（>10秒），刷新一次后继续
   - 遇到登录要求，跳过该分支

**重要约束**:
- 严格按照广度优先顺序执行
- 不要跳过任何可访问的链接
- 保持操作的一致性和可预测性
- 每个决策都要基于当前页面的实际状态

{task}"""
            
            # 创建对话保存目录
            conversations_dir = "d:/code/browser-use-fork/live_browser/backend/conversations"
            os.makedirs(conversations_dir, exist_ok=True)
            
            # 创建agent，使用与stable_website_traversal.py相同的配置
            agent = Agent(
                task=detailed_task,
                llm=llm,
                max_actions_per_step=1,  # 每步只执行一个动作，确保精确控制
                # max_steps=50,  # 限制最大步数，避免无限循环
                # directly_open_url=True,  # 直接打开URL，减少导航步骤
                browser_profile=browser_profile,
                save_conversation_path=f"{conversations_dir}/conversation-{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            )
            
            # 等待浏览器会话初始化完成后创建实时屏幕监控器
            if hasattr(agent, 'browser_session') and agent.browser_session:
                # 创建实时屏幕监控器，传入必需的参数
                self.realtime_watchdog = RealtimeScreenWatchdog(
                    event_bus=agent.browser_session.event_bus,
                    browser_session=agent.browser_session,
                    frame_rate=10,  # 10fps
                    quality=200,     # 图片质量
                    max_width=1280, # 最大宽度
                    max_height=720  # 最大高度
                )
                # 设置SocketIO实例用于实时传输
                self.realtime_watchdog.set_socketio(socketio)
                
                # 将watchdog附加到session
                self.realtime_watchdog.attach_to_session()
                
                # 将watchdog实例保存到session的私有属性中
                agent.browser_session._realtime_screen_watchdog = self.realtime_watchdog
                
                print(f"Agent创建成功，任务: {task}, 目标网站: {website_url}")
                print(f"实时屏幕监控器已集成，帧率: {self.realtime_watchdog.frame_rate}fps")
            else:
                print("警告: 浏览器会话未正确初始化，无法启用实时屏幕监控")
            
            return agent
            
        except Exception as e:
            print(f"创建agent失败: {e}")
            raise e
    
    def start_browser_session(self, task: str, website_url: str):
        """启动浏览器会话"""
        if self.is_running:
            return False, "浏览器会话已在运行中"
            
        try:
            self.agent = self.create_agent(task, website_url)
            self.is_running = True
            
            # 在新线程中运行异步任务
            self.thread = threading.Thread(target=self._run_agent_async)
            self.thread.start()
            
            return True, "浏览器会话启动成功"
        except Exception as e:
            return False, f"启动失败: {str(e)}"
    
    def _run_agent_async(self):
        """在新的事件循环中运行agent"""
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        
        try:
            self.loop.run_until_complete(self._execute_agent())
        except Exception as e:
            socketio.emit('error', {'message': f'Agent执行错误: {str(e)}'})
        finally:
            self.is_running = False
            self.loop.close()
    
    async def _execute_agent(self):
        """执行agent任务"""
        try:
            async def step_monitor(agent):
                """监控agent执行步骤"""
                # 安全地序列化agent输出
                action_info = None
                if agent.state.last_model_output:
                    try:
                        # 尝试获取可序列化的信息
                        if hasattr(agent.state.last_model_output, 'action') and agent.state.last_model_output.action:
                            actions = agent.state.last_model_output.action
                            if isinstance(actions, list) and len(actions) > 0:
                                first_action = actions[0]
                                action_dict = first_action.model_dump() if hasattr(first_action, 'model_dump') else str(first_action)
                                action_info = {
                                    'action_type': type(first_action).__name__,
                                    'action_data': action_dict,
                                    'total_actions': len(actions)
                                }
                            else:
                                action_info = {'action_type': 'unknown', 'action_data': str(actions)}
                        else:
                            action_info = {'action_type': 'no_action', 'action_data': str(agent.state.last_model_output)}
                    except Exception as e:
                        action_info = {'action_type': 'error', 'action_data': f"序列化失败: {str(e)}"}
                
                step_info = {
                    'step': agent.state.n_steps,
                    'max_steps': 100,  # 设置默认最大步数为100，移除15步限制
                    'action': action_info,
                    'timestamp': datetime.now().isoformat(),
                    'consecutive_failures': agent.state.consecutive_failures
                }
                socketio.emit('agent_step', step_info)
                print(f'Step {agent.state.n_steps}: {action_info}')
                
                # 如果连续失败次数过多，提前终止
                if agent.state.consecutive_failures >= 3:
                    print(f"连续失败{agent.state.consecutive_failures}次，建议终止任务")
                    socketio.emit('agent_warning', {
                        'message': f'连续失败{agent.state.consecutive_failures}次，任务可能需要调整',
                        'failures': agent.state.consecutive_failures
                    })
            
            # 发送开始信号
            socketio.emit('session_started', {'message': 'Agent开始执行任务'})
            
            # 执行agent任务，移除最大步数限制
            try:
                result = await self.agent.run(
                    on_step_end=step_monitor
                    # 移除 max_steps=15 限制，允许agent执行更多步骤
                )
                
                # 检查结果
                if result and hasattr(result, 'is_done') and result.is_done():
                    final_result = result.final_result() or "任务完成，但没有返回具体结果"
                    socketio.emit('session_completed', {
                        'message': 'Agent任务执行完成',
                        'result': final_result,
                        'success': True
                    })
                else:
                    socketio.emit('session_completed', {
                        'message': 'Agent任务执行结束，但可能未完全完成',
                        'result': "任务未完全完成",
                        'success': False
                    })
                    
            except Exception as agent_error:
                error_msg = str(agent_error)
                print(f"Agent执行过程中出错: {error_msg}")
                
                # 尝试获取部分结果
                partial_result = "执行过程中遇到错误，无法完成任务"
                if hasattr(self.agent, 'history') and self.agent.history:
                    try:
                        partial_result = self.agent.history.final_result() or partial_result
                    except:
                        pass
                
                socketio.emit('session_completed', {
                    'message': f'Agent执行遇到错误: {error_msg}',
                    'result': partial_result,
                    'success': False,
                    'error': error_msg
                })
            
            # 保存历史记录
            try:
                if hasattr(self.agent, 'history') and self.agent.history:
                    history_path = f'agent_history_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
                    full_path = os.path.join(os.path.dirname(__file__), 'recordings', history_path)
                    self.agent.history.save_to_file(full_path)
                    print(f"历史记录已保存到: {full_path}")
            except Exception as save_error:
                print(f"保存历史记录失败: {str(save_error)}")
            
        except Exception as e:
            error_msg = f'Agent执行失败: {str(e)}'
            print(error_msg)
            socketio.emit('error', {'message': error_msg})
    
    def stop_browser_session(self):
        """停止浏览器会话"""
        if not self.is_running:
            return False, "没有运行中的浏览器会话"
            
        try:
            self.is_running = False
            
            # 停止实时屏幕捕获
            if self.realtime_watchdog:
                asyncio.run_coroutine_threadsafe(
                    self.realtime_watchdog._stop_realtime_capture(), 
                    self.loop
                )
                self.realtime_watchdog = None
            
            if self.loop and not self.loop.is_closed():
                # 取消所有任务
                for task in asyncio.all_tasks(self.loop):
                    task.cancel()
            
            if self.thread and self.thread.is_alive():
                self.thread.join(timeout=5)
            
            socketio.emit('session_stopped', {'message': '浏览器会话已停止'})
            return True, "浏览器会话停止成功"
        except Exception as e:
            return False, f"停止失败: {str(e)}"


# 创建浏览器控制器实例
browser_controller = BrowserController()


@app.route('/api/health', methods=['GET'])
def health_check():
    """健康检查接口"""
    return jsonify({
        'status': 'ok',
        'timestamp': datetime.now().isoformat(),
        'browser_session_active': browser_controller.is_running
    })


@app.route('/api/start_session', methods=['POST'])
def start_session():
    """启动浏览器会话接口"""
    data = request.get_json()
    
    if not data:
        return jsonify({'error': '请求数据为空'}), 400
    
    website_url = data.get('website_url', 'https://xiaozihealth.com')
    custom_task = data.get('task', '')
    
    # 构建任务描述
    task = f"""**网站系统遍历任务 - 确定性执行模式**

**目标网站**: {website_url}

{custom_task if custom_task else '''**执行策略**:
1. **初始化阶段**:
   - 访问主页并等待完全加载（至少3秒）
   - 截图记录初始状态
   - 识别主要导航区域和功能模块

2. **系统性遍历规则**:
   - 采用**广度优先**策略：先完成同级别所有链接，再进入下级
   - 每个页面停留时间：最少5秒，确保页面完全加载
   - 按照**从左到右、从上到下**的顺序点击链接
   - 遍历深度限制：3级

3. **交互行为规范**:
   - 每次点击前先滚动确保元素可见
   - 点击后等待页面响应（2-3秒）
   - 如遇到表单，填写测试数据，謹慎提交
   - 遇到弹窗或模态框，先关闭再继续
   - 避免下载文件或外部链接'''}

**重要约束**:
- 严格按照广度优先顺序执行
- 不要跳过任何可访问的链接
- 保持操作的一致性和可预测性
- 每个决策都要基于当前页面的实际状态"""
    
    success, message = browser_controller.start_browser_session(task, website_url)
    
    if success:
        return jsonify({
            'status': 'success',
            'message': message,
            'website_url': website_url
        })
    else:
        return jsonify({'error': message}), 400


@app.route('/api/stop_session', methods=['POST'])
def stop_session():
    """停止浏览器会话接口"""
    success, message = browser_controller.stop_browser_session()
    
    if success:
        return jsonify({
            'status': 'success',
            'message': message
        })
    else:
        return jsonify({'error': message}), 400


@app.route('/api/session_status', methods=['GET'])
def session_status():
    """获取会话状态接口"""
    return jsonify({
        'is_running': browser_controller.is_running,
        'timestamp': datetime.now().isoformat()
    })


@app.route('/api/recordings', methods=['GET'])
def list_recordings():
    """获取录制文件列表"""
    recordings_dir = os.path.join(os.path.dirname(__file__), 'recordings')
    
    if not os.path.exists(recordings_dir):
        return jsonify({'recordings': []})
    
    recordings = []
    for filename in os.listdir(recordings_dir):
        if filename.endswith('.gif'):
            file_path = os.path.join(recordings_dir, filename)
            file_stat = os.stat(file_path)
            recordings.append({
                'filename': filename,
                'size': file_stat.st_size,
                'created_at': datetime.fromtimestamp(file_stat.st_ctime).isoformat()
            })
    
    return jsonify({'recordings': recordings})


def get_api_data_from_db(limit: int = 50) -> List[Dict[str, Any]]:
    """
    从API数据库中获取最新的API请求数据
    
    Args:
        limit: 返回的记录数量限制
        
    Returns:
        List[Dict]: API请求数据列表
    """
    try:
        if not os.path.exists(API_DB_PATH):
            return []
            
        conn = sqlite3.connect(API_DB_PATH)
        conn.row_factory = sqlite3.Row  # 使结果可以按列名访问
        
        cursor = conn.execute('''
            SELECT id, method, url, host, path, response_status, 
                   timestamp, created_at, response_time
            FROM api_requests 
            ORDER BY timestamp DESC 
            LIMIT ?
        ''', (limit,))
        
        rows = cursor.fetchall()
        conn.close()
        
        # 转换为字典列表
        api_data = []
        for row in rows:
            api_data.append({
                'id': row['id'],
                'method': row['method'],
                'url': row['url'],
                'host': row['host'],
                'path': row['path'],
                'status': row['response_status'],
                'timestamp': row['timestamp'],
                'created_at': row['created_at'],
                'response_time': row['response_time']
            })
            
        return api_data
        
    except Exception as e:
        print(f"获取API数据失败: {e}")
        return []


@app.route('/api/captured_apis', methods=['GET'])
def get_captured_apis():
    """
    获取捕获的API数据接口
    
    Returns:
        JSON: 包含API请求数据的响应
    """
    try:
        limit = request.args.get('limit', 50, type=int)
        api_data = get_api_data_from_db(limit)
        
        return jsonify({
            'status': 'success',
            'data': api_data,
            'count': len(api_data),
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500


def watch_api_database():
    """
    监控API数据库变化，实时推送新数据到前端
    """
    last_check_time = time.time()
    
    while True:
        try:
            if os.path.exists(API_DB_PATH):
                # 检查数据库文件的修改时间
                db_mtime = os.path.getmtime(API_DB_PATH)
                
                if db_mtime > last_check_time:
                    # 数据库有更新，获取最新数据
                    new_data = get_api_data_from_db(10)  # 获取最新10条
                    
                    if new_data:
                        # 通过WebSocket推送到前端
                        socketio.emit('new_api_data', {
                            'data': new_data,
                            'timestamp': datetime.now().isoformat()
                        })
                        
                    last_check_time = db_mtime
                    
        except Exception as e:
            print(f"API数据库监控错误: {e}")
            
        time.sleep(2)  # 每2秒检查一次


# 启动API数据库监控线程
api_monitor_thread = threading.Thread(target=watch_api_database, daemon=True)
api_monitor_thread.start()


# WebSocket事件处理
@socketio.on('connect')
def handle_connect():
    """客户端连接事件"""
    print('客户端已连接')
    emit('connected', {'message': '已连接到服务器'})


@socketio.on('disconnect')
def handle_disconnect():
    """客户端断开连接事件"""
    print('客户端已断开连接')


@socketio.on('ping')
def handle_ping():
    """心跳检测"""
    emit('pong', {'timestamp': datetime.now().isoformat()})


if __name__ == '__main__':
    print("启动实时浏览器操作后端服务...")
    print("服务地址: http://localhost:5000")
    print("WebSocket地址: ws://localhost:5000")
    
    # 创建录制目录
    recordings_dir = os.path.join(os.path.dirname(__file__), 'recordings')
    os.makedirs(recordings_dir, exist_ok=True)
    
    socketio.run(app, host='0.0.0.0', port=5000, debug=True)