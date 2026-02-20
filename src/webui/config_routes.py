"""
配置管理API路由
"""

import os
import shutil
import tomlkit
from datetime import datetime
from fastapi import APIRouter, HTTPException, Body, Depends, Cookie, Header
from typing import Any, Annotated, Optional

from src.common.logger import get_logger
from src.webui.auth import verify_auth_token_from_cookie_or_header
from src.common.toml_utils import save_toml_with_format, _update_toml_doc, format_toml_string
from src.config.config import Config, APIAdapterConfig, CONFIG_DIR, PROJECT_ROOT, TEMPLATE_DIR, load_config, api_ada_load_config
import src.config.config as config_module
from src.config.official_configs import (
    BotConfig,
    PersonalityConfig,
    RelationshipConfig,
    ChatConfig,
    MessageReceiveConfig,
    EmojiConfig,
    ExpressionConfig,
    KeywordReactionConfig,
    ChineseTypoConfig,
    ResponsePostProcessConfig,
    ResponseSplitterConfig,
    TelemetryConfig,
    ExperimentalConfig,
    MaimMessageConfig,
    LPMMKnowledgeConfig,
    ToolConfig,
    MemoryConfig,
    DebugConfig,
    VoiceConfig,
)
from src.config.api_ada_configs import (
    ModelTaskConfig,
    ModelInfo,
    APIProvider,
)
from src.webui.config_schema import ConfigSchemaGenerator

logger = get_logger("webui")

# 模块级别的类型别名（解决 B008 ruff 错误）
ConfigBody = Annotated[dict[str, Any], Body()]
SectionBody = Annotated[Any, Body()]
RawContentBody = Annotated[str, Body(embed=True)]
PathBody = Annotated[dict[str, str], Body()]

router = APIRouter(prefix="/config", tags=["config"])


def require_auth(
    maibot_session: Optional[str] = Cookie(None),
    authorization: Optional[str] = Header(None),
) -> bool:
    """认证依赖：验证用户是否已登录"""
    return verify_auth_token_from_cookie_or_header(maibot_session, authorization)


# ===== 架构获取接口 =====


@router.get("/schema/bot")
async def get_bot_config_schema(_auth: bool = Depends(require_auth)):
    """获取小熙主程序配置架构"""
    try:
        # Config 类包含所有子配置
        schema = ConfigSchemaGenerator.generate_config_schema(Config)
        return {"success": True, "schema": schema}
    except Exception as e:
        logger.error(f"获取配置架构失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取配置架构失败: {str(e)}") from e


@router.get("/schema/model")
async def get_model_config_schema(_auth: bool = Depends(require_auth)):
    """获取模型配置架构（包含提供商和模型任务配置）"""
    try:
        schema = ConfigSchemaGenerator.generate_config_schema(APIAdapterConfig)
        return {"success": True, "schema": schema}
    except Exception as e:
        logger.error(f"获取模型配置架构失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取模型配置架构失败: {str(e)}") from e


# ===== 子配置架构获取接口 =====


@router.get("/schema/section/{section_name}")
async def get_config_section_schema(section_name: str, _auth: bool = Depends(require_auth)):
    """
    获取指定配置节的架构

    支持的section_name:
    - bot: BotConfig
    - personality: PersonalityConfig
    - relationship: RelationshipConfig
    - chat: ChatConfig
    - message_receive: MessageReceiveConfig
    - emoji: EmojiConfig
    - expression: ExpressionConfig
    - keyword_reaction: KeywordReactionConfig
    - chinese_typo: ChineseTypoConfig
    - response_post_process: ResponsePostProcessConfig
    - response_splitter: ResponseSplitterConfig
    - telemetry: TelemetryConfig
    - experimental: ExperimentalConfig
    - maim_message: MaimMessageConfig
    - lpmm_knowledge: LPMMKnowledgeConfig
    - tool: ToolConfig
    - memory: MemoryConfig
    - debug: DebugConfig
    - voice: VoiceConfig
    - jargon: JargonConfig
    - model_task_config: ModelTaskConfig
    - api_provider: APIProvider
    - model_info: ModelInfo
    """
    section_map = {
        "bot": BotConfig,
        "personality": PersonalityConfig,
        "relationship": RelationshipConfig,
        "chat": ChatConfig,
        "message_receive": MessageReceiveConfig,
        "emoji": EmojiConfig,
        "expression": ExpressionConfig,
        "keyword_reaction": KeywordReactionConfig,
        "chinese_typo": ChineseTypoConfig,
        "response_post_process": ResponsePostProcessConfig,
        "response_splitter": ResponseSplitterConfig,
        "telemetry": TelemetryConfig,
        "experimental": ExperimentalConfig,
        "maim_message": MaimMessageConfig,
        "lpmm_knowledge": LPMMKnowledgeConfig,
        "tool": ToolConfig,
        "memory": MemoryConfig,
        "debug": DebugConfig,
        "voice": VoiceConfig,
        "model_task_config": ModelTaskConfig,
        "api_provider": APIProvider,
        "model_info": ModelInfo,
    }

    if section_name not in section_map:
        raise HTTPException(status_code=404, detail=f"配置节 '{section_name}' 不存在")

    try:
        config_class = section_map[section_name]
        schema = ConfigSchemaGenerator.generate_schema(config_class, include_nested=False)
        return {"success": True, "schema": schema}
    except Exception as e:
        logger.error(f"获取配置节架构失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取配置节架构失败: {str(e)}") from e


