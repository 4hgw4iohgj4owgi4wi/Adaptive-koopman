from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_json(path: Path, value: object) -> None:
    path.write_text(
        json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False),
        encoding="utf-8",
    )


def item(comment_id: str, anchor: str, summary: str, status: str, evidence: str, missing: str) -> dict:
    return {
        "comment_id": comment_id,
        "source_anchor": anchor,
        "summary": summary,
        "status": status,
        "current_evidence": evidence,
        "missing_or_minimum_action": missing,
    }


def registered_items() -> list[dict]:
    connector = "report.md; reviewer_response_connector_evidence.md; figure_data/"
    none = "No connector-flow evidence resolves this manuscript-level comment."
    return [
        item("AE-1", "novelty over existing Koopman/MPC/consensus", "Novelty, conditional stability, bilinear Koopman, IRSP and delay-compensation support", "PARTIALLY_ANSWERED", connector, "Reframe novelty and complete non-circular stability, IRSP and delay ablations."),
        item("AE-2", "force-related results and operating-envelope limitations", "Force results, operating envelope, baselines, parameters, statistics and presentation", "PARTIALLY_ANSWERED", connector, "Keep the force trade-off; add operating-envelope, baseline, parameter and statistical evidence."),
        item("R1-1", "Novelty Claim is misleading", "Contribution is an assembly of established techniques", "UNANSWERED", none, "Rewrite contribution and compare against the closest integrated frameworks."),
        item("R1-2", "force peak is higher for NR-KDCC than for AKE-M", "Higher force peak is a core payload-transport metric", "PARTIALLY_ANSWERED", connector, "Run controller-level AKE-M/NR comparison on the frozen four-point plant; report paired force distributions."),
        item("R1-3", "conditional and circularly dependent on simulation logs", "Stability proof is conditional and circular", "UNANSWERED", none, "Derive controller/fallback conditions independently of logged certificate outcomes."),
        item("R1-4", "Network resilience of transport and its comparison is week", "Network-resilience positioning and comparisons are weak", "UNANSWERED", none, "Add the requested resilient network-control baselines and DoS experiments."),
        item("R1-5", "bilinear model as a key contribution", "Bilinear claim conflicts with ablation results", "PARTIALLY_ANSWERED", connector, "The connector smoke test withdraws superiority; complete fair multi-seed Koopman comparison before any new claim."),
        item("R1-6", "tuning parameters for the critical modes", "Critical activation and switching parameters are missing", "UNANSWERED", none, "Publish a complete parameter table and motivation for k_on, k_off and all modes."),
        item("R2-1", "stability analysis is highly conditional", "Closed-loop guarantee is not derived from the controller", "UNANSWERED", none, "Prove or narrow the ISS/UUB claim using independently verifiable conditions."),
        item("R2-2", "continuous control-input domain", "IRSP does not certify the continuous input envelope", "UNANSWERED", none, "Enforce a continuous-domain induced-norm certificate or narrow the claim to sampled inputs."),
        item("R2-3", "ablation results do not substantiate", "Ablations do not support bilinear, IRSP and delay components", "PARTIALLY_ANSWERED", connector, "Bilinear superiority is withdrawn; IRSP and delay still need isolated closed-loop ablations."),
        item("R2-4", "baseline comparison is not sufficiently strong", "Baselines are too weak", "UNANSWERED", none, "Add robust/distributed/delay-resilient MPC and communication-loss-tolerant baselines."),
        item("R2-5", "statistical evidence is insufficient", "Missing uncertainty, significance and multi-seed testing", "UNANSWERED", none, "Run preregistered multi-seed paired trials with intervals, tests and effect sizes."),
        item("R2-6", "entirely simulation/model based", "No high-fidelity or measured connector-force validation", "PARTIALLY_ANSWERED", connector, "Four-point physics replaces the aggregate proxy, but multibody/HIL/hardware measured-force validation is still required."),
        item("R2-7", "operating envelope is too limited", "Low-speed and hairpin limitations", "UNANSWERED", none, "Validate a broader speed/curvature envelope or narrow the vehicular-control claims."),
        item("R3-1", "defensive writing styles", "Defensive manuscript wording", "UNANSWERED", none, "Edit the manuscript for direct scientific statements after claims are frozen."),
        item("R3-2", "info in the citations is missing", "Incomplete citations", "UNANSWERED", none, "Audit and complete references [10], [13], [14], [15] and [37]."),
        item("R3-3", "info of the authors is wrong", "Incorrect author metadata in references", "UNANSWERED", none, "Verify references [13], [33] and [37] against publisher records."),
        item("R3-4", "mathematical inconsistency in Eq (22)", "Eq. 22 does not guarantee the stated norm bound", "UNANSWERED", none, "Correct the gamma_c case split and prove the resulting bound."),
        item("R3-5", "insufficient ablation studies", "Too many modules for the available ablations", "UNANSWERED", none, "Run modular ablations or remove unsupported modules from the contribution claim."),
        item("R3-6", "number of baselines is limited", "Stronger controller baselines required", "UNANSWERED", none, "Add robust/distributed/delay-aware MPC and network-aware consensus baselines."),
        item("R3-7", "Delay-Compensated\" is highlighted", "Title emphasizes delay compensation without evidence", "UNANSWERED", none, "Provide a sensitive delay experiment or remove Delay-Compensated from the title."),
    ]


def markdown_escape(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--review-comments", type=Path, default=ROOT / "review_comments.txt")
    args = parser.parse_args()
    output = args.output_dir.resolve()
    source = args.review_comments.resolve()
    text = source.read_text(encoding="utf-8-sig")
    items = registered_items()
    for entry in items:
        entry["anchor_found"] = entry["source_anchor"].casefold() in text.casefold()
    counts = Counter(entry["status"] for entry in items)
    passed = len(items) == 22 and all(entry["anchor_found"] for entry in items)
    payload = {
        "passed": passed,
        "source": str(source),
        "source_sha256": sha256(source),
        "comment_count": len(items),
        "status_counts": dict(sorted(counts.items())),
        "items": items,
    }
    write_json(output / "review_response_matrix.json", payload)
    lines = [
        "# Reviewer response evidence matrix",
        "",
        f"Source: `{source}`  ",
        f"SHA256: `{payload['source_sha256']}`  ",
        f"Registered comments: {len(items)}; PARTIALLY_ANSWERED={counts['PARTIALLY_ANSWERED']}; UNANSWERED={counts['UNANSWERED']}.",
        "",
        "This connector-flow package does not relabel manuscript-level gaps as solved. `PARTIALLY_ANSWERED` means the current evidence addresses only a defined subclaim.",
        "",
        "| Comment | Status | Issue | Current evidence | Missing evidence / minimum action |",
        "|---|---|---|---|---|",
    ]
    for entry in items:
        lines.append(
            "| {comment_id} | {status} | {summary} | {current_evidence} | {missing_or_minimum_action} |".format(
                **{key: markdown_escape(str(value)) for key, value in entry.items()}
            )
        )
    (output / "review_response_matrix.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({key: value for key, value in payload.items() if key != "items"}, ensure_ascii=False))
    raise SystemExit(0 if passed else 2)


if __name__ == "__main__":
    main()
