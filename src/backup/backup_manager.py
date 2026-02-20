"""
备份管理器

提供数据备份、恢复和管理功能
"""

import os
import json
import shutil
import sqlite3
import zipfile
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, asdict

from src.common.logger import get_logger
from src.config.config import PROJECT_ROOT, CONFIG_DIR

logger = get_logger("backup_manager")

# 备份目录
BACKUP_DIR = os.path.join(PROJECT_ROOT, "backups")

# 最大备份数量（30天）
MAX_BACKUPS = 30

# 需要备份的文件和目录
BACKUP_TARGETS = {
    # 核心数据
    "database": ["data/MaiBot.db"],
    # 配置文件
    "config": ["config/bot_config.toml", "config/model_config.toml"],
    # 本地存储
    "local_store": ["data/local_store.json", "data/webui.json"],
    # 记忆系统
    "hippo_memorizer": ["data/hippo_memorizer"],
    # 表情包
    "emoji": ["data/emoji_registed", "data/emoji_thumbnails"],
}


@dataclass
class BackupInfo:
    """备份信息数据类"""
    id: str
    """备份ID（格式：YYYYMMDD_HHMMSS）"""
    timestamp: str
    """备份时间（ISO格式）"""
    size_bytes: int
    """备份文件大小（字节）"""
    size_human: str
    """备份文件大小（人类可读）"""
    description: str
    """备份描述"""
    is_automatic: bool
    """是否为自动备份"""
    contains: Dict[str, bool]
    """包含的数据类型"""


