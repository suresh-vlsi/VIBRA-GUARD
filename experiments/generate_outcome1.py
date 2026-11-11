import os
import copy
import numpy as np
import matplotlib.pyplot as plt

import main as engine
from main import train_baseline
from vibeagent.diagnosis import Diagnoser, make_dataset
from vibeagent.config import FS

# Reproduce the deterministic imbalance experiment used by the dashboard.
baseline = train_baseline(n=80, seed=5)
X, y = make_dataset(40, seed=42)
diagnoser = Diagnoser().fit(X, y)

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
        verbose=False,
    )
finally:
    engine.RPM_NOM = original_rpm

agent = result["agent"]
signals = agent.sigs
rows = result["rows"]

if result["outcome"] not in ("RECOVERED", "MITIGATED_NOT_RECOVERED"):
    raise RuntimeError(
        f"Scenario did not pass mitigation verification: {result['outcome']}"
    )

action_win = result["action_win"]
verify_win = result["verify_win"]

if action_win is None or verify_win is None:
    raise RuntimeError("Missing action or verification window.")

# Agent records one signal and one row per simulation window.
# The action-window signal is measured before the action is executed.
before_idx = int(action_win)

# Select the first active-running signal after the verification window.
post_rows = [
    row for row in rows
    if row["win"] > verify_win
    and row["rpm"] > 0
    and row["state"] != "STOPPED"
]
if not post_rows:
    raise RuntimeError("No active post-verification signal is available.")

after_idx = int(post_rows[0]["win"])

if max(before_idx, after_idx) >= len(signals):
    raise RuntimeError("Signal indices do not align with recorded windows.")

before_signal = np.asarray(signals[before_idx]).flatten()
after_signal = np.asarray(signals[after_idx]).flatten()

# Use the injected-fault window for the fault waveform.
fault_idx = 10
fault_signal = np.asarray(signals[fault_idx]).flatten()

def fft_amplitude(signal):
    signal = np.asarray(signal, dtype=float)
    window = np.hanning(len(signal))
    amp = 2.0 * np.abs(np.fft.rfft(signal * window)) / max(window.sum(), 1e-12)
    freq = np.fft.rfftfreq(len(signal), d=1.0 / FS)
    return freq, amp

plt.rcParams.update({
    "font.size": 10,
    "axes.titlesize": 12,
    "figure.titlesize": 17,
})

fig, axes = plt.subplots(2, 2, figsize=(15, 9))
fig.suptitle(
    "VIBRA-GUARD | Imbalance Monitoring and Active Rejection",
    fontweight="bold",
)

# 1. Actual processed signal at the fault-injection window.
t_fault = np.arange(len(fault_signal)) / FS
axes[0, 0].plot(t_fault, fault_signal, linewidth=0.8)
axes[0, 0].set_title("1. Processed Vibration Waveform")
axes[0, 0].set_xlabel("Time (s)")
axes[0, 0].set_ylabel("Acceleration (g)")
axes[0, 0].grid(alpha=0.3)

# 2. FFT of the same fault-window signal.
freq, amp = fft_amplitude(fault_signal)
axes[0, 1].plot(freq, amp, linewidth=1.0)
axes[0, 1].set_xlim(0, 500)
axes[0, 1].set_title("2. Frequency-Domain Analysis (FFT)")
axes[0, 1].set_xlabel("Frequency (Hz)")
axes[0, 1].set_ylabel("Amplitude (g)")
axes[0, 1].grid(alpha=0.3)

# 3. Actual RMS trend and event markers.
windows = [row["win"] for row in rows]
rms_values = [row["rms"] for row in rows]
axes[1, 0].plot(windows, rms_values, linewidth=1.5, label="Measured RMS")
axes[1, 0].axvline(10, linestyle="--", label="Fault injection")
axes[1, 0].axvline(action_win, linestyle=":", label="Mitigation action")
axes[1, 0].axvline(verify_win, linestyle="-.", label="Verification")
axes[1, 0].set_title("3. RMS Vibration Trend")
axes[1, 0].set_xlabel("Simulation Window")
axes[1, 0].set_ylabel("RMS Acceleration (g)")
axes[1, 0].legend(fontsize=8)
axes[1, 0].grid(alpha=0.3)

# 4. Correct comparison: immediately before action vs after verification.
n = min(len(before_signal), len(after_signal))
time_axis = np.arange(n) / FS
axes[1, 1].plot(
    time_axis, before_signal[:n],
    label=f"Before action (window {before_idx})",
    linewidth=0.9,
)
axes[1, 1].plot(
    time_axis, after_signal[:n],
    label=f"After verification (window {after_idx})",
    linewidth=0.9,
)
axes[1, 1].set_title("4. Vibration Before vs After Mitigation")
axes[1, 1].set_xlabel("Time (s)")
axes[1, 1].set_ylabel("Acceleration (g)")
axes[1, 1].legend(fontsize=8)
axes[1, 1].grid(alpha=0.3)

fig.text(
    0.5, 0.015,
    "Physics-based simulation | 1200 RPM | Imbalance | "
    "Processed principal-axis signal",
    ha="center",
    fontsize=9,
)
plt.tight_layout(rect=[0, 0.04, 1, 0.94])

os.makedirs("results", exist_ok=True)
output = "results/vibra_guard_outcome1.png"
plt.savefig(output, dpi=250, bbox_inches="tight")

print("\nVIBRA-GUARD OUTCOME 1")
print("---------------------")
print("Diagnosis:", result["diag"])
print("Action window:", action_win)
print("Verification window:", verify_win)
print("Before-action signal window:", before_idx)
print("Post-verification signal window:", after_idx)
print(f"Verified RMS: {result['before']:.4f} -> {result['after']:.4f} g")
print(f"Verified reduction: {result['db']:.2f} dB")
print("Outcome:", result["outcome"])
print("Saved:", output)

plt.show()
