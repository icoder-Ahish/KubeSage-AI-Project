from pydantic_settings import BaseSettings
import os
from typing import Optional

class Settings(BaseSettings):
    # App settings
    APP_NAME: str = "KubeSage K8sGPT Operations Service"
    DEBUG: bool = False
    
    # Database
    DATABASE_URL: str = "sqlite:///k8sgpt_service.db"
    
    # User service URL for authentication
    USER_SERVICE_URL: str = "https://user-service:8000"
    
    # Kubeconfig service URL
    KUBECONFIG_SERVICE_URL: str = "https://kubeconfig-service:8001"
    
    # Redis settings
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_PASSWORD: Optional[str] = None
    
    # SSL
    SSL_ENABLED: bool = True
    SSL_KEYFILE: Optional[str] = "key.pem"
    SSL_CERTFILE: Optional[str] = "cert.pem"
    
    # Cache settings
    CACHE_TTL: int = 3600  # 1 hour cache by default
    
    # K8sGPT settings
    K8SGPT_RESULTS_DIR: str = "analysis_results"
    
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

# Ensure the results directory exists
os.makedirs(settings.K8SGPT_RESULTS_DIR, exist_ok=True)
