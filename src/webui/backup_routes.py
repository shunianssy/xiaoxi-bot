"""
备份管理 API 路由

提供备份的创建、列表、恢复和删除功能
"""

import os
from datetime import datetime
from fastapi import APIRouter, HTTPException, Depends, Body
from typing import Any, Annotated, Optional

from src.common.logger import get_logger
from src.webui.auth import verify_auth_token_from_cookie_or_header
from src.backup.backup_manager import backup_manager, BackupInfo

logger = get_logger("backup_routes")

# 类型别名
CreateBackupBody = Annotated[dict[str, Any], Body()]

router = APIRouter(prefix="/backup", tags=["backup"])


def require_auth(maibot_session: Optional[str] = None, authorization: Optional[str] = None) -> bool:
    """认证依赖：验证用户是否已登录"""
    return verify_auth_token_from_cookie_or_header(maibot_session, authorization)


@router.get("/stats")
async def get_backup_stats(_auth: bool = Depends(require_auth)):
    """
    获取备份统计信息
    """
    try:
        stats = backup_manager.get_backup_stats()
        return {"success": True, "stats": stats}
    except Exception as e:
        logger.error(f"获取备份统计信息失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取备份统计信息失败: {str(e)}") from e


@router.get("/list")
async def list_backups(_auth: bool = Depends(require_auth)):
    """
    获取备份列表
    """
    try:
        backups = backup_manager.list_backups()
        return {
            "success": True,
            "backups": [vars(b) for b in backups],
            "total": len(backups),
        }
    except Exception as e:
        logger.error(f"获取备份列表失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取备份列表失败: {str(e)}") from e


@router.get("/{backup_id}")
async def get_backup_info(backup_id: str, _auth: bool = Depends(require_auth)):
    """
    获取指定备份的详细信息
    """
    try:
        backup_info = backup_manager.get_backup_info(backup_id)
        if not backup_info:
            raise HTTPException(status_code=404, detail=f"备份不存在: {backup_id}")
        
        return {"success": True, "backup": vars(backup_info)}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取备份信息失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取备份信息失败: {str(e)}") from e


@router.post("/create")
async def create_backup(body: CreateBackupBody, _auth: bool = Depends(require_auth)):
    """
    创建手动备份

    请求体:
    - description: 备份描述
    - include_emoji: 是否包含表情包（默认 true）
    - include_hippo: 是否包含记忆系统数据（默认 true）
    """
    try:
        description = body.get("description", "手动备份")
        include_emoji = body.get("include_emoji", True)
        include_hippo = body.get("include_hippo", True)

        backup_info = backup_manager.create_backup(
            description=description,
            is_automatic=False,
            include_emoji=include_emoji,
            include_hippo=include_hippo,
        )

        if not backup_info:
            raise HTTPException(status_code=500, detail="创建备份失败")

        logger.info(f"手动备份创建成功: {backup_info.id}")
        return {"success": True, "backup": vars(backup_info)}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"创建备份失败: {e}")
        raise HTTPException(status_code=500, detail=f"创建备份失败: {str(e)}") from e


@router.post("/{backup_id}/restore")
async def restore_backup(backup_id: str, _auth: bool = Depends(require_auth)):
    """
    恢复指定备份

    注意：恢复操作会覆盖当前数据，恢复前会自动创建当前数据的备份
    """
    try:
        # 检查备份是否存在
        backup_info = backup_manager.get_backup_info(backup_id)
        if not backup_info:
            raise HTTPException(status_code=404, detail=f"备份不存在: {backup_id}")

        # 执行恢复
        result = backup_manager.restore_backup(backup_id)

        if result["success"]:
            logger.info(f"备份恢复成功: {backup_id}")
            return {
                "success": True,
                "message": "备份恢复成功",
                "restored_files": result["restored_files"],
                "backup_info": result["backup_info"],
            }
        else:
            raise HTTPException(
                status_code=500,
                detail=f"备份恢复失败: {', '.join(result['errors'])}"
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"恢复备份失败: {e}")
        raise HTTPException(status_code=500, detail=f"恢复备份失败: {str(e)}") from e


