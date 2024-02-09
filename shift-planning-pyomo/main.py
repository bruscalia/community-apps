import argparse
import datetime
import json
import logging
import sys
from typing import Any

from pyomo.environ import (
    ConcreteModel,
    Constraint,
    NonNegativeIntegers,
    Objective,
    SolverFactory,
    TerminationCondition,
    Var,
    minimize,
    value,
)

# Status of the solver after optimizing.
STATUS = {
    TerminationCondition.feasible: "suboptimal",
    TerminationCondition.infeasible: "infeasible",
    TerminationCondition.optimal: "optimal",
    TerminationCondition.unbounded: "unbounded",
}


def main() -> None:
    """Entry point for the template."""

    parser = argparse.ArgumentParser(description="Solve shift-planning with Pyomo.")
    parser.add_argument(
        "-input",
        default="",
        help="Path to input file. Default is stdin.",
    )
    parser.add_argument(
        "-output",
        default="",
        help="Path to output file. Default is stdout.",
    )
    parser.add_argument(
        "-duration",
        default=30,
        help="Max runtime duration (in seconds). Default is 30.",
        type=int,
    )
    parser.add_argument(
        "-provider",
        default="cbc",
        help="Solver provider. Default is cbc.",
    )
    args = parser.parse_args()

    # Read input data, solve the problem, and write the solution.
    input_data = read_input(args.input)
    log("Solving shift-planning:")
    log(f"  - shifts-templates: {len(input_data.get('shifts', []))}")
    log(f"  - demands: {len(input_data.get('demands', []))}")
    log(f"  - max duration: {args.duration} seconds")
    solution = solve(input_data, args.duration, args.provider)
    write_output(args.output, solution)


