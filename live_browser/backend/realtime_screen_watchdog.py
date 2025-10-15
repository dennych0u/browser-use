"""实时屏幕捕获Watchdog，用于实时传输浏览器画面到前端"""

import asyncio
import base64
import time
from typing import ClassVar, Optional, Dict, Any
from datetime import datetime

from bubus import BaseEvent
from cdp_use.cdp.page.events import ScreencastFrameEvent
from pydantic import PrivateAttr

from browser_use.browser.events import BrowserConnectedEvent, BrowserStopEvent, TabCreatedEvent
from browser_use.browser.watchdog_base import BaseWatchdog


class RealtimeScreenWatchdog(BaseWatchdog):
    """
    实时屏幕捕获Watchdog
    
    功能：
    1. 监听浏览器连接和标签页创建事件
    2. 启动CDP screencast实时捕获
    3. 将捕获的帧通过WebSocket实时传输到前端
    4. 提供帧率控制和质量调节
    """

    LISTENS_TO: ClassVar[list[type[BaseEvent]]] = [
        BrowserConnectedEvent, 
        BrowserStopEvent, 
        TabCreatedEvent
    ]
    EMITS: ClassVar[list[type[BaseEvent]]] = []

    # 配置参数
    frame_rate: int = 10  # 每秒帧数
    quality: int = 60     # 图片质量 (1-100)
    max_width: int = 1280 # 最大宽度
    max_height: int = 720 # 最大高度

    # 私有状态
    _is_recording: bool = PrivateAttr(default=False)
    _last_frame_time: float = PrivateAttr(default=0.0)
    _frame_interval: float = PrivateAttr(default=0.1)  # 1/frame_rate
    _socketio_instance: Optional[Any] = PrivateAttr(default=None)
    _active_sessions: Dict[str, bool] = PrivateAttr(default_factory=dict)

    def __init__(self, **data):
        """初始化实时屏幕捕获watchdog"""
        super().__init__(**data)
        self._frame_interval = 1.0 / self.frame_rate
        
    def set_socketio(self, socketio_instance):
        """设置SocketIO实例用于实时传输"""
        self._socketio_instance = socketio_instance
        
    def update_config(self, frame_rate: int = None, quality: int = None, 
                     max_width: int = None, max_height: int = None):
        """更新配置参数"""
        if frame_rate is not None:
            self.frame_rate = frame_rate
            self._frame_interval = 1.0 / frame_rate
        if quality is not None:
            self.quality = max(1, min(100, quality))
        if max_width is not None:
            self.max_width = max_width
        if max_height is not None:
            self.max_height = max_height

    async def on_BrowserConnectedEvent(self, event: BrowserConnectedEvent) -> None:
        """浏览器连接时启动实时屏幕捕获"""
        try:
            self.logger.info("🎥 启动实时屏幕捕获...")
            await self._start_realtime_capture()
        except Exception as e:
            self.logger.error(f"启动实时屏幕捕获失败: {e}")

    async def on_TabCreatedEvent(self, event: TabCreatedEvent) -> None:
        """新标签页创建时确保屏幕捕获正常工作"""
        try:
            if not self._is_recording:
                await self._start_realtime_capture()
        except Exception as e:
            self.logger.error(f"标签页创建时启动屏幕捕获失败: {e}")

    async def on_BrowserStopEvent(self, event: BrowserStopEvent) -> None:
        """浏览器停止时停止屏幕捕获"""
        await self._stop_realtime_capture()

    async def _start_realtime_capture(self) -> None:
        """启动实时屏幕捕获"""
        if self._is_recording:
            return
            
        try:
            # 获取CDP会话
            cdp_session = await self.browser_session.get_or_create_cdp_session()
            
            # 注册screencast帧事件处理器
            self.browser_session.cdp_client.register.Page.screencastFrame(self._on_screencast_frame)
            
            # 启动screencast
            await cdp_session.cdp_client.send.Page.startScreencast(
                params={
                    'format': 'jpeg',
                    'quality': self.quality,
                    'maxWidth': self.max_width,
                    'maxHeight': self.max_height,
                    'everyNthFrame': max(1, int(30 / self.frame_rate)),  # 基于30fps调整
                },
                session_id=cdp_session.session_id,
            )
            
            self._is_recording = True
            self._active_sessions[cdp_session.session_id] = True
            self.logger.info(f"✅ 实时屏幕捕获已启动 (帧率: {self.frame_rate}fps, 质量: {self.quality})")
            
        except Exception as e:
            self.logger.error(f"启动实时屏幕捕获失败: {e}")
            self._is_recording = False

    async def _stop_realtime_capture(self) -> None:
        """停止实时屏幕捕获"""
        if not self._is_recording:
            return
            
        try:
            # 停止所有活跃的screencast会话
            for session_id in list(self._active_sessions.keys()):
                try:
                    await self.browser_session.cdp_client.send.Page.stopScreencast(
                        session_id=session_id
                    )
                except Exception as e:
                    self.logger.debug(f"停止screencast会话 {session_id} 失败: {e}")
                    
            self._active_sessions.clear()
            self._is_recording = False
            self.logger.info("🛑 实时屏幕捕获已停止")
            
        except Exception as e:
            self.logger.error(f"停止实时屏幕捕获失败: {e}")

    def _on_screencast_frame(self, event: ScreencastFrameEvent, session_id: str | None) -> None:
        """处理screencast帧事件（同步方法）"""
        # 帧率控制
        current_time = time.time()
        if current_time - self._last_frame_time < self._frame_interval:
            # 跳过此帧以控制帧率
            asyncio.create_task(self._ack_screencast_frame(event, session_id))
            return
            
        self._last_frame_time = current_time
        
        # 异步处理帧数据
        asyncio.create_task(self._process_screencast_frame(event, session_id))

    async def _process_screencast_frame(self, event: ScreencastFrameEvent, session_id: str | None) -> None:
        """异步处理screencast帧"""
        try:
            # 获取帧数据
            frame_data = event.get('data', '')
            if not frame_data:
                return
                
            # 通过WebSocket发送实时画面
            if self._socketio_instance:
                frame_info = {
                    'type': 'realtime_frame',
                    'data': frame_data,
                    'timestamp': datetime.now().isoformat(),
                    'session_id': session_id,
                    'metadata': {
                        'width': self.max_width,
                        'height': self.max_height,
                        'quality': self.quality,
                        'format': 'jpeg'
                    }
                }
                
                # 发送到所有连接的客户端
                self._socketio_instance.emit('realtime_screen', frame_info)
                
            # 确认帧处理完成
            await self._ack_screencast_frame(event, session_id)
            
        except Exception as e:
            self.logger.error(f"处理screencast帧失败: {e}")

    async def _ack_screencast_frame(self, event: ScreencastFrameEvent, session_id: str | None) -> None:
        """确认screencast帧处理完成"""
        try:
            session_id_from_event = event.get('sessionId')
            if session_id_from_event:
                await self.browser_session.cdp_client.send.Page.screencastFrameAck(
                    params={'sessionId': session_id_from_event}, 
                    session_id=session_id
                )
        except Exception as e:
            self.logger.debug(f"确认screencast帧失败: {e}")

    def get_status(self) -> Dict[str, Any]:
        """获取实时捕获状态"""
        return {
            'is_recording': self._is_recording,
            'frame_rate': self.frame_rate,
            'quality': self.quality,
            'max_width': self.max_width,
            'max_height': self.max_height,
            'active_sessions': len(self._active_sessions),
            'last_frame_time': self._last_frame_time
        }

    async def take_manual_screenshot(self) -> Optional[str]:
        """手动截取一张屏幕截图"""
        try:
            cdp_session = await self.browser_session.get_or_create_cdp_session()
            
            result = await cdp_session.cdp_client.send.Page.captureScreenshot(
                params={
                    'format': 'jpeg',
                    'quality': self.quality,
                    'captureBeyondViewport': False
                },
                session_id=cdp_session.session_id
            )
            
            if result and 'data' in result:
                return result['data']
                
        except Exception as e:
            self.logger.error(f"手动截图失败: {e}")
            
        return None