# ===== 配置读取接口 =====


@router.get("/bot")
async def get_bot_config(_auth: bool = Depends(require_auth)):
    """获取小熙主程序配置"""
    try:
        config_path = os.path.join(CONFIG_DIR, "bot_config.toml")
        if not os.path.exists(config_path):
            raise HTTPException(status_code=404, detail="配置文件不存在")

        with open(config_path, "r", encoding="utf-8") as f:
            config_data = tomlkit.load(f)

        return {"success": True, "config": config_data}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"读取配置文件失败: {e}")
        raise HTTPException(status_code=500, detail=f"读取配置文件失败: {str(e)}") from e


@router.get("/model")
async def get_model_config(_auth: bool = Depends(require_auth)):
    """获取模型配置（包含提供商和模型任务配置）"""
    try:
        config_path = os.path.join(CONFIG_DIR, "model_config.toml")
        if not os.path.exists(config_path):
            raise HTTPException(status_code=404, detail="配置文件不存在")

        with open(config_path, "r", encoding="utf-8") as f:
            config_data = tomlkit.load(f)

        return {"success": True, "config": config_data}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"读取配置文件失败: {e}")
        raise HTTPException(status_code=500, detail=f"读取配置文件失败: {str(e)}") from e


# ===== 配置更新接口 =====


@router.post("/bot")
async def update_bot_config(config_data: ConfigBody, _auth: bool = Depends(require_auth)):
    """更新小熙主程序配置"""
    try:
        # 验证配置数据
        try:
            Config.from_dict(config_data)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"配置数据验证失败: {str(e)}") from e

        # 保存配置文件（自动保留注释和格式）
        config_path = os.path.join(CONFIG_DIR, "bot_config.toml")
        save_toml_with_format(config_data, config_path)

        # 重新加载内存中的配置
        config_module.global_config = load_config(config_path)

        logger.info("小熙主程序配置已更新")
        return {"success": True, "message": "配置已保存"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"保存配置文件失败: {e}")
        raise HTTPException(status_code=500, detail=f"保存配置文件失败: {str(e)}") from e


@router.post("/model")
async def update_model_config(config_data: ConfigBody, _auth: bool = Depends(require_auth)):
    """更新模型配置"""
    try:
        # 验证配置数据
        try:
            APIAdapterConfig.from_dict(config_data)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"配置数据验证失败: {str(e)}") from e

        # 保存配置文件（自动保留注释和格式）
        config_path = os.path.join(CONFIG_DIR, "model_config.toml")
        save_toml_with_format(config_data, config_path)

        # 重新加载内存中的配置
        config_module.model_config = api_ada_load_config(config_path)

        logger.info("模型配置已更新")
        return {"success": True, "message": "配置已保存"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"保存配置文件失败: {e}")
        raise HTTPException(status_code=500, detail=f"保存配置文件失败: {str(e)}") from e


# ===== 配置节更新接口 =====


@router.post("/bot/section/{section_name}")
async def update_bot_config_section(section_name: str, section_data: SectionBody, _auth: bool = Depends(require_auth)):
    """更新小熙主程序配置的指定节（保留注释和格式）"""
    try:
        # 读取现有配置
        config_path = os.path.join(CONFIG_DIR, "bot_config.toml")
        if not os.path.exists(config_path):
            raise HTTPException(status_code=404, detail="配置文件不存在")

        with open(config_path, "r", encoding="utf-8") as f:
            config_data = tomlkit.load(f)

        # 更新指定节
        if section_name not in config_data:
            raise HTTPException(status_code=404, detail=f"配置节 '{section_name}' 不存在")

        # 使用递归合并保留注释（对于字典类型）
        # 对于数组类型（如 platforms, aliases），直接替换
        if isinstance(section_data, list):
            # 列表直接替换
            config_data[section_name] = section_data
        elif isinstance(section_data, dict) and isinstance(config_data[section_name], dict):
            # 字典递归合并
            _update_toml_doc(config_data[section_name], section_data)
        else:
            # 其他类型直接替换
            config_data[section_name] = section_data

        # 验证完整配置
        try:
            Config.from_dict(config_data)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"配置数据验证失败: {str(e)}") from e

        # 保存配置（格式化数组为多行，保留注释）
        save_toml_with_format(config_data, config_path)

        # 重新加载内存中的配置
        config_module.global_config = load_config(config_path)

        logger.info(f"配置节 '{section_name}' 已更新（保留注释）")
        return {"success": True, "message": f"配置节 '{section_name}' 已保存"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"更新配置节失败: {e}")
        raise HTTPException(status_code=500, detail=f"更新配置节失败: {str(e)}") from e


