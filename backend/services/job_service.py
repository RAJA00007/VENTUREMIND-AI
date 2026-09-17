import asyncio
import uuid
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List, Set

from sqlalchemy import select, and_, or_, desc
from sqlalchemy.orm import Session

from core.config import settings
from core.logging import app_logger
from database.session import SessionLocal
from models.analysis_job import AnalysisJob
from services.analysis_service import analysis_service
from workflows.investment_workflow import investment_graph


class AnalysisJobService:
    def __init__(self):
        self._semaphore: Optional[asyncio.Semaphore] = None
        self._running_tasks: Set[asyncio.Task] = set()

    def _get_semaphore(self) -> asyncio.Semaphore:
        if self._semaphore is None:
            self._semaphore = asyncio.Semaphore(settings.MAX_CONCURRENT_ANALYSIS_JOBS)
        return self._semaphore

    def create_job(
        self,
        db: Session,
        user_id: Optional[int],
        request_data: Dict[str, Any],
        force: bool = False
    ) -> tuple[AnalysisJob, bool]:
        """
        Creates a new analysis job, or returns an existing active job if duplicate.
        Returns tuple: (job, is_new)
        """
        company_name = request_data.get("company", "").strip()

        if not force and company_name:
            # Check for existing queued or running job for this user and company in last 10 minutes
            cutoff = datetime.utcnow() - timedelta(seconds=settings.ANALYSIS_JOB_TIMEOUT_SECONDS)
            stmt = select(AnalysisJob).where(
                and_(
                    AnalysisJob.company_name == company_name,
                    AnalysisJob.status.in_(["queued", "running"]),
                    AnalysisJob.created_at >= cutoff
                )
            )
            if user_id is not None:
                stmt = stmt.where(AnalysisJob.user_id == user_id)
            
            existing = db.execute(stmt).scalars().first()
            if existing:
                app_logger.info(f"Returning existing active job {existing.job_id} for company '{company_name}'")
                return existing, False

        job_id = f"job_{uuid.uuid4().hex}"
        job = AnalysisJob(
            job_id=job_id,
            user_id=user_id,
            company_name=company_name,
            company_id=request_data.get("company_id") or company_name,
            status="queued",
            progress=0,
            current_stage="Queued for analysis",
            current_agent=None,
            input_payload=request_data,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        db.add(job)
        db.commit()
        db.refresh(job)
        return job, True

    def get_job(
        self,
        db: Session,
        job_id: str,
        user_id: Optional[int] = None
    ) -> Optional[AnalysisJob]:
        """
        Fetches an analysis job by job_id, checking ownership and timeout.
        """
        stmt = select(AnalysisJob).where(AnalysisJob.job_id == job_id)
        if user_id is not None:
            stmt = stmt.where(AnalysisJob.user_id == user_id)
        
        job = db.execute(stmt).scalar_one_or_none()
        if not job:
            return None

        # Check for timeout on active jobs
        if job.status in ["queued", "running"]:
            timeout_delta = timedelta(seconds=settings.ANALYSIS_JOB_TIMEOUT_SECONDS)
            if datetime.utcnow() - job.updated_at > timeout_delta:
                job.status = "failed"
                job.error_message = f"Job execution exceeded timeout ({settings.ANALYSIS_JOB_TIMEOUT_SECONDS}s)"
                job.error_type = "JobTimeoutError"
                job.completed_at = datetime.utcnow()
                db.commit()
                db.refresh(job)

        return job

    def get_user_jobs(
        self,
        db: Session,
        user_id: int,
        limit: int = 20
    ) -> List[AnalysisJob]:
        """
        Retrieves recent analysis jobs for a given user.
        """
        stmt = (
            select(AnalysisJob)
            .where(AnalysisJob.user_id == user_id)
            .order_by(desc(AnalysisJob.created_at))
            .limit(limit)
        )
        return list(db.execute(stmt).scalars().all())

    def start_background_job(self, job_id: str) -> None:
        """
        Schedules background execution of the job without blocking.
        """
        task = asyncio.create_task(self._execute_job(job_id))
        self._running_tasks.add(task)
        task.add_done_callback(self._running_tasks.discard)

    async def _execute_job(self, job_id: str) -> None:
        """
        Worker pipeline executing the LangGraph investment workflow asynchronously.
        Guarantees isolated DB sessions and concurrency gating via semaphore.
        """
        sem = self._get_semaphore()
        async with sem:
            # 1. Transition to running
            with SessionLocal() as db:
                job = db.execute(
                    select(AnalysisJob).where(AnalysisJob.job_id == job_id)
                ).scalar_one_or_none()

                if not job:
                    app_logger.error(f"[JobService] Job {job_id} not found at execution start")
                    return

                if job.status == "cancelled":
                    app_logger.info(f"[JobService] Job {job_id} was cancelled before starting")
                    return

                job.status = "running"
                job.progress = 10
                job.current_stage = "Gathering Company Intelligence"
                job.current_agent = "Research, Market, Founder, Finance, GitHub Agents"
                job.started_at = datetime.utcnow()
                job.updated_at = datetime.utcnow()
                db.commit()

                payload = dict(job.input_payload)
                user_id = job.user_id
                company_name = job.company_name

            # 2. Build initial state for workflow
            graph_input = {
                "company": payload.get("company", company_name),
                "company_id": payload.get("company_id") or company_name,
                "industry": payload.get("industry", "AI"),
                "funding": payload.get("funding", 100),
                "employees": payload.get("employees", 100),
                "age": payload.get("age", 3),
                "revenue": payload.get("revenue", 10),
                "growth": payload.get("growth", 20),
                "github_repo": payload.get("github_repo"),
                "founder_names": payload.get("founder_names"),
                "agent_results": {},
                "committee_result": None
            }

            accumulated_state: Dict[str, Any] = {
                "agent_results": {},
                "committee_result": None
            }

            try:
                # 3. Stream through LangGraph nodes to capture real-time progress
                async for event in investment_graph.astream(graph_input):
                    for node_name, node_output in event.items():
                        if node_name == "parallel_independent":
                            if "agent_results" in node_output:
                                accumulated_state["agent_results"].update(node_output["agent_results"])
                            await self._update_job_progress(
                                job_id=job_id,
                                progress=60,
                                current_stage="Evaluating Risk & Predictions",
                                current_agent="Risk Agent, Prediction Agent"
                            )
                        elif node_name == "risk_prediction":
                            if "agent_results" in node_output:
                                accumulated_state["agent_results"].update(node_output["agent_results"])
                            await self._update_job_progress(
                                job_id=job_id,
                                progress=85,
                                current_stage="Deliberating Investment Verdict",
                                current_agent="Investment Committee Agent"
                            )
                        elif node_name == "committee":
                            if "committee_result" in node_output:
                                accumulated_state["committee_result"] = node_output["committee_result"]
                            await self._update_job_progress(
                                job_id=job_id,
                                progress=95,
                                current_stage="Persisting Analysis",
                                current_agent="System"
                            )

                # 4. Save analysis to database
                agent_results = accumulated_state["agent_results"]
                committee_result = accumulated_state["committee_result"]

                with SessionLocal() as db:
                    saved = analysis_service.save_analysis(
                        db=db,
                        company_name=company_name,
                        agent_results=agent_results,
                        committee_result=committee_result,
                        user_id=user_id
                    )

                    job = db.execute(
                        select(AnalysisJob).where(AnalysisJob.job_id == job_id)
                    ).scalar_one_or_none()

                    if job:
                        job.status = "completed"
                        job.progress = 100
                        job.current_stage = "Completed"
                        job.current_agent = None
                        job.analysis_id = saved.id
                        job.completed_at = datetime.utcnow()
                        job.updated_at = datetime.utcnow()
                        db.commit()
                        app_logger.info(f"[JobService] Job {job_id} successfully completed (Analysis ID: {saved.id})")

            except Exception as exc:
                app_logger.error(f"[JobService] Job {job_id} failed with exception: {exc}")
                with SessionLocal() as db:
                    job = db.execute(
                        select(AnalysisJob).where(AnalysisJob.job_id == job_id)
                    ).scalar_one_or_none()
                    if job:
                        job.status = "failed"
                        job.error_message = str(exc)
                        job.error_type = exc.__class__.__name__
                        job.completed_at = datetime.utcnow()
                        job.updated_at = datetime.utcnow()
                        db.commit()

    async def _update_job_progress(
        self,
        job_id: str,
        progress: int,
        current_stage: str,
        current_agent: Optional[str]
    ) -> None:
        """
        Helper to safely update progress state on the job row.
        """
        def _update():
            with SessionLocal() as db:
                job = db.execute(
                    select(AnalysisJob).where(AnalysisJob.job_id == job_id)
                ).scalar_one_or_none()
                if job and job.status == "running":
                    job.progress = progress
                    job.current_stage = current_stage
                    job.current_agent = current_agent
                    job.updated_at = datetime.utcnow()
                    db.commit()

        await asyncio.to_thread(_update)

    def reap_stale_jobs(self) -> int:
        """
        Called during startup lifespan to mark interrupted jobs as failed.
        """
        with SessionLocal() as db:
            stmt = select(AnalysisJob).where(
                AnalysisJob.status.in_(["queued", "running"])
            )
            stale_jobs = db.execute(stmt).scalars().all()
            count = len(stale_jobs)
            for j in stale_jobs:
                j.status = "failed"
                j.error_message = "Server restarted while job was in progress"
                j.error_type = "ServerRestartError"
                j.completed_at = datetime.utcnow()
                j.updated_at = datetime.utcnow()
            if count > 0:
                db.commit()
                app_logger.info(f"[JobService] Reaped {count} stale in-flight jobs on startup")
            return count


job_service = AnalysisJobService()
