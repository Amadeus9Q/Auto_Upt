from __future__ import annotations

import hashlib
from pathlib import Path
from uuid import uuid4

from fastapi import UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.config import get_settings
from backend.app.models.asset import ContentAssetRecord
from backend.app.schemas.asset import AssetResponse


class AssetService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.settings = get_settings()

    async def create_asset(
        self,
        upload: UploadFile,
        asset_type: str,
        purpose: str,
    ) -> ContentAssetRecord:
        storage_dir = Path(self.settings.asset_storage_dir)
        storage_dir.mkdir(parents=True, exist_ok=True)

        original_filename = Path(upload.filename or "asset.bin").name
        suffix = Path(original_filename).suffix
        filename = f"{uuid4().hex}{suffix}"
        file_path = storage_dir / filename
        sha256 = hashlib.sha256()
        file_size = 0

        with file_path.open("wb") as output:
            while chunk := await upload.read(1024 * 1024):
                file_size += len(chunk)
                sha256.update(chunk)
                output.write(chunk)

        record = ContentAssetRecord(
            asset_type=asset_type,
            purpose=purpose,
            original_filename=original_filename,
            filename=filename,
            content_type=upload.content_type or "application/octet-stream",
            file_path=str(file_path),
            file_size=file_size,
            sha256=sha256.hexdigest(),
            asset_metadata={},
        )
        self.session.add(record)
        await self.session.commit()
        await self.session.refresh(record)
        return record

    async def list_assets(self) -> list[ContentAssetRecord]:
        result = await self.session.execute(
            select(ContentAssetRecord).order_by(ContentAssetRecord.created_at.desc())
        )
        return list(result.scalars().all())

    async def get_asset(self, asset_id: str) -> ContentAssetRecord | None:
        return await self.session.get(ContentAssetRecord, asset_id)

    async def delete_asset(self, asset_id: str) -> ContentAssetRecord | None:
        record = await self.get_asset(asset_id)
        if record is None:
            return None
        await self.session.delete(record)
        await self.session.commit()
        path = Path(record.file_path)
        if path.exists():
            path.unlink()
        return record

    def to_response(self, record: ContentAssetRecord) -> AssetResponse:
        return AssetResponse(
            asset_id=record.id,
            asset_type=record.asset_type,
            purpose=record.purpose,
            original_filename=record.original_filename,
            filename=record.filename,
            content_type=record.content_type,
            file_size=record.file_size,
            sha256=record.sha256,
            url=f"{self.settings.public_base_url.rstrip('/')}/api/v1/assets/{record.id}/download",
            metadata=record.asset_metadata,
            created_at=record.created_at,
        )
