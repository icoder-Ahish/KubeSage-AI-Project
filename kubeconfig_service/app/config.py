from pydantic_settings import BaseSettings
import os
from typing import Optional

class Settings(BaseSettings):
    # App settings
    APP_NAME: str = "KubeSage KubeConfig Service"
    DEBUG: bool = False
    
    # Database
    DATABASE_URL: str = "sqlite:///kubeconfig_service.db"
    
    # Kubeconfig storage
    UPLOAD_DIR: str = "uploaded_kubeconfigs"
    
    # User service URL for authentication
    USER_SERVICE_URL: str = "https://user-service:8000"
    
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

# Ensure the upload directory exists
os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
