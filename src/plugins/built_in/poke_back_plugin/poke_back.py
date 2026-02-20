"""
戳一戳回戳动作

当机器人被戳时，AI根据上下文决定是否戳回去
"""

import random
from typing import Tuple

from src.plugin_system import BaseAction, ActionActivationType
from src.common.logger import get_logger
from src.config.config import global_config

logger = get_logger("poke_back")


class PokeBackAction(BaseAction):
    """戳回去动作 - AI根据上下文决定是否戳回去"""

    # 动作激活配置 - 使用KEYWORD激活，当消息包含戳一戳相关文本时激活
    activation_type = ActionActivationType.KEYWORD
    activation_keywords = ["戳了戳", "戳一戳"]
    parallel_action = True

    # 动作基本信息
    action_name = "poke_back"
    action_description = "戳回去 - 当被戳时，根据上下文决定是否戳回去"

    # 动作参数定义
    action_parameters = {
        "poke_back": "是否戳回去，true或false",
    }

    # 动作使用场景
    action_require = [
        "当你被戳时，可以选择戳回去",
        "根据聊天上下文和心情决定是否戳回去",
        "如果对方是好友或关系好，更倾向于戳回去",
        "如果正在忙碌或不想互动，可以选择不戳回去",
        "可以配合文字回复一起使用",
    ]

    # 关联类型
    associated_types = ["poke"]

    async def execute(self) -> Tuple[bool, str]:
        """执行戳回去动作"""
        try:
            # 检查是否启用戳一戳功能
            if not self._is_poke_enabled():
                logger.debug(f"{self.log_prefix} 戳一戳功能未启用")
                return False, "戳一戳功能未启用"

            # 检查是否是戳一戳消息（通过消息内容判断）
            message_text = self.action_message.processed_plain_text if self.action_message else ""
            if "戳了戳" not in message_text:
                logger.debug(f"{self.log_prefix} 不是戳一戳消息，跳过")
                return False, "不是戳一戳消息"

            # 获取是否戳回去的决策
            should_poke_back = self.action_data.get("poke_back", False)

            if not should_poke_back:
                logger.info(f"{self.log_prefix} AI决定不戳回去")
                await self.store_action_info(
                    action_build_into_prompt=True,
                    action_prompt_display="你收到了戳一戳，但决定不戳回去",
                    action_done=True,
                )
                return True, "决定不戳回去"

            # 执行戳回去
            success = await self._send_poke_back()

            if success:
                logger.info(f"{self.log_prefix} 成功戳回去")
                await self.store_action_info(
                    action_build_into_prompt=True,
                    action_prompt_display="你戳了回去",
                    action_done=True,
                )
                return True, "成功戳回去"
            else:
                logger.warning(f"{self.log_prefix} 戳回去失败")
                return False, "戳回去失败"

        except Exception as e:
            logger.error(f"{self.log_prefix} 戳回去动作执行失败: {e}", exc_info=True)
            return False, f"戳回去失败: {str(e)}"

    def _is_poke_enabled(self) -> bool:
        """检查戳一戳功能是否启用"""
        try:
            # 从插件配置中获取
            enabled = self.get_config("enable_poke_back", True)
            return enabled
        except Exception:
            return True

    async def _send_poke_back(self) -> bool:
        """发送戳一戳回去"""
        try:
            # 获取戳一戳的目标用户ID
            target_user_id = self.user_id
            if not target_user_id:
                logger.error(f"{self.log_prefix} 无法获取戳一戳目标用户ID")
                return False

            # 发送戳一戳命令（使用枚举名称SEND_POKE）
            success = await self.send_command(
                command_name="SEND_POKE",
                args={"qq_id": int(target_user_id)},
                display_message=f"戳了戳 {self.user_nickname}",
                storage_message=False,
            )

            return success

        except Exception as e:
            logger.error(f"{self.log_prefix} 发送戳一戳失败: {e}")
            return False
