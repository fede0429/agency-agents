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

logger = logging.getLogger(__name__)


class BasePublisher(ABC):
    """Abstract base class for platform-specific publishers."""

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


# ─── TikTok (Content Posting API v2) ────────────────────────────────────────

class TikTokPublisher(BasePublisher):
    """
    TikTok Content Posting API v2.
    Requires: access_token from OAuth2 flow.
    Flow: POST /v2/post/publish/video/init → upload video → finalize
    Docs: https://developers.tiktok.com/doc/content-posting-api-get-started
    """

    async def publish(self, video_path: str, metadata: dict) -> dict:
        access_token = self.config.get("tiktok", {}).get("access_token")
        if not access_token:
            return {"status": "skipped", "platform": "TikTok", "error": "No access_token configured"}

        file = self._validate_file(video_path)
        logger.info(f"[TikTok] Uploading {file.name} ({file.stat().st_size / 1024 / 1024:.1f} MB)")

        try:
            async with aiohttp.ClientSession() as session:
                # Step 1: Initialize upload
                init_url = "https://open.tiktokapis.com/v2/post/publish/video/init/"
                headers = {
                    "Authorization": f"Bearer {access_token}",
                    "Content-Type": "application/json",
                }
                init_body = {
                    "post_info": {
                        "title": metadata.get("title", "")[:150],
                        "privacy_level": "SELF_ONLY",  # Safe default
                        "disable_comment": False,
                    },
                    "source_info": {
                        "source": "FILE_UPLOAD",
                        "video_size": file.stat().st_size,
                    }
                }

                async with session.post(init_url, headers=headers, json=init_body) as resp:
                    if resp.status != 200:
                        body = await resp.text()
                        return {"status": "failed", "platform": "TikTok", "error": f"Init failed ({resp.status}): {body}"}
                    init_data = await resp.json()

                upload_url = init_data.get("data", {}).get("upload_url")
                publish_id = init_data.get("data", {}).get("publish_id")

                if not upload_url:
                    return {"status": "failed", "platform": "TikTok", "error": "No upload_url in init response"}

                # Step 2: Upload binary
                with open(file, "rb") as f:
                    async with session.put(
                        upload_url,
                        data=f,
                        headers={"Content-Type": "video/mp4"}
                    ) as upload_resp:
                        if upload_resp.status not in (200, 201):
                            body = await upload_resp.text()
                            return {"status": "failed", "platform": "TikTok", "error": f"Upload failed ({upload_resp.status}): {body}"}

                logger.info(f"[TikTok] Upload complete. publish_id={publish_id}")
                return {"status": "success", "platform": "TikTok", "publish_id": publish_id}

        except Exception as e:
            logger.error(f"[TikTok] Publishing failed: {e}")
            return {"status": "failed", "platform": "TikTok", "error": str(e)}


# ─── YouTube Shorts (YouTube Data API v3) ───────────────────────────────────

