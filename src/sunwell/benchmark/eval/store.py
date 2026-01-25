"""SQLite-backed Evaluation Storage (RFC-098).

Stores evaluation runs with full provenance for:
- Historical tracking and trend analysis
- Regression detection
- Lens/model comparison analytics

Storage location: ~/.sunwell/evaluations.db (user-level, cross-project)

Follows patterns from:
- incremental/cache.py (ExecutionCache)
- security/approval_cache.py (SQLiteApprovalCache)
"""

import sqlite3
import threading
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

from sunwell.foundation.utils import safe_json_loads
from sunwell.benchmark.eval.types import (
    EvaluationDetails,
    EvaluationRun,
    EvaluationStats,
    SingleShotResult,
    SunwellResult,
)


@dataclass(frozen=True, slots=True)
class EvaluationSummary:
    """Lightweight summary for list views."""

    id: str
    timestamp: datetime
    task: str
    model: str
    lens: str | None
    single_shot_score: float
    sunwell_score: float
    improvement_percent: float
    winner: Literal["sunwell", "single_shot", "tie"]


class EvaluationStore:
    """SQLite-backed evaluation storage.

    Follows existing patterns from:
    - `incremental/cache.py` (ExecutionCache)
    - `security/approval_cache.py` (SQLiteApprovalCache)

    Storage: ~/.sunwell/evaluations.db
    """

    SCHEMA_VERSION = 1

    SCHEMA = """
    CREATE TABLE IF NOT EXISTS evaluation_runs (
        id TEXT PRIMARY KEY,
        timestamp REAL NOT NULL,
        task TEXT NOT NULL,
        model TEXT NOT NULL,
        lens TEXT,
        sunwell_version TEXT NOT NULL,
        single_shot_score REAL NOT NULL,
        sunwell_score REAL NOT NULL,
        improvement_percent REAL NOT NULL,
        winner TEXT NOT NULL CHECK (winner IN ('sunwell', 'single_shot', 'tie')),
        input_tokens INTEGER NOT NULL,
        output_tokens INTEGER NOT NULL,
        estimated_cost_usd REAL NOT NULL,
        git_commit TEXT,
        config_hash TEXT NOT NULL,
        details_json TEXT NOT NULL
    );

    CREATE INDEX IF NOT EXISTS idx_runs_task ON evaluation_runs(task);
    CREATE INDEX IF NOT EXISTS idx_runs_model ON evaluation_runs(model);
    CREATE INDEX IF NOT EXISTS idx_runs_lens ON evaluation_runs(lens);
    CREATE INDEX IF NOT EXISTS idx_runs_timestamp ON evaluation_runs(timestamp DESC);
    CREATE INDEX IF NOT EXISTS idx_runs_winner ON evaluation_runs(winner);

    CREATE TABLE IF NOT EXISTS metadata (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL
    );
    """

    def __init__(self, db_path: Path | None = None) -> None:
        """Initialize evaluation store.

        Args:
            db_path: Path to SQLite database. Defaults to ~/.sunwell/evaluations.db
        """
        self.db_path = db_path or (Path.home() / ".sunwell" / "evaluations.db")
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        self._conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(self.SCHEMA)
        self._conn.commit()
        self._lock = threading.Lock()

        # Store schema version
        self._set_metadata("schema_version", str(self.SCHEMA_VERSION))

    def close(self) -> None:
        """Close the database connection."""
        self._conn.close()

    def __enter__(self) -> EvaluationStore:
        """Context manager entry."""
        return self

    def __exit__(self, *args: Any) -> None:
        """Context manager exit."""
        self.close()

    @contextmanager
    def transaction(self):
        """Context manager for transactions."""
        with self._lock:
            try:
                yield self._conn
                self._conn.commit()
            except Exception:
                self._conn.rollback()
                raise

    def _set_metadata(self, key: str, value: str) -> None:
        """Set a metadata value."""
        self._conn.execute(
            "INSERT OR REPLACE INTO metadata (key, value) VALUES (?, ?)", (key, value)
        )
        self._conn.commit()

    def _get_metadata(self, key: str) -> str | None:
        """Get a metadata value."""
        row = self._conn.execute(
            "SELECT value FROM metadata WHERE key = ?", (key,)
        ).fetchone()
        return row["value"] if row else None

    # =========================================================================
    # CRUD Operations
    # =========================================================================

    def save(self, run: EvaluationRun) -> None:
        """Save an evaluation run.

        Args:
            run: The evaluation run to save.
        """
        # Serialize complex objects to JSON
        details = {
            "single_shot_result": {
                "files": list(run.single_shot_result.files),
                "output_dir": str(run.single_shot_result.output_dir),
                "time_seconds": run.single_shot_result.time_seconds,
                "turns": run.single_shot_result.turns,
                "input_tokens": run.single_shot_result.input_tokens,
                "output_tokens": run.single_shot_result.output_tokens,
            },
            "sunwell_result": {
                "files": list(run.sunwell_result.files),
                "output_dir": str(run.sunwell_result.output_dir),
                "time_seconds": run.sunwell_result.time_seconds,
                "turns": run.sunwell_result.turns,
                "input_tokens": run.sunwell_result.input_tokens,
                "output_tokens": run.sunwell_result.output_tokens,
                "lens_used": run.sunwell_result.lens_used,
                "judge_scores": list(run.sunwell_result.judge_scores),
                "resonance_iterations": run.sunwell_result.resonance_iterations,
            },
            "evaluation_details": {
                "lens_contribution": list(run.evaluation_details.lens_contribution),
                "judge_rejections": list(run.evaluation_details.judge_rejections),
                "resonance_fixes": list(run.evaluation_details.resonance_fixes),
                "features_delta": list(run.evaluation_details.features_delta),
            },
            "prompts_snapshot": run.prompts_snapshot,
        }

        with self.transaction():
            self._conn.execute(
                """
                INSERT OR REPLACE INTO evaluation_runs (
                    id, timestamp, task, model, lens, sunwell_version,
                    single_shot_score, sunwell_score, improvement_percent, winner,
                    input_tokens, output_tokens, estimated_cost_usd,
                    git_commit, config_hash, details_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run.id,
                    run.timestamp.timestamp(),
                    run.task,
                    run.model,
                    run.lens,
                    run.sunwell_version,
                    run.single_shot_score,
                    run.sunwell_score,
                    run.improvement_percent,
                    run.winner,
                    run.input_tokens,
                    run.output_tokens,
                    run.estimated_cost_usd,
                    run.git_commit,
                    run.config_hash,
                    json.dumps(details),
                ),
            )

    def load(self, run_id: str) -> EvaluationRun | None:
        """Load an evaluation run by ID.

        Args:
            run_id: The run ID to load.

        Returns:
            EvaluationRun if found, None otherwise.
        """
        row = self._conn.execute(
            "SELECT * FROM evaluation_runs WHERE id = ?", (run_id,)
        ).fetchone()

        if not row:
            return None

        return self._row_to_run(row)

    def load_recent(self, limit: int = 50) -> list[EvaluationRun]:
        """Load recent evaluation runs.

        Args:
            limit: Maximum number of runs to return.

        Returns:
            List of EvaluationRun objects, most recent first.
        """
        rows = self._conn.execute(
            "SELECT * FROM evaluation_runs ORDER BY timestamp DESC LIMIT ?",
            (limit,),
        ).fetchall()

        return [self._row_to_run(row) for row in rows]

    def load_summaries(
        self,
        limit: int = 50,
        task: str | None = None,
        model: str | None = None,
        lens: str | None = None,
    ) -> list[EvaluationSummary]:
        """Load lightweight summaries for list views.

        Args:
            limit: Maximum number to return.
            task: Filter by task name.
            model: Filter by model.
            lens: Filter by lens.

        Returns:
            List of EvaluationSummary objects.
        """
        query = """
            SELECT id, timestamp, task, model, lens,
                   single_shot_score, sunwell_score, improvement_percent, winner
            FROM evaluation_runs
            WHERE 1=1
        """
        params: list[Any] = []

        if task:
            query += " AND task = ?"
            params.append(task)
        if model:
            query += " AND model = ?"
            params.append(model)
        if lens:
            query += " AND lens = ?"
            params.append(lens)

        query += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)

        rows = self._conn.execute(query, params).fetchall()

        return [
            EvaluationSummary(
                id=row["id"],
                timestamp=datetime.fromtimestamp(row["timestamp"]),
                task=row["task"],
                model=row["model"],
                lens=row["lens"],
                single_shot_score=row["single_shot_score"],
                sunwell_score=row["sunwell_score"],
                improvement_percent=row["improvement_percent"],
                winner=row["winner"],
            )
            for row in rows
        ]

    def load_by_task(self, task: str) -> list[EvaluationRun]:
        """Load all runs for a specific task."""
        rows = self._conn.execute(
            "SELECT * FROM evaluation_runs WHERE task = ? ORDER BY timestamp DESC",
            (task,),
        ).fetchall()
        return [self._row_to_run(row) for row in rows]

    def load_by_lens(self, lens: str) -> list[EvaluationRun]:
        """Load all runs using a specific lens."""
        rows = self._conn.execute(
            "SELECT * FROM evaluation_runs WHERE lens = ? ORDER BY timestamp DESC",
            (lens,),
        ).fetchall()
        return [self._row_to_run(row) for row in rows]

    def load_by_model(self, model: str) -> list[EvaluationRun]:
        """Load all runs using a specific model."""
        rows = self._conn.execute(
            "SELECT * FROM evaluation_runs WHERE model = ? ORDER BY timestamp DESC",
            (model,),
        ).fetchall()
        return [self._row_to_run(row) for row in rows]

    # =========================================================================
    # Statistics
    # =========================================================================

    def aggregate_stats(self) -> EvaluationStats:
        """Compute aggregate statistics from all runs.

        Returns:
            EvaluationStats with win rates, averages, and breakdowns.
        """
        # Overall counts
        total = self._conn.execute(
            "SELECT COUNT(*) as count FROM evaluation_runs"
        ).fetchone()["count"]

        if total == 0:
            return EvaluationStats(
                total_runs=0,
                sunwell_wins=0,
                single_shot_wins=0,
                ties=0,
                avg_improvement=0.0,
                avg_sunwell_score=0.0,
                avg_single_shot_score=0.0,
            )

        # Win counts
        wins = self._conn.execute("""
            SELECT winner, COUNT(*) as count
            FROM evaluation_runs
            GROUP BY winner
        """).fetchall()

        win_counts = {row["winner"]: row["count"] for row in wins}

        # Averages
        avgs = self._conn.execute("""
            SELECT
                AVG(improvement_percent) as avg_improvement,
                AVG(sunwell_score) as avg_sunwell,
                AVG(single_shot_score) as avg_single_shot
            FROM evaluation_runs
        """).fetchone()

        # By task
        by_task = {}
        task_rows = self._conn.execute("""
            SELECT task, COUNT(*) as count,
                   AVG(improvement_percent) as avg_improvement,
                   SUM(CASE WHEN winner = 'sunwell' THEN 1 ELSE 0 END) as sunwell_wins
            FROM evaluation_runs
            GROUP BY task
        """).fetchall()
        for row in task_rows:
            by_task[row["task"]] = {
                "count": row["count"],
                "avg_improvement": row["avg_improvement"],
                "win_rate": (row["sunwell_wins"] / row["count"]) * 100,
            }

        # By model
        by_model = {}
        model_rows = self._conn.execute("""
            SELECT model, COUNT(*) as count,
                   AVG(improvement_percent) as avg_improvement,
                   SUM(CASE WHEN winner = 'sunwell' THEN 1 ELSE 0 END) as sunwell_wins
            FROM evaluation_runs
            GROUP BY model
        """).fetchall()
        for row in model_rows:
            by_model[row["model"]] = {
                "count": row["count"],
                "avg_improvement": row["avg_improvement"],
                "win_rate": (row["sunwell_wins"] / row["count"]) * 100,
            }

        # By lens
        by_lens = {}
        lens_rows = self._conn.execute("""
            SELECT lens, COUNT(*) as count,
                   AVG(improvement_percent) as avg_improvement,
                   AVG(sunwell_score) as avg_score
            FROM evaluation_runs
            WHERE lens IS NOT NULL
            GROUP BY lens
        """).fetchall()
        for row in lens_rows:
            by_lens[row["lens"]] = {
                "count": row["count"],
                "avg_improvement": row["avg_improvement"],
                "avg_score": row["avg_score"],
            }

        return EvaluationStats(
            total_runs=total,
            sunwell_wins=win_counts.get("sunwell", 0),
            single_shot_wins=win_counts.get("single_shot", 0),
            ties=win_counts.get("tie", 0),
            avg_improvement=avgs["avg_improvement"] or 0.0,
            avg_sunwell_score=avgs["avg_sunwell"] or 0.0,
            avg_single_shot_score=avgs["avg_single_shot"] or 0.0,
            by_task=by_task,
            by_model=by_model,
            by_lens=by_lens,
        )

    # =========================================================================
    # Regression Detection
    # =========================================================================

    def compare_to_baseline(
        self,
        baseline_version: str,
        current_version: str,
    ) -> dict[str, Any]:
        """Compare current version performance to a baseline.

        Args:
            baseline_version: Sunwell version to compare against.
            current_version: Current Sunwell version.

        Returns:
            Dict with comparison metrics.
        """
        baseline = self._conn.execute("""
            SELECT AVG(sunwell_score) as avg_score,
                   AVG(improvement_percent) as avg_improvement,
                   COUNT(*) as count
            FROM evaluation_runs
            WHERE sunwell_version = ?
        """, (baseline_version,)).fetchone()

        current = self._conn.execute("""
            SELECT AVG(sunwell_score) as avg_score,
                   AVG(improvement_percent) as avg_improvement,
                   COUNT(*) as count
            FROM evaluation_runs
            WHERE sunwell_version = ?
        """, (current_version,)).fetchone()

        if not baseline or baseline["count"] == 0:
            return {"error": f"No baseline data for version {baseline_version}"}
        if not current or current["count"] == 0:
            return {"error": f"No current data for version {current_version}"}

        score_delta = current["avg_score"] - baseline["avg_score"]
        improvement_delta = current["avg_improvement"] - baseline["avg_improvement"]

        return {
            "baseline_version": baseline_version,
            "current_version": current_version,
            "baseline_avg_score": baseline["avg_score"],
            "current_avg_score": current["avg_score"],
            "score_delta": score_delta,
            "improvement_delta": improvement_delta,
            "regression": score_delta < -0.5,  # >0.5 point drop = regression
            "baseline_runs": baseline["count"],
            "current_runs": current["count"],
        }

    # =========================================================================
    # Helpers
    # =========================================================================

    def _row_to_run(self, row: sqlite3.Row) -> EvaluationRun:
        """Convert database row to EvaluationRun."""
        details = safe_json_loads(row["details_json"])

        single_shot_data = details["single_shot_result"]
        sunwell_data = details["sunwell_result"]
        eval_details = details["evaluation_details"]

        return EvaluationRun(
            id=row["id"],
            timestamp=datetime.fromtimestamp(row["timestamp"]),
            task=row["task"],
            model=row["model"],
            lens=row["lens"],
            sunwell_version=row["sunwell_version"],
            single_shot_score=row["single_shot_score"],
            sunwell_score=row["sunwell_score"],
            improvement_percent=row["improvement_percent"],
            winner=row["winner"],
            single_shot_result=SingleShotResult(
                files=tuple(single_shot_data["files"]),
                output_dir=Path(single_shot_data["output_dir"]),
                time_seconds=single_shot_data["time_seconds"],
                turns=single_shot_data["turns"],
                input_tokens=single_shot_data["input_tokens"],
                output_tokens=single_shot_data["output_tokens"],
            ),
            sunwell_result=SunwellResult(
                files=tuple(sunwell_data["files"]),
                output_dir=Path(sunwell_data["output_dir"]),
                time_seconds=sunwell_data["time_seconds"],
                turns=sunwell_data["turns"],
                input_tokens=sunwell_data["input_tokens"],
                output_tokens=sunwell_data["output_tokens"],
                lens_used=sunwell_data["lens_used"],
                judge_scores=tuple(sunwell_data["judge_scores"]),
                resonance_iterations=sunwell_data["resonance_iterations"],
            ),
            evaluation_details=EvaluationDetails(
                lens_contribution=tuple(eval_details["lens_contribution"]),
                judge_rejections=tuple(eval_details["judge_rejections"]),
                resonance_fixes=tuple(eval_details["resonance_fixes"]),
                features_delta=tuple(eval_details["features_delta"]),
            ),
            input_tokens=row["input_tokens"],
            output_tokens=row["output_tokens"],
            estimated_cost_usd=row["estimated_cost_usd"],
            git_commit=row["git_commit"],
            config_hash=row["config_hash"],
            prompts_snapshot=details.get("prompts_snapshot", {}),
        )

    def clear(self) -> None:
        """Clear all evaluation data.

        Warning: This deletes all history.
        """
        with self.transaction():
            self._conn.execute("DELETE FROM evaluation_runs")

    def vacuum(self) -> None:
        """Compact the database."""
        self._conn.execute("VACUUM")


# Re-export types for convenience
__all__ = [
    "EvaluationStore",
    "EvaluationRun",
    "EvaluationSummary",
    "EvaluationStats",
]
