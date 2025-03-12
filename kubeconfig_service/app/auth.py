from fastapi import HTTPException, Depends, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
import httpx
from app.config import settings
from app.logger import logger
from typing import Dict, Optional

# Token handling
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

async def get_current_user_from_token(token: str = Depends(oauth2_scheme)) -> Dict:
    """
    Validate token with user service and get current user information
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        # Call user service to validate token and get user info
        async with httpx.AsyncClient(verify=False) as client:
            response = await client.get(
                f"{settings.USER_SERVICE_URL}/auth/validate-token",
                headers={"Authorization": f"Bearer {token}"}
            )
            
            if response.status_code == 200:
                user_data = response.json()
                return user_data
            else:
                logger.error(f"Token validation failed: {response.text}")
                raise credentials_exception
    except httpx.RequestError as e:
        logger.error(f"Error connecting to user service: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="User authentication service unavailable"
        )
    except Exception as e:
        logger.error(f"Error in authentication: {str(e)}")
        raise credentials_exception

# Simplified version for development if user service is not available yet
async def get_current_user_from_token_dev(token: str = Depends(oauth2_scheme)) -> Dict:
    """
    Development version - simply extracts user ID from token without validation
    """
    try:
        # This is a simplified version that just extracts the user ID
        # without proper validation - only for development
        payload = jwt.decode(
            token, 
            "development-secret-key",  # This is just for development
            algorithms=["HS256"]
        )
        user_id = int(payload.get("sub", 0))
        if user_id <= 0:
            raise ValueError("Invalid user ID")
            
        return {"id": user_id, "username": f"user{user_id}"}
    except Exception as e:
        logger.error(f"Dev token validation error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

# Use the appropriate function based on environment
get_current_user = get_current_user_from_token_dev  # Change to get_current_user_from_token in production
