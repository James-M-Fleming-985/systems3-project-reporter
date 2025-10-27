from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    feature_003_001_enabled: bool = True
    feature_003_002_enabled: bool = True
    feature_003_003_enabled: bool = True
    feature_003_004_enabled: bool = True
    feature_003_005_enabled: bool = True
    feature_003_006_enabled: bool = True
    
    class Config:
        env_file = ".env"

settings = Settings()