from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routes import auth_router, user_router
from app.database import create_db_and_tables
from app.config import Settings
from app.logger import logger

app = FastAPI(title="KubeSage User Authentication Service")

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure properly in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth_router, prefix="/auth", tags=["Authentication"])
app.include_router(user_router, prefix="/users", tags=["Users"])

@app.on_event("startup")
def on_startup():
    logger.info("Starting User Authentication Service")
    create_db_and_tables()

@app.get("/health")
def health_check():
    return {"status": "healthy"}

if __name__ == "__main__":
    import uvicorn
    settings = Settings()
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        ssl_keyfile=settings.ssl_keyfile,
        ssl_certfile=settings.ssl_certfile
    )
