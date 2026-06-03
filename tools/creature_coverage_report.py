from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.database import SessionLocal
from backend.models import Card
from backend.rules_engine import build_creature_coverage
from sqlalchemy import select


def main() -> int:
    parser = argparse.ArgumentParser(description="Report Playmode creature automation coverage.")
    parser.add_argument("--summary", action="store_true", help="Print only high-level counts.")
    args = parser.parse_args()

    with SessionLocal() as db:
        cards = db.scalars(select(Card).where(Card.type.ilike("%creature%")).order_by(Card.name.asc(), Card.id.asc())).all()
    coverage = build_creature_coverage(cards)
    if args.summary:
        print(json.dumps({
            "total_creatures": coverage["total_creatures"],
            "status_counts": coverage["status_counts"],
            "automated_tag_counts": coverage["automated_tag_counts"],
            "partial_tag_counts": coverage["partial_tag_counts"],
            "missing_tag_counts": coverage["missing_tag_counts"],
            "highest_priority_missing": [
                {
                    "id": item["id"],
                    "name": item["name"],
                    "missing_tags": item["missing_tags"],
                }
                for item in coverage["highest_priority_missing"][:30]
            ],
        }, indent=2, ensure_ascii=False))
        return 0
    print(json.dumps(coverage, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
