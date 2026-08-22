from __future__ import annotations

import json
from datetime import datetime
from email.utils import parsedate_to_datetime

from backend.database.models.bet_history import (
    BetHistory,
)
from backend.database.models.bet_leg import (
    BetLeg,
)
from backend.database.session import (
    SessionLocal,
)

from backend.integrations.stake.bet_history_service import (
    StakeBetHistoryService,
)


class StakeBetHistorySyncService:
    def __init__(
        self,
        bet_history_service: StakeBetHistoryService,
    ) -> None:
        self.bet_history_service = (
            bet_history_service
        )

    async def sync_all_history(
        self,
    ) -> int:
        db = SessionLocal()

        imported = 0

        try:
            offset = 0

            while True:
                bets = (
                    await self.bet_history_service.get_bet_history(
                        limit=20,
                        offset=offset,
                    )
                )

                if not bets:
                    break

                for bet in bets:
                    imported += (
                        self._store_bet(
                            db,
                            bet,
                        )
                    )

                db.commit()

                offset += 20

                if offset > 1000:
                    break

            return imported

        finally:
            db.close()

    def _store_bet(
        self,
        db,
        bet: dict,
    ) -> int:
        existing = (
            db.query(BetHistory)
            .filter(
                BetHistory.stake_bet_id
                == bet["bet_id"]
            )
            .first()
        )

        if existing:
            existing.status = bet["status"]

            existing.amount = float(
                bet["amount"]
            )

            existing.payout = (
                float(
                    bet["payout"]
                )
                if bet["payout"] is not None
                else None
            )

            existing.payout_multiplier = (
                float(
                    bet["payout_multiplier"]
                )
                if bet["payout_multiplier"]
                is not None
                else None
            )

            existing.outcomes_json = json.dumps(
                bet["outcomes"]
            )

            existing.updated_at = (
                parsedate_to_datetime(
                    bet["updated_at"]
                )
            )

            return 0

        history = BetHistory(
            stake_bet_id=bet["bet_id"],
            status=bet["status"],
            amount=float(
                bet["amount"]
            ),
            payout=float(
                bet["payout"]
            )
            if bet["payout"] is not None
            else None,
            payout_multiplier=(
                float(
                    bet["payout_multiplier"]
                )
                if bet["payout_multiplier"]
                is not None
                else None
            ),
            outcomes_json=json.dumps(
                bet["outcomes"]
            ),
            created_at=(
                parsedate_to_datetime(
                    bet["created_at"]
                )
            ),
            updated_at=(
                parsedate_to_datetime(
                    bet["updated_at"]
                )
            ),
        )

        db.add(history)

        db.flush()

        for leg in bet["outcomes"]:
            db.add(
                BetLeg(
                    stake_bet_id=bet[
                        "bet_id"
                    ],
                    stake_bet_slip_id=bet[
                        "bet_slip_id"
                    ],
                    bet_history_id=history.id,
                    fixture_id=leg[
                        "fixture"
                    ].get("id"),
                    fixture_name=leg[
                        "fixture"
                    ].get("name"),
                    fixture_slug=leg[
                        "fixture"
                    ].get("slug"),
                    market_id=leg[
                        "market"
                    ].get("id"),
                    market_name=leg[
                        "market"
                    ].get("name"),
                    outcome_id=leg[
                        "outcome"
                    ].get("id"),
                    outcome_name=leg[
                        "outcome"
                    ].get("name"),
                    odds=leg.get(
                        "odds"
                    ),
                    total_odds=leg.get(
                        "total_odds"
                    ),
                    leg_status=leg.get(
                        "leg_status"
                    ),
                    market_status=leg[
                        "market"
                    ].get("status"),
                    fixture_status=leg[
                        "fixture"
                    ].get("status"),
                    bet_status=bet[
                        "status"
                    ],
                    created_at=(
                        parsedate_to_datetime(
                            bet[
                                "created_at"
                            ]
                        )
                    ),
                    updated_at=(
                        parsedate_to_datetime(
                            bet[
                                "updated_at"
                            ]
                        )
                    ),
                )
            )

        return 1