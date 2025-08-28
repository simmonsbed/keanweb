# main.py — 웹 전용 백엔드 v0
import os, asyncio
from urllib.parse import quote
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import httpx

load_dotenv()
NX_API_KEY = os.getenv("NX_API_KEY")
if not NX_API_KEY:
    raise RuntimeError("NX_API_KEY not set in .env")

BASE = "https://open.api.nexon.com/heroes/v2"
HDRS = {"x-nxopen-api-key": NX_API_KEY}

app = FastAPI(title="Vindictus Tools API (v0)")

# 개발 중엔 * 허용, 배포 시 Pages 도메인만 적어줘!
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 예: ["https://simmonsbed.github.io"]
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
async def health():
    return {"ok": True}

async def get_json(url: str):
    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.get(url, headers=HDRS)
        if r.status_code != 200:
            raise HTTPException(r.status_code, detail=f"Nexon API error: {r.text[:200]}")
        return r.json()

@app.get("/api/id")
async def get_ocid(name: str):
    return await get_json(f"{BASE}/id?character_name={quote(name)}")

@app.get("/api/character")
async def character_aggregate(name: str):
    """닉네임 -> ocid -> 기본/길드/장착타이틀/스탯 한 번에"""
    ocid_data = await get_json(f"{BASE}/id?character_name={quote(name)}")
    ocid = ocid_data.get("ocid")
    if not ocid:
        raise HTTPException(404, detail="캐릭터를 찾을 수 없습니다.")

    async with httpx.AsyncClient(timeout=15, headers=HDRS) as client:
        basic_req = client.get(f"{BASE}/character/basic?ocid={ocid}")
        guild_req = client.get(f"{BASE}/character/guild?ocid={ocid}")
        title_req = client.get(f"{BASE}/character/title-equipment?ocid={ocid}")
        stat_req  = client.get(f"{BASE}/character/stat?ocid={ocid}")

        # ✅ 핵심: asyncio.gather 사용
        basic, guild, title, stat = await asyncio.gather(
            basic_req, guild_req, title_req, stat_req
        )

    def ok(resp: httpx.Response):
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
