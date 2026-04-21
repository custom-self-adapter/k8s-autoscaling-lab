"""Plot the DoubleWave user count curve used by Locust."""

import matplotlib.pyplot as plt
from pandas import pandas

# Copied from tests/scenarios/locustfile.py
STAGES: list[dict[str, int]] = [
    {"end": 30, "users": 20, "spawn_rate": 20},
    {"end": 120, "users": 100, "spawn_rate": 2},
    {"end": 200, "users": 60, "spawn_rate": 2},
    {"end": 250, "users": 120, "spawn_rate": 10},
    {"end": 300, "users": 20, "spawn_rate": 10},
]


def tick(run_time: int) -> tuple[int, int] | None:
    for stage in STAGES:
        if run_time < stage["end"]:
            return (stage["users"], stage["spawn_rate"])
    return None


def build_step_curve(stages: list[dict[str, int]]) -> dict[str, list[int]]:
    data = {
        "ts": [],
        "users": []
    }
    total_users = 0
    for time in range(0, 300):
        tick_data = tick(time)
        if tick_data:
            users, rate = tick_data
            if total_users < users:
                total_users = min(total_users + rate, users)
            elif total_users > users:
                total_users = max(total_users - rate, users)
            data["ts"].append(time)
            data["users"].append(total_users)
        else:
            break
    
    return data
    

def main() -> None:
    data = build_step_curve(STAGES)
    df = pandas.DataFrame.from_dict(data)

    _, ax = plt.subplots(figsize=(12, 4))
    ax.plot(
        df["ts"],
        df["users"]
    )
    ax.set_title("Locust DoubleWave User Count")
    ax.set_xlabel("Time (s)")
    ax.set_ylabel("Users")
    ax.grid(True, linestyle="--", alpha=0.4)

    plt.show()


if __name__ == "__main__":
    main()