class BackupManager:
    """备份管理器"""

    def __init__(self, backup_dir: str = BACKUP_DIR, max_backups: int = MAX_BACKUPS):
        self.backup_dir = backup_dir
        self.max_backups = max_backups
        self._ensure_backup_dir()

    def _ensure_backup_dir(self):
        """确保备份目录存在"""
        os.makedirs(self.backup_dir, exist_ok=True)
        logger.debug(f"备份目录: {self.backup_dir}")

    def _get_backup_path(self, backup_id: str) -> str:
        """获取备份文件路径"""
        return os.path.join(self.backup_dir, f"backup_{backup_id}.zip")

    def _get_meta_path(self, backup_id: str) -> str:
        """获取备份元数据文件路径"""
        return os.path.join(self.backup_dir, f"backup_{backup_id}.json")

    def _format_size(self, size_bytes: int) -> str:
        """格式化文件大小"""
        for unit in ["B", "KB", "MB", "GB"]:
            if size_bytes < 1024:
                return f"{size_bytes:.2f} {unit}"
            size_bytes /= 1024
        return f"{size_bytes:.2f} TB"

    def _collect_backup_files(self) -> Dict[str, List[str]]:
        """收集需要备份的文件"""
        collected = {}
        
        for category, targets in BACKUP_TARGETS.items():
            collected[category] = []
            for target in targets:
                full_path = os.path.join(PROJECT_ROOT, target)
                if os.path.exists(full_path):
                    collected[category].append(target)
                else:
                    logger.debug(f"备份目标不存在: {target}")
        
        return collected

    def create_backup(
        self,
        description: str = "每日自动备份",
        is_automatic: bool = True,
        include_emoji: bool = True,
        include_hippo: bool = True,
    ) -> Optional[BackupInfo]:
        """
        创建备份

        Args:
            description: 备份描述
            is_automatic: 是否为自动备份
            include_emoji: 是否包含表情包
            include_hippo: 是否包含记忆系统数据

        Returns:
            备份信息，失败返回 None
        """
        try:
            # 生成备份ID
            backup_id = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = self._get_backup_path(backup_id)
            meta_path = self._get_meta_path(backup_id)

            logger.info(f"开始创建备份: {backup_id}")

            # 收集文件
            collected = self._collect_backup_files()
            
            # 创建 ZIP 备份
            contains = {}
            total_size = 0
            
            with zipfile.ZipFile(backup_path, 'w', zipfile.ZIP_DEFLATED) as zf:
                # 备份数据库
                if collected.get("database"):
                    for db_file in collected["database"]:
                        full_path = os.path.join(PROJECT_ROOT, db_file)
                        if os.path.exists(full_path):
                            # 先备份数据库到临时文件（确保数据一致性）
                            temp_db = self._backup_database(full_path)
                            if temp_db:
                                zf.write(temp_db, db_file)
                                os.remove(temp_db)
                                total_size += os.path.getsize(full_path)
                    contains["database"] = True
                else:
                    contains["database"] = False

                # 备份配置文件
                if collected.get("config"):
                    for config_file in collected["config"]:
                        full_path = os.path.join(PROJECT_ROOT, config_file)
                        if os.path.exists(full_path):
                            zf.write(full_path, config_file)
                            total_size += os.path.getsize(full_path)
                    contains["config"] = True
                else:
                    contains["config"] = False

                # 备份本地存储
                if collected.get("local_store"):
                    for store_file in collected["local_store"]:
                        full_path = os.path.join(PROJECT_ROOT, store_file)
                        if os.path.exists(full_path):
                            zf.write(full_path, store_file)
                            total_size += os.path.getsize(full_path)
                    contains["local_store"] = True
                else:
                    contains["local_store"] = False

                # 备份记忆系统
                if include_hippo and collected.get("hippo_memorizer"):
                    for hippo_dir in collected["hippo_memorizer"]:
                        full_path = os.path.join(PROJECT_ROOT, hippo_dir)
                        if os.path.isdir(full_path):
                            for root, dirs, files in os.walk(full_path):
                                for file in files:
                                    file_path = os.path.join(root, file)
                                    arcname = os.path.relpath(file_path, PROJECT_ROOT)
                                    zf.write(file_path, arcname)
                                    total_size += os.path.getsize(file_path)
                    contains["hippo_memorizer"] = True
                else:
                    contains["hippo_memorizer"] = False

                # 备份表情包
                if include_emoji and collected.get("emoji"):
                    for emoji_dir in collected["emoji"]:
                        full_path = os.path.join(PROJECT_ROOT, emoji_dir)
                        if os.path.isdir(full_path):
                            for root, dirs, files in os.walk(full_path):
                                for file in files:
                                    file_path = os.path.join(root, file)
                                    arcname = os.path.relpath(file_path, PROJECT_ROOT)
                                    zf.write(file_path, arcname)
                                    total_size += os.path.getsize(file_path)
                    contains["emoji"] = True
                else:
                    contains["emoji"] = False

            # 获取备份文件大小
            backup_size = os.path.getsize(backup_path)

            # 创建备份信息
            backup_info = BackupInfo(
                id=backup_id,
                timestamp=datetime.now().isoformat(),
                size_bytes=backup_size,
                size_human=self._format_size(backup_size),
                description=description,
                is_automatic=is_automatic,
                contains=contains,
            )

            # 保存元数据
            with open(meta_path, 'w', encoding='utf-8') as f:
                json.dump(asdict(backup_info), f, ensure_ascii=False, indent=2)

            logger.info(f"备份创建成功: {backup_id}, 大小: {backup_info.size_human}")

            # 清理旧备份
            self._cleanup_old_backups()

            return backup_info

        except Exception as e:
            logger.error(f"创建备份失败: {e}", exc_info=True)
            return None

    def _backup_database(self, db_path: str) -> Optional[str]:
        """
        备份数据库（确保数据一致性）

        Args:
            db_path: 数据库文件路径

        Returns:
            临时备份文件路径，失败返回 None
        """
        try:
            # 创建临时文件
            temp_path = db_path + ".backup_temp"
            
            # 使用 SQLite 的备份 API 确保数据一致性
            source_conn = sqlite3.connect(db_path)
            dest_conn = sqlite3.connect(temp_path)
            
            source_conn.backup(dest_conn)
            
            dest_conn.close()
            source_conn.close()
            
            return temp_path

        except Exception as e:
            logger.error(f"备份数据库失败: {e}")
            return None

    def _cleanup_old_backups(self):
        """清理旧备份，保留最新的 max_backups 个"""
        try:
            # 获取所有备份
            backups = self.list_backups()
            
            if len(backups) > self.max_backups:
                # 按时间排序，删除最旧的
                backups.sort(key=lambda x: x.timestamp, reverse=True)
                
                for old_backup in backups[self.max_backups:]:
                    self.delete_backup(old_backup.id)
                    logger.info(f"已删除旧备份: {old_backup.id}")

        except Exception as e:
            logger.error(f"清理旧备份失败: {e}")

    def list_backups(self) -> List[BackupInfo]:
        """
        列出所有备份

        Returns:
            备份信息列表
        """
        backups = []
        
        try:
            for filename in os.listdir(self.backup_dir):
                if filename.startswith("backup_") and filename.endswith(".json"):
                    meta_path = os.path.join(self.backup_dir, filename)
                    try:
                        with open(meta_path, 'r', encoding='utf-8') as f:
                            data = json.load(f)
                            backup_info = BackupInfo(**data)
                            backups.append(backup_info)
                    except Exception as e:
                        logger.warning(f"读取备份元数据失败: {filename}, {e}")

            # 按时间倒序排列
            backups.sort(key=lambda x: x.timestamp, reverse=True)

        except Exception as e:
            logger.error(f"列出备份失败: {e}")

        return backups

    def get_backup_info(self, backup_id: str) -> Optional[BackupInfo]:
        """
        获取指定备份的信息

        Args:
            backup_id: 备份ID

        Returns:
            备份信息，不存在返回 None
        """
        meta_path = self._get_meta_path(backup_id)
        
        if os.path.exists(meta_path):
            try:
                with open(meta_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    return BackupInfo(**data)
            except Exception as e:
                logger.error(f"读取备份元数据失败: {backup_id}, {e}")
        
        return None

    def restore_backup(self, backup_id: str) -> Dict[str, Any]:
        """
        恢复备份

        Args:
            backup_id: 备份ID

        Returns:
            恢复结果
        """
        result = {
            "success": False,
            "restored_files": [],
            "errors": [],
            "backup_info": None,
        }

        try:
            backup_path = self._get_backup_path(backup_id)
            backup_info = self.get_backup_info(backup_id)

            if not os.path.exists(backup_path):
                result["errors"].append(f"备份文件不存在: {backup_id}")
                return result

            if not backup_info:
                result["errors"].append(f"备份元数据不存在: {backup_id}")
                return result

            result["backup_info"] = asdict(backup_info)

            logger.info(f"开始恢复备份: {backup_id}")

            # 创建当前数据的备份（以防万一）
            pre_restore_backup = self.create_backup(
                description="恢复前自动备份",
                is_automatic=True,
                include_emoji=True,
                include_hippo=True,
            )
            if pre_restore_backup:
                logger.info(f"已创建恢复前备份: {pre_restore_backup.id}")

            # 解压备份文件
            with zipfile.ZipFile(backup_path, 'r') as zf:
                for member in zf.namelist():
                    try:
                        # 提取文件
                        target_path = os.path.join(PROJECT_ROOT, member)
                        
                        # 确保目标目录存在
                        os.makedirs(os.path.dirname(target_path), exist_ok=True)
                        
                        # 提取文件
                        with zf.open(member) as source, open(target_path, 'wb') as target:
                            target.write(source.read())
                        
                        result["restored_files"].append(member)
                        logger.debug(f"已恢复: {member}")

                    except Exception as e:
                        error_msg = f"恢复文件失败: {member}, {e}"
                        result["errors"].append(error_msg)
                        logger.error(error_msg)

            result["success"] = len(result["restored_files"]) > 0
            logger.info(f"备份恢复完成: {backup_id}, 恢复了 {len(result['restored_files'])} 个文件")

        except Exception as e:
            error_msg = f"恢复备份失败: {e}"
            result["errors"].append(error_msg)
            logger.error(error_msg, exc_info=True)

        return result

    def delete_backup(self, backup_id: str) -> bool:
        """
        删除备份

        Args:
            backup_id: 备份ID

        Returns:
            是否成功
        """
        try:
            backup_path = self._get_backup_path(backup_id)
            meta_path = self._get_meta_path(backup_id)

            deleted = False

            if os.path.exists(backup_path):
                os.remove(backup_path)
                deleted = True
                logger.debug(f"已删除备份文件: {backup_path}")

            if os.path.exists(meta_path):
                os.remove(meta_path)
                deleted = True
                logger.debug(f"已删除备份元数据: {meta_path}")

            if deleted:
                logger.info(f"已删除备份: {backup_id}")

            return deleted

        except Exception as e:
            logger.error(f"删除备份失败: {backup_id}, {e}")
            return False

    def get_backup_stats(self) -> Dict[str, Any]:
        """
        获取备份统计信息

        Returns:
            统计信息
        """
        backups = self.list_backups()
        
        total_size = sum(b.size_bytes for b in backups)
        
        return {
            "total_backups": len(backups),
            "total_size_bytes": total_size,
            "total_size_human": self._format_size(total_size),
            "max_backups": self.max_backups,
            "backup_dir": self.backup_dir,
            "oldest_backup": backups[-1].timestamp if backups else None,
            "newest_backup": backups[0].timestamp if backups else None,
            "automatic_count": sum(1 for b in backups if b.is_automatic),
            "manual_count": sum(1 for b in backups if not b.is_automatic),
        }


# 全局备份管理器实例
backup_manager = BackupManager()
