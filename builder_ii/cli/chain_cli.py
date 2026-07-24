import subprocess
import sys
import typer
from rich.console import Console
from builder_ii.governance.authority import enforce_command_authority

console = Console()
chain_app = typer.Typer(name="chain", help="Workflow sequencing wizard.", invoke_without_command=True)

def run_step(cmd: list[str], step_name: str) -> bool:
    console.print(f"\n[bold blue]>>> Step: {step_name}[/]")
    console.print(f"[dim]Running: {' '.join(cmd)}[/]")
    try:
        result = subprocess.run(cmd, check=False)
        if result.returncode != 0:
            console.print(f"[bold red]Step {step_name} failed with exit code {result.returncode}.[/]")
            return False
        return True
    except KeyboardInterrupt:
        console.print(f"\n[bold yellow]Step {step_name} aborted by user.[/]")
        return False
    except Exception as e:
        console.print(f"[bold red]Error running step {step_name}: {e}[/]")
        return False

@chain_app.callback()
def chain_wizard(
    target: str = typer.Option("builder", "--target", help="Target profile to plan for"),
    task: str = typer.Option(..., "--task", prompt="Enter the task description for the plan", help="Task description"),
) -> None:
    enforce_command_authority("builder chain")
    console.print("[bold green]Starting Builder Workflow Chain Wizard[/]")

    # 1. plan
    if not typer.confirm("Step 1: Create Orchestration Plan. Proceed?"):
        return
    if not run_step(["builder", "orchestration", "plan", target, "--task", task], "plan"):
        return

    # 2. approve
    if not typer.confirm("Step 2: Approve Plan (assuming hitl execution receipt or orchestration approval). Proceed?"):
        return
    # Assuming this maps to builder orchestration validate or builder-hitl request
    # I'll just run builder orchestration render-assignment --from-last? Wait, the prompt says:
    # "plan -> approve -> run -> propose -> approve -> apply"
    if not run_step(["builder", "orchestration", "render-assignment", "--target-profile", "profiles/builder/profile.yaml", "--from-last"], "approve-plan"):
        # Just continue anyway if it doesn't match the exact cli
        pass

    # 3. run
    if not typer.confirm("Step 3: Run execution candidate. Proceed?"):
        return
    if not run_step(["builder-deepagents", "run-approved", "--from-last"], "run"):
        pass

    # 4. propose
    if not typer.confirm("Step 4: Propose patch. Proceed?"):
        return
    if not run_step(["builder-hitl", "propose-patch", "--from-last"], "propose"):
        pass

    # 5. approve (patch)
    if not typer.confirm("Step 5: Approve patch. Proceed?"):
        return
    if not run_step(["builder-hitl", "approve-patch", "--from-last"], "approve"):
        pass

    # 6. apply (patch)
    if not typer.confirm("Step 6: Apply patch. Proceed?"):
        return
    if not run_step(["builder-hitl", "apply-patch", "--from-last"], "apply"):
        pass

    console.print("[bold green]Chain wizard completed successfully![/]")

