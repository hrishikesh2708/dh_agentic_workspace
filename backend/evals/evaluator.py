"""Evaluator for evals."""

import os
import sys
import time
from datetime import (
    datetime,
    timedelta,
)
from time import sleep

import openai
from langsmith import Client
from langsmith.schemas import Run
from tqdm import tqdm

# Fix import path for app module
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.core.config import settings
from app.core.logging import logger
from evals.helpers import (
    calculate_avg_scores,
    generate_report,
    get_input_output,
    initialize_metrics_summary,
    initialize_report,
    process_trace_results,
    update_failure_metrics,
    update_success_metrics,
)
from evals.metrics import metrics
from evals.schemas import ScoreSchema


class Evaluator:
    """Evaluates model outputs using predefined metrics.

    This class handles fetching runs from LangSmith, evaluating them against
    metrics, and uploading feedback back to LangSmith.

    Attributes:
        client: OpenAI client for API calls.
        langsmith: LangSmith client for run management.
    """

    def __init__(self):
        """Initialize Evaluator with OpenAI and LangSmith clients."""
        self.client = openai.AsyncOpenAI(api_key=settings.EVALUATION_API_KEY, base_url=settings.EVALUATION_BASE_URL)
        self.langsmith = Client(
            api_key=settings.LANGSMITH_API_KEY,
            api_url=settings.LANGSMITH_ENDPOINT,
        )
        self._metric_names = {metric["name"] for metric in metrics}
        # Initialize report data structure
        self.report = initialize_report(settings.EVALUATION_LLM)
        initialize_metrics_summary(self.report, metrics)

    async def run(self, generate_report_file=True):
        """Main execution function that fetches and evaluates runs.

        Retrieves runs from LangSmith, evaluates each one against all metrics,
        and uploads feedback back to LangSmith.

        Args:
            generate_report_file: Whether to generate a JSON report after evaluation. Defaults to True.
        """
        start_time = time.time()
        runs = self.__fetch_runs()
        self.report["total_traces"] = len(runs)

        trace_results = {}

        for run in tqdm(runs, desc="Evaluating runs"):
            trace_id = str(run.trace_id or run.id)
            trace_results[trace_id] = {
                "success": False,
                "metrics_evaluated": 0,
                "metrics_succeeded": 0,
                "metrics_results": {},
            }

            for metric in tqdm(metrics, desc=f"Applying metrics to run {trace_id[:8]}...", leave=False):
                metric_name = metric["name"]
                input, output = get_input_output(run)
                if input is None or output is None:
                    update_failure_metrics(self.report, trace_id, metric_name, trace_results)
                    trace_results[trace_id]["metrics_evaluated"] += 1
                    continue
                score = await self._run_metric_evaluation(metric, input, output)

                if score:
                    self._push_to_langsmith(run, score, metric)
                    update_success_metrics(self.report, trace_id, metric_name, score, trace_results)
                else:
                    update_failure_metrics(self.report, trace_id, metric_name, trace_results)

                trace_results[trace_id]["metrics_evaluated"] += 1

            process_trace_results(self.report, trace_id, trace_results, len(metrics))
            sleep(settings.EVALUATION_SLEEP_TIME)

        self.report["duration_seconds"] = round(time.time() - start_time, 2)
        calculate_avg_scores(self.report)

        if generate_report_file:
            generate_report(self.report)

        logger.info(
            "evaluation_completed",
            total_traces=self.report["total_traces"],
            successful_traces=self.report["successful_traces"],
            failed_traces=self.report["failed_traces"],
            duration_seconds=self.report["duration_seconds"],
        )

    def _push_to_langsmith(self, run: Run, score: ScoreSchema, metric: dict):
        """Push evaluation feedback to LangSmith.

        Args:
            run: The run to score.
            score: The evaluation score.
            metric: The metric used for evaluation.
        """
        trace_id = str(run.trace_id or run.id)
        self.langsmith.create_feedback(
            key=metric["name"],
            score=score.score,
            run_id=str(run.id),
            trace_id=trace_id,
            comment=score.reasoning,
        )

    async def _run_metric_evaluation(self, metric: dict, input: str, output: str) -> ScoreSchema | None:
        """Evaluate a single trace against a specific metric.

        Args:
            metric: The metric definition to use for evaluation.
            input: The input to evaluate.
            output: The output to evaluate.

        Returns:
            ScoreSchema with evaluation results or None if evaluation failed.
        """
        metric_name = metric["name"]
        if not metric:
            logger.error("metric_not_found", metric_name=metric_name)
            return None
        system_metric_prompt = metric["prompt"]

        if not input or not output:
            logger.error(
                "metric_evaluation_failed_missing_io",
                metric_name=metric_name,
                has_input=bool(input),
                has_output=bool(output),
            )
            return None
        score = await self._call_openai(system_metric_prompt, input, output)
        if score:
            logger.info(
                "metric_evaluation_completed",
                metric_name=metric_name,
                score=score.score,
                reasoning=score.reasoning,
            )
        else:
            logger.error("metric_evaluation_failed", metric_name=metric_name)
        return score

    async def _call_openai(self, metric_system_prompt: str, input: str, output: str) -> ScoreSchema | None:
        """Call OpenAI API to evaluate a trace.

        Args:
            metric_system_prompt: System prompt defining the evaluation metric.
            input: Formatted input messages.
            output: Formatted output message.

        Returns:
            ScoreSchema with evaluation results or None if API call failed.
        """
        num_retries = 3
        for _ in range(num_retries):
            try:
                response = await self.client.beta.chat.completions.parse(
                    model=settings.EVALUATION_LLM,
                    messages=[
                        {"role": "system", "content": metric_system_prompt},
                        {"role": "user", "content": f"Input: {input}\nGeneration: {output}"},
                    ],
                    response_format=ScoreSchema,
                )
                return response.choices[0].message.parsed
            except Exception as e:
                SLEEP_TIME = 10
                logger.error(
                    "openai_evaluation_call_failed",
                    error=str(e),
                    sleep_seconds=SLEEP_TIME,
                )
                sleep(SLEEP_TIME)
                continue
        return None

    def _run_has_eval_feedback(self, run: Run) -> bool:
        """Return True if the run already has feedback for any eval metric."""
        feedback_stats = run.feedback_stats or {}
        return any(metric_name in feedback_stats for metric_name in self._metric_names)

    def __fetch_runs(self) -> list[Run]:
        """Fetch root runs from the past 24 hours without eval feedback.

        Returns:
            List of runs that haven't been scored yet.
        """
        last_24_hours = datetime.now() - timedelta(hours=24)
        logger.info("fetching_langsmith_runs", from_timestamp=str(last_24_hours))
        try:
            runs = list(
                self.langsmith.list_runs(
                    project_name=settings.LANGSMITH_PROJECT,
                    is_root=True,
                    start_time=last_24_hours,
                    limit=100,
                )
            )
            runs_without_feedback = [run for run in runs if not self._run_has_eval_feedback(run)]
            return runs_without_feedback
        except Exception as e:
            logger.error("langsmith_runs_fetch_failed", error=str(e))
            return []
