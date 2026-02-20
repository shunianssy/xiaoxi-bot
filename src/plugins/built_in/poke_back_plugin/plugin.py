"""
戳一戳回戳插件

当机器人被戳时，AI根据上下文决定是否戳回去
"""

from typing import List, Tuple, Type

from src.plugin_system import BasePlugin, register_plugin, ComponentInfo
from src.plugin_system.base.config_types import ConfigField
from src.common.logger import get_logger

from src.plugins.built_in.poke_back_plugin.poke_back import PokeBackAction

logger = get_logger("poke_back_plugin")


@register_plugin
class PokeBackPlugin(BasePlugin):
    """戳一戳回戳插件

    提供AI根据上下文决定是否戳回去的功能：
    - 当机器人被戳时，AI可以决定是否戳回去
    - 支持配置是否启用此功能
    """

    # 插件基本信息
    plugin_name: str = "poke_back"
    enable_plugin: bool = True
    dependencies: list[str] = []
    python_dependencies: list[str] = []
    config_file_name: str = "config.toml"

    # 配置节描述
    config_section_descriptions = {
        "plugin": "插件启用配置",
        "components": "组件启用配置",
    }

    # 配置Schema定义
    config_schema: dict = {
        "plugin": {
            "enabled": ConfigField(type=bool, default=True, description="是否启用戳一戳回戳插件"),
            "config_version": ConfigField(type=str, default="1.0.0", description="配置文件版本"),
        },
        "components": {
            "enable_poke_back": ConfigField(type=bool, default=True, description="是否启用戳回去动作"),
        },
        "poke_back": {
            "enable_poke_back": ConfigField(type=bool, default=True, description="是否启用戳回去功能"),
        },
    }

    def get_plugin_components(self) -> List[Tuple[ComponentInfo, Type]]:
        """返回插件包含的组件列表"""
        components = []

        # 根据配置注册戳回去动作
        if self.get_config("components.enable_poke_back", True):
            components.append((PokeBackAction.get_action_info(), PokeBackAction))

        return components
