# Engineering Pipeline Output

## Feature Request
Design and implement a 'ViralCopywriter' module in 'services/viral_copywriter.py'. This class must asynchronously connect to an LLM via OpenAI API to generate viral social media titles, descriptions, and hashtags based on the video context (product data and script). Provide the interface to return a parsed JSON with 'title', 'description', and 'tags'. Then, demonstrate how to inject this inside 'core/orchestrator.py' right before the Multi-Platform Publishing step overrides the hardcoded metadata dictionary.

## Architecture Plan
To implement a `ViralCopywriter` module that generates viral social media content using OpenAI's API, we will follow a structured approach. Let's break this down into a detailed technical implementation plan:

## Implementation Plan

### 1. **Create the `ViralCopywriter` Module**

**File to be created:**
- `services/viral_copywriter.py`

**Design Details:**
- The `ViralCopywriter` class will use Python's `asyncio` to handle asynchronous API calls to OpenAI.
- The class will expose a method `generate_content(video_context)` which takes in `video_context` (containing product data and script).
- The method will connect to OpenAI's API to fetch titles, descriptions, and hashtags, and return them as a parsed JSON.

**Basic Structure:**
```python
# services/viral_copywriter.py

import asyncio
import openai

class ViralCopywriter:
    def __init__(self, api_key):
        openai.api_key = api_key

    async def generate_content(self, video_context):
        prompt = self._create_prompt(video_context)
        response = await openai.Completion.create(
            engine="text-davinci-003",
            prompt=prompt,
            max_tokens=150
        )
        return self._parse_response(response)

    def _create_prompt(self, video_context):
        # Construct a prompt based on video context
        return f"Generate a viral title, description, and hashtags for a video about {video_context}"

    def _parse_response(self, response):
        # Assume the response is structured as a JSON object
        return {
            "title": response.choices[0].text.split('\n')[0],
            "description": response.choices[0].text.split('\n')[1],
            "tags": response.choices[0].text.split('\n')[2].split(',')
        }
```

### 2. **Modify `core/orchestrator.py`**

**File to be modified:**
- `core/orchestrator.py`

**Design Details:**
- Integrate the `ViralCopywriter` class within the `core/orchestrator.py`.
- Inject the viral content generation step right before the Multi-Platform Publishing step.
- Retrieve video context data from the orchestrator's existing context management.

**Modifications:**
```python
# core/orchestrator.py

import asyncio
from services.viral_copywriter import ViralCopywriter

class Orchestrator:
    def __init__(self, config):
        self.config = config
        self.viral_copywriter = ViralCopywriter(config['openai_api_key'])

    async def orchestrate(self, video_context):
        # Generate viral content
        viral_content = await self.viral_copywriter.generate_content(video_context)
        
        # Inject viral content into the metadata
        self._override_metadata_with_viral_content(viral_content)
        
        # Proceed with existing orchestration
        self.multi_platform_publish()

    def _override_metadata_with_viral_content(self, viral_content):
        self.metadata['title'] = viral_content['title']
        self.metadata['description'] = viral_content['description']
        self.metadata['tags'] = viral_content['tags']

    def multi_platform_publish(self):
        # Existing code for publishing
        pass
```

### 3. **Configuration and Testing**

**Additional Files/Modifications:**
- **`config.json`**: Ensure it includes the OpenAI API key.
    ```json
    {
        "openai_api_key": "your_openai_api_key_here"
    }
    ```
- **`tests/integration/test_viral_copywriter.py`**: Create tests to verify the integration and correctness of content generation.

### 4. **Quality Assurance**

- **Concurrency Handling**: Ensure the asyncio loop is managed correctly in the orchestrator to handle multiple requests.
- **Error Handling**: Implement try-except blocks for OpenAI API calls to gracefully handle errors such as connectivity issues or API limits.
- **Logging**: Add appropriate logging to track API request-response cycles and any anomalies.

### 5. **Trade-offs and Considerations**

