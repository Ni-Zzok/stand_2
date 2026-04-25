from __future__ import annotations

import argparse
import asyncio
import csv
import statistics
import time
from dataclasses import dataclass
from datetime import datetime, timedelta

import httpx


@dataclass
class RunStats:
    mode: str
    total_requests: int
    success_count: int
    conflict_count: int
    error_count: int
    avg_response_ms: float
    max_response_ms: float


class CompareClient:
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip('/')

    async def reset_and_seed(self, client: httpx.AsyncClient) -> None:
        reset_resp = await client.post(f'{self.base_url}/experiments/reset')
        seed_resp = await client.post(f'{self.base_url}/experiments/seed')
        reset_resp.raise_for_status()
        seed_resp.raise_for_status()

    async def book(self, client: httpx.AsyncClient, payload: dict) -> tuple[int, float]:
        started = time.perf_counter()
        try:
            resp = await client.post(f'{self.base_url}/bookings', json=payload)
            elapsed_ms = (time.perf_counter() - started) * 1000
            return resp.status_code, elapsed_ms
        except httpx.HTTPError:
            elapsed_ms = (time.perf_counter() - started) * 1000
            return 0, elapsed_ms


async def scenario_a(client: CompareClient, http: httpx.AsyncClient, mode: str) -> RunStats:
    base = datetime(2026, 4, 20, 8, 0, 0)
    statuses: list[int] = []
    times: list[float] = []

    for i in range(20):
        room_id = (i % 3) + 1
        payload = {
            'room_id': room_id,
            'user_id': ((i + 1) % 3) + 1,
            'start_time': (base + timedelta(hours=i)).isoformat(),
            'end_time': (base + timedelta(hours=i + 1)).isoformat(),
            'mode': mode,
            'scenario': 'scenario_a_seq',
        }
        status, elapsed = await client.book(http, payload)
        statuses.append(status)
        times.append(elapsed)

    return build_stats(mode, statuses, times)


async def scenario_b(client: CompareClient, http: httpx.AsyncClient, mode: str) -> RunStats:
    statuses: list[int] = []
    times: list[float] = []
    base_start = datetime(2026, 4, 20, 10, 0, 0)

    async def one_call(i: int) -> tuple[int, float]:
        payload = {
            'room_id': 1 if i < 14 else ((i % 3) + 1),
            'user_id': (i % 3) + 1,
            'start_time': base_start.isoformat() if i < 14 else (base_start + timedelta(hours=i)).isoformat(),
            'end_time': (base_start + timedelta(hours=1)).isoformat() if i < 14 else (base_start + timedelta(hours=i + 1)).isoformat(),
            'mode': mode,
            'scenario': 'scenario_b_parallel',
        }
        return await client.book(http, payload)

    results = await asyncio.gather(*(one_call(i) for i in range(20)))
    for status, elapsed in results:
        statuses.append(status)
        times.append(elapsed)

    return build_stats(mode, statuses, times)


def build_stats(mode: str, statuses: list[int], times: list[float]) -> RunStats:
    success_count = sum(1 for s in statuses if s in (200, 201))
    conflict_count = sum(1 for s in statuses if s == 409)
    error_count = len(statuses) - success_count - conflict_count

    return RunStats(
        mode=mode,
        total_requests=len(statuses),
        success_count=success_count,
        conflict_count=conflict_count,
        error_count=error_count,
        avg_response_ms=round(statistics.mean(times), 3) if times else 0.0,
        max_response_ms=round(max(times), 3) if times else 0.0,
    )


def append_csv(path: str, rows: list[RunStats]) -> None:
    with open(path, 'w', newline='', encoding='utf-8') as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=[
                'mode',
                'total_requests',
                'success_count',
                'conflict_count',
                'error_count',
                'avg_response_ms',
                'max_response_ms',
            ],
        )
        writer.writeheader()
        for row in rows:
            writer.writerow(row.__dict__)


async def run(base_url: str, scenario: str, output: str) -> None:
    cc = CompareClient(base_url)
    async with httpx.AsyncClient(timeout=30) as client:
        rows: list[RunStats] = []
        for mode in ('centralized_sync', 'hybrid_async'):
            await cc.reset_and_seed(client)
            if scenario == 'a':
                stats = await scenario_a(cc, client, mode)
            else:
                stats = await scenario_b(cc, client, mode)
            rows.append(stats)

    append_csv(output, rows)
    print(f'Results saved to {output}')
    for row in rows:
        print(row)


def main() -> None:
    parser = argparse.ArgumentParser(description='Compare booking processing modes')
    parser.add_argument('--base-url', default='http://127.0.0.1:8000')
    parser.add_argument('--scenario', choices=['a', 'b'], default='a')
    parser.add_argument('--output', default='results.csv')
    args = parser.parse_args()
    asyncio.run(run(args.base_url, args.scenario, args.output))


if __name__ == '__main__':
    main()
