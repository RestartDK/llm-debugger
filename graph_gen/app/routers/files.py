from fastapi import APIRouter, Response, status

router = APIRouter(
    prefix="/files",
    tags=["files"]
)

@router.get("/", status_code=status.HTTP_200_OK)
async def get_most_recent_file(
    files: list
):
    files.sort(reverse=True)

    return files[0]