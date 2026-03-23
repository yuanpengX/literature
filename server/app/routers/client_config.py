"""客户端公开配置（无需鉴权）：供 App 在「域名 / 服务端下发的 IP 根地址」间切换。"""

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.config import settings

router = APIRouter(prefix="/config", tags=["config"])


class ClientConfigOut(BaseModel):
    http_ip_base: str = Field(
        default="",
        description="服务端配置的 HTTP(S) 根地址（通常为公网 IP:80），空表示未配置",
    )


@router.get("/client", response_model=ClientConfigOut)
def get_client_config():
    return ClientConfigOut(http_ip_base=(settings.literature_http_ip_base or "").strip())
