"""
agency_adapter.py
=================
Core bridging layer to connect 'agency-agents' Markdown prompts 
to the 'commercial_engine' backend.
"""

import os
import re
from pathlib import Path
from dotenv import load_dotenv
from pydantic import BaseModel, Field
from openai import AsyncOpenAI
from rich.console import Console

# Auto-load .env from the commercial_engine directory
_env_path = Path(__file__).parent.parent / "commercial_engine" / ".env"
if _env_path.exists():
    load_dotenv(_env_path)

console = Console()

class AgentProfile(BaseModel):
    name: str = Field(..., description="The name of the agent")
    description: str = Field(..., description="Short description of the agent")
    system_prompt: str = Field(..., description="The parsed system prompt from markdown")

class AgencyPromptLoader:
    """Loads and parses the Markdown prompts from agency-agents root directory."""
    
    def __init__(self, repo_root: str):
        self.repo_root = Path(repo_root)
        
    def load_prompt(self, relative_path: str) -> AgentProfile:
        """
        Load an agent's markdown file. Example: 'marketing/marketing-short-video-editing-coach.md'
        Extracts the # Title as Name, and the content under ## System Prompt
        """
        file_path = self.repo_root / relative_path
        if not file_path.exists():
            raise FileNotFoundError(f"Agent prompt not found at {file_path}")
            
        content = file_path.read_text(encoding='utf-8')
        
        # Parse Name (First H1)
        name_match = re.search(r'^#\s+(.+)$', content, re.MULTILINE)
        name = name_match.group(1).strip() if name_match else Path(relative_path).stem
        
        # We use the whole markdown as the system prompt context because 
        # msitarzewski/agency-agents models define persona via the entire document.
        system_prompt = f"You are the following expert agent. Adhere strictly to these instructions:\n\n{content}"
        
        return AgentProfile(
            name=name,
            description=f"Agent parsed from {relative_path}",
            system_prompt=system_prompt
        )


class AgencyLLMClient:
    """Handles communications with the LLM using the loaded AgentProfiles."""
    
    def __init__(self, api_key: str = None, base_url: str = None, model: str = "gpt-4o"):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.base_url = base_url or os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
        self.model = model
        self.client = AsyncOpenAI(api_key=self.api_key, base_url=self.base_url)
        console.print(f"[green]AgencyLLMClient ready | model={self.model} | key=...{self.api_key[-8:] if self.api_key else 'MISSING'}[/green]")
        
    async def process_task(self, agent: AgentProfile, user_input: str, response_format=None) -> str:
        """
        Executes a task as the specified agent.
        """
        console.print(f"[cyan]Executing task with Agent: {agent.name}[/cyan]")
        
        messages = [
            {"role": "system", "content": agent.system_prompt},
            {"role": "user", "content": user_input}
        ]
        
        kwargs = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.7,
        }
        
        if response_format:
            kwargs["response_format"] = {"type": "json_object"}
            
        response = await self.client.chat.completions.create(**kwargs)
        result = response.choices[0].message.content
        return result
