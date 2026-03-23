"""客户端公开配置（无需鉴权）：供端上在「HTTPS 域名 / 服务端下发的直连根地址」间切换。"""

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.config import settings

router = APIRouter(prefix="/config", tags=["config"])


class ClientConfigOut(BaseModel):
    http_ip_base: str = Field(
        default="",
        description="服务端配置的 API 根地址（生产建议 https://），空表示未配置",
    )


@router.get("/client", response_model=ClientConfigOut)
def get_client_config():
    return ClientConfigOut(http_ip_base=(settings.literature_http_ip_base or "").strip())
