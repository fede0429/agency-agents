import asyncio
import os
import json
from pathlib import Path
from agency_adapter import AgencyPromptLoader, AgencyLLMClient
from rich.console import Console

console = Console()

class EngineeringPipeline:
    def __init__(self, repo_root: str):
        self.repo_root = Path(repo_root)
        self.loader = AgencyPromptLoader(repo_root)
        self.client = AgencyLLMClient()
        
    def _get_codebase_structure(self) -> str:
        """Scan the commercial_engine directory to provide context to the Architect."""
        target_dir = self.repo_root / "src" / "commercial_engine"
        if not target_dir.exists():
            return "No codebase found at src/commercial_engine. Please initialize it first."
            
        structure = []
        for root, dirs, files in os.walk(target_dir):
            if "__pycache__" in root or ".git" in root:
                continue
            level = root.replace(str(target_dir), "").count(os.sep)
            indent = " " * 4 * level
            structure.append(f"{indent}{os.path.basename(root)}/")
            subindent = " " * 4 * (level + 1)
            for f in files:
                if f.endswith(".py") or f.endswith(".json") or f.endswith(".md"):
                    structure.append(f"{subindent}{f}")
        return "\n".join(structure[:500])  # limit to prevent context overflow if too massive

    async def run(self, feature_request: str):
        console.print(f"\n[bold green]--- Starting Multi-Agent Engineering Pipeline ---[/bold green]")
        console.print(f"[bold cyan]Feature/Task Request:[/bold cyan] {feature_request}\n")
        
        codebase_tree = self._get_codebase_structure()
        
        # 1. Software Architect (System Design)
        console.print("[yellow][1/3] Calling Software Architect...[/yellow]")
        architect_profile = self.loader.load_prompt("engineering/engineering-software-architect.md")
        architect_prompt = (
            f"We are upgrading our video orchestration backend.\n"
            f"Here is our current repository structure under `src/commercial_engine`:\n"
            f"```text\n{codebase_tree}\n```\n\n"
            f"FEATURE TASK: {feature_request}\n\n"
            f"Please output a detailed technical implementation plan, stating exactly which files need "
            f"to be modified or created, and the classes/functions mapping."
        )
        architecture_plan = await self.client.process_task(architect_profile, architect_prompt)
        console.print("[green][OK] Architecture Plan Designed![/green]\n")
        console.print(architecture_plan[:300] + "\n... (truncated for display)\n")
        
        # 2. Senior Developer (Implementation)
        console.print("[yellow][2/3] Calling Senior Python Developer...[/yellow]")
        developer_profile = self.loader.load_prompt("engineering/engineering-senior-developer.md")
        dev_prompt = (
            f"You are writing code to fulfill a feature based on the Architect's plan.\n"
            f"ARCHITECT PLAN:\n{architecture_plan}\n\n"
            f"Please write the actual Python code needed. For each file being modified or created, "
            f"wrap the code in a markdown block starting with ```python\n# filepath: <relative_path>\n"
        )
        developer_code = await self.client.process_task(developer_profile, dev_prompt)
        console.print("[green][OK] First Draft Code Generated![/green]\n")
        
        # 3. Code Reviewer (Validation & Securing)
        console.print("[yellow][3/3] Calling Code Reviewer...[/yellow]")
        reviewer_profile = self.loader.load_prompt("engineering/engineering-code-reviewer.md")
        review_prompt = (
            f"Review the following code written by the Senior Developer for the Commercial Engine.\n"
            f"FEATURE GOAL: {feature_request}\n\n"
            f"CODE TO REVIEW:\n{developer_code}\n\n"
            f"Spot bugs, logic errors, or missing imports. Output the final perfect code blocks, "
            f"wrapped with ```python\n# filepath: <relative_path>\n."
        )
        final_code = await self.client.process_task(reviewer_profile, review_prompt)
        console.print("[green][OK] Code Review Complete! Finalizing Output.[/green]\n")
        
        # Save the full output to a UTF-8 file (avoids Windows terminal encoding issues)
        output_dir = self.repo_root / "src" / "orchestrator" / "output"
        output_dir.mkdir(parents=True, exist_ok=True)
        output_file = output_dir / "engineering_output.md"
        output_file.write_text(
            f"# Engineering Pipeline Output\n\n"
            f"## Feature Request\n{feature_request}\n\n"
            f"## Architecture Plan\n{architecture_plan}\n\n"
            f"## Developer Code\n{developer_code}\n\n"
            f"## Code Review & Final Code\n{final_code}\n",
            encoding="utf-8"
        )
        
        print(f"\n{'='*60}")
        print(f"ENGINEERING PIPELINE COMPLETE!")
        print(f"Full output saved to: {output_file}")
        print(f"{'='*60}")
        
        return final_code

if __name__ == "__main__":
    p = EngineeringPipeline(str(Path(__file__).parent.parent.parent.parent))
    asyncio.run(p.run("Add a REST endpoint to core/orchestrator.py for health checks."))
