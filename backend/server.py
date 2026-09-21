"""FastAPI 后端 — 金沙江流域水文智能 Agent API"""

import sys
import os
from datetime import datetime
from typing import Optional

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from agent.executor import run_agent
from agent.tools import _safe_query

app = FastAPI(
    title="金沙江流域水文智能 Agent API",
    description="DQH + BtPzh 双流域水文数据查询与 AI 分析",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:8501"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None
    chat_history: Optional[list] = None


class ChatResponse(BaseModel):
    output: str
    intent: dict
    plan: list
    corrected: bool
    session_id: str


@app.get("/health")
async def health():
    return {"status": "ok", "service": "jsj-water-agent", "version": "1.0.0"}


@app.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    """Agent 对话接口（同步调用，生产环境建议改为 run_in_executor）"""
    import asyncio

    session_id = req.session_id or datetime.now().strftime("%Y%m%d_%H%M%S")
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(
        None,
        lambda: run_agent(req.message, chat_history=req.chat_history, session_id=session_id),
    )
    return ChatResponse(
        output=result["output"],
        intent=result["intent"],
        plan=result.get("plan", []),
        corrected=result["corrected"],
        session_id=session_id,
    )


@app.get("/basins")
async def list_basins():
    rows = _safe_query("SELECT basin_id, basin_name, basin_type, river, area_km2 FROM basin_metadata")
    return {"data": rows, "count": len(rows)}


@app.get("/stations")
async def list_stations(basin_id: Optional[str] = None):
    if basin_id:
        rows = _safe_query(
            "SELECT station_id, name_cn, lat, lon, is_approximate FROM station_metadata WHERE basin_id=? ORDER BY station_id",
            (basin_id,),
        )
    else:
        rows = _safe_query(
            "SELECT station_id, basin_id, name_cn, lat, lon FROM station_metadata ORDER BY basin_id, station_id"
        )
    return {"data": rows, "count": len(rows)}


@app.get("/dqh/events")
async def dqh_events(resolution: Optional[str] = None):
    sql = "SELECT event_code, resolution, start_time, end_time, timesteps FROM dqh_event_metadata"
    params: tuple = ()
    if resolution:
        sql += " WHERE resolution=?"
        params = (resolution,)
    rows = _safe_query(sql + " ORDER BY resolution, event_code", params)
    return {"data": rows, "count": len(rows)}


@app.get("/dqh/rainfall/{event_code}")
async def dqh_rainfall(event_code: str, resolution: str = "hourly", station_id: str = "", limit: int = 200):
    from agent.tools import query_dqh_rainfall
    raw = query_dqh_rainfall.invoke({"event_code": event_code, "resolution": resolution,
                                     "station_id": station_id, "limit": limit})
    return {"data": raw}


@app.get("/dqh/statistics/{event_code}")
async def dqh_statistics(event_code: str, resolution: str = "hourly"):
    from agent.tools import query_dqh_statistics
    raw = query_dqh_statistics.invoke({"event_code": event_code, "resolution": resolution})
    return {"data": raw}


@app.get("/btpzh/rainfall")
async def btpzh_rainfall(
    start_date: str = Query(...),
    end_date: str = Query(...),
    resolution: str = "daily",
    station_names: str = "",
    limit: int = 200,
):
    from agent.tools import query_btpzh_rainfall
    raw = query_btpzh_rainfall.invoke({"start_date": start_date, "end_date": end_date,
                                       "resolution": resolution, "station_names": station_names,
                                       "limit": limit})
    return {"data": raw}


@app.get("/btpzh/statistics")
async def btpzh_statistics(
    start_date: str = Query(...),
    end_date: str = Query(...),
    resolution: str = "daily",
    station_names: str = "",
):
    from agent.tools import query_btpzh_statistics
    raw = query_btpzh_statistics.invoke({"start_date": start_date, "end_date": end_date,
                                         "resolution": resolution, "station_names": station_names})
    return {"data": raw}


@app.get("/topology/{basin_id}")
async def topology(basin_id: str):
    from knowledge.knowledge_tools import query_basin_topology
    return {"data": query_basin_topology.invoke({"basin_id": basin_id})}


@app.get("/knowledge")
async def knowledge_search(query: str = Query(...), basin_id: str = ""):
    from knowledge.knowledge_tools import search_hydro_knowledge
    return {"data": search_hydro_knowledge.invoke({"query": query, "basin_id": basin_id})}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8765)