- **Performance**: Asynchronous API calls can improve throughput but may introduce complexity. Test under load conditions.
- **Security**: Securely manage the OpenAI API key via environment variables or a secure vault.
- **Scalability**: Ensure that the orchestrator can handle multiple concurrent video contexts, scaling up if needed.

This plan lays out a clear path for integrating a viral content generation capability into your existing orchestration backend, leveraging OpenAI's LLM for content creation.

## Developer Code
Certainly! Below are the code implementations based on the Architect's plan for integrating a `ViralCopywriter` module to generate viral social media content using OpenAI's API.

### 1. **Create the `ViralCopywriter` Module**

```python
# filepath: services/viral_copywriter.py

import asyncio
import openai

class ViralCopywriter:
    def __init__(self, api_key):
        openai.api_key = api_key

    async def generate_content(self, video_context):
        prompt = self._create_prompt(video_context)
        response = await openai.Completion.create(
            engine="text-davinci-003",
            prompt=prompt,
            max_tokens=150
        )
        return self._parse_response(response)

    def _create_prompt(self, video_context):
        # Construct a prompt based on video context
        return f"Generate a viral title, description, and hashtags for a video about {video_context}"

    def _parse_response(self, response):
        # Assume the response is structured as a JSON object
        return {
            "title": response.choices[0].text.split('\n')[0],
            "description": response.choices[0].text.split('\n')[1],
            "tags": response.choices[0].text.split('\n')[2].split(',')
        }
```

### 2. **Modify `core/orchestrator.py`**

```python
# filepath: core/orchestrator.py

import asyncio
from services.viral_copywriter import ViralCopywriter

class Orchestrator:
    def __init__(self, config):
        self.config = config
        self.viral_copywriter = ViralCopywriter(config['openai_api_key'])

    async def orchestrate(self, video_context):
        try:
            # Generate viral content
            viral_content = await self.viral_copywriter.generate_content(video_context)
            
            # Inject viral content into the metadata
            self._override_metadata_with_viral_content(viral_content)
            
            # Proceed with existing orchestration
            self.multi_platform_publish()
        except Exception as e:
            # Log the exception and handle gracefully
            print(f"Error generating viral content: {e}")

    def _override_metadata_with_viral_content(self, viral_content):
        self.metadata['title'] = viral_content['title']
        self.metadata['description'] = viral_content['description']
        self.metadata['tags'] = viral_content['tags']

    def multi_platform_publish(self):
        # Existing code for publishing
        pass
```

### 3. **Configuration and Testing**

Make sure your `config.json` includes the OpenAI API key:

```json
# filepath: config.json

{
    "openai_api_key": "your_openai_api_key_here"
}
```

### 4. **Testing the Integration**

You would typically create a test file to ensure the integration is correct, like so:

```python
# filepath: tests/integration/test_viral_copywriter.py

import pytest
import asyncio
from services.viral_copywriter import ViralCopywriter

@pytest.mark.asyncio
async def test_generate_content():
    api_key = "test_openai_api_key"  # Use a mock or test key
    viral_copywriter = ViralCopywriter(api_key)
    
    video_context = "an innovative tech product"
    content = await viral_copywriter.generate_content(video_context)
    
    assert 'title' in content
    assert 'description' in content
    assert 'tags' in content
    assert isinstance(content['tags'], list)
```

### 5. **Quality Assurance Considerations**

- Ensure that `asyncio` is correctly managed within the orchestrator.
- Implement logging and error-handling as needed in production environments.
- Secure API keys using environment variables or other secure methods, especially in production.

This implementation follows the structured plan to integrate a viral content generation feature using OpenAI's API, ensuring a seamless addition to your backend orchestration.

## Code Review & Final Code
## Summary

The provided code outlines the implementation of a `ViralCopywriter` module to asynchronously generate viral content for social media using the OpenAI API. It's integrated into the `Orchestrator` class. Overall, the code is well-structured, but there are some areas for improvement, particularly around correctness, maintainability, and security.

## Key Concerns

