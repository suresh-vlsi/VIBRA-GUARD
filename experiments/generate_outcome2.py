import os
import copy
import numpy as np
import matplotlib.pyplot as plt

import main as engine
from main import train_baseline
from vibeagent.diagnosis import Diagnoser, make_dataset

# Same models and experiment settings as the dashboard
baseline = train_baseline(n=80, seed=5)
X, y = make_dataset(40, seed=42)
diagnoser = Diagnoser().fit(X, y)

# Reproduce dashboard RPM configuration
original_rpm = engine.RPM_NOM

try:
    engine.RPM_NOM = 1200.0

    result = engine.run_scenario(
        name="imbalance",
        baseline=copy.deepcopy(baseline),
        diagnoser=diagnoser,
        seed=100,
        n_win=60,
        inject_at=10,
        verbose=False
    )
finally:
    engine.RPM_NOM = original_rpm

# Use official results returned by main.py
before = result["before"]
after = result["after"]
db = result["db"]
diagnosis = result["diag"]
outcome = result["outcome"]
actions = result["actions"]
rows = result["rows"]
events = result["agent"].events

print("\nVIBRA-GUARD OUTCOME 2")
print("----------------------")
print("Diagnosis:", diagnosis)
print("Actions:", actions)
print("RMS before:", before)
print("RMS after:", after)
print("Reduction:", db, "dB")
print("Outcome:", outcome)

# Do not create a misleading figure if the scenario was not mitigated
if not np.isfinite(before) or not np.isfinite(after):
    raise RuntimeError(
        "No valid before/after mitigation measurements. "
        "Check the experiment output above."
    )

reduction = 100 * (1 - after / before)

# Prepare actual event timeline
wanted = ["ANOMALY", "DIAGNOSE", "ACTION", "VERIFY", "RECOVERED", "TRIP"]
selected_events = [
    e for e in events if e.get("type") in wanted
]

# Figure
plt.rcParams.update({
    "font.size": 10,
    "axes.titlesize": 12,
    "figure.titlesize": 17
})

fig, axes = plt.subplots(2, 2, figsize=(15, 9))
fig.suptitle(
    "VIBRA-GUARD | Agentic Diagnosis and Active Mitigation",
    fontweight="bold"
)

# 1. Closed-loop RMS response
ax = axes[0, 0]
windows = [r["win"] for r in rows]
rms = [r["rms"] for r in rows]

ax.plot(windows, rms, linewidth=1.5, label="Measured RMS")
ax.axvline(11, linestyle="--", label="Fault injection")

for e in selected_events:
    if e["type"] == "ACTION":
        ax.axvline(e["win"], linestyle=":", alpha=0.8)

ax.set_title("1. Closed-Loop Vibration Response")
ax.set_xlabel("Simulation Window")
ax.set_ylabel("RMS Acceleration (g)")
ax.legend()
ax.grid(alpha=0.3)

# 2. Actual agent event timeline
ax = axes[0, 1]
levels = {
    "ANOMALY": 5,
    "DIAGNOSE": 4,
    "ACTION": 3,
    "VERIFY": 2,
    "RECOVERED": 1,
    "TRIP": 0
}

for e in selected_events:
    kind = e["type"]
    x = e["win"]
    y = levels[kind]

    ax.scatter(x, y, s=65)
    ax.annotate(
        kind, (x, y),
        xytext=(4, 5),
        textcoords="offset points",
        fontsize=8
    )

ax.set_yticks(list(levels.values()))
ax.set_yticklabels(list(levels.keys()))
ax.set_xlabel("Simulation Window")
ax.set_title("2. Autonomous Agent Event Timeline")
ax.grid(alpha=0.3)

# 3. Official before/after mitigation values
ax = axes[1, 0]
bars = ax.bar(
    ["Before mitigation", "After mitigation"],
    [before, after],
    width=0.5
)
ax.bar_label(bars, fmt="%.4f g", padding=4)
ax.set_ylabel("RMS Acceleration (g)")
ax.set_title("3. Mitigation Verification")
ax.text(
    0.5, 0.85,
    f"RMS reduction: {reduction:.1f}%\n"
    f"Vibration reduction: {db:.2f} dB",
    transform=ax.transAxes,
    ha="center"
)
ax.grid(axis="y", alpha=0.3)

# 4. Actual agent decision summary
ax = axes[1, 1]
ax.axis("off")

action_text = "\n".join(actions) if actions else "No action recorded"

summary = (
    "AUTONOMOUS DIAGNOSIS\n"
    f"Injected fault: Imbalance\n"
    f"Diagnosed fault: {diagnosis}\n\n"
    "MITIGATION ACTIONS\n"
    f"{action_text}\n\n"
    "VERIFICATION RESULT\n"
    f"RMS before: {before:.4f} g\n"
    f"RMS after: {after:.4f} g\n"
    f"Reduction: {reduction:.1f}%\n"
    f"Vibration reduction: {db:.2f} dB\n\n"
    f"FINAL OUTCOME: {outcome}"
)

ax.text(
    0.04, 0.95, summary,
    transform=ax.transAxes,
    va="top",
    fontsize=10,
    linespacing=1.5,
    bbox=dict(boxstyle="round,pad=0.8", alpha=0.08)
)
ax.set_title("4. Agent Decision and Outcome")

fig.text(
    0.5, 0.015,
    "Physics-based simulation | 1200 RPM | Seed 100 | "
    "Measured agent and verification results",
    ha="center",
    fontsize=9
)

plt.tight_layout(rect=[0, 0.04, 1, 0.94])

os.makedirs("results", exist_ok=True)
output = "results/vibra_guard_outcome2.png"

plt.savefig(output, dpi=250, bbox_inches="tight")
print("\nFigure saved:", output)

plt.show()
