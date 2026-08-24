import json
import os
from pathlib import Path
from typing import Dict

def render_isolated_profile(session_id: str, base_path: Path) -> Dict[str, str]:
    """
    Renders an isolated profile for Goose and DeepSeek Harness (DSH).
    
    This ensures that DSH uses DSH_HOME and Goose uses GOOSE_PATH_ROOT,
    completely ignoring `~/.dsh` and `~/.config/goose`.
    
    Returns the strict environment variables needed for launch.
    """
    session_root = base_path / ".builder" / "runtime" / "dsh" / session_id
    dsh_home = session_root / "dsh-home"
    goose_root = session_root / "goose-root"
    goose_config_dir = goose_root / "config"
    
    # Ensure directories exist
    dsh_home.mkdir(parents=True, exist_ok=True)
    goose_config_dir.mkdir(parents=True, exist_ok=True)
    
    # Render Goose config strictly disabling 'developer' and allowing only builder-II MCP
    # A default goose config inside the isolated root.
    goose_config_path = goose_config_dir / "config.yaml"
    if not goose_config_path.exists():
        goose_config_path.write_text(
            "extensions:\n"
            "  developer:\n"
            "    enabled: false\n"
            "  builder_ii_mcp:\n"
            "    enabled: true\n"
            "    cmd: builder-mcp\n"
            "    args: ['serve', '--governed']\n"
        )
        
    # Render minimal DSH config to avoid external plugins
    dsh_config_dir = dsh_home / "config"
    dsh_config_dir.mkdir(parents=True, exist_ok=True)
    dsh_config_path = dsh_config_dir / "settings.json"
    if not dsh_config_path.exists():
        dsh_config_path.write_text(json.dumps({
            "plugins": {
                "allowLocal": False,
                "allowUnpinned": False
            },
            "sandbox": {
                "enabled": True,
                "bypass": False
            }
        }))
        
    # Expose only loopback/gateway credentials, stripping all user ambient creds
    # (Implementation of credential stripping would happen at subprocess launch)
    
    return {
        "DSH_HOME": str(dsh_home.absolute()),
        "GOOSE_PATH_ROOT": str(goose_root.absolute()),
        # Additional safety
        "GOOSE_PROVIDER": "builder-gateway"
    }
