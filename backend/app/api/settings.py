"""
处理与应用设置相关的 API 端点。
提供获取、更新应用设置的功能，包括同步设置、推送通知配置、界面排序设置等。支持测试推送通知和重置失败计数器。
"""
import logging
from typing import Dict, Any, Optional, List
from fastapi import APIRouter, Depends, status
from sqlmodel import Session
from pydantic import BaseModel
import backoff 

from app.db import get_session
from app.exceptions import ApiException
from app.api.dependencies import get_token_from_cookie
from app.api.users import get_current_github_user
from app.core import settings_service
from app.core.notifiers.factory import create_notifier
from app.core.notifiers.base import Notifier
from app.core.security import decrypt_data
from app.models import AppSettings

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/settings",
    tags=["Settings"],
)

class AppSettingsUpdateRequest(BaseModel):
    """更新应用设置的请求体模型。"""
    is_background_sync_enabled: Optional[bool] = None
    sync_interval_hours: Optional[int] = None
    is_push_enabled: Optional[bool] = None
    push_channel: Optional[str] = None
    push_config: Optional[Dict[str, Any]] = None
    is_dnd_enabled: Optional[bool] = None
    dnd_start_hour: Optional[int] = None
    dnd_end_hour: Optional[int] = None
    is_push_proxy_enabled: Optional[bool] = None
    ui_language: Optional[str] = None
    # AI 总结相关
    is_ai_enabled: Optional[bool] = None
    is_auto_analysis_enabled: Optional[bool] = None
    ai_base_url: Optional[str] = None
    ai_api_key: Optional[str] = None
    ai_model: Optional[str] = None
    ai_concurrency: Optional[int] = None

class AppSettingsResponse(BaseModel):
    """获取应用设置的响应体模型。"""
    is_background_sync_enabled: bool
    sync_interval_hours: int
    is_push_enabled: bool
    push_channel: Optional[str]
    push_config: Optional[Dict[str, Any]] = None # 解密后的推送配置
    is_dnd_enabled: bool
    dnd_start_hour: int
    dnd_end_hour: int
    failed_push_count: int
    is_push_proxy_enabled: bool
    tags_order: List[str]
    languages_order: List[str]
    ui_language: Optional[str]
    test_push_status: Optional[str] = None # 测试推送的状态: "success" 或 "failed"
    test_push_error: Optional[str] = None # 测试推送失败时的错误信息
    # AI 总结相关
    is_ai_enabled: bool
    is_auto_analysis_enabled: bool
    ai_base_url: Optional[str]
    ai_api_key: Optional[str]
    ai_model: Optional[str]
    ai_concurrency: int

@router.get("", response_model=AppSettingsResponse, summary="Get application settings")
async def get_settings(
    session: Session = Depends(get_session),
    _token: str = Depends(get_current_github_user),
):
    """获取当前的应用设置，包括解密后的推送配置。"""
    app_settings = settings_service.get_app_settings(session)

    # 解密推送配置以供前端使用
    decrypted_push_config = None
    if app_settings.push_config:
        try:
            import json
            decrypted_push_config = json.loads(decrypt_data(app_settings.push_config))
        except Exception as e:
            logger.error(f"Failed to decrypt or parse push_config: {e}", exc_info=True)
            # 解密失败时返回空字典，避免前端出错
            decrypted_push_config = {}

    # 解密 AI API 密钥以供前端使用
    decrypted_ai_api_key = None
    if app_settings.ai_api_key:
        try:
            decrypted_ai_api_key = decrypt_data(app_settings.ai_api_key)
        except Exception as e:
            logger.error(f"Failed to decrypt ai_api_key: {e}", exc_info=True)
            decrypted_ai_api_key = None

    return AppSettingsResponse(
        is_background_sync_enabled=app_settings.is_background_sync_enabled,
        sync_interval_hours=app_settings.sync_interval_hours,
        is_push_enabled=app_settings.is_push_enabled,
        push_channel=app_settings.push_channel,
        push_config=decrypted_push_config,
        is_dnd_enabled=app_settings.is_dnd_enabled,
        dnd_start_hour=app_settings.dnd_start_hour,
        dnd_end_hour=app_settings.dnd_end_hour,
        failed_push_count=app_settings.failed_push_count,
        is_push_proxy_enabled=app_settings.is_push_proxy_enabled,
        tags_order=app_settings.tags_order,
        languages_order=app_settings.languages_order,
        ui_language=app_settings.ui_language,
        is_ai_enabled=app_settings.is_ai_enabled,
        is_auto_analysis_enabled=app_settings.is_auto_analysis_enabled,
        ai_base_url=app_settings.ai_base_url,
        ai_api_key=decrypted_ai_api_key,  # 使用解密后的密钥
        ai_model=app_settings.ai_model,
        ai_concurrency=app_settings.ai_concurrency,
    )

