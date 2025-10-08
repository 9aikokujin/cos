from contextlib import asynccontextmanager
from typing import List, Dict, Any, Optional, Tuple
from fastapi import Body, FastAPI, APIRouter, Path, Query, HTTPException
from datetime import date
from clickhouse_client import ClickHouseClient
from schema import CreateVideoView, VideoView
from fastapi.middleware.cors import CORSMiddleware

ch_client = ClickHouseClient()

@asynccontextmanager
async def lifespan(app: FastAPI):
    await ch_client.init()
    await ch_client.create_views_table()
    yield


app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
    allow_origin_regex=None,
)


router = APIRouter(
    prefix="/analytics",
    tags=["analytics"]
)


@router.get("/hashtags", response_model=List[str])
async def get_hashtags(
    user_id: Optional[int] = Query(None, description="Filter hashtags by user ID")
):
    hashtags = await ch_client.get_unique_hashtags(user_id=user_id)
    return hashtags


@router.post("/video")
async def insert_video_view(payload: List[CreateVideoView] = Body(...)):
    await ch_client.insert_video_views(payload)
    return {"status": "ok", "inserted": len(payload)}


@router.get("/all")
async def get_all_data_simple():
    try:
        raw_data: List[Tuple] = await ch_client.get_everything()

        final_result = [list(row) for row in raw_data]

        return final_result

    except RuntimeError as re:
        raise HTTPException(status_code=500, detail=str(re))
    except Exception as e:
        print(e)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/analytics", response_model=List[Dict[str, Any]])
async def get_user_analytics_filtered(
    user_id: Optional[int] = Query(None, title="The ID of the user", ge=1),
    group_by: List[str] = Query(
        ...,
        title="Fields to group by",
        description="List of fields to group results by. Supported: day, hashtag, channel_id, channel_type. At least one is required.",
    ),
    hashtag: Optional[str] = Query(None, title="Filter by hashtag"),
    channel_id: Optional[int] = Query(None, title="Filter by channel ID", ge=1),
    channel_type: Optional[List[str]] = Query(None, title="Filter by channel types (multiple allowed)"),
    video_url: Optional[str] = Query(None, title="Filter by video URL"),
    date_from: Optional[date] = Query(None, title="Filter from date (inclusive)"),
    date_to: Optional[date] = Query(None, title="Filter to date (inclusive)"),
):
    supported_group_by = {'day', 'hashtag', 'channel_id', 'channel_type'}
    if not group_by or not set(group_by).issubset(supported_group_by):
        raise HTTPException(
            status_code=422,
            detail=f"group_by must be a list containing one or more of: {supported_group_by}"
        )

    try:
        result = await ch_client.user_analytics_filtered(
            user_id=user_id,
            group_by_fields=group_by,
            filter_hashtag=hashtag,
            filter_channel_id=channel_id,
            filter_channel_type=channel_type,
            filter_video_url=video_url,
            filter_date_from=date_from,
            filter_date_to=date_to,
        )
        return result
    except RuntimeError as re:
        raise HTTPException(status_code=500, detail=str(re))
    except ValueError as ve:
        raise HTTPException(status_code=422, detail=str(ve))
    except Exception as e:
        print("❌ Ошибка в user_analytics_filtered:")
        print(f"  Тип ошибки: {type(e).__name__}")
        print(f"  Сообщение: {str(e)}")
        # print(f"  Query:\n{query}")
        # print(f"  Params: {params}")
        import traceback
        print(f"  Traceback:\n{traceback.format_exc()}")
        raise RuntimeError(f"Failed to execute analytics query: {str(e)}")

app.include_router(router)
