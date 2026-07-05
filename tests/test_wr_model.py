"""
Regression tests for the Withdrawal-Rate model redesign (Model B1').

See PLAN_wr_model_redesign.md for the full spec. Under B1', the withdrawal
rate defines the actual amount Monte Carlo and the deterministic trajectory
withdraw (portfolio x WR, a "lifestyle budget" set once at retirement start
and inflated thereafter) -- not the user's separately stated expenses. Stated
expenses still size the FIRE number and now drive a "deemed WR" check: the
withdrawal rate the user's stated spending would actually require against
their current portfolio.

Covers:
  - WR monotonicity: higher WR strictly lowers MC success (the core bug fix
    -- previously WR never reached Monte Carlo at all)
  - Pension raises MC success (the WR budget's draw is offset by pension)
  - Scale ~invariance: with no pension, success depends on WR/return/vol, not
    on absolute portfolio size (documents decision D1's trade-off)
  - Deemed-WR arithmetic and warning/headroom messaging
  - Safe-WR finder coherence: the returned rate actually clears its target
    success rate when run back through the main simulation
  - Trajectory: first retirement year's draw ties out to the lifestyle
    budget + NHI - pension (+ year-1 shock); lifestyle_budget_jpy inflates
"""
from models.profile import FinancialProfile
from models.scenario import AssumptionSet
from engine.fire_calculator import run_fire_scenario, project_net_worth


def base_profile(**kwargs) -> FinancialProfile:
    defaults = dict(
        current_age=50,
        target_retirement_age=50,
        employment_type="company_employee",
        annual_gross_income_jpy=8_000_000,
        monthly_expenses_jpy=300_000,
        nisa_balance_jpy=60_000_000,
        cash_savings_jpy=20_000_000,
        taxable_brokerage_jpy=20_000_000,
        nenkin_contribution_months=300,
        nenkin_claim_age=65,
        avg_standard_monthly_remuneration_jpy=400_000,
    )
    defaults.update(kwargs)
    return FinancialProfile(**defaults)


def base_assumptions(**kwargs) -> AssumptionSet:
    defaults = dict(
        investment_return_pct=5.0,
        retirement_return_pct=5.0,
        withdrawal_rate_pct=3.5,
        monte_carlo_simulations=3000,
        nhi_municipality_key="national_average",
        nhi_household_members=1,
    )
    defaults.update(kwargs)
    return AssumptionSet(**defaults)


# Deterministic UUIDs for run_fire_scenario's required scenario_id param.
_UUID = "00000000-0000-4000-8000-{:012d}".format


class TestWithdrawalRateMonotonicity:
    def test_higher_wr_strictly_lowers_mc_success(self):
        """The headline bug fix: WR now actually reaches Monte Carlo, so a
        higher rate drawing more from the same portfolio must show strictly
        lower survival. (Previously identical regardless of WR.)"""
        profile = base_profile()
        r_low = run_fire_scenario(
            profile, "low", _UUID(1), base_assumptions(withdrawal_rate_pct=3.0),
            "tokyo", _skip_mortgage_rate_scenarios=True,
        )
        r_high = run_fire_scenario(
            profile, "high", _UUID(2), base_assumptions(withdrawal_rate_pct=5.0),
            "tokyo", _skip_mortgage_rate_scenarios=True,
        )
        assert r_high.monte_carlo.success_rate_pct < r_low.monte_carlo.success_rate_pct

    def test_wr_budget_scales_linearly_with_rate(self):
        """wr_budget_annual_jpy = current_portfolio x WR -- doubling the rate
        roughly doubles the budget (small variation from portfolio drift is
        not expected here since both runs share the same accumulation)."""
        profile = base_profile()
        r3 = run_fire_scenario(
            profile, "r3", _UUID(3), base_assumptions(withdrawal_rate_pct=3.0),
            "tokyo", _skip_mortgage_rate_scenarios=True,
        )
        r6 = run_fire_scenario(
            profile, "r6", _UUID(4), base_assumptions(withdrawal_rate_pct=6.0),
            "tokyo", _skip_mortgage_rate_scenarios=True,
        )
        assert r6.wr_budget_annual_jpy == 2 * r3.wr_budget_annual_jpy


class TestPensionOffsetsMcDraw:
    def test_pension_raises_mc_success(self):
        """Same portfolio/WR, pension vs no pension: pension offsets the WR
        budget draw once it starts, so survival must be higher with it."""
        no_pension = base_profile(nenkin_contribution_months=0)
        with_pension = base_profile(nenkin_contribution_months=480)
        assumptions = base_assumptions(withdrawal_rate_pct=4.0)
        r_no = run_fire_scenario(
            no_pension, "no-pension", _UUID(5), assumptions, "tokyo",
            _skip_mortgage_rate_scenarios=True,
        )
        r_with = run_fire_scenario(
            with_pension, "with-pension", _UUID(6), assumptions, "tokyo",
            _skip_mortgage_rate_scenarios=True,
        )
        assert r_with.annual_pension_net_jpy > r_no.annual_pension_net_jpy
        assert r_with.monte_carlo.success_rate_pct > r_no.monte_carlo.success_rate_pct