# ===== 原始 TOML 文件操作接口 =====


@router.get("/bot/raw")
async def get_bot_config_raw(_auth: bool = Depends(require_auth)):
    """获取小熙主程序配置的原始 TOML 内容"""
    try:
        config_path = os.path.join(CONFIG_DIR, "bot_config.toml")
        if not os.path.exists(config_path):
            raise HTTPException(status_code=404, detail="配置文件不存在")

        with open(config_path, "r", encoding="utf-8") as f:
            raw_content = f.read()

        return {"success": True, "content": raw_content}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"读取配置文件失败: {e}")
        raise HTTPException(status_code=500, detail=f"读取配置文件失败: {str(e)}") from e


@router.post("/bot/raw")
async def update_bot_config_raw(raw_content: RawContentBody, _auth: bool = Depends(require_auth)):
    """更新小熙主程序配置（直接保存原始 TOML 内容，会先验证格式）"""
    try:
        # 验证 TOML 格式
        try:
            config_data = tomlkit.loads(raw_content)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"TOML 格式错误: {str(e)}") from e

        # 验证配置数据结构
        try:
            Config.from_dict(config_data)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"配置数据验证失败: {str(e)}") from e

        # 保存配置文件
        config_path = os.path.join(CONFIG_DIR, "bot_config.toml")
        with open(config_path, "w", encoding="utf-8") as f:
            f.write(raw_content)

        # 重新加载内存中的配置
        config_module.global_config = load_config(config_path)

        logger.info("小熙主程序配置已更新（原始模式）")
        return {"success": True, "message": "配置已保存"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"保存配置文件失败: {e}")
        raise HTTPException(status_code=500, detail=f"保存配置文件失败: {str(e)}") from e


@router.post("/model/section/{section_name}")
async def update_model_config_section(
    section_name: str, section_data: SectionBody, _auth: bool = Depends(require_auth)
):
    """更新模型配置的指定节（保留注释和格式）"""
    try:
        # 读取现有配置
        config_path = os.path.join(CONFIG_DIR, "model_config.toml")
        if not os.path.exists(config_path):
            raise HTTPException(status_code=404, detail="配置文件不存在")

        with open(config_path, "r", encoding="utf-8") as f:
            config_data = tomlkit.load(f)

        # 更新指定节
        if section_name not in config_data:
            raise HTTPException(status_code=404, detail=f"配置节 '{section_name}' 不存在")

        # 使用递归合并保留注释（对于字典类型）
        # 对于数组表（如 [[models]], [[api_providers]]），直接替换
        if isinstance(section_data, list):
            # 列表直接替换
            config_data[section_name] = section_data
        elif isinstance(section_data, dict) and isinstance(config_data[section_name], dict):
            # 字典递归合并
            _update_toml_doc(config_data[section_name], section_data)
        else:
            # 其他类型直接替换
            config_data[section_name] = section_data

        # 验证完整配置
        try:
            APIAdapterConfig.from_dict(config_data)
        except Exception as e:
            logger.error(f"配置数据验证失败，详细错误: {str(e)}")
            # 特殊处理：如果是更新 api_providers，检查是否有模型引用了已删除的provider
            if section_name == "api_providers" and "api_provider" in str(e):
                provider_names = {p.get("name") for p in section_data if isinstance(p, dict)}
                models = config_data.get("models", [])
                orphaned_models = [
                    m.get("name") for m in models if isinstance(m, dict) and m.get("api_provider") not in provider_names
                ]
                if orphaned_models:
                    error_msg = f"以下模型引用了已删除的提供商: {', '.join(orphaned_models)}。请先在模型管理页面删除这些模型，或重新分配它们的提供商。"
                    raise HTTPException(status_code=400, detail=error_msg) from e
            raise HTTPException(status_code=400, detail=f"配置数据验证失败: {str(e)}") from e

        # 保存配置（格式化数组为多行，保留注释）
        save_toml_with_format(config_data, config_path)

        # 重新加载内存中的配置
        config_module.model_config = api_ada_load_config(config_path)

        logger.info(f"配置节 '{section_name}' 已更新（保留注释）")
        return {"success": True, "message": f"配置节 '{section_name}' 已保存"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"更新配置节失败: {e}")
        raise HTTPException(status_code=500, detail=f"更新配置节失败: {str(e)}") from e


# ===== 适配器配置管理接口 =====


def _normalize_adapter_path(path: str) -> str:
    """将路径转换为绝对路径（如果是相对路径，则相对于项目根目录）"""
    if not path:
        return path

    # 如果已经是绝对路径，直接返回
    if os.path.isabs(path):
        return path

    # 相对路径，转换为相对于项目根目录的绝对路径
    return os.path.normpath(os.path.join(PROJECT_ROOT, path))


