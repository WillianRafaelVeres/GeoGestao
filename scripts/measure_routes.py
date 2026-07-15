"""Measure GET route latency and database round trips.

This script uses Flask's test client against the configured DATABASE_URL. It logs
in by placing an active user id in the session, then performs GET requests only.
It is intended for local diagnostics and CI smoke checks, not load testing. Avoid
using it against an uninitialized database if a GET route may run lazy repair.
"""

from __future__ import annotations

import argparse
import os
import sys
import threading
import time
from pathlib import Path
from statistics import median

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import app as geogestao  # noqa: E402


DEFAULT_PATHS = [
    "/",
    "/projects",
    "/project/create",
    "/my-missions",
    "/clients",
    "/cartorios",
    "/users",
    "/cartorio",
    "/reports",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Measure GeoGestao route performance.")
    parser.add_argument(
        "--runs",
        type=int,
        default=int(os.environ.get("GEOGESTAO_BENCHMARK_RUNS", "3")),
        help="number of GET requests per path",
    )
    parser.add_argument(
        "--paths",
        default=os.environ.get("GEOGESTAO_BENCHMARK_PATHS", ""),
        help="comma-separated path list; defaults to the main GET routes",
    )
    parser.add_argument(
        "--cache-mode",
        choices=("warm", "route-expired", "invalidated", "cold"),
        default=os.environ.get("GEOGESTAO_BENCHMARK_CACHE_MODE", "warm"),
        help=(
            "cache state before each timed request: warm (default), "
            "route-expired, invalidated (same state as after a write), or cold"
        ),
    )
    return parser.parse_args()


def fetch_active_user_id() -> int:
    with geogestao.app.app_context():
        user = geogestao.query_db(
            """
            SELECT id
            FROM usuarios
            WHERE ativo = 1
            ORDER BY
                CASE perfil_acesso
                    WHEN 'admin' THEN 0
                    WHEN 'coordenador' THEN 1
                    WHEN 'tecnico' THEN 2
                    ELSE 3
                END,
                id
            LIMIT 1
            """,
            one=True,
        )
        if not user:
            raise RuntimeError("No active user found for benchmark session.")
        return int(user["id"])


def fetch_first_project_path() -> str | None:
    with geogestao.app.app_context():
        project = geogestao.query_db("SELECT id FROM projetos ORDER BY id LIMIT 1", one=True)
        if not project:
            return None
        return f"/project/{project['id']}"


def fetch_first_client_fragment_path() -> str | None:
    with geogestao.app.app_context():
        client = geogestao.query_db("SELECT id FROM clientes ORDER BY id LIMIT 1", one=True)
        if not client:
            return None
        return f"/clients/{client['id']}/fragment"


def build_paths(path_arg: str) -> list[str]:
    if path_arg.strip():
        return [path.strip() for path in path_arg.split(",") if path.strip()]
    paths = list(DEFAULT_PATHS)
    project_path = fetch_first_project_path()
    if project_path:
        project_id = project_path.rsplit("/", 1)[-1]
        paths.insert(2, f"/projects/{project_id}/fragment")
        paths.insert(4, project_path)
    client_fragment_path = fetch_first_client_fragment_path()
    if client_fragment_path:
        paths.insert(paths.index("/clients") + 1, client_fragment_path)
    return paths


class QueryProbe:
    def __init__(self) -> None:
        self.original = geogestao._execute_cursor
        self.measured_thread_id: int | None = None
        self.reset()

    def reset(self) -> None:
        self.count = 0
        self.seconds = 0.0

    def start_measurement(self) -> None:
        self.reset()
        self.measured_thread_id = threading.get_ident()

    def stop_measurement(self) -> None:
        self.measured_thread_id = None

    def install(self) -> None:
        def wrapper(cur, query, args=()):
            should_record = threading.get_ident() == self.measured_thread_id
            start = time.perf_counter() if should_record else 0.0
            try:
                return self.original(cur, query, args)
            finally:
                if should_record:
                    self.count += 1
                    self.seconds += time.perf_counter() - start

        geogestao._execute_cursor = wrapper

    def uninstall(self) -> None:
        self.stop_measurement()
        geogestao._execute_cursor = self.original


def wait_for_background_refresh(timeout_seconds: float = 10.0) -> None:
    """Let a refresh triggered by warm-up finish before timed samples start."""
    deadline = time.monotonic() + timeout_seconds
    while getattr(geogestao, "_refreshing_due_statuses", False):
        if time.monotonic() >= deadline:
            return
        time.sleep(0.01)


def is_route_cache_key(key) -> bool:
    if isinstance(key, str):
        return key.startswith("route_")
    return bool(
        isinstance(key, tuple)
        and key
        and isinstance(key[0], str)
        and key[0].startswith("route_")
    )


def prepare_cache_state(mode: str) -> None:
    if mode == "warm":
        return
    if mode == "invalidated":
        geogestao.invalidate_runtime_caches()
        return
    with geogestao._lookup_cache_lock:
        if mode == "route-expired":
            expired = [key for key in geogestao._lookup_cache if is_route_cache_key(key)]
            for key in expired:
                geogestao._lookup_cache.pop(key, None)
        elif mode == "cold":
            geogestao._lookup_cache_generation += 1
            geogestao._lookup_cache.clear()
            geogestao._lookup_cache_key_locks.clear()


def measure_path(client, probe: QueryProbe, path: str, runs: int, cache_mode: str) -> dict:
    # Warm caches and lazy route state without including this request in results.
    probe.stop_measurement()
    client.get(path)
    wait_for_background_refresh()

    samples = []
    statuses = []
    sizes = []
    for _ in range(runs):
        prepare_cache_state(cache_mode)
        probe.start_measurement()
        try:
            start = time.perf_counter()
            response = client.get(path)
            total_ms = (time.perf_counter() - start) * 1000
        finally:
            probe.stop_measurement()
        samples.append(
            {
                "total_ms": total_ms,
                "db_ms": probe.seconds * 1000,
                "queries": probe.count,
            }
        )
        statuses.append(response.status_code)
        sizes.append(len(response.get_data()))
    return {
        "path": path,
        "status": statuses[-1],
        "median_total_ms": median(sample["total_ms"] for sample in samples),
        "median_db_ms": median(sample["db_ms"] for sample in samples),
        "median_queries": median(sample["queries"] for sample in samples),
        "bytes": sizes[-1],
    }


def main() -> int:
    args = parse_args()
    if args.runs < 1:
        raise SystemExit("--runs must be at least 1")

    user_id = fetch_active_user_id()
    paths = build_paths(args.paths)
    # O benchmark mede somente as rotas pedidas. Impede que uma atualizacao
    # periodica em background contamine tempo e contagem de queries.
    geogestao._due_statuses_next_refresh = float("inf")
    probe = QueryProbe()
    rows = []
    probe.install()
    try:
        with geogestao.app.test_client() as client:
            with client.session_transaction() as sess:
                sess["user_id"] = user_id
            for path in paths:
                rows.append(measure_path(client, probe, path, args.runs, args.cache_mode))
    finally:
        probe.uninstall()

    print(f"Cache mode: {args.cache_mode}")
    print("| Route | Status | Median total ms | Median DB ms | Median queries | Bytes |")
    print("| --- | ---: | ---: | ---: | ---: | ---: |")
    for row in rows:
        print(
            "| {path} | {status} | {total:.1f} | {db:.1f} | {queries:.0f} | {bytes} |".format(
                path=row["path"],
                status=row["status"],
                total=row["median_total_ms"],
                db=row["median_db_ms"],
                queries=row["median_queries"],
                bytes=row["bytes"],
            )
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
