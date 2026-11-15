"""Background builds of target folders, one job per target id (CONTRACTS v0.3 "Live API").

Real mode calls track A (`pipeline.query`, `pipeline.build.build_target`); once the field is ready,
track B (`detect.run.detect_target`: JPL known objects, detections) runs in the background (T51,
`GET /api/targets/<id>/objects`). Fixture mode copies `fixtures/targets/demo-synthetic`, which stays labelled
`"synthetic": true`.
"""
from __future__ import annotations

import inspect
import json
import shutil
import threading
import time
import traceback
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
FIXTURE = REPO / "fixtures" / "targets" / "demo-synthetic"



def movers_ran(t: dict) -> bool:
    """T106: did the mover search (T06) run on this field (found something, nothing, skipped or failed)?"""
    return any("(T06)" in (p.get("service") or "") for p in t.get("provenance", []))

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
    refresh: bool = False
    detector: int | None = None         # T89: only this detector's images (one band of the map)

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
        self._label_jobs: dict[str, dict] = {}
        self._object_jobs: dict[str, dict] = {}
        self._lock = threading.Lock()
        self._write_lock = threading.Lock()   # T51: label + objects jobs both rewrite target.json

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

    def active_count(self) -> int:
        """T58: field builds running now."""
        with self._lock:
            return sum(1 for j in self._jobs.values() if j.status == "building")

    def building_ids(self) -> frozenset:
        with self._lock:
            return frozenset(t for t, j in self._jobs.items() if j.status == "building")

    def request(self, tid: str, ra: float, dec: float, size: int, refresh: bool = False,
                detector: int | None = None) -> Job:
        with self._lock:
            job = self._jobs.get(tid)
            if job and job.status == "building":
                return job
            if not refresh and self.is_cached(tid):
                return Job(tid, ra, dec, size, status="ready", detector=detector)
            job = Job(tid, ra, dec, size, refresh=refresh, detector=detector)
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
            if not self.fixture:
                self.objects(job.id)   # T51: known objects from JPL in the background, field shows now
        except NoData as e:
            job.status, job.message = "no_data", str(e)
        except Exception as e:  # noqa: BLE001 - reported to the client, full trace to the log
            traceback.print_exc()
            job.status, job.message = "error", f"{type(e).__name__}: {e}"

    def _set(self, job: Job, step: str, message: str, done=None, total=None) -> None:
        job.progress = {"step": step, "done": done, "total": total, "message": message}

    # -- T37: catalogue labels on request ------------------------------------------------------

    def labels(self, tid: str) -> dict:
        """Start (once) or report the label job for a built target: {status, n, message}."""
        tj = self.target_dir(tid) / "target.json"
        if not tj.is_file():
            return {"status": "error", "message": "target not built"}
        with self._lock:
            job = self._label_jobs.get(tid)
            if job is None:
                t = json.loads(tj.read_text(encoding="utf-8"))
                if t.get("labels_requested"):
                    return {"status": "ready", "n": len(t.get("labels", []))}
                job = {"status": "building", "n": None, "message": "asking SIMBAD and Gaia"}
                self._label_jobs[tid] = job
                threading.Thread(target=self._run_labels, args=(tid, job), daemon=True,
                                 name=f"labels-{tid}").start()
        return dict(job)

    def _run_labels(self, tid: str, job: dict) -> None:
        tj = self.target_dir(tid) / "target.json"
        try:
            t = json.loads(tj.read_text(encoding="utf-8"))
            if t.get("synthetic"):
                t["labels"] = []
            else:
                from pipeline.labels import add_labels   # track A (T19), unchanged
                add_labels(t)
            self._merge(tid, t, ("labels",), "labels_requested")
            job.update(status="ready", n=len(t["labels"]))
            job.pop("message", None)
        except Exception as e:  # noqa: BLE001
            traceback.print_exc()
            job.update(status="error", message=f"{type(e).__name__}: {e}")
        finally:
            with self._lock:      # done: later requests read labels_requested from target.json
                self._label_jobs.pop(tid, None)

    def _merge(self, tid: str, t: dict, fields: tuple[str, ...], flag: str) -> None:
        """Write `fields` of t, its new provenance entries and `flag: true` into the target.json on
        disk, re-read under a lock, so the labels and objects jobs never overwrite each other."""
        tj = self.target_dir(tid) / "target.json"
        with self._write_lock:
            cur = json.loads(tj.read_text(encoding="utf-8"))
            for f in fields:
                cur[f] = t.get(f, [])
            seen = {json.dumps(p, sort_keys=True) for p in cur.get("provenance", [])}
            cur.setdefault("provenance", []).extend(
                p for p in t.get("provenance", []) if json.dumps(p, sort_keys=True) not in seen)
            cur[flag] = True
            tmp = tj.with_suffix(f".{flag}.part")
            tmp.write_text(json.dumps(cur, indent=1), encoding="utf-8")
            tmp.replace(tj)

    # -- T51: known objects (JPL) + detections, in the background after a build ---------------

    def objects(self, tid: str) -> dict:
        """Start (once) or report the detect job for a built target: {status, n, message}."""
        tj = self.target_dir(tid) / "target.json"
        if not tj.is_file():
            return {"status": "error", "message": "target not built"}
        with self._lock:
            job = self._object_jobs.get(tid)
            if job is None:
                t = json.loads(tj.read_text(encoding="utf-8"))
                done = t.get("objects_requested")
                if t.get("synthetic") or (done and movers_ran(t)):
                    return {"status": "ready", "n": len(t.get("known_objects", [])) + len(t.get("detections", []))}
                # T106: a field whose known objects were looked up before T06 existed gets only the mover search
                # (a few seconds), not the JPL lookup again (minutes)
                job = {"status": "building", "n": None,
                       "message": "looking for moving sources in the field's images" if done else
                                  "asking JPL for known asteroids and comets (can take a few minutes)"}
                self._object_jobs[tid] = job
                threading.Thread(target=self._run_objects, args=(tid, job, bool(done)), daemon=True,
                                 name=f"objects-{tid}").start()
        return dict(job)

    def _run_objects(self, tid: str, job: dict, movers_only: bool = False) -> None:
        tj = self.target_dir(tid) / "target.json"
        try:
            from detect.run import detect_target
            t = json.loads(tj.read_text(encoding="utf-8"))
            if movers_only:
                from detect.classify import classify_detections
                from detect.movers import find_movers
                t["detections"] = []
                find_movers(t)
                if t["detections"]:
                    classify_detections(t)
            else:
                detect_target(t)
            self._merge(tid, t, ("known_objects", "detections"), "objects_requested")
            job.update(status="ready", n=len(t["known_objects"]) + len(t["detections"]))
            job.pop("message", None)
        except Exception as e:  # noqa: BLE001
            traceback.print_exc()
            job.update(status="error", message=f"{type(e).__name__}: {e}")
        finally:
            with self._lock:
                self._object_jobs.pop(tid, None)

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
        # Track A, imported lazily (needs astropy/pyvo). build_target queries IRSA itself (with a
        # cached exposure list, T27) and raises LookupError when there is no data.
        from pipeline.build import build_target

        self._set(job, "query", "searching IRSA for SPHEREx images")
        kwargs = {}
        if "refresh" in inspect.signature(build_target).parameters:
            kwargs["refresh"] = job.refresh
        if "final_root" in inspect.signature(build_target).parameters:
            kwargs["final_root"] = self.cache_root     # late labels land in the cache folder
        if "progress" in inspect.signature(build_target).parameters:
            kwargs["progress"] = lambda step, done=None, total=None, message="": \
                self._set(job, step, message or step, done, total)
        early: dict = {}
        if "early" in inspect.signature(build_target).parameters:
            kwargs["early"] = lambda stub: self._start_early(stub, early)
        if job.detector:
            kwargs["detectors"] = {job.detector}
        # Build into a temp root so a half-finished build is never served from the cache.
        tmp_root = self.cache_root / ".building"
        tmp_root.mkdir(exist_ok=True)
        try:
            built = Path(build_target(job.id, job.ra_deg, job.dec_deg, job.size_arcmin,
                                      out_root=tmp_root, **kwargs))
        except LookupError as e:  # pipeline.build: no usable SPHEREx images here
            raise NoData(str(e)) from None

        out = self.target_dir(job.id)
        shutil.rmtree(out, ignore_errors=True)
        built.rename(out)
        self._finish_early(job.id, early)   # T54: labels + known objects computed during the download

    # -- T54: labels + known objects while the images download -------------------------------

    EARLY_WAIT_S = 20   # after the frames are ready; otherwise the on-request jobs take over

    def _start_early(self, stub: dict, early: dict) -> None:
        """Labels and known objects need only frame times + the grid: start both on the stub now."""
        import copy

        def labels():
            from pipeline.labels import add_labels
            early["labels"] = add_labels(copy.deepcopy(stub))

        def objects():
            from detect.run import detect_target
            early["objects"] = detect_target(copy.deepcopy(stub), movers=False)   # T106: no images yet

        early["stub"] = stub
        early["threads"] = [threading.Thread(target=fn, daemon=True, name=f"early-{fn.__name__}-{stub['id']}")
                            for fn in (labels, objects)]
        for th in early["threads"]:
            th.start()

    def _finish_early(self, tid: str, early: dict) -> None:
        """Map the early results onto the built frames and merge them (labels_requested /
        objects_requested set, so the viewer and objects() find them ready)."""
        if not early.get("threads"):
            return
        from pipeline.build import remap_to_frames
        from pipeline.motion import summarize

        end = time.monotonic() + self.EARLY_WAIT_S
        for th in early["threads"]:
            th.join(max(0.0, end - time.monotonic()))
        tj = self.target_dir(tid) / "target.json"
        frames = json.loads(tj.read_text(encoding="utf-8"))["frames"]
        stub_frames = early["stub"]["frames"]
        try:
            if "labels" in early:
                t = early["labels"]
                t["labels"] = remap_to_frames(t.get("labels", []), stub_frames, frames)
                scale = t["image"]["pixel_scale_arcsec"]
                for l in t["labels"]:
                    l["motion"] = summarize(l["positions"], frames, scale)
                self._merge(tid, t, ("labels",), "labels_requested")
            if "objects" in early:
                t = early["objects"]
                t["known_objects"] = remap_to_frames(t.get("known_objects", []), stub_frames, frames)
                t["detections"] = []
                self._merge(tid, t, ("known_objects", "detections"), "objects_requested")
        except Exception:  # noqa: BLE001 - the on-request jobs (labels(), objects()) still work
            traceback.print_exc()
