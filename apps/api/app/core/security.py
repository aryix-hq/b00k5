import uuid
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional, Any, Set
import jwt
import bcrypt
import redis
from app.core.config import settings

logger = logging.getLogger("b00k5_security")

# In-memory revocation cache fallback
_REVOKED_TOKENS_MEM: Set[str] = set()

def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        pw_bytes = plain_password.encode('utf-8')[:72] if isinstance(plain_password, str) else plain_password[:72]
        hash_bytes = hashed_password.encode('utf-8') if isinstance(hashed_password, str) else hashed_password
        return bcrypt.checkpw(pw_bytes, hash_bytes)
    except Exception:
        return False

def get_password_hash(password: str) -> str:
    pw_bytes = password.encode('utf-8')[:72] if isinstance(password, str) else password[:72]
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(pw_bytes, salt).decode('utf-8')

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    now = datetime.now(timezone.utc)
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    
    # DEF-03 & SEC-03: Include unique JWT ID (jti), issued-at (iat), and issuer (iss)
    jti = str(uuid.uuid4())
    to_encode.update({
        "exp": expire,
        "iat": now,
        "iss": to_encode.get("iss", "b00k5-auth-authority"),
        "jti": jti
    })
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt

def decode_access_token(token: str, expected_issuer: Optional[str] = None) -> Optional[dict]:
    if not token or not isinstance(token, str):
        return None
    try:
        # SEC-03: Reject 'none' algorithm or asymmetric/symmetric confusion before decoding
        unverified_header = jwt.get_unverified_header(token)
        if unverified_header.get("alg") != settings.ALGORITHM:
            return None
        decode_kwargs = {
            "algorithms": [settings.ALGORITHM],
            "options": {"require": ["exp"]}
        }
        if expected_issuer:
            decode_kwargs["issuer"] = expected_issuer
        payload = jwt.decode(token, settings.SECRET_KEY, **decode_kwargs)
        return payload
    except jwt.PyJWTError:
        return None

_REDIS_POOL: Optional[redis.ConnectionPool] = None
_REDIS_CLIENT: Optional[redis.Redis] = None

def get_redis_client() -> Optional[redis.Redis]:
    """
    Returns a persistent, thread-safe Redis client using a singleton ConnectionPool.
    Eliminates TCP socket churn and port exhaustion under high concurrency (DEF-32).
    """
    global _REDIS_POOL, _REDIS_CLIENT
    if _REDIS_CLIENT is None:
        try:
            _REDIS_POOL = redis.ConnectionPool.from_url(
                settings.REDIS_URL,
                decode_responses=True,
                max_connections=20,
                socket_timeout=3,
                socket_connect_timeout=3
            )
            _REDIS_CLIENT = redis.Redis(connection_pool=_REDIS_POOL)
        except Exception as e:
            logger.warning(f"Could not initialize shared Redis connection pool: {e}")
            return None
    return _REDIS_CLIENT

def revoke_token(token: str) -> bool:
    """
    Server-side JWT revocation via Redis blocklist with TTL matching remaining token lifespan.
    """
    try:
        payload = decode_access_token(token)
        if not payload:
            # Try decoding without verification if expired/tampered
            payload = jwt.decode(token, options={"verify_signature": False})
        
        jti = payload.get("jti") or token[-32:]
        exp = payload.get("exp")
        
        now_ts = datetime.now(timezone.utc).timestamp()
        ttl = max(60, int(exp - now_ts)) if exp else 3600

        # Always record in memory cache
        _REVOKED_TOKENS_MEM.add(jti)

        # Store in Redis via shared pool
        r = get_redis_client()
        if r:
            try:
                r.set(f"revoked_token:{jti}", "revoked", ex=ttl)
                logger.info(f"JWT revoked in Redis: jti={jti}, ttl={ttl}s")
            except Exception as e:
                logger.warning(f"Could not record token revocation in Redis: {e}. In-memory fallback used.")

        return True
    except Exception as e:
        logger.error(f"Error revoking token: {e}")
        return False

def is_token_revoked(token: str) -> bool:
    """
    Checks whether the JWT token has been explicitly revoked server-side.
    """
    try:
        payload = decode_access_token(token)
        if not payload:
            return True
        
        jti = payload.get("jti")
        if not jti:
            return False

        if jti in _REVOKED_TOKENS_MEM:
            return True

        r = get_redis_client()
        if r:
            try:
                is_rev = r.get(f"revoked_token:{jti}")
                if is_rev:
                    _REVOKED_TOKENS_MEM.add(jti)
                    return True
            except Exception:
                pass

        return False
    except Exception:
        return True