def _to_relative_path(path: str) -> str:
    """尝试将绝对路径转换为相对于项目根目录的相对路径，如果无法转换则返回原路径"""
    if not path or not os.path.isabs(path):
        return path

    try:
        # 尝试获取相对路径
        rel_path = os.path.relpath(path, PROJECT_ROOT)
        # 如果相对路径不是以 .. 开头（说明文件在项目目录内），则返回相对路径
        if not rel_path.startswith(".."):
            return rel_path
    except (ValueError, TypeError):
        # 在 Windows 上，如果路径在不同驱动器，relpath 会抛出 ValueError
        pass

    # 无法转换为相对路径，返回绝对路径
    return path


@router.get("/adapter-config/path")
async def get_adapter_config_path(_auth: bool = Depends(require_auth)):
    """获取保存的适配器配置文件路径"""
    try:
        # 从 data/webui.json 读取路径偏好
        webui_data_path = os.path.join("data", "webui.json")
        if not os.path.exists(webui_data_path):
            return {"success": True, "path": None}

        import json

        with open(webui_data_path, "r", encoding="utf-8") as f:
            webui_data = json.load(f)

        adapter_config_path = webui_data.get("adapter_config_path")
        if not adapter_config_path:
            return {"success": True, "path": None}

        # 将路径规范化为绝对路径
        abs_path = _normalize_adapter_path(adapter_config_path)

        # 检查文件是否存在并返回最后修改时间
        if os.path.exists(abs_path):
            import datetime

            mtime = os.path.getmtime(abs_path)
            last_modified = datetime.datetime.fromtimestamp(mtime).isoformat()
            # 返回相对路径（如果可能）
            display_path = _to_relative_path(abs_path)
            return {"success": True, "path": display_path, "lastModified": last_modified}
        else:
            # 文件不存在，返回原路径
            return {"success": True, "path": adapter_config_path, "lastModified": None}

    except Exception as e:
        logger.error(f"获取适配器配置路径失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取配置路径失败: {str(e)}") from e


@router.post("/adapter-config/path")
async def save_adapter_config_path(data: PathBody, _auth: bool = Depends(require_auth)):
    """保存适配器配置文件路径偏好"""
    try:
        path = data.get("path")
        if not path:
            raise HTTPException(status_code=400, detail="路径不能为空")

        # 保存到 data/webui.json
        webui_data_path = os.path.join("data", "webui.json")
        import json

        # 读取现有数据
        if os.path.exists(webui_data_path):
            with open(webui_data_path, "r", encoding="utf-8") as f:
                webui_data = json.load(f)
        else:
            webui_data = {}

        # 将路径规范化为绝对路径
        abs_path = _normalize_adapter_path(path)

        # 尝试转换为相对路径保存（如果文件在项目目录内）
        save_path = _to_relative_path(abs_path)

        # 更新路径
        webui_data["adapter_config_path"] = save_path

        # 保存
        os.makedirs("data", exist_ok=True)
        with open(webui_data_path, "w", encoding="utf-8") as f:
            json.dump(webui_data, f, ensure_ascii=False, indent=2)

        logger.info(f"适配器配置路径已保存: {save_path}（绝对路径: {abs_path}）")
        return {"success": True, "message": "路径已保存"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"保存适配器配置路径失败: {e}")
        raise HTTPException(status_code=500, detail=f"保存路径失败: {str(e)}") from e


@router.get("/adapter-config")
async def get_adapter_config(path: str, _auth: bool = Depends(require_auth)):
    """从指定路径读取适配器配置文件"""
    try:
        if not path:
            raise HTTPException(status_code=400, detail="路径参数不能为空")

        # 将路径规范化为绝对路径
        abs_path = _normalize_adapter_path(path)

        # 检查文件是否存在
        if not os.path.exists(abs_path):
            raise HTTPException(status_code=404, detail=f"配置文件不存在: {path}")

        # 检查文件扩展名
        if not abs_path.endswith(".toml"):
            raise HTTPException(status_code=400, detail="只支持 .toml 格式的配置文件")

        # 读取文件内容
        with open(abs_path, "r", encoding="utf-8") as f:
            content = f.read()

        logger.info(f"已读取适配器配置: {path} (绝对路径: {abs_path})")
        return {"success": True, "content": content}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"读取适配器配置失败: {e}")
        raise HTTPException(status_code=500, detail=f"读取配置失败: {str(e)}") from e