def solve(input_data: dict[str, Any], duration: int, provider: str) -> dict[str, Any]:
    """Solves the given problem and returns the solution."""

    # Silence all Pyomo logging.
    logging.getLogger("pyomo.core").setLevel(logging.ERROR)

    # Create the Pyomo model
    model = ConcreteModel()

    # Prepare data
    shifts, demands = convert_data(input_data)
    options = input_data.get("options", {})

    # Generate concrete shifts from shift templates.
    concrete_shifts = get_concrete_shifts(shifts)

    # Determine all unique time periods in which demands occur and the shifts covering them.
    periods = get_demand_coverage_periods(concrete_shifts, demands)

    # Determine the time we need to cover.
    required_hours = sum((p.end_time - p.start_time).seconds for p in periods) / 3600

    # Create integer variables indicating how many times a shift is planned.
    model.x_assign = Var([(s["id"],) for s in concrete_shifts], within=NonNegativeIntegers)

    # Bound assignment variables by the minimum and maximum number of workers.
    for s in concrete_shifts:
        model.x_assign[s["id"]].setlb(s["min_workers"])
        if s["max_workers"] >= 0:
            model.x_assign[s["id"]].setub(s["max_workers"])

    # Create variables for tracking various costs.
    if "under_supply_cost" in options:
        model.x_under = Var([(p,) for p in periods], within=NonNegativeIntegers)
        model.underSupply = Var(within=NonNegativeIntegers)
    if "over_supply_cost" in options:
        model.overSupply = Var(within=NonNegativeIntegers)
    model.shift_cost = Var(within=NonNegativeIntegers)

    # Objective function: minimize the cost of the planned shifts
    obj_expr = 0
    if "under_supply_cost" in options:
        obj_expr += sum(model.x_under[p] for p in periods) * options["under_supply_cost"]
    if "over_supply_cost" in options:
        obj_expr += model.overSupply * options["over_supply_cost"]
    obj_expr += model.shift_cost
    model.objective = Objective(expr=obj_expr, sense=minimize)

    # Constraints

    # We need to make sure that all demands are covered (or track under supply).
    for p in periods:
        constraint_name = f"DemandCover_{p.start_time}_{p.end_time}_{p.qualification}"
        # Add the new constraint
        model.add_component(
            constraint_name,
            Constraint(
                expr=sum([model.x_assign[s["id"]] for s in p.covering_shifts]) == sum(d["count"] for d in p.demands)
            ),
        )

    # Track under supply
    if "under_supply_cost" in options:
        model.under_supply = Constraint(
            expr=model.underSupply
            == sum(model.x_under[p] * (p.end_time - p.start_time).seconds / 3600 for p in periods)
        )

    # Track over supply
    if "over_supply_cost" in options:
        model.over_supply = Constraint(
            expr=model.overSupply
            == sum(model.x_assign[s["id"]] * (s["end_time"] - s["start_time"]).seconds / 3600 for s in concrete_shifts)
            - required_hours
        )

    # Track shift cost
    model.shift_cost_track = Constraint(
        expr=model.shift_cost == sum(model.x_assign[s["id"]] * s["cost"] for s in concrete_shifts)
    )

    # Solve the model.
    solver = SolverFactory(provider)
    results = solver.solve(model, tee=False, timelimit=duration)

    # Convert to solution format.
    val = value(model.objective, exception=False)
    schedule = {
        "planned_shifts": [
            {
                "id": s["id"],
                "shift_id": s["shift_id"],
                "time_id": s["time_id"],
                "start_time": s["start_time"],
                "end_time": s["end_time"],
                "qualification": s["qualification"],
                "count": int(round(model.x_assign[s["id"]].value)),
            }
            for s in concrete_shifts
            if model.x_assign[s["id"]].value > 0.5
        ]
        if val
        else [],
    }

    # Creates the statistics.
    statistics = {
        "result": {
            "custom": {
                "provider": provider,
                "status": STATUS.get(results.solver.termination_condition, "unknown"),
                "has_solution": val is not None,
                "constraints": model.nconstraints(),
                "variables": model.nvariables(),
                "planned_shifts": len(schedule["planned_shifts"]),
                "planned_count": sum(s["count"] for s in schedule["planned_shifts"]),
                "shift_cost": model.shift_cost() if val else 0.0,
                "under_supply": model.underSupply() if val and "under_supply_cost" in options else 0.0,
                "over_supply": model.overSupply() if val and "over_supply_cost" in options else 0.0,
                "over_supply_cost": model.overSupply() * options["over_supply_cost"]
                if val and "over_supply_cost" in options
                else 0.0,
                "under_supply_cost": model.underSupply() * options["under_supply_cost"]
                if val and "under_supply_cost" in options
                else 0.0,
            },
            "duration": results.solver.time,
            "value": val,
        },
        "run": {
            "duration": results.solver.time,
        },
        "schema": "v1",
    }

    log(f"  - status: {statistics['result']['custom']['status']}")
    log(f"  - value: {statistics['result']['value']}")
    log(f"  - planned shifts: {statistics['result']['custom']['planned_shifts']}")
    log(f"  - planned count: {statistics['result']['custom']['planned_count']}")
    log(f"  - under supply: {statistics['result']['custom']['under_supply']}")
    log(f"  - over supply: {statistics['result']['custom']['over_supply']}")
    log(f"  - shift cost: {statistics['result']['custom']['shift_cost']}")
    log(f"  - over supply cost: {statistics['result']['custom']['over_supply_cost']}")
    log(f"  - under supply cost: {statistics['result']['custom']['under_supply_cost']}")

    return {
        "solutions": [schedule],
        "statistics": statistics,
    }


class UniqueQualificationDemandPeriod:
    """
    Represents a unique time-period and qualification combination. It lists all demands
    causing the need for this qualification in this time period, as well as all shifts
    helping in covering them.
    """

    def __init__(
        self,
        start_time: datetime.datetime,
        end_time: datetime.datetime,
        qualification: str,
        covering_shifts: list[str],
        demands: list[str],
    ):
        """Creates a new unique time-period and qualification combination."""

        self.start_time = start_time
        self.end_time = end_time
        self.qualification = qualification
        self.covering_shifts = covering_shifts
        self.demands = demands

    def __str__(self) -> str:
        """Returns a string representation of this object."""

        return f"{self.start_time.isoformat()}_{self.end_time.isoformat()}_{self.qualification}"


