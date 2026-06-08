"""Helper functions for the evaluation process."""

import json
import os
from datetime import datetime
from typing import (
    Any,
    Dict,
    List,
    Optional,
    Tuple,
)

from langsmith.schemas import Run

from app.core.logging import logger
from evals.schemas import ScoreSchema


def _message_role(message: dict) -> str:
    """Extract role/type from a LangSmith or LangChain message dict."""
    return str(message.get("role") or message.get("type") or "unknown")


def _message_content(message: dict) -> str:
    """Extract string content from a message dict."""
    content = message.get("content")
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, dict):
                text = block.get("text") or block.get("content")
                if text:
                    parts.append(str(text))
            elif block:
                parts.append(str(block))
        return " ".join(parts)
    return str(content)


def _extract_messages(data: Any) -> list[dict]:
    """Extract message list from LangSmith run inputs/outputs."""
    if not isinstance(data, dict):
        return []

    messages = data.get("messages")
    if isinstance(messages, list):
        return [m for m in messages if isinstance(m, dict)]

    return []


def format_messages(messages: list[dict]) -> str:
    """Format a list of messages for evaluation.

    Args:
        messages: List of message dictionaries.

    Returns:
        String representation of formatted messages.
    """
    formatted_messages = []
    for idx, message in enumerate(messages):
        role = _message_role(message)
        content = _message_content(message)

        if role == "tool" or message.get("type") == "tool":
            previous_message = messages[idx - 1] if idx > 0 else {}
            tool_call = previous_message.get("additional_kwargs", {}).get("tool_calls", [])
            if tool_call:
                args = tool_call[0].get("function", {}).get("arguments")
            else:
                prev_tool_calls = previous_message.get("tool_calls")
                args = prev_tool_calls[0].get("args") if prev_tool_calls else {}
            formatted_messages.append(
                f"tool {message.get('name', 'unknown')} input: {args} {content[:100]}..."
                if len(content) > 100
                else f"tool {message.get('name', 'unknown')}: {content}"
            )
        elif content:
            formatted_messages.append(f"{role}: {content}")

    return "\n".join(formatted_messages)


def get_input_output(run: Run) -> Tuple[Optional[str], Optional[str]]:
    """Extract and format input and output messages from a LangSmith run.

    Args:
        run: The LangSmith run to extract messages from.

    Returns:
        Tuple of (formatted_input, formatted_output). None if output is not parseable.
    """
    input_messages = _extract_messages(run.inputs)
    output_messages = _extract_messages(run.outputs)

    if output_messages:
        input_text = format_messages(input_messages) if input_messages else None
        output_text = format_messages([output_messages[-1]])
        return input_text or "", output_text

    outputs = run.outputs or {}
    if isinstance(outputs, dict) and outputs.get("messages"):
        return None, None

    if isinstance(outputs, dict):
        output_content = outputs.get("content") or outputs.get("output")
        if output_content:
            input_text = format_messages(input_messages) if input_messages else ""
            return input_text, str(output_content)

    return None, None


def initialize_report(model_name: str) -> Dict[str, Any]:
    """Initialize report data structure.

    Args:
        model_name: Name of the model being evaluated.

    Returns:
        Dict containing initialized report structure.
    """
    return {
        "timestamp": datetime.now().isoformat(),
        "model": model_name,
        "total_traces": 0,
        "successful_traces": 0,
        "failed_traces": 0,
        "duration_seconds": 0,
        "metrics_summary": {},
        "successful_traces_details": [],
        "failed_traces_details": [],
    }


def initialize_metrics_summary(report: Dict[str, Any], metrics: List[Dict[str, str]]) -> None:
    """Initialize metrics summary in the report.

    Args:
        report: The report dictionary.
        metrics: List of metric definitions.
    """
    for metric in metrics:
        report["metrics_summary"][metric["name"]] = {"success_count": 0, "failure_count": 0, "avg_score": 0.0}


def update_success_metrics(
    report: Dict[str, Any], trace_id: str, metric_name: str, score: ScoreSchema, trace_results: Dict[str, Any]
) -> None:
    """Update metrics for a successful evaluation.

    Args:
        report: The report dictionary.
        trace_id: ID of the trace being evaluated.
        metric_name: Name of the metric.
        score: The score object.
        trace_results: Dictionary to store trace results.
    """
    trace_results[trace_id]["metrics_succeeded"] += 1
    trace_results[trace_id]["metrics_results"][metric_name] = {
        "success": True,
        "score": score.score,
        "reasoning": score.reasoning,
    }
    report["metrics_summary"][metric_name]["success_count"] += 1
    report["metrics_summary"][metric_name]["avg_score"] += score.score


def update_failure_metrics(
    report: Dict[str, Any], trace_id: str, metric_name: str, trace_results: Dict[str, Any]
) -> None:
    """Update metrics for a failed evaluation.

    Args:
        report: The report dictionary.
        trace_id: ID of the trace being evaluated.
        metric_name: Name of the metric.
        trace_results: Dictionary to store trace results.
    """
    trace_results[trace_id]["metrics_results"][metric_name] = {"success": False}
    report["metrics_summary"][metric_name]["failure_count"] += 1


def process_trace_results(
    report: Dict[str, Any], trace_id: str, trace_results: Dict[str, Any], metrics_count: int
) -> None:
    """Process results for a single trace.

    Args:
        report: The report dictionary.
        trace_id: ID of the trace being evaluated.
        trace_results: Dictionary to store trace results.
        metrics_count: Total number of metrics.
    """
    if trace_results[trace_id]["metrics_succeeded"] == metrics_count:
        trace_results[trace_id]["success"] = True
        report["successful_traces"] += 1
        report["successful_traces_details"].append(
            {"trace_id": trace_id, "metrics_results": trace_results[trace_id]["metrics_results"]}
        )
    else:
        report["failed_traces"] += 1
        report["failed_traces_details"].append(
            {
                "trace_id": trace_id,
                "metrics_evaluated": trace_results[trace_id]["metrics_evaluated"],
                "metrics_succeeded": trace_results[trace_id]["metrics_succeeded"],
                "metrics_results": trace_results[trace_id]["metrics_results"],
            }
        )


def calculate_avg_scores(report: Dict[str, Any]) -> None:
    """Calculate average scores for each metric.

    Args:
        report: The report dictionary.
    """
    for _, data in report["metrics_summary"].items():
        if data["success_count"] > 0:
            data["avg_score"] = round(data["avg_score"] / data["success_count"], 2)


def generate_report(report: Dict[str, Any]) -> str:
    """Generate a JSON report file with evaluation results.

    Args:
        report: The report dictionary.

    Returns:
        str: Path to the generated report file.
    """
    report_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "reports")
    os.makedirs(report_dir, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_path = os.path.join(report_dir, f"evaluation_report_{timestamp}.json")

    with open(report_path, "w") as f:
        json.dump(report, f, indent=2)

    # Add the report path to the report data for reference
    report["generate_report_path"] = report_path

    logger.info("evaluation_report_generated", report_path=report_path)
    return report_path