@router.post("/adapter-config")
async def save_adapter_config(data: PathBody, _auth: bool = Depends(require_auth)):
    """保存适配器配置到指定路径"""
    try:
        path = data.get("path")
        content = data.get("content")

        if not path:
            raise HTTPException(status_code=400, detail="路径不能为空")
        if content is None:
            raise HTTPException(status_code=400, detail="配置内容不能为空")

        # 将路径规范化为绝对路径
        abs_path = _normalize_adapter_path(path)

        # 检查文件扩展名
        if not abs_path.endswith(".toml"):
            raise HTTPException(status_code=400, detail="只支持 .toml 格式的配置文件")

        # 验证 TOML 格式
        try:
            tomlkit.loads(content)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"TOML 格式错误: {str(e)}") from e

        # 确保目录存在
        dir_path = os.path.dirname(abs_path)
        if dir_path:
            os.makedirs(dir_path, exist_ok=True)

        # 保存文件
        with open(abs_path, "w", encoding="utf-8") as f:
            f.write(content)

        logger.info(f"适配器配置已保存: {path} (绝对路径: {abs_path})")
        return {"success": True, "message": "配置已保存"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"保存适配器配置失败: {e}")
        raise HTTPException(status_code=500, detail=f"保存配置失败: {str(e)}") from e


# ===== 一键重置配置接口 =====

# 需要保留的基础配置节（不会被重置）
PRESERVED_SECTIONS = {"bot", "personality", "maim_message", "inner"}

# 需要重置的配置节（恢复到模板默认值）
RESET_SECTIONS = {
    "expression",
    "chat",
    "memory",
    "dream",
    "tool",
    "emoji",
    "voice",
    "message_receive",
    "lpmm_knowledge",
    "keyword_reaction",
    "response_post_process",
    "chinese_typo",
    "response_splitter",
    "log",
    "debug",
    "telemetry",
    "webui",
    "experimental",
    "relationship",
}


