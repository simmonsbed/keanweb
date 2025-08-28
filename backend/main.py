# main.py
# /cogs  아님! 웹 백엔드용 초미니 프록시
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import os
import httpx
from dotenv import load_dotenv

load_dotenv()
NX_API_KEY = os.getenv("NX_API_KEY")
if not NX_API_KEY:
    raise RuntimeError("NX_API_KEY not set in .env")

app = FastAPI()

# CORS: 개발 중엔 * 허용, 배포 시 GitHub Pages origin만 허용
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 예: ["https://simmonsbed.github.io"]
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE = "https://open.api.nexon.com/heroes/v2"
HDRS = {"x-nxopen-api-key": NX_API_KEY}

async def get_json(url: str):
    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.get(url, headers=HDRS)
        if r.status_code != 200:
            raise HTTPException(status_code=r.status_code, detail=f"Nexon API error: {r.text[:200]}")
        return r.json()

@app.get("/api/id")
async def get_ocid(name: str):
    from urllib.parse import quote
    return await get_json(f"{BASE}/id?character_name={quote(name)}")

@app.get("/api/character")
async def character_aggregate(name: str):
    """닉네임 → ocid → 기본/길드/장착타이틀/스탯 묶어서 전달"""
    from urllib.parse import quote

    # 1) ocid
    ocid_data = await get_json(f"{BASE}/id?character_name={quote(name)}")
    ocid = ocid_data.get("ocid")
    if not ocid:
        raise HTTPException(404, detail="캐릭터를 찾을 수 없습니다.")

    # 2) 병렬로 가져오기
    async with httpx.AsyncClient(timeout=15, headers=HDRS) as client:
        basic, guild, title, stat = await httpx.AsyncClient.gather(
            client.get(f"{BASE}/character/basic?ocid={ocid}"),
            client.get(f"{BASE}/character/guild?ocid={ocid}"),
            client.get(f"{BASE}/character/title-equipment?ocid={ocid}"),
            client.get(f"{BASE}/character/stat?ocid={ocid}")
        )

    def ok(resp):
        if resp.status_code == 200:
            return resp.json()
        raise HTTPException(resp.status_code, detail=f"Nexon API error: {resp.text[:200]}")

    return {
        "ocid": ocid,
        "basic": ok(basic),
        "guild": ok(guild),
        "title": ok(title),
        "stat": ok(stat),
    }
