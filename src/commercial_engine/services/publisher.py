"""
services/publisher.py
=====================
Multi-platform video publishing with REAL API structures.

Each publisher:
  1. Accepts config with OAuth tokens/API keys
  2. Uploads the binary video file (multipart)
  3. Is fully async (aiohttp) to avoid blocking the event loop
  4. Returns structured result with platform-specific video URL

Supported Platforms:
  - TikTok (Content Posting API v2)
  - YouTube Shorts (YouTube Data API v3 resumable upload)
  - Douyin (抖音开放平台 video.upload)
  - Instagram Reels (Instagram Graph API container flow)
"""
from abc import ABC, abstractmethod
import os
import json
import logging
import aiohttp
from pathlib import Path

class PublisherError(Exception):
    """Base exception for publishing failures."""
    pass

class PublisherAuthenticationError(PublisherError):
    """Raised when authentication tokens are missing or invalid."""
    pass

class PublisherTokenExpiredError(PublisherAuthenticationError):
    """Raised specifically when a token is expired and needs refresh."""
    pass

class PublisherAPIError(PublisherError):
    """Raised when the platform API returns an error response."""
    pass

logger = logging.getLogger(__name__)


class BasePublisher(ABC):
    """Abstract base class for platform-specific publishers."""
    
    # Constants to eliminate magic numbers
    MAX_TIKTOK_TITLE_LEN = 150
    MAX_YT_TITLE_LEN = 100
    MAX_YT_DESC_LEN = 5000
    MAX_YT_TAGS = 30
    YT_CATEGORY_ID = "22"

    def __init__(self, config: dict):
        self.config = config

    @abstractmethod
    async def publish(self, video_path: str, metadata: dict) -> dict:
        """
        Publish a video to the platform.

        :param video_path: Absolute path to the video file.
        :param metadata: Dict with 'title', 'description', 'tags'.
        :return: Dict with 'status', 'platform', 'video_url' or 'error'.
        """
        pass

    def _validate_file(self, video_path: str) -> Path:
        """Validate that a video file exists and is readable."""
        p = Path(video_path)
        if not p.exists():
            raise FileNotFoundError(f"Video file not found: {video_path}")
        if p.stat().st_size == 0:
            raise ValueError(f"Video file is empty: {video_path}")
        return p

    async def _refresh_token_if_needed(self, platform: str) -> str:
        """
        Attempts to refresh the OAuth token using a configured callback.
        Updates the token in self.config and returns it.
        """
        refresh_callback = self.config.get(platform, {}).get("refresh_callback")
        if not refresh_callback:
            raise PublisherAuthenticationError(f"Token expired and no refresh_callback provided for platform: {platform}")
        
        try:
            import inspect
            if inspect.iscoroutinefunction(refresh_callback):
                new_token = await refresh_callback()
            else:
                new_token = refresh_callback()
                
            if not new_token:
                raise ValueError("Refresh callback returned empty token")
                
            self.config[platform]["access_token"] = new_token
            logger.info(f"[{platform.capitalize()}] Successfully refreshed OAuth token.")
            return new_token
        except Exception as e:
            logger.error(f"[{platform.capitalize()}] Token refresh failed: {e}")
            raise PublisherAuthenticationError(f"Failed to refresh {platform} token: {e}") from e


# ─── TikTok (Content Posting API v2) ────────────────────────────────────────

