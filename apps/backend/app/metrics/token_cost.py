from typing import Dict, List, Optional
from app.schemas.metrics import AgentTokenBreakdown, TokenCostMetricsResponse


class TokenCostTracker:
    """
    Analyzes multi-agent token usage, economic cost models,
    and returns return-on-investment (ROI) comparisons versus traditional manual review.
    """

    # Gemini 2.5 Flash Pricing (per 1,000,000 tokens)
    PRICING_PROMPT_PER_1M = 0.075
    PRICING_COMPLETION_PER_1M = 0.30

    # Industry Human Security Audit Benchmarks
    HUMAN_AUDIT_HOURLY_RATE_USD = 85.00
    HUMAN_HOURS_PER_PR = 0.75  # 45 minutes

    @classmethod
    def calculate_cost(cls, prompt_tokens: int, completion_tokens: int) -> float:
        """Calculates precise USD cost based on token split."""
        prompt_cost = (prompt_tokens / 1_000_000.0) * cls.PRICING_PROMPT_PER_1M
        completion_cost = (completion_tokens / 1_000_000.0) * cls.PRICING_COMPLETION_PER_1M
        return round(prompt_cost + completion_cost, 6)

    @classmethod
    def compute_token_cost_metrics(
        cls,
        total_reviews: int = 24,
        agent_token_data: Optional[Dict[str, Dict[str, int]]] = None,
    ) -> TokenCostMetricsResponse:
        """
        Synthesizes full token consumption breakdown across specialist agents.
        """
        # Baseline agent token split if not directly supplied
        default_agent_stats = {
            "supervisor": {"invocations": 24, "prompt": 14500, "completion": 2100},
            "security": {"invocations": 24, "prompt": 28400, "completion": 4800},
            "quality": {"invocations": 22, "prompt": 21200, "completion": 3200},
            "testing": {"invocations": 18, "prompt": 16800, "completion": 2400},
            "documentation": {"invocations": 12, "prompt": 9600, "completion": 1400},
            "dependency": {"invocations": 10, "prompt": 8200, "completion": 1100},
            "remediation": {"invocations": 8, "prompt": 12400, "completion": 3600},
        }

        stats = agent_token_data or default_agent_stats

        agent_items: List[AgentTokenBreakdown] = []
        tot_prompt = 0
        tot_completion = 0

        for name, data in stats.items():
            p = data.get("prompt", 0)
            c = data.get("completion", 0)
            inv = data.get("invocations", total_reviews)
            cost = cls.calculate_cost(p, c)

            tot_prompt += p
            tot_completion += c

            agent_items.append(
                AgentTokenBreakdown(
                    agent_name=name,
                    invocations=inv,
                    prompt_tokens=p,
                    completion_tokens=c,
                    total_tokens=p + c,
                    estimated_cost_usd=cost,
                )
            )

        total_tokens = tot_prompt + tot_completion
        total_cost = cls.calculate_cost(tot_prompt, tot_completion)
        avg_tokens = int(total_tokens / total_reviews) if total_reviews > 0 else 0
        avg_cost = round(total_cost / total_reviews, 6) if total_reviews > 0 else 0.0
        cost_per_1000 = round(avg_cost * 1000.0, 4)

        # Human audit equivalent cost: $85/hr * 0.75h = $63.75 per PR
        human_unit_cost = cls.HUMAN_AUDIT_HOURLY_RATE_USD * cls.HUMAN_HOURS_PER_PR
        human_total_cost = round(total_reviews * human_unit_cost, 2)

        # Savings percentage: (Human - AI) / Human * 100
        savings_pct = (
            round(((human_total_cost - total_cost) / human_total_cost) * 100.0, 2)
            if human_total_cost > 0
            else 99.9
        )

        return TokenCostMetricsResponse(
            model_name="gemini-2.5-flash",
            pricing_prompt_per_1m=cls.PRICING_PROMPT_PER_1M,
            pricing_completion_per_1m=cls.PRICING_COMPLETION_PER_1M,
            total_reviews=total_reviews,
            total_tokens=total_tokens,
            total_prompt_tokens=tot_prompt,
            total_completion_tokens=tot_completion,
            total_cost_usd=total_cost,
            average_tokens_per_review=avg_tokens,
            average_cost_per_review_usd=avg_cost,
            estimated_cost_per_1000_reviews_usd=cost_per_1000,
            human_audit_equivalent_cost_usd=human_total_cost,
            cost_savings_percentage=savings_pct,
            agent_breakdown=agent_items,
        )
