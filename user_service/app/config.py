from pydantic_settings import BaseSettings
import os
from typing import Optional, Dict, Any


class Settings(BaseSettings):
    # App settings
    APP_NAME: str = "KubeSage User Service"
    DEBUG: bool = False
    
    # Database
    DATABASE_URL: str = "sqlite:///user_service.db"
    
    # JWT Auth
    SECRET_KEY: str = "your-super-secret-key-change-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    
    
    # SSL
    SSL_ENABLED: bool = True
    SSL_KEYFILE: Optional[str] = "key.pem"
    SSL_CERTFILE: Optional[str] = "cert.pem"
    
    @property
    def ssl_keyfile(self) -> Optional[str]:
        if self.SSL_ENABLED:
            return self.SSL_KEYFILE
        return None
    
    @property
    def ssl_certfile(self) -> Optional[str]:
        if self.SSL_ENABLED:
            return self.SSL_CERTFILE
        return None
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True
        
settings = Settings()
