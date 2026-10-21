"""Apply only a reviewed saved plan whose exact hash the operator explicitly approves."""
import argparse
import hashlib
import pathlib
import subprocess


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan", type=pathlib.Path)
    parser.add_argument("--approve-plan-sha256", required=True)
    parser.add_argument("--approved-budget", required=True, help="Approval reference and maximum cost/duration")
    args = parser.parse_args()
    plan = args.plan.resolve(strict=True)
    digest = hashlib.sha256(plan.read_bytes()).hexdigest()
    if digest != args.approve_plan_sha256 or len(args.approved_budget.strip()) < 8:
        parser.error("Plan digest or explicit budget approval is missing/incorrect. No apply ran.")
    print(f"Applying operator-approved plan {digest}; budget reference: {args.approved_budget}")
    subprocess.run(["terraform", "apply", str(plan)], cwd=plan.parent, check=True)


if __name__ == "__main__":
    main()
