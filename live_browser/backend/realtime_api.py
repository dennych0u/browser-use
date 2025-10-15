"""实时屏幕捕获API端点"""

from flask import Blueprint, request, jsonify
from typing import Dict, Any
from datetime import datetime

# 创建蓝图
realtime_bp = Blueprint('realtime', __name__, url_prefix='/api/realtime')


@realtime_bp.route('/screen/config', methods=['GET'])
def get_screen_config():
    """获取实时屏幕捕获配置"""
    try:
        from app import browser_controller
        
        if browser_controller.realtime_watchdog:
            status = browser_controller.realtime_watchdog.get_status()
            return jsonify({
                'success': True,
                'config': status
            })
        else:
            return jsonify({
                'success': False,
                'message': '实时屏幕捕获未启动'
            }), 400
            
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'获取配置失败: {str(e)}'
        }), 500


@realtime_bp.route('/screen/config', methods=['POST'])
def update_screen_config():
    """更新实时屏幕捕获配置"""
    try:
        from app import browser_controller
        
        if not browser_controller.realtime_watchdog:
            return jsonify({
                'success': False,
                'message': '实时屏幕捕获未启动'
            }), 400
            
        data = request.get_json()
        if not data:
            return jsonify({
                'success': False,
                'message': '请提供配置数据'
            }), 400
            
        # 更新配置
        browser_controller.realtime_watchdog.update_config(
            frame_rate=data.get('frame_rate'),
            quality=data.get('quality'),
            max_width=data.get('max_width'),
            max_height=data.get('max_height')
        )
        
        return jsonify({
            'success': True,
            'message': '配置更新成功',
            'config': browser_controller.realtime_watchdog.get_status()
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'更新配置失败: {str(e)}'
        }), 500


@realtime_bp.route('/screen/screenshot', methods=['POST'])
def take_manual_screenshot():
    """手动截取屏幕截图"""
    try:
        from app import browser_controller
        import asyncio
        
        if not browser_controller.realtime_watchdog:
            return jsonify({
                'success': False,
                'message': '实时屏幕捕获未启动'
            }), 400
            
        # 在事件循环中执行异步截图
        if browser_controller.loop and not browser_controller.loop.is_closed():
            future = asyncio.run_coroutine_threadsafe(
                browser_controller.realtime_watchdog.take_manual_screenshot(),
                browser_controller.loop
            )
            screenshot_data = future.result(timeout=10)
            
            if screenshot_data:
                return jsonify({
                    'success': True,
                    'screenshot': screenshot_data,
                    'timestamp': datetime.now().isoformat()
                })
            else:
                return jsonify({
                    'success': False,
                    'message': '截图失败'
                }), 500
        else:
            return jsonify({
                'success': False,
                'message': '浏览器会话未运行'
            }), 400
            
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'截图失败: {str(e)}'
        }), 500


@realtime_bp.route('/screen/status', methods=['GET'])
def get_screen_status():
    """获取实时屏幕捕获状态"""
    try:
        from app import browser_controller
        
        if browser_controller.realtime_watchdog:
            status = browser_controller.realtime_watchdog.get_status()
            return jsonify({
                'success': True,
                'status': status,
                'is_active': browser_controller.is_running
            })
        else:
            return jsonify({
                'success': True,
                'status': {
                    'is_recording': False,
                    'frame_rate': 0,
                    'quality': 0,
                    'max_width': 0,
                    'max_height': 0,
                    'active_sessions': 0,
                    'last_frame_time': 0
                },
                'is_active': False
            })
            
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'获取状态失败: {str(e)}'
        }), 500