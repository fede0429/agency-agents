import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src', 'commercial_engine')))

import unittest
from unittest.mock import AsyncMock, patch, MagicMock
from core.orchestrator import VideoOrchestrator, VideoRequest, PipelineExecutionError
from services.video_intelligence import VideoIntelligenceExtractor, VideoDownloadError

class TestCommercialEngineRefactor(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.config = {
            "video": {"output_dir": "/tmp/test"},
            "publisher": {"enable_tiktok": False},
            "storyboard": {"enabled": False},
            "bgm_matcher": {"enabled": False},
            "viral_copywriter": {"enabled": False},
            "director": {"enabled": False} # Legacy mode
        }
    
    @patch('core.orchestrator.get_model_adapter')
    @patch('core.orchestrator.VideoStitcher')
    @patch('core.orchestrator.FrameChainer')
    @patch('core.orchestrator.ScriptGenerator')
    async def test_orchestrator_legacy_success(self, MockScript, MockFrame, MockStitcher, mock_get_model):
        
        # Setup mocks
        mock_model = MagicMock()
        mock_model.calculate_segments.return_value = [5, 5, 5]
        mock_get_model.return_value = mock_model
        
        mock_script_gen = MockScript.return_value
        mock_script_gen.generate_script = AsyncMock()
        mock_script_gen.generate_script.return_value = MagicMock(num_segments=3, raw_json="{}")
        
        mock_chainer = MockFrame.return_value
        mock_chainer.chain_segments = AsyncMock()
        mock_chainer.chain_segments.return_value = ["/tmp/1.mp4", "/tmp/2.mp4", "/tmp/3.mp4"]
        
        mock_stitch = MockStitcher.return_value
        mock_stitch.stitch = AsyncMock()
        mock_stitch.stitch.return_value = "/tmp/final.mp4"
        
        orchestrator = VideoOrchestrator(self.config)
        
        # We also need to mock preparation
        orchestrator._prepare_context = AsyncMock(return_value=({}, None))
        orchestrator._post_production = AsyncMock(return_value=("/tmp/final.mp4", None, {}, []))
        
        request = VideoRequest(
            user_id=1, chat_id=1, mode="test", model="auto", duration=15, language="en"
        )
        
        result = await orchestrator.generate(request)
        
        self.assertEqual(result.video_path, "/tmp/final.mp4")
        self.assertEqual(result.num_segments, 3)

    @patch('core.orchestrator.get_model_adapter')
    async def test_orchestrator_execution_error_bubbles_up(self, mock_get_model):
        orchestrator = VideoOrchestrator(self.config)
        # Mock prepare context to fail
        orchestrator._prepare_context = AsyncMock(side_effect=Exception("API failure"))
        
        request = VideoRequest(
            user_id=1, chat_id=1, mode="test", model="auto", duration=15, language="en"
        )
        
        with self.assertRaises(PipelineExecutionError):
            await orchestrator.generate(request)

    @patch('services.video_intelligence.asyncio.create_subprocess_exec')
    async def test_video_intelligence_exception(self, mock_exec):
        process_mock = AsyncMock()
        process_mock.communicate = AsyncMock(return_value=(b"", b"youtube-dl error details"))
        process_mock.returncode = 1
        mock_exec.return_value = process_mock
        
        extractor = VideoIntelligenceExtractor({})
        with self.assertRaises(VideoDownloadError):
            await extractor._download_video("https://fake.url")

    @patch('core.orchestrator.VideoStitcher')
    async def test_orchestrator_storyboard_mode(self, MockStitcher):
        # Configure orchestrator to use storyboard agent
        config = dict(self.config)
        
        # Mocks
        mock_storyboard = AsyncMock()
        mock_episode = MagicMock()
        
        class DummyShot:
            def __init__(self, prompt, duration):
                self.prompt = prompt
                self.duration_seconds = duration
                self.camera_movement = "pan right"
                
        mock_episode.shots = [DummyShot("A man running", 3), DummyShot("Close up shoes", 2)]
        mock_episode.title = "Test Storyboard"
        mock_episode.to_dict.return_value = {"title": "Test Storyboard"}
        mock_episode.to_markdown.return_value = "markdown"
        
        mock_storyboard.generate_episode.return_value = mock_episode
        
        mock_registry = AsyncMock()
        
        class DummyResult:
            success = True
            video_url = "http://fake.vid/url"
            error = ""
            
        mock_registry.generate.return_value = DummyResult()
        
        mock_stitch = MockStitcher.return_value
        mock_stitch.stitch = AsyncMock(return_value="/tmp/storyboard_final.mp4")
        
        orchestrator = VideoOrchestrator(config)
        orchestrator.storyboard_agent = mock_storyboard
        orchestrator.video_registry = mock_registry
        orchestrator.video_stitcher = mock_stitch
        
        # Mock prep and post
        orchestrator._prepare_context = AsyncMock(return_value=({"product":"details"}, "url_content"))
        orchestrator._post_production = AsyncMock(return_value=("/tmp/storyboard_final.mp4", None, {}, []))
        
        # Mock file downloading within the orchestrator
        with patch('aiohttp.ClientSession.get') as mock_get:
            mock_resp = AsyncMock()
            mock_resp.status = 200
            mock_resp.read.return_value = b"fake video data"
            
            # Using an async context manager mock
            mock_get.return_value.__aenter__.return_value = mock_resp
            mock_get.return_value.__aexit__.return_value = None
            
            with patch('builtins.open', new_callable=unittest.mock.mock_open):
                request = VideoRequest(
                    user_id=1, chat_id=1, mode="test", model="auto", duration=5, language="en"
                )
                result = await orchestrator.generate(request)
                
        self.assertEqual(result.video_path, "/tmp/storyboard_final.mp4")
        self.assertEqual(result.num_segments, 2)
        self.assertEqual(result.duration, 5) # 3 + 2
        mock_storyboard.generate_episode.assert_called_once()
        self.assertEqual(mock_registry.generate.call_count, 2)
        
    async def test_publisher_refresh_on_401(self):
        from services.publisher import TikTokPublisher, PublisherAuthenticationError
        
        refresh_mock = AsyncMock(return_value="new_token_123")
        config = {
            "tiktok": {
                "access_token": "expired_token",
                "refresh_callback": refresh_mock
            }
        }
        
        publisher = TikTokPublisher(config)
        publisher._validate_file = MagicMock()
        publisher._validate_file.return_value.name = "test.mp4"
        publisher._validate_file.return_value.stat.return_value.st_size = 1024
        
        # We need to mock the aiohttp session used inside publish
        import aiohttp
        
        # First call to post (init) returns 401
        resp_401 = AsyncMock()
        resp_401.status = 401
        resp_401.text.return_value = "Unauthorized"
        
        # Second call to post (init retry) returns 200
        resp_200_init = AsyncMock()
        resp_200_init.status = 200
        resp_200_init.json.return_value = {"data": {"upload_url": "http://fake.upload", "publish_id": "123"}}
        
        # Call to put (upload) returns 200
        resp_200_upload = AsyncMock()
        resp_200_upload.status = 200
        
        with patch('aiohttp.ClientSession.post') as mock_post:
            # We want post to return 401 the first time, 200 the second time
            # Mocking async context managers
            ctx_401 = MagicMock()
            ctx_401.__aenter__.return_value = resp_401
            ctx_401.__aexit__.return_value = None
            
            ctx_200 = MagicMock()
            ctx_200.__aenter__.return_value = resp_200_init
            ctx_200.__aexit__.return_value = None
            
            mock_post.side_effect = [ctx_401, ctx_200]
            
            with patch('aiohttp.ClientSession.put') as mock_put:
                ctx_put = MagicMock()
                ctx_put.__aenter__.return_value = resp_200_upload
                ctx_put.__aexit__.return_value = None
                mock_put.return_value = ctx_put
                
                with patch('builtins.open', new_callable=unittest.mock.mock_open):
                    result = await publisher.publish("/tmp/test.mp4", {"title": "Test"})
                    
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["publish_id"], "123")
        refresh_mock.assert_called_once()
        self.assertEqual(config["tiktok"]["access_token"], "new_token_123")


if __name__ == '__main__':
    unittest.main()
