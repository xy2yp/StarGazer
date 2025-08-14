"""
封装所有对 AppSettings 表的数据库操作，提供一个服务层接口。
本模块负责处理所有与应用设置相关的业务逻辑，包括获取、更新设置，以及处理敏感数据（如 token 和推送配置）的加解密。
所有函数都只准备数据库更改，而不提交事务，将事务控制权交给上层的 API 路由。
"""
import logging
from typing import Optional, Dict, Any
from sqlmodel import Session, select

from app.models import AppSettings
from app.core.security import encrypt_data, decrypt_data

logger = logging.getLogger(__name__)

# 定义了允许用户通过 API 修改的设置项白名单
USER_UPDATABLE_SETTINGS_KEYS = [
    "is_background_sync_enabled",
    "sync_interval_hours",
    "is_push_enabled",
    "push_channel",
    "push_config",
    "is_dnd_enabled",
    "dnd_start_hour",
    "dnd_end_hour",
    "is_push_proxy_enabled",
    "ui_language"
]

def _get_or_create_settings(session: Session) -> AppSettings:
    """
    获取唯一的 AppSettings 记录，如果不存在则创建新的默认记录。    
    这是一个幂等操作，确保应用中总有且仅有一行配置记录。
    """
    settings_record = session.get(AppSettings, 1)

    # 如果记录不存在（如首次运行），则创建一个新的实例
    if not settings_record:
        logger.info("No AppSettings record found, creating a new one with default values.")
        settings_record = AppSettings(id=1)
        session.add(settings_record)
        # 使用 flush 将新对象发送到数据库，使其在当前事务中可用，但不提交事务
        try:
            session.flush()
            session.refresh(settings_record) # 刷新以获取数据库生成的默认值
        except Exception as e:
            logger.error(f"Failed to flush initial AppSettings record: {e}", exc_info=True)
            session.rollback() # 如果 flush 失败，回滚
            raise

    return settings_record

def save_access_token(session: Session, token: Optional[str]):
    """
    加密并准备保存用户的 GitHub access token。    
    如果 token 为 None，则准备清空数据库中的字段。
    """
    settings_record = _get_or_create_settings(session)
    if token:
        encrypted_token = encrypt_data(token)
        settings_record.github_access_token = encrypted_token
        logger.info("Access token has been encrypted and staged for saving.")
    else:
        # 如果 token 为 None (例如登出)，则清空数据库字段
        settings_record.github_access_token = None
        logger.info("Access token clearing has been staged.")
        
    session.add(settings_record)

def get_access_token(session: Session) -> Optional[str]:
    """从数据库中读取并解密 access token。"""
    settings_record = _get_or_create_settings(session)
    encrypted_token = settings_record.github_access_token
    
    # 在返回前解密
    if encrypted_token:
        return decrypt_data(encrypted_token)
    return None

def get_app_settings(session: Session) -> AppSettings:
    """获取完整的应用设置对象。"""
    return _get_or_create_settings(session)

def update_app_settings(session: Session, settings_data: Dict[str, Any]) -> AppSettings:
    """
    准备更新应用设置的更改。    
    只允许更新白名单内的字段，并对敏感的 `push_config` 字段进行加密。
    """
    settings_record = _get_or_create_settings(session)
    
    updated_fields = []
    for key, value in settings_data.items():
        # 安全性检查：只允许更新白名单里的字段
        if key in USER_UPDATABLE_SETTINGS_KEYS:
            # 对 push_config 字段进行加密处理
            if key == 'push_config':
                if value:
                    # 将字典转换为JSON字符串再加密
                    import json
                    value_to_save = encrypt_data(json.dumps(value))
                else:
                    # 如果传入空值，则清空数据库字段
                    value_to_save = None
                setattr(settings_record, key, value_to_save)
            else:
                setattr(settings_record, key, value)
            updated_fields.append(key)

    if updated_fields:
        session.add(settings_record)
        logger.info(f"App settings update staged for fields: {', '.join(updated_fields)}")
        
    return settings_record

def get_decrypted_push_config(session: Session) -> Optional[Dict[str, Any]]:
    """
    从数据库获取并解密推送配置。
    这是为通知器模块提供的专用函数，以确保它们总是获得可用的明文配置。
    """
    settings = get_app_settings(session)
    encrypted_config_str = settings.push_config

    if not encrypted_config_str:
        return None

    try:
        import json
        decrypted_config = json.loads(decrypt_data(encrypted_config_str))
        return decrypted_config
    except Exception as e:
        logger.error(f"Failed to decrypt or parse push_config for notifier: {e}", exc_info=True)
        # 关键：在解密失败时返回 None，以防止加密的配置被错误地使用
        return None

def increment_failed_push_count(session: Session):
    """准备将推送失败计数器加一。"""
    settings_record = _get_or_create_settings(session)
    current_count = settings_record.failed_push_count or 0
    settings_record.failed_push_count = current_count + 1
    session.add(settings_record)
    logger.info(f"Staged increment of failed_push_count from {current_count} to {settings_record.failed_push_count}.")

def reset_failed_push_count(session: Session):
    """准备将推送失败计数器重置为零。"""
    settings_record = _get_or_create_settings(session)
    if settings_record.failed_push_count > 0:
        settings_record.failed_push_count = 0
        session.add(settings_record)
        logger.info("Staged reset of failed push count to 0.")

def update_tags_order(session: Session, tags_order: list[str]) -> AppSettings:
    """准备更新自定义标签排序的更改。"""
    settings_record = _get_or_create_settings(session)
    settings_record.tags_order = tags_order
    session.add(settings_record)
    logger.info("Staged update for tags_order.")
    return settings_record

def update_languages_order(session: Session, languages_order: list[str]) -> AppSettings:
    """准备更新自定义语言排序的更改。"""
    settings_record = _get_or_create_settings(session)
    settings_record.languages_order = languages_order
    session.add(settings_record)
    logger.info("Staged update for languages_order.")
    return settings_record
