#!/usr/bin/env python3
"""
Validator for tui-exploration-report artifacts.
kind: tui-exploration-validator
"""
import argparse
import json
import sys
from pathlib import Path

def validate_report(report_path: Path) -> list[str]:
    errors = []
    if not report_path.exists():
        return [f"File {report_path} does not exist"]
    
    try:
        data = json.loads(report_path.read_text(encoding="utf-8"))
    except Exception as e:
        return [f"Failed to parse JSON: {e}"]
        
    if not isinstance(data, dict):
        return ["Root of artifact must be a JSON object"]
        
    # Check kind
    kind = data.get("kind")
    if kind != "builder_ii.tui_exploration_report":
        errors.append(f"Invalid kind: expected 'builder_ii.tui_exploration_report', got '{kind}'")
        
    # Check schema version
    schema_version = data.get("schema_version")
    if schema_version != 1:
        errors.append(f"Invalid schema_version: expected 1, got {schema_version}")
        
    # Check surfaces
    surfaces = data.get("surfaces")
    if not isinstance(surfaces, list):
        errors.append("Missing or invalid 'surfaces' list")
    else:
        for idx, surface in enumerate(surfaces):
            if not isinstance(surface, dict):
                errors.append(f"surfaces[{idx}] must be an object")
                continue
                
            name = surface.get("name")
            if not isinstance(name, str) or not name:
                errors.append(f"surfaces[{idx}] missing 'name'")
                
            verdict = surface.get("verdict")
            if verdict not in ("SOLID", "NEEDS WORK", "BROKEN"):
                errors.append(f"surfaces[{idx}] invalid 'verdict': {verdict}")
                
            first_impression = surface.get("first_impression")
            if not isinstance(first_impression, str) or not first_impression:
                errors.append(f"surfaces[{idx}] missing 'first_impression'")
                
            nav = surface.get("navigation_map")
            if not isinstance(nav, list):
                errors.append(f"surfaces[{idx}] missing or invalid 'navigation_map'")
                
            works = surface.get("what_works")
            if not isinstance(works, list) and not isinstance(works, str):
                errors.append(f"surfaces[{idx}] missing or invalid 'what_works'")
                
            broken = surface.get("what_is_broken")
            if not isinstance(broken, list) and not isinstance(broken, str):
                errors.append(f"surfaces[{idx}] missing or invalid 'what_is_broken'")
                
            edge = surface.get("edge_case_behavior")
            if not isinstance(edge, str) or not edge:
                errors.append(f"surfaces[{idx}] missing 'edge_case_behavior'")
                
    return errors

def main():
    parser = argparse.ArgumentParser(description="Validate tui-exploration-report JSON artifact.")
    parser.add_argument("report_path", type=Path, help="Path to the JSON report file.")
    args = parser.parse_args()
    
    errors = validate_report(args.report_path)
    if errors:
        print(f"Validation failed for {args.report_path}:")
        for err in errors:
            print(f"  - {err}")
        sys.exit(1)
        
    print(f"Artifact {args.report_path} is valid.")
    sys.exit(0)

if __name__ == "__main__":
    main()