1. **Correctness**:
   - The `openai.Completion.create` method should use `await` with `aiohttp` or another async HTTP client since OpenAI's Python library is synchronous. You will need to use the `openai.AsyncOpenAI` or handle the async requests with `aiohttp`.
   - Error handling around the OpenAI API call is minimal, which can lead to unhandled exceptions in production.

2. **Security**:
   - The API key should not be set directly in the class; it should be securely managed using environment variables or a secrets manager.

3. **Maintainability**:
   - The `generate_content` method assumes a fixed structure in the response which might change, leading to potential failures.
   - Parsing should be more robust to handle unexpected API response formats.
   - Consider adding logging for better traceability and debugging.

4. **Testing**:
   - The test uses a real API key. Consider using mocking to simulate API responses to ensure tests do not rely on external services.

## Detailed Review

### 1. `ViralCopywriter` Module

```python
# filepath: services/viral_copywriter.py

import openai
import os
import aiohttp  # New import

class ViralCopywriter:
    def __init__(self):
        self.api_key = os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("OpenAI API key must be set as an environment variable.")

    async def generate_content(self, video_context):
        prompt = self._create_prompt(video_context)
        async with aiohttp.ClientSession() as session:
            headers = {"Authorization": f"Bearer {self.api_key}"}
            data = {
                "model": "text-davinci-003",
                "prompt": prompt,
                "max_tokens": 150
            }
            async with session.post("https://api.openai.com/v1/completions", headers=headers, json=data) as response:
                if response.status != 200:
                    raise Exception(f"Failed to fetch content: {response.status}")
                result = await response.json()
                return self._parse_response(result)

    def _create_prompt(self, video_context):
        return f"Generate a viral title, description, and hashtags for a video about {video_context}"

    def _parse_response(self, response):
        try:
            text = response['choices'][0]['text']
            lines = text.strip().split('\n')
            return {
                "title": lines[0],
                "description": lines[1],
                "tags": lines[2].split(',') if len(lines) > 2 else []
            }
        except (IndexError, KeyError) as e:
            raise ValueError(f"Unexpected response format: {e}")
```

### 2. `Orchestrator` Class

```python
# filepath: core/orchestrator.py

import asyncio
from services.viral_copywriter import ViralCopywriter

class Orchestrator:
    def __init__(self, config):
        self.config = config
        self.viral_copywriter = ViralCopywriter()

    async def orchestrate(self, video_context):
        try:
            viral_content = await self.viral_copywriter.generate_content(video_context)
            self._override_metadata_with_viral_content(viral_content)
            self.multi_platform_publish()
        except Exception as e:
            # Replace print with logging
            print(f"Error generating viral content: {e}")

    def _override_metadata_with_viral_content(self, viral_content):
        self.metadata = {
            'title': viral_content.get('title', 'Default Title'),
            'description': viral_content.get('description', 'Default Description'),
            'tags': viral_content.get('tags', [])
        }

    def multi_platform_publish(self):
        # Existing code for publishing
        pass
```

### 3. **Testing**

```python
# filepath: tests/integration/test_viral_copywriter.py

import pytest
import asyncio
from services.viral_copywriter import ViralCopywriter
from unittest.mock import patch

@pytest.mark.asyncio
async def test_generate_content():
    with patch('aiohttp.ClientSession.post') as mock_post:
        mock_post.return_value.__aenter__.return_value.json.return_value = {
            'choices': [{'text': 'Viral Title\nViral Description\n#tag1,#tag2'}]
        }
        
        viral_copywriter = ViralCopywriter()
        video_context = "an innovative tech product"
        
        content = await viral_copywriter.generate_content(video_context)
        
        assert 'title' in content
        assert 'description' in content
        assert 'tags' in content
        assert isinstance(content['tags'], list)
        assert content['title'] == 'Viral Title'
```

## Next Steps

- Implement robust error handling around the network calls.
- Use environment variables for API keys.
- Add logging for better debugging and traceability.
- Refactor tests to use mocking for API interactions.