class TikTokPublisher(BasePublisher):
    """
    TikTok Content Posting API v2.
    Requires: access_token from OAuth2 flow.
    Flow: POST /v2/post/publish/video/init → upload video → finalize
    Docs: https://developers.tiktok.com/doc/content-posting-api-get-started
    """

    async def publish(self, video_path: str, metadata: dict, is_retry: bool = False) -> dict:
        access_token = self.config.get("tiktok", {}).get("access_token")
        if not access_token:
            raise PublisherAuthenticationError("No TikTok access_token configured")

        file_path_obj = self._validate_file(video_path)
        logger.info(f"[TikTok] Uploading {file_path_obj.name} ({file_path_obj.stat().st_size / 1024 / 1024:.1f} MB)")

        async with aiohttp.ClientSession() as session:
            try:
                init_data = await self._init_upload(session, access_token, file_path_obj, metadata)
            except PublisherTokenExpiredError:
                if not is_retry:
                    logger.warning("[TikTok] 401 Unauthorized during init. Attempting token refresh...")
                    await self._refresh_token_if_needed("tiktok")
                    return await self.publish(video_path, metadata, is_retry=True)
                raise PublisherAuthenticationError("TikTok token refresh failed or token still rejected after retry.")
                
            upload_url = init_data.get("data", {}).get("upload_url")
            publish_id = init_data.get("data", {}).get("publish_id")

            if not upload_url:
                raise PublisherAPIError("No upload_url in init response")

            await self._upload_binary(session, upload_url, file_path_obj)

            logger.info(f"[TikTok] Upload complete. publish_id={publish_id}")
            return {"status": "success", "platform": "TikTok", "publish_id": publish_id}

    async def _init_upload(self, session: aiohttp.ClientSession, access_token: str, file_path_obj: Path, metadata: dict) -> dict:
        init_url = "https://open.tiktokapis.com/v2/post/publish/video/init/"
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }
        title = metadata.get("title", "")[:self.MAX_TIKTOK_TITLE_LEN]
        init_body = {
            "post_info": {
                "title": title,
                "privacy_level": "SELF_ONLY",
                "disable_comment": False,
            },
            "source_info": {
                "source": "FILE_UPLOAD",
                "video_size": file_path_obj.stat().st_size,
            }
        }

        async with session.post(init_url, headers=headers, json=init_body) as resp:
            if resp.status == 401:
                raise PublisherTokenExpiredError("TikTok token expired")
                
            if resp.status != 200:
                error_body = await resp.text()
                raise PublisherAPIError(f"Init failed ({resp.status}): {error_body}")
            return await resp.json()

    async def _upload_binary(self, session: aiohttp.ClientSession, upload_url: str, file_path_obj: Path) -> None:
        with open(file_path_obj, "rb") as f:
            async with session.put(
                upload_url,
                data=f,
                headers={"Content-Type": "video/mp4"}
            ) as upload_resp:
                if upload_resp.status not in (200, 201):
                    error_body = await upload_resp.text()
                    raise PublisherAPIError(f"Upload failed ({upload_resp.status}): {error_body}")


# ─── YouTube Shorts (YouTube Data API v3) ───────────────────────────────────

