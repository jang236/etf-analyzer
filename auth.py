"""API 키 인증 미들웨어.

사용:
    @app.get("/v1/...", dependencies=[Depends(verify_api_key)])

키는 Replit Secrets의 ETF_API_KEY 환경변수에 저장.
설정되지 않은 경우(로컬 개발 등)엔 경고 후 통과 (프로덕션에선 반드시 설정할 것).
"""
import os
from fastapi import Header, HTTPException

API_KEY = os.environ.get("ETF_API_KEY")

if not API_KEY:
    print("⚠️  WARNING: ETF_API_KEY 환경변수가 설정되지 않았습니다.")
    print("    → 개발 모드에서는 인증이 비활성화됩니다.")
    print("    → 배포 시 반드시 Replit Secrets에 ETF_API_KEY를 등록하세요.")


async def verify_api_key(x_api_key: str = Header(None, alias="X-API-Key")):
    """X-API-Key 헤더 검증."""
    if not API_KEY:
        # 개발 환경: 통과
        return
    if not x_api_key or x_api_key != API_KEY:
        raise HTTPException(
            status_code=401,
            detail="Invalid or missing X-API-Key header",
        )