class TestScaleInvariance:
    def test_success_rate_independent_of_portfolio_size(self):
        """Documents D1's trade-off: with no pension, MC success depends only
        on WR/return/volatility, not on absolute portfolio size -- a ¥300M
        portfolio and a ¥30M portfolio drawing the same WR must show success
        within ~1pp of each other. This is why the deemed-WR check exists:
        high MC success alone doesn't mean the withdrawn amount is livable."""
        assumptions = base_assumptions(withdrawal_rate_pct=4.0, monte_carlo_simulations=5000)
        small = base_profile(nisa_balance_jpy=30_000_000, cash_savings_jpy=0,
                              taxable_brokerage_jpy=0, nenkin_contribution_months=0)
        large = base_profile(nisa_balance_jpy=300_000_000, cash_savings_jpy=0,
                              taxable_brokerage_jpy=0, nenkin_contribution_months=0)
        r_small = run_fire_scenario(
            small, "small", _UUID(7), assumptions, "tokyo",
            _skip_mortgage_rate_scenarios=True,
        )
        r_large = run_fire_scenario(
            large, "large", _UUID(8), assumptions, "tokyo",
            _skip_mortgage_rate_scenarios=True,
        )
        assert abs(r_small.monte_carlo.success_rate_pct - r_large.monte_carlo.success_rate_pct) <= 2.0


class TestDeemedWithdrawalRate:
    def test_warning_fires_when_stated_spending_exceeds_wr_budget(self):
        """A conservative WR (3.0%) against this profile's portfolio doesn't
        cover its stated spending -- the deemed-WR warning must fire and
        name the shortfall."""
        profile = base_profile()
        r = run_fire_scenario(
            profile, "low-wr", _UUID(9), base_assumptions(withdrawal_rate_pct=3.0),
            "tokyo", _skip_mortgage_rate_scenarios=True,
        )
        assert r.deemed_wr_gap_pct > 3.0
        assert any("actually mean drawing at" in w for w in r.warnings)

    def test_headroom_message_when_wr_budget_covers_spending(self):
        """A generous WR (5.0%) against the same profile covers its stated
        spending with room to spare -- headroom info, not a warning."""
        profile = base_profile()
        r = run_fire_scenario(
            profile, "high-wr", _UUID(10), base_assumptions(withdrawal_rate_pct=5.0),
            "tokyo", _skip_mortgage_rate_scenarios=True,
        )
        assert r.deemed_wr_gap_pct < 5.0
        assert any("more than your stated spending" in w for w in r.warnings)
        assert not any("actually mean drawing at" in w for w in r.warnings)

    def test_deemed_wr_independent_of_chosen_wr(self):
        """Deemed WR reflects stated spending vs portfolio only -- it must
        not change when the chosen withdrawal_rate_pct changes."""
        profile = base_profile()
        r_a = run_fire_scenario(
            profile, "a", _UUID(11), base_assumptions(withdrawal_rate_pct=3.0),
            "tokyo", _skip_mortgage_rate_scenarios=True,
        )
        r_b = run_fire_scenario(
            profile, "b", _UUID(12), base_assumptions(withdrawal_rate_pct=5.5),
            "tokyo", _skip_mortgage_rate_scenarios=True,
        )
        assert r_a.deemed_wr_gap_pct == r_b.deemed_wr_gap_pct


class TestSafeWithdrawalRateCoherence:
    def test_safe_rate_actually_clears_its_own_target(self):
        """The safe-WR finder's whole purpose: running the MAIN simulation at
        its returned rate should land close to the target success rate.
        (Previously this finder ignored expenses and double-subtracted
        pension -- this test would not have caught that, since it never
        exercised the finder's own coherence; it exercises it now.)"""
        profile = base_profile()
        assumptions = base_assumptions(withdrawal_rate_pct=3.5)
        r = run_fire_scenario(
            profile, "base", _UUID(13), assumptions, "tokyo",
            _skip_mortgage_rate_scenarios=True,
        )
        assert r.mc_safe_withdrawal_rate_pct > 0

        r_at_safe_rate = run_fire_scenario(
            profile, "at-safe-rate", _UUID(14),
            base_assumptions(withdrawal_rate_pct=r.mc_safe_withdrawal_rate_pct,
                              monte_carlo_simulations=5000),
            "tokyo", _skip_mortgage_rate_scenarios=True,
        )
        assert abs(
            r_at_safe_rate.monte_carlo.success_rate_pct - r.mc_safe_withdrawal_target_pct
        ) <= 3.0


class TestTrajectoryLifestyleBudget:
    def test_first_retirement_year_draw_ties_to_lifestyle_budget(self):
        """net_from_portfolio in the first retirement year should equal the
        lifestyle budget (portfolio x WR) plus NHI minus pension (floored at
        0), plus any year-1 residence tax shock."""
        profile = base_profile()
        assumptions = base_assumptions(withdrawal_rate_pct=4.0)
        traj = project_net_worth(profile, assumptions, "tokyo")
        first_retirement = next(t for t in traj if t.phase == "retirement")

        expected_net_need = max(
            0, first_retirement.lifestyle_budget_jpy - first_retirement.pension_income_jpy
        )
        expected_draw = (
            expected_net_need + first_retirement.nhi_premium_jpy
            + first_retirement.year1_residence_tax_jpy
        )
        assert first_retirement.net_from_portfolio_jpy == expected_draw

    def test_lifestyle_budget_matches_portfolio_times_wr_at_retirement_start(self):
        """The lifestyle budget in year 1 of retirement should be exactly the
        prior year's closing portfolio value x WR -- not a separately stated
        expense figure. Uses a profile with accumulation years (no property/
        mortgage adjustments in the retirement-start year) so the last
        accumulation year's closing balance is directly comparable."""
        profile = base_profile(current_age=45, target_retirement_age=50)
        assumptions = base_assumptions(withdrawal_rate_pct=4.0)
        traj = project_net_worth(profile, assumptions, "tokyo")
        last_accum = [t for t in traj if t.phase == "accumulation"][-1]
        first_retirement = next(t for t in traj if t.phase == "retirement")

        expected_budget = int(last_accum.portfolio_value_jpy * (assumptions.withdrawal_rate_pct / 100))
        assert first_retirement.lifestyle_budget_jpy == expected_budget
