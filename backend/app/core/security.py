"""
提供对称加密和解密功能。
使用 Fernet (cryptography 库) 进行加密操作，密钥从应用的 SECRET_KEY 派生而来。
用于保护敏感数据，如 GitHub access token 和推送渠道配置。
"""
import base64
import hashlib
from cryptography.fernet import Fernet
from app.config import settings
import logging

logger = logging.getLogger(__name__)

# --- 密钥初始化 ---
# 从应用的 SECRET_KEY 安全地派生一个32字节的加密密钥。
# 使用 SHA-256 哈希函数确保密钥长度符合 Fernet 要求。
try:
    key = hashlib.sha256(settings.SECRET_KEY.encode('utf-8')).digest()
    ENCRYPTION_KEY = base64.urlsafe_b64encode(key)
    fernet = Fernet(ENCRYPTION_KEY)
    logger.info("Encryption service initialized successfully.")
except Exception as e:
    logger.critical(f"FATAL: Could not initialize encryption service. SECRET_KEY might be missing or invalid. Error: {e}")
    fernet = None

def encrypt_data(data: str) -> str:
    """
    使用初始化的密钥加密给定的字符串数据。
    参数:
        data: 要加密的明文字符串。        
    返回:
        加密后的 base64 编码字符串。
    """
    if not fernet:
        raise RuntimeError("Encryption service is not available.")
    if not data:
        return data
    return fernet.encrypt(data.encode('utf-8')).decode('utf-8')

def decrypt_data(encrypted_data: str) -> str:
    """
    使用初始化的密钥解密给定的字符串数据。    
    参数:
        encrypted_data: 要解密的 base64 编码字符串。        
    返回:
        解密后的明文字符串。如果解密失败，返回空字符串。
    """
    if not fernet:
        raise RuntimeError("Encryption service is not available.")
    if not encrypted_data:
        return encrypted_data
    try:
        return fernet.decrypt(encrypted_data.encode('utf-8')).decode('utf-8')
    except Exception as e:
        # 如果解密失败，记录错误并返回空字符串，以避免程序崩溃
        logger.error(f"Failed to decrypt data: {e}. Returning empty string.")
        return ""
