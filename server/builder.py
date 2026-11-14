"""Background builds of target folders, one job per target id (CONTRACTS v0.3 "Live API").

Real mode calls track A (`pipeline.query`, `pipeline.build.build_target`) and, if present, track B
(`detect.run.detect`). Fixture mode copies `fixtures/targets/demo-synthetic`, which stays labelled
`"synthetic": true`.
"""
from __future__ import annotations

import inspect
import json
import shutil
import threading
import traceback
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
FIXTURE = REPO / "fixtures" / "targets" / "demo-synthetic"


class NoData(Exception):
    """SPHEREx has no images at the requested position."""


@dataclass
class Job:
    id: str
    ra_deg: float
    dec_deg: float
    size_arcmin: int
    status: str = "building"            # building | ready | no_data | error
    progress: dict = field(default_factory=lambda: {"step": "query", "done": None, "total": None,
                                                    "message": "queued"})
    message: str | None = None

    def body(self) -> dict:
        b: dict = {"status": self.status, "id": self.id}
        if self.status == "ready":
            b["target_url"] = f"/api/targets/{self.id}/target.json"
        elif self.status == "building":
            b["progress"] = self.progress
            b["poll_url"] = f"/api/jobs/{self.id}"
        else:
            b["message"] = self.message
        return b


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class Builder:
    def __init__(self, cache_root: Path, fixture: bool = False):
        self.cache_root = Path(cache_root)
        self.cache_root.mkdir(parents=True, exist_ok=True)
        self.fixture = fixture
        self._jobs: dict[str, Job] = {}
        self._lock = threading.Lock()

    # -- cache ---------------------------------------------------------------------------------

    def target_dir(self, tid: str) -> Path:
        return self.cache_root / tid

    def is_cached(self, tid: str) -> bool:
        return (self.target_dir(tid) / "target.json").is_file()

    def index(self) -> dict:
        targets = []
        for tj in sorted(self.cache_root.glob("*/target.json")):
            try:
                t = json.loads(tj.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            targets.append({"id": t["id"], "name": t.get("name", t["id"]),
                            "synthetic": bool(t.get("synthetic")),
                            "ra_deg": t["center"]["ra_deg"], "dec_deg": t["center"]["dec_deg"],
                            "n_frames": len(t.get("frames", []))})
        return {"schema_version": "0.1", "targets": targets}

    # -- jobs ----------------------------------------------------------------------------------

    def get(self, tid: str) -> Job | None:
        with self._lock:
            job = self._jobs.get(tid)
        if job is None and self.is_cached(tid):
            job = Job(tid, 0, 0, 0, status="ready")
        return job

    def request(self, tid: str, ra: float, dec: float, size: int, refresh: bool = False) -> Job:
        with self._lock:
            job = self._jobs.get(tid)
            if job and job.status == "building":
                return job
            if not refresh and self.is_cached(tid):
                return Job(tid, ra, dec, size, status="ready")
            job = Job(tid, ra, dec, size)
            self._jobs[tid] = job
        threading.Thread(target=self._run, args=(job,), daemon=True, name=f"build-{tid}").start()
        return job

    def _run(self, job: Job) -> None:
        try:
            if self.fixture:
                self._build_fixture(job)
            else:
                self._build_live(job)
            job.status = "ready"
        except NoData as e:
            job.status, job.message = "no_data", str(e)
        except Exception as e:  # noqa: BLE001 - reported to the client, full trace to the log
            traceback.print_exc()
            job.status, job.message = "error", f"{type(e).__name__}: {e}"

    def _set(self, job: Job, step: str, message: str, done=None, total=None) -> None:
        job.progress = {"step": step, "done": done, "total": total, "message": message}

    # -- fixture mode --------------------------------------------------------------------------

    def _build_fixture(self, job: Job) -> None:
        self._set(job, "render", "fixture mode: copying synthetic demo field")
        out = self.target_dir(job.id)
        tmp = out.with_name(out.name + ".tmp")
        shutil.rmtree(tmp, ignore_errors=True)
        shutil.copytree(FIXTURE, tmp)
        tj = tmp / "target.json"
        t = json.loads(tj.read_text(encoding="utf-8"))
        t["id"] = job.id
        t["synthetic"] = True
        t["name"] = (f"Synthetic demo field (NOT SPHEREx data), served for request "
                     f"RA {job.ra_deg:.4f} Dec {job.dec_deg:+.4f}")
        t.setdefault("provenance", []).append({
            "service": "server --fixture",
            "query": f"ra={job.ra_deg} dec={job.dec_deg} size={job.size_arcmin}; "
                     f"copied {FIXTURE.relative_to(REPO).as_posix()}",
            "retrieved_utc": _now()})
        tj.write_text(json.dumps(t, indent=2), encoding="utf-8")
        shutil.rmtree(out, ignore_errors=True)
        tmp.rename(out)

    # -- live mode -----------------------------------------------------------------------------

    def _build_live(self, job: Job) -> None:
        from pipeline.query import find_exposures  # track A, imported lazily (needs astropy/pyvo)

        self._set(job, "query", "searching IRSA for SPHEREx images")
        exposures, _prov = find_exposures(job.ra_deg, job.dec_deg)
        if not exposures:
            raise NoData(f"no SPHEREx images cover RA {job.ra_deg} Dec {job.dec_deg}")

        try:
            from pipeline.build import build_target
        except ImportError:
            raise RuntimeError(
                f"found {len(exposures)} SPHEREx images, but pipeline.build (T02-T04) is not "
                f"available yet; run the server with --fixture meanwhile") from None

        self._set(job, "download", f"building from {len(exposures)} SPHEREx images",
                  0, len(exposures))
        kwargs = {}
        if "progress" in inspect.signature(build_target).parameters:
            kwargs["progress"] = lambda step, done=None, total=None, message="": \
                self._set(job, step, message or step, done, total)
        # Build into a temp root so a half-finished build is never served from the cache.
        tmp_root = self.cache_root / ".building"
        tmp_root.mkdir(exist_ok=True)
        built = Path(build_target(job.id, job.ra_deg, job.dec_deg, job.size_arcmin,
                                  out_root=tmp_root, **kwargs))

        try:
            from detect.run import detect
        except ImportError:
            detect = None
        if detect is not None:
            self._set(job, "detect", "looking for moving sources")
            detect(built)

        out = self.target_dir(job.id)
        shutil.rmtree(out, ignore_errors=True)
        built.rename(out)
