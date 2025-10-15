import asyncio
import os
import sys
import json
from typing import List, Optional
from datetime import datetime

# 设置代理绕过规则，确保localhost不经过代理
os.environ['NO_PROXY'] = 'localhost,127.0.0.1,::1'

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from dotenv import load_dotenv
from pydantic import BaseModel

from browser_use import Agent, ChatGoogle

load_dotenv()

api_key = os.getenv('GOOGLE_API_KEY')
if not api_key:
	raise ValueError('GOOGLE_API_KEY is not set')

llm = ChatGoogle(model='gemini-2.5-pro', api_key=api_key)


# 数据模型定义
class TestAction(BaseModel):
	action_id: str
	action_type: str
	selector: str
	target_description: str
	input_value: Optional[str] = None
	expected_result: str
	wait_condition: Optional[str] = None


class PageSection(BaseModel):
	section_name: str
	section_url: str
	depth_level: int
	parent_section: Optional[str] = None
	test_actions: List[TestAction]


class InteractionStep(BaseModel):
	step_number: int
	page_title: str
	page_url: str
	section_info: PageSection
	interaction_type: str
	target_element: str
	interaction_result: str
	description: str
	traversal_strategy: str


class AutomationTestScript(BaseModel):
	script_name: str
	website_url: str
	total_sections: int
	total_actions: int
	successful_actions: int
	failed_actions: int
	page_sections: List[PageSection]
	interaction_steps: List[InteractionStep]
	test_script_code: str


async def run_traversal(website_url: str, traversal_depth: int = 3):
	# 详细的任务描述，指导代理进行深度优先+广度遍历的网站交互测试
	enhanced_task = f"""
**人工操作模拟 - 网站遍历任务**

**目标**: 像真实用户一样浏览 {website_url}

**人工操作特征模拟**:
1. **浏览节奏**:
   - 页面加载后先观察2-3秒
   - 滚动浏览页面内容，速度适中
   - 在感兴趣的区域停留更长时间

2. **点击行为**:
   - 优先点击显眼的导航菜单
   - 对标题和按钮表现出"好奇心"
   - 避免连续快速点击
   - 偶尔返回上一页重新探索

3. **交互模式**:
   - 先浏览概览，再深入细节
   - 对相似功能进行对比
   - 遇到表单会尝试填写但谨慎提交
   - 会查看页脚和侧边栏信息

4. **决策逻辑**:
   - 基于页面内容的重要性排序
   - 优先探索主要功能模块
   - 对用户常用功能给予更多关注
   - 避免重复访问相同类型的页面

**执行顺序**:
1. 主导航菜单（从左到右）
2. 主要功能区域
3. 次要链接和辅助功能
4. 页脚和其他区域

请严格模拟真实用户的浏览习惯和决策过程。
"""

	stability_system_message = """
**遍历稳定性增强指令**:

1. **决策一致性**:
   - 每次面临相同情况时，采用相同的处理策略
   - 建立明确的优先级规则：导航菜单 > 主要内容 > 辅助功能
   - 使用确定性的元素选择策略（优先选择ID，其次class，最后xpath）

2. **错误恢复机制**:
   - 遇到页面加载失败，等待5秒后刷新
   - 元素不可点击时，先滚动使其可见
   - 出现意外弹窗，先处理弹窗再继续原计划

3. **状态管理**:
   - 每步操作前检查当前页面状态
   - 维护已访问页面的清单，避免重复访问
   - 记录当前遍历的深度和位置

4. **时间控制**:
   - 每个页面最少停留3秒，最多停留30秒
   - 操作间隔保持1-2秒，模拟人工思考时间
   - 总体任务时间控制在15分钟内
"""

	# 创建Agent时添加更多配置选项
	agent = Agent(
		task=enhanced_task,  # 使用优化后的任务描述
		llm=llm,
		extend_system_message=stability_system_message,   # 使用遍历稳定性增强指令
		# 核心稳定性参数
		max_history_items=15,  # 适中的历史记录，避免过度截断
		flash_mode=False,  # 保持完整的思考过程
		use_thinking=True,  # 启用思考模式，提高决策质量
		use_vision=True,  # 保持视觉能力
		# 超时和重试配置
		llm_timeout=240,  # 4分钟超时，避免匆忙决策
		step_timeout=180,  # 3分钟步骤超时
		max_failures=2,  # 减少重试次数，避免错误累积
		final_response_after_failure=True,
		# 行为控制参数
		max_actions_per_step=5,  # 限制单步操作数，提高可控性
		directly_open_url=True,  # 直接打开URL，减少导航步骤
		# 浏览器配置
		browser_config={
			'headless': False,
			'disable_security': True,
			'slow_mo': 1000,  # 添加1秒延迟，模拟人工操作
			'timeout': 30000,  # 30秒页面加载超时
		},
		save_conversation_path=f"d:/code/browser-use-fork/examples/auto_test/conversation-human_simulate-{datetime.now().strftime('%Y%m%d_%H%M%S')}",
	)

	async def step_monitor(agent):
		print(f'Step {agent.state.n_steps}: {agent.state.last_model_output}')

	result = await agent.run(on_step_end=step_monitor)
	agent.save_history(f'd:/code/browser-use-fork/examples/auto_test/agent_history_human_simulate-{datetime.now().strftime("%Y%m%d_%H%M%S")}.json')
	print('Agent运行成功完成')


if __name__ == '__main__':
	website_url = 'https://xiaozihealth.com'
	asyncio.run(run_traversal(website_url))