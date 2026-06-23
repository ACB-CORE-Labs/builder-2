from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass
from pathlib import Path

import httpx
import psutil

from builder_ii.backends import check_health
from builder_ii.compliance import run_compliance_checks
from builder_ii.config import Settings


@dataclass(frozen=True)
class BenchmarkReport:
    backend: str
    model_tier: str
    base_url: str
    server_reachable: bool
    server_message: str
    ttft_seconds: float | None
    tokens_per_second: float | None
    tool_call_ok: bool
    compliance: dict[str, object]
    memory_rss_gb: float
    memory_green: bool
    wall_seconds: float


def _chat_completion(
    settings: Settings,
    messages: list[dict[str, str]],
    *,
    tools: list[dict] | None = None,
    max_tokens: int = 64,
) -> dict:
    payload: dict = {
        "model": "default",
        "messages": messages,
        "temperature": settings.temperature,
        "max_tokens": max_tokens,
    }
    if tools:
        payload["tools"] = tools
        payload["tool_choice"] = "auto"
    with httpx.Client(timeout=120.0) as client:
        response = client.post(
            f"{settings.base_url.rstrip('/')}/chat/completions",
            json=payload,
        )
        response.raise_for_status()
        return response.json()


def _measure_perf(settings: Settings) -> tuple[float | None, float | None, bool]:
    prompt = "Reply with exactly: OK"
    start = time.perf_counter()
    try:
        data = _chat_completion(settings, [{"role": "user", "content": prompt}], max_tokens=8)
    except httpx.HTTPError:
        return None, None, False
    ttft = time.perf_counter() - start
    content = data["choices"][0]["message"].get("content") or ""
    tok_est = max(1, len(content.split()))
    elapsed = max(ttft, 0.001)
    tps = tok_est / elapsed

    tools = [
        {
            "type": "function",
            "function": {
                "name": "read_file",
                "description": "Read a file path",
                "parameters": {
                    "type": "object",
                    "properties": {"path": {"type": "string"}},
                    "required": ["path"],
                },
            },
        }
    ]
    try:
        tool_data = _chat_completion(
            settings,
            [{"role": "user", "content": "Call read_file with path AGENTS.md"}],
            tools=tools,
            max_tokens=128,
        )
        msg = tool_data["choices"][0]["message"]
        tool_ok = bool(msg.get("tool_calls"))
    except httpx.HTTPError:
        tool_ok = False
    return ttft, tps, tool_ok


def run_benchmark(settings: Settings) -> BenchmarkReport:
    t0 = time.perf_counter()
    reachable, msg = check_health(settings)
    ttft, tps, tool_ok = (None, None, False)
    if reachable:
        ttft, tps, tool_ok = _measure_perf(settings)

    compliance = run_compliance_checks()
    rss_gb = psutil.Process().memory_info().rss / (1024**3)
    proc = psutil.virtual_memory()
    used_gb = (proc.total - proc.available) / (1024**3)

    return BenchmarkReport(
        backend=settings.backend,
        model_tier=settings.model_tier,
        base_url=settings.base_url,
        server_reachable=reachable,
        server_message=msg,
        ttft_seconds=ttft,
        tokens_per_second=tps,
        tool_call_ok=tool_ok,
        compliance=asdict(compliance),
        memory_rss_gb=round(used_gb, 2),
        memory_green=used_gb < 11.5,
        wall_seconds=round(time.perf_counter() - t0, 2),
    )


def format_benchmark_report(report: BenchmarkReport) -> str:
    lines = [
        "CORE Agent Platform Benchmark",
        f"backend={report.backend} tier={report.model_tier} url={report.base_url}",
        f"server: {'REACHABLE' if report.server_reachable else 'DOWN'} ({report.server_message})",
    ]
    if report.ttft_seconds is not None:
        lines.append(f"TTFT: {report.ttft_seconds:.3f}s")
    if report.tokens_per_second is not None:
        lines.append(f"tok/s (est): {report.tokens_per_second:.1f}")
    lines.append(f"tool_call: {'PASS' if report.tool_call_ok else 'SKIP/FAIL'}")
    lines.append(
        f"compliance: init_literals={'PASS' if report.compliance['init_literals_ok'] else 'FAIL'} "
        f"refusal_probe={'PASS' if report.compliance['refusal_probe_ok'] else 'FAIL'}"
    )
    lines.append(
        f"memory: {report.memory_rss_gb} GB used "
        f"({'GREEN' if report.memory_green else 'RED'}, limit 11.5 GB)"
    )
    lines.append(f"wall: {report.wall_seconds}s")
    return "\n".join(lines)


def write_benchmark_report(report: BenchmarkReport, path: Path) -> None:
    path.write_text(format_benchmark_report(report) + "\n\n" + json.dumps(asdict(report), indent=2))