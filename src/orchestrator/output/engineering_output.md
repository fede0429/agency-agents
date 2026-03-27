# Engineering Pipeline Output

## Feature Request
Design a 'services/bgm_matcher.py' with an 'AIBGMMatcher' class. It should use an LLM (AsyncOpenAI via config) to analyze a video script and determine its emotional mood and optimal music genre. Then, it selects a matching '.mp3' from a mock local inventory. Provide an 'add_bgm(video_path, script_context)' async method that uses ffmpeg to mix the original video's audio with the selected BGM track at a 15% volume level, outputting a final mixed video. Show how to inject this into 'core/orchestrator.py' right after the VideoStitcher step completes.

## Architecture Plan
To implement the `services/bgm_matcher.py` with the `AIBGMMatcher` class and integrate it into the existing architecture, here is a detailed technical implementation plan:

### Step 1: File and Class Creation

#### 1. Create `services/bgm_matcher.py`

- **AIBGMMatcher Class**
  - **Attributes**:
    - `llm_client`: An instance of `AsyncOpenAI` configured via a configuration file to analyze the script.
    - `music_inventory`: A dictionary to mock local inventory mapping moods to `.mp3` files.
  - **Methods**:
    - `__init__(self, llm_config_path: str)`: Initializes the LLM client and loads the music inventory.
    - `analyze_script(self, script_context: str) -> str`: Uses the LLM to determine the emotional mood of the script.
    - `select_music(self, mood: str) -> str`: Selects an appropriate `.mp3` file from the inventory based on the mood.
    - `add_bgm(self, video_path: str, script_context: str) -> str`: Asynchronously mixes the selected BGM track with the original video using `ffmpeg` and outputs the final video file path.

### Step 2: Modify `core/orchestrator.py`

#### 2. Inject `AIBGMMatcher` into `core/orchestrator.py`

- **Step in Orchestrator**:
  - After the `VideoStitcher` step, integrate the `AIBGMMatcher` to process the video.
  - Assume that `VideoStitcher`'s output is passed onto this step as `stitched_video_path`.

- **Integration Method**:
  - `add_background_music(self, stitched_video_path: str, script_context: str) -> str`: Uses `AIBGMMatcher` to add background music to the stitched video.

### Detailed Implementation

#### 1. `services/bgm_matcher.py`

```python
# services/bgm_matcher.py

import asyncio
from openai import AsyncOpenAI  # Hypothetical async OpenAI client
import ffmpeg

class AIBGMMatcher:
    def __init__(self, llm_config_path: str):
        self.llm_client = AsyncOpenAI(config_path=llm_config_path)
        self.music_inventory = {
            "happy": "happy_tune.mp3",
            "sad": "sad_melody.mp3",
            "exciting": "exciting_beat.mp3",
            # Add more mood-to-file mappings as needed
        }

    async def analyze_script(self, script_context: str) -> str:
        response = await self.llm_client.analyze(script_context)
        mood = response.get("mood")
        return mood

    def select_music(self, mood: str) -> str:
        return self.music_inventory.get(mood, "default_track.mp3")

    async def add_bgm(self, video_path: str, script_context: str) -> str:
        mood = await self.analyze_script(script_context)
        bgm_file = self.select_music(mood)
        
        output_video_path = video_path.replace(".mp4", "_with_bgm.mp4")
        
        # Mix audio with ffmpeg
        (
            ffmpeg
            .input(video_path)
            .output(bgm_file)
            .filter('volume', 0.15)
            .output(output_video_path)
            .run_async()
        )
        
        return output_video_path
```

#### 2. `core/orchestrator.py`

```python
# core/orchestrator.py

from services.bgm_matcher import AIBGMMatcher

class Orchestrator:
    def __init__(self):
        # Initialize other components
        self.bgm_matcher = AIBGMMatcher(llm_config_path='config/llm_config.json')

    async def execute(self, stitched_video_path: str, script_context: str):
        # Other steps
        video_with_music = await self.add_background_music(stitched_video_path, script_context)
        return video_with_music

    async def add_background_music(self, stitched_video_path: str, script_context: str) -> str:
        return await self.bgm_matcher.add_bgm(stitched_video_path, script_context)
```

### Summary of Changes

- **New File**: `services/bgm_matcher.py` with `AIBGMMatcher` class for script analysis and BGM addition.
- **Modified File**: `core/orchestrator.py` to integrate the `AIBGMMatcher` into the orchestration workflow.

