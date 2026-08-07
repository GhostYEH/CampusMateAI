"""安全工具 — 文件名/路径校验 + 密码哈希 + JWT 签发与校验。

设计原则:
- 不引入 bcrypt / PyJWT 等额外依赖，使用标准库 hashlib + hmac + base64 + json。
- 密码使用 PBKDF2-HMAC-SHA256(salt + 100k 迭代)。
- JWT 使用 HS256(HMAC-SHA256)，仅签发与校验，不引入外部库。
- 不在日志中记录 token 或密码明文。
- 错误响应中不泄露用户名是否存在。
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import re
import secrets
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from cryptography.fernet import Fernet
from passlib.context import CryptContext

from .config import get_settings

# 从 jwt_secret 生成一个确定性的 32 字节密钥
settings = get_settings()
hashed_secret = hashlib.sha256(settings.jwt_secret.encode()).digest()
fernet_key = base64.urlsafe_b64encode(hashed_secret)
fernet = Fernet(fernet_key)

def encrypt(data: str) -> str:
    return fernet.encrypt(data.encode()).decode()

def decrypt(token: str) -> str:
    return fernet.decrypt(token.encode()).decode()

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# ===== 文件名 / 路径穿越校验 =====

# 合法文件名：中文/英文/数字/下划线/连字符/点/常见中文标点(括号、方括号等)，长度 1~200
_SAFE_NAME = re.compile(r"^[\w\u4e00-\u9fa5\-. ()（）\[\]【】、，]{1,200}$")


def sanitize_filename(name: str) -> str:
    """返回去掉路径部分的纯文件名；不合法时抛 ValueError。"""
    if not name or not isinstance(name, str):
        raise ValueError("文件名为空")
    # 去掉路径分隔符（防止路径穿越）
    base = Path(name).name
    if not base or base in (".", ".."):
        raise ValueError("文件名为空或非法")
    if ".." in base or "/" in base or "\\" in base:
        raise ValueError("文件名包含非法路径字符")
    if not _SAFE_NAME.match(base):
        raise ValueError("文件名包含非法字符")
    return base


def is_path_traversal(path: Path, base_dir: Path) -> bool:
    """判断解析后的绝对路径是否仍位于 base_dir 之内。"""
    try:
        resolved = path.resolve()
        base = base_dir.resolve()
        return base not in resolved.parents and resolved != base
    except (OSError, RuntimeError):
        return True


# ===== 密码哈希 (PBKDF2-HMAC-SHA256) =====

_PBKDF2_ITERATIONS = 100_000
_HASH_ALGORITHM = "pbkdf2_sha256"
_DELIMITER = "$"


def hash_password(password: str) -> str:
    """返回 PBKDF2-HMAC-SHA256 哈希串: pbkdf2_sha256$<iter>$<salt_b64>$<hash_b64>。"""
    if not password:
        raise ValueError("密码不能为空")
    salt = secrets.token_bytes(16)
    derived = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt, _PBKDF2_ITERATIONS, dklen=32
    )
    return _DELIMITER.join(
        [
            _HASH_ALGORITHM,
            str(_PBKDF2_ITERATIONS),
            base64.b64encode(salt).decode("ascii"),
            base64.b64encode(derived).decode("ascii"),
        ]
    )


def verify_password(password: str, stored_hash: str) -> bool:
    """验证密码是否匹配存储的哈希；使用恒定时间比较防时序攻击。"""
    if not password or not stored_hash:
        return False
    parts = stored_hash.split(_DELIMITER)
    if len(parts) != 4:
        return False
    algo, iter_str, salt_b64, hash_b64 = parts
    if algo != _HASH_ALGORITHM:
        return False
    try:
        iterations = int(iter_str)
        salt = base64.b64decode(salt_b64)
        expected = base64.b64decode(hash_b64)
    except (ValueError, base64.binascii.Error):  # type: ignore[attr-defined]
        return False
    derived = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt, iterations, dklen=len(expected)
    )
    return hmac.compare_digest(derived, expected)

# ===== JWT (HS256) =====
# 仅使用标准库实现 HS256，避免引入 PyJWT。
# Token 结构: <header_b64>.<payload_b64>.<signature_b64> (均 urlsafe_base64, 无 padding)


@dataclass
class TokenPayload:
    """JWT payload 解析后的结构。"""

    sub: str  # user_id
    role: str
    type: str  # "access" / "refresh"
    jti: str  # token id
    iat: int  # 签发时间(unix)
    exp: int  # 过期时间(unix)

    def to_dict(self) -> dict:
        return {
            "sub": self.sub,
            "role": self.role,
            "type": self.type,
            "jti": self.jti,
            "iat": self.iat,
            "exp": self.exp,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "TokenPayload":
        return cls(
            sub=str(data["sub"]),
            role=str(data["role"]),
            type=str(data["type"]),
            jti=str(data["jti"]),
            iat=int(data["iat"]),
            exp=int(data["exp"]),
        )


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64url_decode(s: str) -> bytes:
    pad = "=" * (-len(s) % 4)
    return base64.urlsafe_b64decode(s + pad)


_HEADER = {"alg": "HS256", "typ": "JWT"}


def encode_jwt(payload: TokenPayload, secret: str) -> str:
    """签发 JWT。"""
    header_b64 = _b64url_encode(
        json.dumps(_HEADER, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    )
    payload_b64 = _b64url_encode(
        json.dumps(payload.to_dict(), separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    )
    signing_input = f"{header_b64}.{payload_b64}".encode("ascii")
    signature = hmac.new(secret.encode("utf-8"), signing_input, hashlib.sha256).digest()
    sig_b64 = _b64url_encode(signature)
    return f"{header_b64}.{payload_b64}.{sig_b64}"


class JWTError(Exception):
    """JWT 解析/校验失败。"""


def decode_jwt(token: str, secret: str) -> TokenPayload:
    """校验签名 + 过期时间，返回 payload。失败抛 JWTError。"""
    if not token or not isinstance(token, str):
        raise JWTError("token 为空")
    parts = token.split(".")
    if len(parts) != 3:
        raise JWTError("token 格式错误")
    header_b64, payload_b64, sig_b64 = parts
    signing_input = f"{header_b64}.{payload_b64}".encode("ascii")
    expected_sig = hmac.new(secret.encode("utf-8"), signing_input, hashlib.sha256).digest()
    try:
        given_sig = _b64url_decode(sig_b64)
    except Exception as e:
        raise JWTError("签名解码失败") from e
    if not hmac.compare_digest(expected_sig, given_sig):
        raise JWTError("签名不匹配")
    try:
        payload_data = json.loads(_b64url_decode(payload_b64).decode("utf-8"))
    except Exception as e:
        raise JWTError("payload 解码失败") from e
    try:
        payload = TokenPayload.from_dict(payload_data)
    except (KeyError, ValueError, TypeError) as e:
        raise JWTError(f"payload 字段缺失: {e}") from e
    now = int(time.time())
    if payload.exp <= now:
        raise JWTError("token 已过期")
    return payload


def create_access_token(
    user_id: str,
    role: str,
    secret: str,
    *,
    expires_in_minutes: Optional[int] = None,
) -> tuple[str, TokenPayload]:
    """签发 access token，返回 (token_str, payload)。"""
    now = int(time.time())
    exp_minutes = expires_in_minutes if expires_in_minutes is not None else 30
    payload = TokenPayload(
        sub=user_id,
        role=role,
        type="access",
        jti=secrets.token_hex(16),
        iat=now,
        exp=now + exp_minutes * 60,
    )
    return encode_jwt(payload, secret), payload


def create_refresh_token(
    user_id: str,
    role: str,
    secret: str,
    *,
    expires_in_days: Optional[int] = None,
) -> tuple[str, TokenPayload]:
    """签发 refresh token，返回 (token_str, payload)。"""
    now = int(time.time())
    exp_days = expires_in_days if expires_in_days is not None else 14
    payload = TokenPayload(
        sub=user_id,
        role=role,
        type="refresh",
        jti=secrets.token_hex(16),
        iat=now,
        exp=now + exp_days * 86400,
    )
    return encode_jwt(payload, secret), payload


def hash_token(token: str) -> str:
    """对 refresh token 做 SHA-256 哈希(用于入库比对，避免直接存原 token)。"""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


__all__ = [
    "sanitize_filename",
    "is_path_traversal",
    "hash_password",
    "verify_password",
    "encode_jwt",
    "decode_jwt",
    "create_access_token",
    "create_refresh_token",
    "hash_token",
    "TokenPayload",
    "JWTError",
    "encrypt",
    "decrypt",
]
