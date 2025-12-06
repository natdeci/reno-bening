from fastapi import Header, HTTPException, status
import hmac
import secrets

from .settings import settings

def verify_api_key(x_api_key: str = Header(..., alias="X-API-Key")):     
    received_key = x_api_key.encode('utf-8')
    expected_key = settings.api_key_secret.encode('utf-8')

    print("Verifying api key...")
    
    if not hmac.compare_digest(received_key, expected_key):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API Key"
        )
    
    print("Verified!")
    return x_api_key