### Considerations

- **Trade-offs**: Integrating the LLM increases external dependency complexity but enhances contextual music selection. Ensure fallback mechanisms are in place if LLM calls fail.
- **Testing**: Verify that the LLM analysis and ffmpeg integration work as expected via unit and integration tests.
- **Configuration**: Ensure `llm_config.json` is correctly set up to authenticate and configure `AsyncOpenAI`.

## Developer Code
Certainly, here is the implementation according to the Architect's plan:

```python
# filepath: services/bgm_matcher.py

import asyncio
from openai import AsyncOpenAI  # Hypothetical async OpenAI client
import ffmpeg

class AIBGMMatcher:
    def __init__(self, llm_config_path: str):
        self.llm_client = AsyncOpenAI(config_path=llm_config_path)
        self.music_inventory = {
            "happy": "happy_tune.mp3",
            "sad": "sad_melody.mp3",
            "exciting": "exciting_beat.mp3",
            # Add more mood-to-file mappings as needed
        }

    async def analyze_script(self, script_context: str) -> str:
        response = await self.llm_client.analyze(script_context)
        mood = response.get("mood")
        return mood

    def select_music(self, mood: str) -> str:
        return self.music_inventory.get(mood, "default_track.mp3")

    async def add_bgm(self, video_path: str, script_context: str) -> str:
        mood = await self.analyze_script(script_context)
        bgm_file = self.select_music(mood)
        
        output_video_path = video_path.replace(".mp4", "_with_bgm.mp4")
        
        # Mix audio with ffmpeg
        (
            ffmpeg
            .input(video_path)
            .output(bgm_file)
            .filter('volume', 0.15)
            .output(output_video_path)
            .run_async()
        )
        
        return output_video_path
```

```python
# filepath: core/orchestrator.py

from services.bgm_matcher import AIBGMMatcher

class Orchestrator:
    def __init__(self):
        # Initialize other components
        self.bgm_matcher = AIBGMMatcher(llm_config_path='config/llm_config.json')

    async def execute(self, stitched_video_path: str, script_context: str):
        # Other steps
        video_with_music = await self.add_background_music(stitched_video_path, script_context)
        return video_with_music

    async def add_background_music(self, stitched_video_path: str, script_context: str) -> str:
        return await self.bgm_matcher.add_bgm(stitched_video_path, script_context)
```

### Summary of Changes

- **New File**: `services/bgm_matcher.py` is created with the `AIBGMMatcher` class for script analysis and background music addition.
- **Modified File**: `core/orchestrator.py` now integrates the `AIBGMMatcher` into the orchestration workflow.

### Considerations

- **Trade-offs**: Integrating the LLM increases external dependency complexity but enhances contextual music selection. Ensure fallback mechanisms are in place if LLM calls fail.
- **Testing**: Verify that the LLM analysis and ffmpeg integration work as expected via unit and integration tests.
- **Configuration**: Ensure `llm_config.json` is correctly set up to authenticate and configure `AsyncOpenAI`.

## Code Review & Final Code
## Summary of the Review

Overall, the implementation provides a good foundation for the `AIBGMMatcher` class and its integration into the orchestrator. However, there are some critical issues that need addressing to ensure functionality and avoid runtime errors. Key areas of concern include the ffmpeg usage, error handling, and missing imports.

### Key Concerns

1. **Correctness:**
   - The ffmpeg command in `add_bgm` is incorrect. The `ffmpeg` library is not properly used to mix the audio tracks, and the volume filter is not correctly applied.

2. **Error Handling:**
   - The code lacks error handling for both LLM analysis and ffmpeg processing. This could lead to unhandled exceptions disrupting the flow.

3. **Imports:**
   - Some necessary imports are missing, notably for handling asynchronous operations (`asyncio`) and the ffmpeg command.

4. **Performance:**
   - The current implementation of `ffmpeg` might block the event loop if not correctly awaited or handled asynchronously.

5. **Testing:**
   - There should be a provision to mock the LLM and ffmpeg operations for unit testing.

### Detailed Review

#### 🔴 Blockers