@router.put("", response_model=AppSettingsResponse, summary="Update application settings")
async def update_settings(
    settings_data: AppSettingsUpdateRequest,
    session: Session = Depends(get_session),
    _token: str = Depends(get_current_github_user),
):
    """
    更新应用设置。
    支持部分字段更新，并在推送配置发生变化时自动发送测试通知。
    包含数据联动逻辑：关闭后台同步时会自动关闭推送和免打扰功能。
    """
    try:
        # 获取前端提交的更新数据（仅包含有值的字段）
        update_data = settings_data.model_dump(exclude_unset=True)

        # 获取当前数据库中的设置，用于新旧值比较
        current_settings = settings_service.get_app_settings(session)
        
        # 解密当前存储的推送配置，用于新旧值比较
        current_push_config_decrypted = {}
        if current_settings.push_config:
            try:
                import json
                current_push_config_decrypted = json.loads(decrypt_data(current_settings.push_config))
            except Exception as e:
                logger.warning(f"Failed to decrypt current push_config for comparison: {e}")

        # 执行数据联动规则：关闭后台同步时自动关闭相关功能
        if update_data.get('is_background_sync_enabled') is False:
            update_data['is_push_enabled'] = False
            update_data['is_dnd_enabled'] = False
        if update_data.get('is_push_enabled') is False:
            update_data['is_dnd_enabled'] = False

        # 判断是否需要发送测试推送（仅当推送配置发生变化且推送功能开启时）
        should_send_test_push = False
        final_push_enabled_state = update_data.get('is_push_enabled', current_settings.is_push_enabled)

        if final_push_enabled_state:
            # 检查推送渠道是否发生变化
            new_channel = update_data.get('push_channel')
            channel_has_changed = new_channel is not None and new_channel != current_settings.push_channel
            
            # 检查推送配置是否发生变化
            new_config = update_data.get('push_config')
            config_has_changed = new_config is not None and new_config != current_push_config_decrypted
            
            if channel_has_changed or config_has_changed:
                should_send_test_push = True

        # 将经过校准的数据更新到数据库
        updated_settings = settings_service.update_app_settings(session, update_data)
        
        test_push_status = None
        test_push_error = None

        # 解密更新后的推送配置以供测试使用
        decrypted_push_config_for_test = None
        if updated_settings.push_config:
            try:
                import json
                decrypted_push_config_for_test = json.loads(decrypt_data(updated_settings.push_config))
            except Exception as e:
                logger.error(f"Failed to decrypt push_config for test notification: {e}")
                decrypted_push_config_for_test = {}

        # 解密更新后的 AI API 密钥以供返回
        decrypted_ai_api_key_for_response = None
        if updated_settings.ai_api_key:
            try:
                decrypted_ai_api_key_for_response = decrypt_data(updated_settings.ai_api_key)
            except Exception as e:
                logger.error(f"Failed to decrypt ai_api_key: {e}")
                decrypted_ai_api_key_for_response = None
        
        # 创建用于测试的临时设置对象（包含解密后的配置）
        temp_settings_for_test = updated_settings.model_copy(
            update={"push_config": decrypted_push_config_for_test}
        )

        # 根据判断结果发送测试推送
        if should_send_test_push:
            notifier = create_notifier(session, temp_settings_for_test)
            
            if notifier:
                try:
                    title = "【StarGazer 星眸】测试推送 / Test Notification"
                    content = "🎉 恭喜！您的 StarGazer 星眸 通知推送已成功配置！\n🎉 Congratulations! Your StarGazer push notification is configured successfully!"
                    
                    @backoff.on_exception(backoff.expo, Exception, max_tries=2, max_time=10)
                    async def send_with_retry(notifier_instance: Notifier, t: str, c: str):
                        return await notifier_instance.send(t, c)

                    success = await send_with_retry(notifier, title, content)

                    if success:
                        test_push_status = "success"
                        logger.info("Test notification sent successfully.")
                    else:
                        test_push_status = "failed"
                        test_push_error = "Notifier returned False without an exception."
                        logger.warning(f"Test notification failed: {test_push_error}")
                
                except Exception as e:
                    test_push_status = "failed"
                    test_push_error = f"An exception occurred: {e}"
                    logger.error(f"Test notification failed with exception: {e}", exc_info=True)
            else:
                logger.warning("Could not create a notifier for test push. Check channel name or config.")
                test_push_status = "failed"
                test_push_error = "Could not create notifier. Check channel name or config."

        # 提交事务并刷新对象以获取最新状态
        session.commit()
        session.refresh(updated_settings)

        return AppSettingsResponse(
            is_background_sync_enabled=updated_settings.is_background_sync_enabled,
            sync_interval_hours=updated_settings.sync_interval_hours,
            is_push_enabled=updated_settings.is_push_enabled,
            push_channel=updated_settings.push_channel,
            push_config=decrypted_push_config_for_test,
            is_dnd_enabled=updated_settings.is_dnd_enabled,
            dnd_start_hour=updated_settings.dnd_start_hour,
            dnd_end_hour=updated_settings.dnd_end_hour,
            failed_push_count=updated_settings.failed_push_count,
            is_push_proxy_enabled=updated_settings.is_push_proxy_enabled,
            tags_order=updated_settings.tags_order,
            languages_order=updated_settings.languages_order,
            ui_language=updated_settings.ui_language,
            test_push_status=test_push_status,
            test_push_error=test_push_error,
            is_ai_enabled=updated_settings.is_ai_enabled,
            is_auto_analysis_enabled=updated_settings.is_auto_analysis_enabled,
            ai_base_url=updated_settings.ai_base_url,
            ai_api_key=decrypted_ai_api_key_for_response,  # 使用解密后的密钥
            ai_model=updated_settings.ai_model,
            ai_concurrency=updated_settings.ai_concurrency,
        )

    except Exception as e:
        session.rollback()
        logger.error(f"Failed to update settings, transaction rolled back: {e}", exc_info=True)
        raise ApiException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            code="SETTINGS_UPDATE_FAILED",
            message_zh="更新设置时发生错误",
            message_en="Failed to update settings"
        )