class YouTubeShortsPublisher(BasePublisher):
    """
    YouTube Data API v3 resumable upload.
    Requires: access_token from Google OAuth2 (youtube.upload scope).
    Docs: https://developers.google.com/youtube/v3/guides/uploading_a_video
    """

    async def publish(self, video_path: str, metadata: dict) -> dict:
        access_token = self.config.get("youtube", {}).get("access_token")
        if not access_token:
            return {"status": "skipped", "platform": "YouTube Shorts", "error": "No access_token configured"}

        file = self._validate_file(video_path)
        logger.info(f"[YouTube] Uploading {file.name} ({file.stat().st_size / 1024 / 1024:.1f} MB)")

        try:
            async with aiohttp.ClientSession() as session:
                # Step 1: Initiate resumable upload
                init_url = "https://www.googleapis.com/upload/youtube/v3/videos?uploadType=resumable&part=snippet,status"
                headers = {
                    "Authorization": f"Bearer {access_token}",
                    "Content-Type": "application/json; charset=UTF-8",
                    "X-Upload-Content-Type": "video/mp4",
                    "X-Upload-Content-Length": str(file.stat().st_size),
                }
                body = {
                    "snippet": {
                        "title": metadata.get("title", "AI Video")[:100],
                        "description": metadata.get("description", "")[:5000],
                        "tags": metadata.get("tags", [])[:30],
                        "categoryId": "22",  # People & Blogs
                    },
                    "status": {
                        "privacyStatus": "private",  # Safe default
                        "selfDeclaredMadeForKids": False,
                    }
                }

                async with session.post(init_url, headers=headers, json=body) as resp:
                    if resp.status != 200:
                        err = await resp.text()
                        return {"status": "failed", "platform": "YouTube Shorts", "error": f"Init failed ({resp.status}): {err}"}
                    upload_url = resp.headers.get("Location")

                if not upload_url:
                    return {"status": "failed", "platform": "YouTube Shorts", "error": "No Location header in init response"}

                # Step 2: Upload binary
                with open(file, "rb") as f:
                    async with session.put(
                        upload_url,
                        data=f,
                        headers={"Content-Type": "video/mp4"}
                    ) as upload_resp:
                        if upload_resp.status not in (200, 201):
                            err = await upload_resp.text()
                            return {"status": "failed", "platform": "YouTube Shorts", "error": f"Upload failed ({upload_resp.status}): {err}"}
                        result = await upload_resp.json()

                video_id = result.get("id", "unknown")
                logger.info(f"[YouTube] Upload complete. video_id={video_id}")
                return {
                    "status": "success",
                    "platform": "YouTube Shorts",
                    "video_id": video_id,
                    "video_url": f"https://youtube.com/shorts/{video_id}",
                }

        except Exception as e:
            logger.error(f"[YouTube] Publishing failed: {e}")
            return {"status": "failed", "platform": "YouTube Shorts", "error": str(e)}


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
            return {"status": "skipped", "platform": "Douyin", "error": "No access_token or open_id configured"}

        file = self._validate_file(video_path)
        logger.info(f"[Douyin] Uploading {file.name} ({file.stat().st_size / 1024 / 1024:.1f} MB)")

        try:
            async with aiohttp.ClientSession() as session:
                # Step 1: Upload video binary
                upload_url = "https://open.douyin.com/api/douyin/v1/video/upload_video/"
                form = aiohttp.FormData()
                form.add_field("video", open(file, "rb"), filename=file.name, content_type="video/mp4")

                headers = {"access-token": access_token}

                async with session.post(upload_url, data=form, headers=headers) as resp:
                    if resp.status != 200:
                        err = await resp.text()
                        return {"status": "failed", "platform": "Douyin", "error": f"Upload failed ({resp.status}): {err}"}
                    upload_data = await resp.json()

                video_id = upload_data.get("data", {}).get("video", {}).get("video_id")
                if not video_id:
                    return {"status": "failed", "platform": "Douyin", "error": f"No video_id in upload response: {upload_data}"}

                # Step 2: Create/publish the video
                create_url = "https://open.douyin.com/api/douyin/v1/video/create_video/"
                create_body = {
                    "video_id": video_id,
                    "text": f"{metadata.get('title', '')} {metadata.get('description', '')}",
                    "open_id": open_id,
                }

                async with session.post(create_url, json=create_body, headers=headers) as resp:
                    if resp.status != 200:
                        err = await resp.text()
                        return {"status": "failed", "platform": "Douyin", "error": f"Create failed ({resp.status}): {err}"}
                    create_data = await resp.json()

                logger.info(f"[Douyin] Upload complete. video_id={video_id}")
                return {"status": "success", "platform": "Douyin", "video_id": video_id}

        except Exception as e:
            logger.error(f"[Douyin] Publishing failed: {e}")
            return {"status": "failed", "platform": "Douyin", "error": str(e)}


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
            return {"status": "skipped", "platform": "Instagram Reels", "error": "No access_token or ig_user_id configured"}

        # Instagram requires a publicly accessible URL for the video
        video_url = self.config.get("instagram", {}).get("video_host_url")
        if not video_url:
            return {"status": "skipped", "platform": "Instagram Reels", "error": "Instagram requires a public video URL (video_host_url). Host the video first."}

        logger.info(f"[Instagram] Creating Reels container for video: {video_url}")

        try:
            async with aiohttp.ClientSession() as session:
                # Step 1: Create media container
                container_url = f"https://graph.facebook.com/v19.0/{ig_user_id}/media"
                container_params = {
                    "media_type": "REELS",
                    "video_url": video_url,
                    "caption": f"{metadata.get('title', '')} - {metadata.get('description', '')}",
                    "access_token": access_token,
                }

                async with session.post(container_url, params=container_params) as resp:
                    if resp.status != 200:
                        err = await resp.text()
                        return {"status": "failed", "platform": "Instagram Reels", "error": f"Container failed ({resp.status}): {err}"}
                    container_data = await resp.json()

                creation_id = container_data.get("id")
                if not creation_id:
                    return {"status": "failed", "platform": "Instagram Reels", "error": "No creation_id in container response"}

                # Step 2: Publish
                publish_url = f"https://graph.facebook.com/v19.0/{ig_user_id}/media_publish"
                publish_params = {
                    "creation_id": creation_id,
                    "access_token": access_token,
                }

                async with session.post(publish_url, params=publish_params) as resp:
                    if resp.status != 200:
                        err = await resp.text()
                        return {"status": "failed", "platform": "Instagram Reels", "error": f"Publish failed ({resp.status}): {err}"}
                    publish_data = await resp.json()

                media_id = publish_data.get("id")
                logger.info(f"[Instagram] Reels published. media_id={media_id}")
                return {"status": "success", "platform": "Instagram Reels", "media_id": media_id}

        except Exception as e:
            logger.error(f"[Instagram] Publishing failed: {e}")
            return {"status": "failed", "platform": "Instagram Reels", "error": str(e)}