def get_concrete_shifts(shifts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    # Convert shift templates into concrete shifts. I.e., for every shift and every time
    # it can be planned, we create a concrete shift.
    # While most characteristics are given on the shift itself (except for the time), many
    # of them can be overwritten by the individual times a shift can be planned. E.g., the
    # maximum number of workers that can be assigned to a shift may be less during a night
    # shift than during a day shift.
    concrete_shifts = [
        {
            "id": f"{shift['id']}_{time['id']}",
            "shift_id": shift["id"],
            "time_id": time["id"],
            "start_time": time["start_time"],
            "end_time": time["end_time"],
            # Min workers is 0 at default. Furthermore, it can be overwritten by the individual time.
            "min_workers": time["min_workers"]
            if "min_workers" in time
            else shift["min_workers"]
            if "min_workers" in shift
            else 0,
            # Max workers is -1 at default (unbounded). Furthermore, it can be overwritten by the individual time.
            "max_workers": time["max_workers"]
            if "max_workers" in time
            else shift["max_workers"]
            if "max_workers" in shift
            else -1,
            # Cost is required. Furthermore, it can be overwritten by the individual time.
            "cost": time["cost"] if "cost" in time else shift["cost"],
            # Make sure that the qualification is present.
            "qualification": shift["qualification"] if "qualification" in shift else "",
        }
        for shift in shifts
        for time in shift["times"]
    ]
    return concrete_shifts


def get_demand_coverage_periods(
    concrete_shifts: list[dict[str, Any]], demands: list[dict[str, Any]]
) -> list[UniqueQualificationDemandPeriod]:
    """
    Determines all unique time-periods with demand for a qualification. It returns all
    demands contributing and all shifts potentially covering this time period.
    """

    # Group demands by their required qualification
    demands_per_qualification = {}
    for d in demands:
        qualification = d["qualification"] if "qualification" in d else ""
        if qualification not in demands_per_qualification:
            demands_per_qualification[qualification] = []
        demands_per_qualification[qualification].append(d)

    # Determine all concrete shifts covering a demand
    shifts_per_qualification = {}
    for q in demands_per_qualification:
        shifts_per_qualification[q] = [s for s in concrete_shifts if q == s["qualification"]]

    # Determine all unique time periods
    periods = []
    for q in demands_per_qualification:
        # Determine all unique times for this qualification
        times = set()
        for d in demands_per_qualification[q]:
            times.add(d["start_time"])
            times.add(d["end_time"])
        for s in shifts_per_qualification[q]:
            times.add(s["start_time"])
            times.add(s["end_time"])
        times = sorted(times)

        # Create unique time periods
        for i in range(len(times) - 1):
            start, end = times[i], times[i + 1]
            # Collect all shifts covering this time period and demands contributing to it
            covering_shifts = [
                s for s in shifts_per_qualification[q] if s["start_time"] <= start and s["end_time"] >= end
            ]
            contributing_demands = [
                d for d in demands_per_qualification[q] if d["start_time"] <= start and d["end_time"] >= end
            ]
            if not any(contributing_demands):
                continue
            periods.append(
                UniqueQualificationDemandPeriod(
                    start,
                    end,
                    q,
                    covering_shifts,
                    contributing_demands,
                )
            )

    return periods


def convert_data(
    input_data: dict[str, Any],
) -> tuple[
    list[dict[str, Any]],
    list[dict[str, Any]],
]:
    """Converts the input data into the format expected by the model."""
    shifts = input_data["shifts"]
    demands = input_data["demands"]
    # In-place convert all times to datetime objects.
    for s in shifts:
        for t in s["times"]:
            t["start_time"] = datetime.datetime.fromisoformat(t["start_time"])
            t["end_time"] = datetime.datetime.fromisoformat(t["end_time"])
    for d in demands:
        d["start_time"] = datetime.datetime.fromisoformat(d["start_time"])
        d["end_time"] = datetime.datetime.fromisoformat(d["end_time"])
        d["qualification"] = d["qualification"] if "qualification" in d else ""
    return shifts, demands


def log(message: str) -> None:
    """Logs a message. We need to use stderr since stdout is used for the solution."""

    print(message, file=sys.stderr)


def read_input(input_path) -> dict[str, Any]:
    """Reads the input from stdin or a given input file."""

    input_file = {}
    if input_path:
        with open(input_path, encoding="utf-8") as file:
            input_file = json.load(file)
    else:
        input_file = json.load(sys.stdin)

    return input_file


def write_output(output_path, output) -> None:
    """Writes the output to stdout or a given output file."""

    content = json.dumps(output, indent=2, default=custom_serial)
    if output_path:
        with open(output_path, "w", encoding="utf-8") as file:
            file.write(content + "\n")
    else:
        print(content)


def custom_serial(obj):
    """JSON serializer for objects not serializable by default serializer."""

    if isinstance(obj, (datetime.datetime | datetime.date)):
        return obj.isoformat()
    raise TypeError("Type %s not serializable" % type(obj))


if __name__ == "__main__":
    main()