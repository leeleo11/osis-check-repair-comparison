from __future__ import annotations

from scripts.run_campaign import campaign_order, run_campaign


def test_campaign_order_keeps_t6_in_serial_tail() -> None:
    parallel, serial = campaign_order(["T6", "T2", "T1", "T5"])
    assert parallel == ["T1", "T2", "T5"]
    assert serial == ["T6"]


def test_campaign_calls_every_pair_and_passes_resume() -> None:
    calls: list[tuple[str, str, bool]] = []

    class FakeRunner:
        def run(self, sample, architecture_id, **kwargs):
            calls.append((sample, architecture_id, kwargs["resume"]))
            return {"status": "completed", "architecture_id": architecture_id}

    results = run_campaign(
        runner=FakeRunner(),
        samples=["a", "b"],
        architectures=["T2", "T6"],
        seed=9,
        model="m",
        label="formal",
        resume=True,
        jobs=2,
    )
    assert len(results) == 4
    assert set(calls) == {
        ("a", "T2", True),
        ("b", "T2", True),
        ("a", "T6", True),
        ("b", "T6", True),
    }