class YouTubeShortsPublisher(BasePublisher):
    """
    YouTube Data API v3 resumable upload.
    Requires: access_token from Google OAuth2 (youtube.upload scope).
    Docs: https://developers.google.com/youtube/v3/guides/uploading_a_video
    """

    async def publish(self, video_path: str, metadata: dict, is_retry: bool = False) -> dict:
        access_token = self.config.get("youtube", {}).get("access_token")
        if not access_token:
            raise PublisherAuthenticationError("No YouTube access_token configured")

        file_path_obj = self._validate_file(video_path)
        logger.info(f"[YouTube] Uploading {file_path_obj.name} ({file_path_obj.stat().st_size / 1024 / 1024:.1f} MB)")

        async with aiohttp.ClientSession() as session:
            try:
                upload_url = await self._init_upload(session, access_token, file_path_obj, metadata)
            except PublisherTokenExpiredError:
                if not is_retry:
                    logger.warning("[YouTube] 401 Unauthorized during init. Attempting token refresh...")
                    await self._refresh_token_if_needed("youtube")
                    return await self.publish(video_path, metadata, is_retry=True)
                raise PublisherAuthenticationError("YouTube token refresh failed or token still rejected after retry.")

            if not upload_url:
                raise PublisherAPIError("No Location header in init response")

            result = await self._upload_binary(session, upload_url, file_path_obj)

            video_id = result.get("id", "unknown")
            logger.info(f"[YouTube] Upload complete. video_id={video_id}")
            return {
                "status": "success",
                "platform": "YouTube Shorts",
                "video_id": video_id,
                "video_url": f"https://youtube.com/shorts/{video_id}",
            }

    async def _init_upload(self, session: aiohttp.ClientSession, access_token: str, file_path_obj: Path, metadata: dict) -> str:
        init_url = "https://www.googleapis.com/upload/youtube/v3/videos?uploadType=resumable&part=snippet,status"
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json; charset=UTF-8",
            "X-Upload-Content-Type": "video/mp4",
            "X-Upload-Content-Length": str(file_path_obj.stat().st_size),
        }
        title = metadata.get("title", "AI Video")[:self.MAX_YT_TITLE_LEN]
        desc = metadata.get("description", "")[:self.MAX_YT_DESC_LEN]
        tags = metadata.get("tags", [])[:self.MAX_YT_TAGS]
        
        body = {
            "snippet": {
                "title": title,
                "description": desc,
                "tags": tags,
                "categoryId": self.YT_CATEGORY_ID,
            },
            "status": {
                "privacyStatus": "private",
                "selfDeclaredMadeForKids": False,
            }
        }

        async with session.post(init_url, headers=headers, json=body) as resp:
            if resp.status == 401:
                raise PublisherTokenExpiredError("YouTube token expired")
                
            if resp.status != 200:
                error_body = await resp.text()
                raise PublisherAPIError(f"Init failed ({resp.status}): {error_body}")
            return resp.headers.get("Location", "")

    async def _upload_binary(self, session: aiohttp.ClientSession, upload_url: str, file_path_obj: Path) -> dict:
        with open(file_path_obj, "rb") as f:
            async with session.put(
                upload_url,
                data=f,
                headers={"Content-Type": "video/mp4"}
            ) as upload_resp:
                if upload_resp.status not in (200, 201):
                    error_body = await upload_resp.text()
                    raise PublisherAPIError(f"Upload failed ({upload_resp.status}): {error_body}")
                return await upload_resp.json()


# ─── Douyin (抖音开放平台) ──────────────────────────────────────────────────

class DouyinPublisher(BasePublisher):
    """
    Douyin Open Platform video upload.
    Requires: access_token from Douyin OAuth2.
    Flow: POST /video/upload → POST /video/create
    Docs: https://developer.open-douyin.com/
    """

    async def publish(self, video_path: str, metadata: dict) -> dict:
        access_token = self.config.get("douyin", {}).get("access_token")
        open_id = self.config.get("douyin", {}).get("open_id")
        if not access_token or not open_id:
            raise PublisherAuthenticationError("No Douyin access_token or open_id configured")

        file_path_obj = self._validate_file(video_path)
        logger.info(f"[Douyin] Uploading {file_path_obj.name} ({file_path_obj.stat().st_size / 1024 / 1024:.1f} MB)")

        async with aiohttp.ClientSession() as session:
            video_id = await self._upload_binary(session, access_token, file_path_obj)
            await self._create_video(session, access_token, open_id, video_id, metadata)
            
            logger.info(f"[Douyin] Upload complete. video_id={video_id}")
            return {"status": "success", "platform": "Douyin", "video_id": video_id}

    async def _upload_binary(self, session: aiohttp.ClientSession, access_token: str, file_path_obj: Path) -> str:
        upload_url = "https://open.douyin.com/api/douyin/v1/video/upload_video/"
        headers = {"access-token": access_token}
        
        with open(file_path_obj, "rb") as f:
            form = aiohttp.FormData()
            form.add_field("video", f, filename=file_path_obj.name, content_type="video/mp4")
            
            async with session.post(upload_url, data=form, headers=headers) as resp:
                if resp.status != 200:
                    error_body = await resp.text()
                    raise PublisherAPIError(f"Upload failed ({resp.status}): {error_body}")
                upload_data = await resp.json()

        video_id = upload_data.get("data", {}).get("video", {}).get("video_id")
        if not video_id:
            raise PublisherAPIError(f"No video_id in upload response: {upload_data}")
        return video_id

    async def _create_video(self, session: aiohttp.ClientSession, access_token: str, open_id: str, video_id: str, metadata: dict) -> None:
        create_url = "https://open.douyin.com/api/douyin/v1/video/create_video/"
        headers = {"access-token": access_token}
        title = metadata.get('title', '')
        desc = metadata.get('description', '')
        
        create_body = {
            "video_id": video_id,
            "text": f"{title} {desc}".strip(),
            "open_id": open_id,
        }

        async with session.post(create_url, json=create_body, headers=headers) as resp:
            if resp.status != 200:
                error_body = await resp.text()
                raise PublisherAPIError(f"Create failed ({resp.status}): {error_body}")


