from fastapi import HTTPException, Depends, status
from fastapi.security import OAuth2PasswordBearer
import httpx
from app.config import settings
from app.logger import logger
from typing import Dict

# Token handling
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

async def get_current_user(token: str = Depends(oauth2_scheme)) -> Dict:
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
