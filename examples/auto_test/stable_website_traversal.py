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

from browser_use import Agent, ChatGoogle, BrowserProfile
from browser_use.browser.profile import ProxySettings

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
	"""
	运行网站遍历任务
	
	Args:
		website_url: 目标网站URL
		traversal_depth: 遍历深度，默认为3级
	"""
	# 创建代理配置对象
	proxy_settings = ProxySettings(server='http://127.0.0.1:8080')
	print(f"代理配置: {proxy_settings}")
	print(f"代理服务器: {proxy_settings.server}")
	
	# 创建浏览器配置文件
	browser_profile = BrowserProfile(
		headless=False,
		disable_security=True,
		proxy=proxy_settings,
		minimum_wait_page_load_time=3.0,
		wait_between_actions=1.0,
	)
	
	agent = Agent(
		task=f"""**网站系统遍历任务 - 确定性执行模式**

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
- 每个决策都要基于当前页面的实际状态""",
		llm=llm,
		max_actions_per_step=1,  # 每步只执行一个动作，确保精确控制
		max_steps=50,  # 限制最大步数，避免无限循环
		directly_open_url=True,  # 直接打开URL，减少导航步骤
		# 使用BrowserProfile而不是browser_config字典
		browser_profile=browser_profile,
		save_conversation_path=f"d:/code/browser-use-fork/examples/auto_test/conversation-stable-{datetime.now().strftime('%Y%m%d_%H%M%S')}",
	)

	async def step_monitor(agent):
		print(f'Step {agent.state.n_steps}: {agent.state.last_model_output}')

	result = await agent.run(on_step_end=step_monitor)
	agent.save_history(f'd:/code/browser-use-fork/examples/auto_test/agent_history_stable_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json')
	print('Agent运行成功完成')


if __name__ == '__main__':
	website_url = 'https://xiaozihealth.com'
	asyncio.run(run_traversal(website_url))