# ─── Instagram Reels (Instagram Graph API) ──────────────────────────────────

class InstagramReelsPublisher(BasePublisher):
    """
    Instagram Graph API container-based publish.
    Requires: access_token + ig_user_id from Facebook OAuth2.
    Flow: POST /media (container) → POST /media_publish
    Docs: https://developers.facebook.com/docs/instagram-api/guides/content-publishing
    """

    async def publish(self, video_path: str, metadata: dict) -> dict:
        access_token = self.config.get("instagram", {}).get("access_token")
        ig_user_id = self.config.get("instagram", {}).get("ig_user_id")
        if not access_token or not ig_user_id:
            raise PublisherAuthenticationError("No Instagram access_token or ig_user_id configured")

        video_url = self.config.get("instagram", {}).get("video_host_url")
        if not video_url:
            raise PublisherAPIError("Instagram requires a public video URL (video_host_url). Host the video first.")

        logger.info(f"[Instagram] Creating Reels container for video: {video_url}")

        async with aiohttp.ClientSession() as session:
            creation_id = await self._create_container(session, access_token, ig_user_id, video_url, metadata)
            media_id = await self._publish_container(session, access_token, ig_user_id, creation_id)

            logger.info(f"[Instagram] Reels published. media_id={media_id}")
            return {"status": "success", "platform": "Instagram Reels", "media_id": media_id}

    async def _create_container(self, session: aiohttp.ClientSession, access_token: str, ig_user_id: str, video_url: str, metadata: dict) -> str:
        container_url = f"https://graph.facebook.com/v19.0/{ig_user_id}/media"
        title = metadata.get('title', '')
        desc = metadata.get('description', '')
        
        container_params = {
            "media_type": "REELS",
            "video_url": video_url,
            "caption": f"{title} - {desc}".strip(),
            "access_token": access_token,
        }

        async with session.post(container_url, params=container_params) as resp:
            if resp.status != 200:
                error_body = await resp.text()
                raise PublisherAPIError(f"Container failed ({resp.status}): {error_body}")
            container_data = await resp.json()

        creation_id = container_data.get("id")
        if not creation_id:
            raise PublisherAPIError("No creation_id in container response")
        return creation_id

    async def _publish_container(self, session: aiohttp.ClientSession, access_token: str, ig_user_id: str, creation_id: str) -> str:
        publish_url = f"https://graph.facebook.com/v19.0/{ig_user_id}/media_publish"
        publish_params = {
            "creation_id": creation_id,
            "access_token": access_token,
        }

        async with session.post(publish_url, params=publish_params) as resp:
            if resp.status != 200:
                error_body = await resp.text()
                raise PublisherAPIError(f"Publish failed ({resp.status}): {error_body}")
            publish_data = await resp.json()

        return publish_data.get("id")