@router.delete("/{backup_id}")
async def delete_backup(backup_id: str, _auth: bool = Depends(require_auth)):
    """
    删除指定备份
    """
    try:
        # 检查备份是否存在
        backup_info = backup_manager.get_backup_info(backup_id)
        if not backup_info:
            raise HTTPException(status_code=404, detail=f"备份不存在: {backup_id}")

        # 删除备份
        success = backup_manager.delete_backup(backup_id)

        if success:
            logger.info(f"备份删除成功: {backup_id}")
            return {"success": True, "message": f"备份 {backup_id} 已删除"}
        else:
            raise HTTPException(status_code=500, detail="删除备份失败")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"删除备份失败: {e}")
        raise HTTPException(status_code=500, detail=f"删除备份失败: {str(e)}") from e


# ===== 备份管理页面 HTML =====

BACKUP_PAGE_HTML = """
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>备份管理 - MaiBot</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
            min-height: 100vh;
            color: #fff;
        }
        .container {
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
        }
        .header {
            text-align: center;
            padding: 30px 0;
        }
        .header h1 {
            font-size: 32px;
            margin-bottom: 10px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }
        .header p {
            color: #888;
        }
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }
        .stat-card {
            background: rgba(255, 255, 255, 0.05);
            border-radius: 12px;
            padding: 20px;
            text-align: center;
        }
        .stat-card .value {
            font-size: 28px;
            font-weight: bold;
            color: #667eea;
        }
        .stat-card .label {
            font-size: 14px;
            color: #888;
            margin-top: 5px;
        }
        .actions-bar {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 20px;
            flex-wrap: wrap;
            gap: 15px;
        }
        .token-input {
            padding: 12px 15px;
            border: 1px solid #333;
            border-radius: 8px;
            background: rgba(255, 255, 255, 0.05);
            color: #fff;
            font-size: 14px;
            width: 300px;
        }
        .token-input:focus {
            outline: none;
            border-color: #667eea;
        }
        .btn {
            padding: 12px 24px;
            border: none;
            border-radius: 8px;
            font-size: 14px;
            font-weight: 500;
            cursor: pointer;
            transition: all 0.2s;
        }
        .btn-primary {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
        }
        .btn-primary:hover {
            transform: translateY(-2px);
            box-shadow: 0 5px 20px rgba(102, 126, 234, 0.4);
        }
        .btn-danger {
            background: linear-gradient(135deg, #dc3545 0%, #c82333 100%);
            color: white;
        }
        .btn-danger:hover {
            transform: translateY(-2px);
            box-shadow: 0 5px 20px rgba(220, 53, 69, 0.4);
        }
        .btn-secondary {
            background: rgba(255, 255, 255, 0.1);
            color: #fff;
            border: 1px solid #333;
        }
        .btn-secondary:hover {
            background: rgba(255, 255, 255, 0.2);
        }
        .btn-small {
            padding: 8px 16px;
            font-size: 12px;
        }
        .backups-list {
            background: rgba(255, 255, 255, 0.05);
            border-radius: 12px;
            overflow: hidden;
        }
        .backup-item {
            display: flex;
            align-items: center;
            padding: 20px;
            border-bottom: 1px solid rgba(255, 255, 255, 0.05);
            transition: background 0.2s;
        }
        .backup-item:hover {
            background: rgba(255, 255, 255, 0.05);
        }
        .backup-item:last-child {
            border-bottom: none;
        }
        .backup-icon {
            width: 50px;
            height: 50px;
            border-radius: 10px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 24px;
            margin-right: 15px;
        }
        .backup-icon.auto {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        }
        .backup-icon.manual {
            background: linear-gradient(135deg, #28a745 0%, #20c997 100%);
        }
        .backup-info {
            flex: 1;
        }
        .backup-info .id {
            font-size: 16px;
            font-weight: 500;
            margin-bottom: 5px;
        }
        .backup-info .meta {
            font-size: 13px;
            color: #888;
        }
        .backup-info .meta span {
            margin-right: 15px;
        }
        .backup-tags {
            display: flex;
            gap: 8px;
            margin-top: 8px;
        }
        .tag {
            font-size: 11px;
            padding: 3px 8px;
            border-radius: 4px;
            background: rgba(255, 255, 255, 0.1);
        }
        .tag.active {
            background: rgba(102, 126, 234, 0.3);
            color: #667eea;
        }
        .backup-actions {
            display: flex;
            gap: 10px;
        }
        .loading {
            text-align: center;
            padding: 40px;
            color: #888;
        }
        .loading .spinner {
            width: 40px;
            height: 40px;
            border: 3px solid rgba(255, 255, 255, 0.1);
            border-top-color: #667eea;
            border-radius: 50%;
            animation: spin 1s linear infinite;
            margin: 0 auto 15px;
        }
        @keyframes spin {
            to { transform: rotate(360deg); }
        }
        .empty-state {
            text-align: center;
            padding: 60px 20px;
            color: #888;
        }
        .empty-state svg {
            width: 80px;
            height: 80px;
            margin-bottom: 20px;
            opacity: 0.5;
        }
        .modal {
            display: none;
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: rgba(0, 0, 0, 0.7);
            justify-content: center;
            align-items: center;
            z-index: 1000;
        }
        .modal.active {
            display: flex;
        }
        .modal-content {
            background: #1a1a2e;
            border-radius: 16px;
            padding: 30px;
            max-width: 450px;
            width: 90%;
        }
        .modal-content h3 {
            margin-bottom: 15px;
        }
        .modal-content p {
            color: #888;
            margin-bottom: 20px;
            line-height: 1.6;
        }
        .modal-actions {
            display: flex;
            gap: 10px;
            justify-content: flex-end;
        }
        .toast {
            position: fixed;
            bottom: 20px;
            right: 20px;
            padding: 15px 25px;
            border-radius: 8px;
            color: white;
            font-size: 14px;
            z-index: 2000;
            animation: slideIn 0.3s ease;
        }
        .toast.success {
            background: linear-gradient(135deg, #28a745 0%, #20c997 100%);
        }
        .toast.error {
            background: linear-gradient(135deg, #dc3545 0%, #c82333 100%);
        }
        @keyframes slideIn {
            from {
                transform: translateX(100%);
                opacity: 0;
            }
            to {
                transform: translateX(0);
                opacity: 1;
            }
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>💾 备份管理</h1>
            <p>管理您的数据备份，支持创建、恢复和删除备份</p>
        </div>

        <div class="stats-grid" id="statsGrid">
            <div class="stat-card">
                <div class="value" id="totalBackups">-</div>
                <div class="label">总备份数</div>
            </div>
            <div class="stat-card">
                <div class="value" id="totalSize">-</div>
                <div class="label">总大小</div>
            </div>
            <div class="stat-card">
                <div class="value" id="autoBackups">-</div>
                <div class="label">自动备份</div>
            </div>
            <div class="stat-card">
                <div class="value" id="manualBackups">-</div>
                <div class="label">手动备份</div>
            </div>
        </div>

        <div class="actions-bar">
            <input type="text" class="token-input" id="tokenInput" placeholder="请输入 WebUI Access Token">
            <div>
                <button class="btn btn-primary" onclick="createBackup()">➕ 创建备份</button>
                <button class="btn btn-secondary" onclick="loadData()">🔄 刷新</button>
            </div>
        </div>

        <div class="backups-list" id="backupsList">
            <div class="loading">
                <div class="spinner"></div>
                <p>加载中...</p>
            </div>
        </div>
    </div>

    <!-- 恢复确认对话框 -->
    <div class="modal" id="restoreModal">
        <div class="modal-content">
            <h3>⚠️ 确认恢复</h3>
            <p>您确定要恢复此备份吗？<br><strong>当前数据将被覆盖！</strong><br>恢复前会自动创建当前数据的备份。</p>
            <div class="modal-actions">
                <button class="btn btn-secondary" onclick="closeModal('restoreModal')">取消</button>
                <button class="btn btn-danger" id="confirmRestoreBtn">确认恢复</button>
            </div>
        </div>
    </div>

    <!-- 删除确认对话框 -->
    <div class="modal" id="deleteModal">
        <div class="modal-content">
            <h3>🗑️ 确认删除</h3>
            <p>您确定要删除此备份吗？此操作不可撤销。</p>
            <div class="modal-actions">
                <button class="btn btn-secondary" onclick="closeModal('deleteModal')">取消</button>
                <button class="btn btn-danger" id="confirmDeleteBtn">确认删除</button>
            </div>
        </div>
    </div>

    <script>
        const API_BASE = '/api/webui';
        let currentBackupId = null;

        function getAuthToken() {
            const token = document.getElementById('tokenInput').value.trim();
            if (!token) {
                showToast('请输入 WebUI Access Token', 'error');
                return null;
            }
            return token;
        }

        function showToast(message, type = 'success') {
            const toast = document.createElement('div');
            toast.className = `toast ${type}`;
            toast.textContent = message;
            document.body.appendChild(toast);
            setTimeout(() => toast.remove(), 3000);
        }

        async function loadData() {
            const token = getAuthToken();
            if (!token) return;

            try {
                // 加载统计信息
                const statsRes = await fetch(`${API_BASE}/backup/stats`, {
                    headers: { 'Authorization': `Bearer ${token}` }
                });
                const statsData = await statsRes.json();
                
                if (statsData.success) {
                    const stats = statsData.stats;
                    document.getElementById('totalBackups').textContent = stats.total_backups;
                    document.getElementById('totalSize').textContent = stats.total_size_human;
                    document.getElementById('autoBackups').textContent = stats.automatic_count;
                    document.getElementById('manualBackups').textContent = stats.manual_count;
                }

                // 加载备份列表
                const listRes = await fetch(`${API_BASE}/backup/list`, {
                    headers: { 'Authorization': `Bearer ${token}` }
                });
                const listData = await listRes.json();
                
                if (listData.success) {
                    renderBackups(listData.backups);
                }

            } catch (error) {
                showToast('加载数据失败: ' + error.message, 'error');
            }
        }

        function renderBackups(backups) {
            const container = document.getElementById('backupsList');
            
            if (backups.length === 0) {
                container.innerHTML = `
                    <div class="empty-state">
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1">
                            <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
                            <polyline points="17 8 12 3 7 8"/>
                            <line x1="12" y1="3" x2="12" y2="15"/>
                        </svg>
                        <p>暂无备份<br>点击上方按钮创建第一个备份</p>
                    </div>
                `;
                return;
            }

            container.innerHTML = backups.map(backup => `
                <div class="backup-item">
                    <div class="backup-icon ${backup.is_automatic ? 'auto' : 'manual'}">
                        ${backup.is_automatic ? '🤖' : '👤'}
                    </div>
                    <div class="backup-info">
                        <div class="id">${backup.id}</div>
                        <div class="meta">
                            <span>📅 ${formatDate(backup.timestamp)}</span>
                            <span>📦 ${backup.size_human}</span>
                            <span>${backup.is_automatic ? '自动备份' : '手动备份'}</span>
                        </div>
                        <div class="backup-tags">
                            ${backup.contains.database ? '<span class="tag active">数据库</span>' : ''}
                            ${backup.contains.config ? '<span class="tag active">配置</span>' : ''}
                            ${backup.contains.emoji ? '<span class="tag active">表情包</span>' : ''}
                            ${backup.contains.hippo_memorizer ? '<span class="tag active">记忆</span>' : ''}
                        </div>
                    </div>
                    <div class="backup-actions">
                        <button class="btn btn-primary btn-small" onclick="showRestoreModal('${backup.id}')">恢复</button>
                        <button class="btn btn-danger btn-small" onclick="showDeleteModal('${backup.id}')">删除</button>
                    </div>
                </div>
            `).join('');
        }

        function formatDate(isoString) {
            const date = new Date(isoString);
            return date.toLocaleString('zh-CN', {
                year: 'numeric',
                month: '2-digit',
                day: '2-digit',
                hour: '2-digit',
                minute: '2-digit'
            });
        }

        async function createBackup() {
            const token = getAuthToken();
            if (!token) return;

            try {
                showToast('正在创建备份...', 'success');
                
                const res = await fetch(`${API_BASE}/backup/create`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'Authorization': `Bearer ${token}`
                    },
                    body: JSON.stringify({
                        description: '手动备份',
                        include_emoji: true,
                        include_hippo: true
                    })
                });
                
                const data = await res.json();
                
                if (data.success) {
                    showToast('备份创建成功！', 'success');
                    loadData();
                } else {
                    showToast('创建失败: ' + (data.detail || '未知错误'), 'error');
                }
            } catch (error) {
                showToast('创建备份失败: ' + error.message, 'error');
            }
        }

        function showRestoreModal(backupId) {
            currentBackupId = backupId;
            document.getElementById('restoreModal').classList.add('active');
        }

        function showDeleteModal(backupId) {
            currentBackupId = backupId;
            document.getElementById('deleteModal').classList.add('active');
        }

        function closeModal(modalId) {
            document.getElementById(modalId).classList.remove('active');
            currentBackupId = null;
        }

        async function restoreBackup() {
            const token = getAuthToken();
            if (!token || !currentBackupId) return;

            closeModal('restoreModal');
            showToast('正在恢复备份...', 'success');

            try {
                const res = await fetch(`${API_BASE}/backup/${currentBackupId}/restore`, {
                    method: 'POST',
                    headers: { 'Authorization': `Bearer ${token}` }
                });
                
                const data = await res.json();
                
                if (data.success) {
                    showToast('备份恢复成功！', 'success');
                } else {
                    showToast('恢复失败: ' + (data.detail || '未知错误'), 'error');
                }
            } catch (error) {
                showToast('恢复备份失败: ' + error.message, 'error');
            }
        }

        async function deleteBackup() {
            const token = getAuthToken();
            if (!token || !currentBackupId) return;

            closeModal('deleteModal');
            showToast('正在删除备份...', 'success');

            try {
                const res = await fetch(`${API_BASE}/backup/${currentBackupId}`, {
                    method: 'DELETE',
                    headers: { 'Authorization': `Bearer ${token}` }
                });
                
                const data = await res.json();
                
                if (data.success) {
                    showToast('备份删除成功！', 'success');
                    loadData();
                } else {
                    showToast('删除失败: ' + (data.detail || '未知错误'), 'error');
                }
            } catch (error) {
                showToast('删除备份失败: ' + error.message, 'error');
            }
        }

        // 绑定确认按钮事件
        document.getElementById('confirmRestoreBtn').onclick = restoreBackup;
        document.getElementById('confirmDeleteBtn').onclick = deleteBackup;

        // 页面加载时尝试从 Cookie 获取 token
        window.onload = function() {
            const cookies = document.cookie.split(';');
            for (const cookie of cookies) {
                const [name, value] = cookie.trim().split('=');
                if (name === 'maibot_session') {
                    document.getElementById('tokenInput').value = value;
                    loadData();
                    break;
                }
            }
        };
    </script>
</body>
</html>
"""


@router.get("/page", include_in_schema=False)
async def get_backup_page():
    """
    返回备份管理页面 HTML
    """
    from fastapi.responses import HTMLResponse
    return HTMLResponse(content=BACKUP_PAGE_HTML)