# 重置页面 HTML 模板
RESET_PAGE_HTML = """
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>配置重置 - MaiBot</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            display: flex;
            justify-content: center;
            align-items: center;
            padding: 20px;
        }
        .container {
            background: white;
            border-radius: 16px;
            box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
            max-width: 800px;
            width: 100%;
            overflow: hidden;
        }
        .header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 30px;
            text-align: center;
        }
        .header h1 {
            font-size: 28px;
            margin-bottom: 10px;
        }
        .header p {
            opacity: 0.9;
            font-size: 14px;
        }
        .content {
            padding: 30px;
        }
        .warning-box {
            background: #fff3cd;
            border: 1px solid #ffc107;
            border-radius: 8px;
            padding: 15px 20px;
            margin-bottom: 25px;
            display: flex;
            align-items: flex-start;
            gap: 12px;
        }
        .warning-box svg {
            flex-shrink: 0;
            color: #856404;
        }
        .warning-box span {
            color: #856404;
            font-size: 14px;
            line-height: 1.5;
        }
        .section {
            margin-bottom: 25px;
        }
        .section-title {
            font-size: 16px;
            font-weight: 600;
            color: #333;
            margin-bottom: 12px;
            display: flex;
            align-items: center;
            gap: 8px;
        }
        .section-title .badge {
            font-size: 12px;
            padding: 2px 8px;
            border-radius: 12px;
            font-weight: normal;
        }
        .badge-green {
            background: #d4edda;
            color: #155724;
        }
        .badge-red {
            background: #f8d7da;
            color: #721c24;
        }
        .config-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
            gap: 10px;
        }
        .config-item {
            background: #f8f9fa;
            border-radius: 8px;
            padding: 12px 15px;
            font-size: 13px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        .config-item.preserved {
            background: #d4edda;
        }
        .config-item.reset {
            background: #f8d7da;
        }
        .config-item .name {
            font-weight: 500;
            color: #333;
        }
        .config-item .desc {
            font-size: 11px;
            color: #666;
            margin-top: 2px;
        }
        .status-icon {
            font-size: 16px;
        }
        .actions {
            display: flex;
            gap: 15px;
            margin-top: 30px;
            padding-top: 20px;
            border-top: 1px solid #eee;
        }
        .btn {
            flex: 1;
            padding: 14px 24px;
            border: none;
            border-radius: 8px;
            font-size: 15px;
            font-weight: 500;
            cursor: pointer;
            transition: all 0.2s;
        }
        .btn-primary {
            background: linear-gradient(135deg, #dc3545 0%, #c82333 100%);
            color: white;
        }
        .btn-primary:hover {
            transform: translateY(-2px);
            box-shadow: 0 5px 20px rgba(220, 53, 69, 0.4);
        }
        .btn-primary:disabled {
            background: #ccc;
            cursor: not-allowed;
            transform: none;
            box-shadow: none;
        }
        .btn-secondary {
            background: #f8f9fa;
            color: #333;
            border: 1px solid #ddd;
        }
        .btn-secondary:hover {
            background: #e9ecef;
        }
        .loading {
            display: none;
            text-align: center;
            padding: 20px;
        }
        .loading.active {
            display: block;
        }
        .spinner {
            width: 40px;
            height: 40px;
            border: 4px solid #f3f3f3;
            border-top: 4px solid #667eea;
            border-radius: 50%;
            animation: spin 1s linear infinite;
            margin: 0 auto 15px;
        }
        @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }
        .result {
            display: none;
            padding: 20px;
            border-radius: 8px;
            margin-top: 20px;
        }
        .result.success {
            display: block;
            background: #d4edda;
            color: #155724;
        }
        .result.error {
            display: block;
            background: #f8d7da;
            color: #721c24;
        }
        .confirm-dialog {
            display: none;
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: rgba(0, 0, 0, 0.5);
            justify-content: center;
            align-items: center;
            z-index: 1000;
        }
        .confirm-dialog.active {
            display: flex;
        }
        .confirm-box {
            background: white;
            border-radius: 12px;
            padding: 30px;
            max-width: 400px;
            text-align: center;
        }
        .confirm-box h3 {
            color: #dc3545;
            margin-bottom: 15px;
        }
        .confirm-box p {
            color: #666;
            margin-bottom: 25px;
            line-height: 1.6;
        }
        .confirm-actions {
            display: flex;
            gap: 10px;
        }
        .token-input {
            width: 100%;
            padding: 12px 15px;
            border: 1px solid #ddd;
            border-radius: 8px;
            font-size: 14px;
            margin-bottom: 15px;
        }
        .token-input:focus {
            outline: none;
            border-color: #667eea;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>⚙️ 配置重置</h1>
            <p>重置除基础配置外的所有配置项到默认值</p>
        </div>
        <div class="content">
            <div class="warning-box">
                <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"></path>
                    <line x1="12" y1="9" x2="12" y2="13"></line>
                    <line x1="12" y1="17" x2="12.01" y2="17"></line>
                </svg>
                <span><strong>警告：</strong>此操作将重置大部分配置到默认值。重置前会自动备份当前配置，但仍建议您手动备份重要配置。</span>
            </div>

            <div class="token-input-wrapper">
                <input type="text" class="token-input" id="tokenInput" placeholder="请输入 WebUI Access Token">
            </div>

            <div class="section">
                <div class="section-title">
                    保留的配置 <span class="badge badge-green">不会被重置</span>
                </div>
                <div class="config-grid" id="preservedList">
                    <div class="config-item preserved">
                        <div>
                            <div class="name">bot</div>
                            <div class="desc">账号、昵称、主人配置</div>
                        </div>
                        <span class="status-icon">✓</span>
                    </div>
                    <div class="config-item preserved">
                        <div>
                            <div class="name">personality</div>
                            <div class="desc">人格配置</div>
                        </div>
                        <span class="status-icon">✓</span>
                    </div>
                    <div class="config-item preserved">
                        <div>
                            <div class="name">maim_message</div>
                            <div class="desc">API Server 配置</div>
                        </div>
                        <span class="status-icon">✓</span>
                    </div>
                </div>
            </div>

            <div class="section">
                <div class="section-title">
                    重置的配置 <span class="badge badge-red">恢复到默认值</span>
                </div>
                <div class="config-grid" id="resetList">
                    <div class="config-item reset"><div><div class="name">expression</div><div class="desc">表达学习</div></div><span class="status-icon">↺</span></div>
                    <div class="config-item reset"><div><div class="name">chat</div><div class="desc">聊天设置</div></div><span class="status-icon">↺</span></div>
                    <div class="config-item reset"><div><div class="name">memory</div><div class="desc">记忆配置</div></div><span class="status-icon">↺</span></div>
                    <div class="config-item reset"><div><div class="name">dream</div><div class="desc">做梦配置</div></div><span class="status-icon">↺</span></div>
                    <div class="config-item reset"><div><div class="name">emoji</div><div class="desc">表情包配置</div></div><span class="status-icon">↺</span></div>
                    <div class="config-item reset"><div><div class="name">voice</div><div class="desc">语音识别</div></div><span class="status-icon">↺</span></div>
                    <div class="config-item reset"><div><div class="name">log</div><div class="desc">日志配置</div></div><span class="status-icon">↺</span></div>
                    <div class="config-item reset"><div><div class="name">debug</div><div class="desc">调试配置</div></div><span class="status-icon">↺</span></div>
                    <div class="config-item reset"><div><div class="name">webui</div><div class="desc">WebUI 配置</div></div><span class="status-icon">↺</span></div>
                    <div class="config-item reset"><div><div class="name">keyword_reaction</div><div class="desc">关键词反应</div></div><span class="status-icon">↺</span></div>
                    <div class="config-item reset"><div><div class="name">response_post_process</div><div class="desc">回复后处理</div></div><span class="status-icon">↺</span></div>
                    <div class="config-item reset"><div><div class="name">chinese_typo</div><div class="desc">错别字生成</div></div><span class="status-icon">↺</span></div>
                    <div class="config-item reset"><div><div class="name">response_splitter</div><div class="desc">回复分割器</div></div><span class="status-icon">↺</span></div>
                    <div class="config-item reset"><div><div class="name">lpmm_knowledge</div><div class="desc">知识库配置</div></div><span class="status-icon">↺</span></div>
                    <div class="config-item reset"><div><div class="name">message_receive</div><div class="desc">消息过滤</div></div><span class="status-icon">↺</span></div>
                    <div class="config-item reset"><div><div class="name">relationship</div><div class="desc">关系系统</div></div><span class="status-icon">↺</span></div>
                    <div class="config-item reset"><div><div class="name">experimental</div><div class="desc">实验性功能</div></div><span class="status-icon">↺</span></div>
                    <div class="config-item reset"><div><div class="name">telemetry</div><div class="desc">遥测配置</div></div><span class="status-icon">↺</span></div>
                </div>
            </div>

            <div class="loading" id="loading">
                <div class="spinner"></div>
                <p>正在重置配置...</p>
            </div>

            <div class="result" id="result"></div>

            <div class="actions" id="actions">
                <button class="btn btn-secondary" onclick="window.history.back()">返回</button>
                <button class="btn btn-primary" id="resetBtn" onclick="showConfirm()">重置配置</button>
            </div>
        </div>
    </div>

    <div class="confirm-dialog" id="confirmDialog">
        <div class="confirm-box">
            <h3>⚠️ 确认重置</h3>
            <p>您确定要重置配置吗？此操作将把上述配置项恢复到默认值。配置文件会自动备份到 config/old/ 目录。</p>
            <div class="confirm-actions">
                <button class="btn btn-secondary" onclick="hideConfirm()">取消</button>
                <button class="btn btn-primary" onclick="executeReset()">确认重置</button>
            </div>
        </div>
    </div>

    <script>
        const API_BASE = '/api/webui';

        function getAuthToken() {
            const token = document.getElementById('tokenInput').value.trim();
            if (!token) {
                alert('请输入 WebUI Access Token');
                return null;
            }
            return token;
        }

        function showConfirm() {
            const token = getAuthToken();
            if (!token) return;
            document.getElementById('confirmDialog').classList.add('active');
        }

        function hideConfirm() {
            document.getElementById('confirmDialog').classList.remove('active');
        }

        async function executeReset() {
            const token = getAuthToken();
            if (!token) return;

            hideConfirm();
            
            const loading = document.getElementById('loading');
            const result = document.getElementById('result');
            const actions = document.getElementById('actions');
            const resetBtn = document.getElementById('resetBtn');

            loading.classList.add('active');
            result.className = 'result';
            result.textContent = '';
            resetBtn.disabled = true;

            try {
                const response = await fetch(`${API_BASE}/config/reset/confirm`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'Authorization': `Bearer ${token}`
                    }
                });

                const data = await response.json();

                if (response.ok && data.success) {
                    result.className = 'result success';
                    result.innerHTML = `
                        <strong>✅ 重置成功！</strong><br>
                        备份文件: ${data.backup_path}<br>
                        已重置 ${data.reset_sections.length} 个配置节
                    `;
                    actions.innerHTML = `
                        <button class="btn btn-secondary" onclick="window.location.reload()">刷新页面</button>
                        <button class="btn btn-primary" onclick="window.history.back()">返回</button>
                    `;
                } else {
                    throw new Error(data.detail || '重置失败');
                }
            } catch (error) {
                result.className = 'result error';
                result.innerHTML = `<strong>❌ 重置失败</strong><br>${error.message}`;
                resetBtn.disabled = false;
            } finally {
                loading.classList.remove('active');
            }
        }

        // 尝试从 Cookie 获取 token
        window.onload = function() {
            const cookies = document.cookie.split(';');
            for (const cookie of cookies) {
                const [name, value] = cookie.trim().split('=');
                if (name === 'maibot_session') {
                    document.getElementById('tokenInput').value = value;
                    break;
                }
            }
        };
    </script>
</body>
</html>
"""


