"""Aggregate Phase 6AK live-eval results."""
import json
from pathlib import Path

DIR = Path(__file__).resolve().parents[1] / "audits" / "LIVE_EVAL_RESULTS" / "phase6AK"
rows = []
for p in sorted(DIR.glob("*.json")):
    d = json.loads(p.read_text(encoding="utf-8"))
    cs = d.get("category_scores", {})
    rows.append({
        "id": d.get("prompt_id"),
        "slides": d.get("generated_slide_count"),
        "in_window": d.get("slide_count_in_window"),
        "sources": d.get("source_count"),
        "min_req": d.get("min_sources_required"),
        "ext_met": d.get("external_source_expectation_met"),
        "quality_ok": d.get("deck_quality_ok"),
        "invalid": d.get("deck_quality_invalid_count"),
        "layouts_ok": d.get("all_required_layouts_present"),
        "missing": d.get("required_layouts_missing"),
        "chart_met": d.get("chart_requirement_met"),
        "dc": cs.get("deck_correctness"),
        "ea": cs.get("evidence_accuracy"),
    })

def pct(b):
    n = sum(1 for x in rows if x[b])
    return f"{n}/{len(rows)}"

print(f"{'id':12} {'sl':>3} {'win':>4} {'src':>4} {'min':>4} {'ext':>4} {'qok':>4} {'inv':>4} {'lay':>4} {'dc':>4} {'ea':>4}")
for r in rows:
    print(f"{r['id']:12} {r['slides']:>3} {str(r['in_window']):>4} {r['sources']:>4} {r['min_req']:>4} {str(r['ext_met']):>4} {str(r['quality_ok']):>4} {r['invalid']:>4} {str(r['layouts_ok']):>4} {r['dc']:>4} {r['ea']:>4}")

print()
print(f"delivered:                 {len(rows)}/11")
print(f"slide_count_in_window:     {pct('in_window')}")
print(f"external_source_met:       {pct('ext_met')}")
print(f"deck_quality_ok:           {pct('quality_ok')}")
print(f"all_required_layouts:      {pct('layouts_ok')}")
print(f"chart_requirement_met:     {pct('chart_met')}")
dcs = [r['dc'] for r in rows if r['dc'] is not None]
eas = [r['ea'] for r in rows if r['ea'] is not None]
print(f"mean deck_correctness:     {sum(dcs)/len(dcs):.2f}  (n={len(dcs)})")
print(f"mean evidence_accuracy:    {sum(eas)/len(eas):.2f}  (n={len(eas)})")

print("\nmissing layouts per prompt:")
for r in rows:
    if r['missing']:
        print(f"  {r['id']}: {r['missing']}")