@router.post("/reset-failed-push-count", status_code=status.HTTP_204_NO_CONTENT, summary="Reset failed push notification counter")
async def reset_counter(
    session: Session = Depends(get_session),
    _token: str = Depends(get_current_github_user),
):
    """重置推送失败计数器。"""
    try:
        settings_service.reset_failed_push_count(session)
        session.commit()
    except Exception as e:
        session.rollback()
        logger.error(f"Failed to reset failed push count, transaction rolled back: {e}", exc_info=True)
        raise ApiException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            code="COUNTER_RESET_FAILED",
            message_zh="重置计数器时发生错误",
            message_en="Failed to reset counter"
        )
    return

@router.put(
    "/tags-order", 
    status_code=status.HTTP_204_NO_CONTENT, 
    summary="Update custom order of tags"
)
async def update_tags_order(
    tags: List[str],
    session: Session = Depends(get_session),
    _token: str = Depends(get_current_github_user),
):
    """更新用户自定义的标签排序。"""
    try:
        settings_service.update_tags_order(session, tags)
        session.commit()
    except Exception as e:
        session.rollback()
        logger.error(f"Failed to update tags order, transaction rolled back: {e}", exc_info=True)
        raise ApiException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            code="ORDER_UPDATE_FAILED",
            message_zh="更新分组排序时发生错误",
            message_en="Failed to update tags order"
        )
    return

@router.put(
    "/languages-order", 
    status_code=status.HTTP_204_NO_CONTENT, 
    summary="Update custom order of languages"
)
async def update_languages_order(
    languages: List[str],
    session: Session = Depends(get_session),
    _token: str = Depends(get_current_github_user),
):
    """更新用户自定义的编程语言排序。"""
    try:
        settings_service.update_languages_order(session, languages)
        session.commit()
    except Exception as e:
        session.rollback()
        logger.error(f"Failed to update languages order, transaction rolled back: {e}", exc_info=True)
        raise ApiException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            code="ORDER_UPDATE_FAILED",
            message_zh="更新语言排序时发生错误",
            message_en="Failed to update languages order"
        )
    return