@router.get("/reset/page", include_in_schema=False)
async def get_reset_page():
    """
    返回配置重置页面 HTML

    这是一个独立的 HTML 页面，用于配置重置功能
    """
    from fastapi.responses import HTMLResponse

    return HTMLResponse(content=RESET_PAGE_HTML)


@router.get("/reset/preview")
async def get_reset_preview(_auth: bool = Depends(require_auth)):
    """
    获取重置预览信息

    返回哪些配置会被保留，哪些会被重置
    """
    try:
        config_path = os.path.join(CONFIG_DIR, "bot_config.toml")
        template_path = os.path.join(TEMPLATE_DIR, "bot_config_template.toml")

        if not os.path.exists(config_path):
            raise HTTPException(status_code=404, detail="配置文件不存在")

        if not os.path.exists(template_path):
            raise HTTPException(status_code=404, detail="模板文件不存在")

        # 读取当前配置
        with open(config_path, "r", encoding="utf-8") as f:
            current_config = tomlkit.load(f)

        # 读取模板配置
        with open(template_path, "r", encoding="utf-8") as f:
            template_config = tomlkit.load(f)

        # 构建预览信息
        preserved_sections_info = {}
        reset_sections_info = {}

        for section_name in current_config.keys():
            if section_name in PRESERVED_SECTIONS:
                # 保留的配置
                preserved_sections_info[section_name] = {
                    "status": "保留",
                    "description": _get_section_description(section_name),
                }
            elif section_name in RESET_SECTIONS:
                # 需要重置的配置
                current_section = current_config.get(section_name, {})
                template_section = template_config.get(section_name, {})

                # 检查是否有差异
                has_changes = _compare_sections(current_section, template_section)

                reset_sections_info[section_name] = {
                    "status": "重置",
                    "description": _get_section_description(section_name),
                    "has_changes": has_changes,
                }

        return {
            "success": True,
            "preview": {
                "preserved": preserved_sections_info,
                "reset": reset_sections_info,
                "total_preserved": len(preserved_sections_info),
                "total_reset": len(reset_sections_info),
            },
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取重置预览失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取重置预览失败: {str(e)}") from e


@router.post("/reset/confirm")
async def reset_config(_auth: bool = Depends(require_auth)):
    """
    执行一键重置配置

    保留 bot、personality、maim_message、inner 配置节
    其他配置节恢复到模板默认值
    """
    try:
        config_path = os.path.join(CONFIG_DIR, "bot_config.toml")
        template_path = os.path.join(TEMPLATE_DIR, "bot_config_template.toml")
        old_config_dir = os.path.join(CONFIG_DIR, "old")

        if not os.path.exists(config_path):
            raise HTTPException(status_code=404, detail="配置文件不存在")

        if not os.path.exists(template_path):
            raise HTTPException(status_code=404, detail="模板文件不存在")

        # 读取当前配置
        with open(config_path, "r", encoding="utf-8") as f:
            current_config = tomlkit.load(f)

        # 读取模板配置
        with open(template_path, "r", encoding="utf-8") as f:
            template_config = tomlkit.load(f)

        # 创建备份
        os.makedirs(old_config_dir, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = os.path.join(old_config_dir, f"bot_config_reset_backup_{timestamp}.toml")
        shutil.copy2(config_path, backup_path)
        logger.info(f"重置前已备份配置文件到: {backup_path}")

        # 构建新配置：保留基础配置，其他使用模板默认值
        new_config = tomlkit.document()

        # 首先复制模板的完整结构（保留注释）
        for key, value in template_config.items():
            if key in PRESERVED_SECTIONS:
                # 保留用户的基础配置
                new_config[key] = current_config.get(key, value)
            else:
                # 使用模板默认值
                new_config[key] = value

        # 验证新配置
        try:
            Config.from_dict(new_config)
        except Exception as e:
            # 验证失败，恢复备份
            shutil.copy2(backup_path, config_path)
            logger.error(f"重置后配置验证失败，已恢复备份: {e}")
            raise HTTPException(status_code=400, detail=f"重置后配置验证失败: {str(e)}") from e

        # 保存新配置
        with open(config_path, "w", encoding="utf-8") as f:
            f.write(format_toml_string(new_config))

        # 重新加载内存中的配置
        config_module.global_config = load_config(config_path)

        logger.info("配置重置完成")
        return {
            "success": True,
            "message": "配置已重置",
            "backup_path": backup_path,
            "reset_sections": list(RESET_SECTIONS),
            "preserved_sections": list(PRESERVED_SECTIONS),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"重置配置失败: {e}")
        raise HTTPException(status_code=500, detail=f"重置配置失败: {str(e)}") from e


def _get_section_description(section_name: str) -> str:
    """获取配置节的描述"""
    descriptions = {
        "inner": "版本信息",
        "bot": "机器人基本配置（账号、昵称、主人配置）",
        "personality": "人格配置（性格、说话风格）",
        "maim_message": "API Server 配置",
        "expression": "表达学习配置",
        "chat": "聊天设置",
        "memory": "记忆配置",
        "dream": "做梦配置",
        "tool": "工具配置",
        "emoji": "表情包配置",
        "voice": "语音识别配置",
        "message_receive": "消息过滤配置",
        "lpmm_knowledge": "知识库配置",
        "keyword_reaction": "关键词反应",
        "response_post_process": "回复后处理",
        "chinese_typo": "错别字生成器",
        "response_splitter": "回复分割器",
        "log": "日志配置",
        "debug": "调试配置",
        "telemetry": "遥测配置",
        "webui": "WebUI 配置",
        "experimental": "实验性功能",
        "relationship": "关系系统",
    }
    return descriptions.get(section_name, "未知配置节")


def _compare_sections(current: Any, template: Any) -> bool:
    """
    比较两个配置节是否有差异

    Returns:
        True 表示有差异，False 表示相同
    """
    if isinstance(current, dict) and isinstance(template, dict):
        # 比较字典
        all_keys = set(current.keys()) | set(template.keys())
        for key in all_keys:
            if key not in current or key not in template:
                return True
            if _compare_sections(current.get(key), template.get(key)):
                return True
        return False
    else:
        # 比较值
        return current != template
