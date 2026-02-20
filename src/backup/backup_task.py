"""
每日自动备份定时任务

每天凌晨执行一次数据备份
"""

import asyncio
from datetime import datetime, time

from src.common.logger import get_logger
from src.manager.async_task_manager import AsyncTask
from src.backup.backup_manager import backup_manager

logger = get_logger("daily_backup_task")


class DailyBackupTask(AsyncTask):
    """每日自动备份定时任务"""

    def __init__(self, backup_hour: int = 3, backup_minute: int = 0):
        """
        初始化每日备份任务

        Args:
            backup_hour: 备份时间（小时），默认凌晨3点
            backup_minute: 备份时间（分钟），默认0分
        """
        self.backup_hour = backup_hour
        self.backup_minute = backup_minute
        
        # 计算到下次备份的时间间隔
        wait_seconds = self._calculate_wait_seconds()
        
        super().__init__(
            task_name="Daily Backup Task",
            wait_before_start=wait_seconds,
            run_interval=24 * 60 * 60,  # 每24小时执行一次
        )

    def _calculate_wait_seconds(self) -> int:
        """计算到下次备份时间的秒数"""
        now = datetime.now()
        target_time = time(self.backup_hour, self.backup_minute)
        target_datetime = datetime.combine(now.date(), target_time)
        
        # 如果今天的备份时间已过，则计算到明天的时间
        if now.time() > target_time:
            from datetime import timedelta
            target_datetime = datetime.combine(
                now.date() + timedelta(days=1), 
                target_time
            )
        
        wait_seconds = int((target_datetime - now).total_seconds())
        logger.info(f"下次备份将在 {wait_seconds} 秒后执行（{target_datetime}）")
        
        return wait_seconds

    async def run(self):
        """执行备份任务"""
        try:
            logger.info("开始执行每日自动备份...")
            
            # 执行备份
            backup_info = backup_manager.create_backup(
                description="每日自动备份",
                is_automatic=True,
                include_emoji=True,
                include_hippo=True,
            )
            
            if backup_info:
                logger.info(
                    f"每日自动备份完成: {backup_info.id}, "
                    f"大小: {backup_info.size_human}"
                )
            else:
                logger.error("每日自动备份失败")

        except Exception as e:
            logger.error(f"执行每日自动备份任务时出错: {e}", exc_info=True)

    def get_next_backup_time(self) -> str:
        """获取下次备份时间"""
        from datetime import timedelta
        now = datetime.now()
        target_time = time(self.backup_hour, self.backup_minute)
        target_datetime = datetime.combine(now.date(), target_time)
        
        if now.time() > target_time:
            target_datetime = datetime.combine(
                now.date() + timedelta(days=1), 
                target_time
            )
        
        return target_datetime.strftime("%Y-%m-%d %H:%M:%S")