1. **Correctness: ffmpeg Usage**
   - The current ffmpeg command does not correctly mix the audio. The `output` method is incorrectly used for the background music file.
   
   ```python
   # Incorrect ffmpeg usage
   (
       ffmpeg
       .input(video_path)
       .output(bgm_file)  # This is incorrect; you should not output bgm_file here
       .filter('volume', 0.15)
       .output(output_video_path)
       .run_async()
   )
   ```

   **Suggestion:** Use the `filter_complex` to correctly mix the audio tracks and set the background music volume.

   ```python
   # Correct ffmpeg usage
   (
       ffmpeg
       .input(video_path)
       .input(bgm_file)
       .filter_complex('[1]volume=0.15[a];[0][a]amix=inputs=2:duration=first')
       .output(output_video_path)
       .run_async(overwrite_output=True)
   )
   ```

2. **Missing Error Handling**
   - Add try-except blocks around the LLM call and ffmpeg processing to handle potential exceptions.

   **Suggestion:**

   ```python
   async def analyze_script(self, script_context: str) -> str:
       try:
           response = await self.llm_client.analyze(script_context)
           mood = response.get("mood")
           return mood
       except Exception as e:
           # Log the error and handle fallback
           print(f"Error analyzing script: {e}")
           return "default"
   ```

   ```python
   async def add_bgm(self, video_path: str, script_context: str) -> str:
       try:
           mood = await self.analyze_script(script_context)
           bgm_file = self.select_music(mood)
           
           output_video_path = video_path.replace(".mp4", "_with_bgm.mp4")
           
           (
               ffmpeg
               .input(video_path)
               .input(bgm_file)
               .filter_complex('[1]volume=0.15[a];[0][a]amix=inputs=2:duration=first')
               .output(output_video_path)
               .run_async(overwrite_output=True)
           )
           
           return output_video_path
       except Exception as e:
           print(f"Error adding BGM: {e}")
           return video_path  # Return the original path if processing fails
   ```

#### 🟡 Suggestions

1. **Imports and Asynchronous Handling:**
   - Ensure that all necessary imports are included for asynchronous operations and error handling.
   - Consider using `run_async()` with proper asyncio handling to avoid blocking.

2. **Testing:**
   - Create mocks for `AsyncOpenAI` and `ffmpeg` during unit testing to simulate their behavior without real network calls or file operations.

### Final Code

```python
# filepath: services/bgm_matcher.py

import asyncio
from openai import AsyncOpenAI  # Hypothetical async OpenAI client
import ffmpeg

class AIBGMMatcher:
    def __init__(self, llm_config_path: str):
        self.llm_client = AsyncOpenAI(config_path=llm_config_path)
        self.music_inventory = {
            "happy": "happy_tune.mp3",
            "sad": "sad_melody.mp3",
            "exciting": "exciting_beat.mp3",
            # Add more mood-to-file mappings as needed
        }

    async def analyze_script(self, script_context: str) -> str:
        try:
            response = await self.llm_client.analyze(script_context)
            mood = response.get("mood")
            return mood
        except Exception as e:
            print(f"Error analyzing script: {e}")
            return "default"

    def select_music(self, mood: str) -> str:
        return self.music_inventory.get(mood, "default_track.mp3")

    async def add_bgm(self, video_path: str, script_context: str) -> str:
        try:
            mood = await self.analyze_script(script_context)
            bgm_file = self.select_music(mood)
            
            output_video_path = video_path.replace(".mp4", "_with_bgm.mp4")
            
            (
                ffmpeg
                .input(video_path)
                .input(bgm_file)
                .filter_complex('[1]volume=0.15[a];[0][a]amix=inputs=2:duration=first')
                .output(output_video_path)
                .run_async(overwrite_output=True)
            )
            
            return output_video_path
        except Exception as e:
            print(f"Error adding BGM: {e}")
            return video_path
```

```python
# filepath: core/orchestrator.py

from services.bgm_matcher import AIBGMMatcher

class Orchestrator:
    def __init__(self):
        # Initialize other components
        self.bgm_matcher = AIBGMMatcher(llm_config_path='config/llm_config.json')

    async def execute(self, stitched_video_path: str, script_context: str):
        # Other steps
        video_with_music = await self.add_background_music(stitched_video_path, script_context)
        return video_with_music

    async def add_background_music(self, stitched_video_path: str, script_context: str) -> str:
        return await self.bgm_matcher.add_bgm(stitched_video_path, script_context)
```

### Encouragement and Next Steps

Great job on integrating the LLM to enhance the contextual music selection! Once the suggested changes are implemented, consider setting up a comprehensive test suite to ensure robustness and reliability. Keep up the excellent work on improving the Commercial Engine's capabilities!
