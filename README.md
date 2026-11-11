# VIBRA-GUARD

### Agentic Vibration Monitoring, Fault Diagnosis & Active Rejection

<p align="center">
  <a href="https://suresh-vlsi.github.io/VIBRA-GUARD/">
    <img src="https://img.shields.io/badge/Project-Portfolio-36D7C2?style=for-the-badge" />
  </a>
  <a href="https://vibra-guard.streamlit.app/">
    <img src="https://img.shields.io/badge/Live-Interactive_Demo-FF4B4B?style=for-the-badge&logo=streamlit&logoColor=white" />
  </a>
  <a href="https://github.com/suresh-vlsi/VIBRA-GUARD">
    <img src="https://img.shields.io/badge/Source-GitHub-181717?style=for-the-badge&logo=github" />
  </a>
</p>

**Explore the project:**
- 🌐 [Official Project Portfolio](https://suresh-vlsi.github.io/VIBRA-GUARD/)
- 🚀 [Launch Interactive Dashboard](https://vibra-guard.streamlit.app/)
- 💻 [View Source Code](https://github.com/suresh-vlsi/VIBRA-GUARD)


## Agentic Vibration Monitoring, Fault Diagnosis and Active Rejection

VIBRA-GUARD is a **software-only, simulation-based demonstrator** for closed-loop rotating-machine vibration monitoring. It combines a physics-based machine simulator, synthetic 3-axis IMU signals, signal processing, anomaly detection, hybrid fault diagnosis, agentic mitigation and measurement-based verification.

> **Validation scope:** Results in this repository are from simulation. They are not evidence of performance on physical machinery or real IMU hardware.

## System workflow

```text
Physics-based machine simulator
            |
      Synthetic 3-axis IMU
            |
  Preprocessing and DSP features
            |
      Anomaly detection
            |
  Probe / fault diagnosis (ML + rules)
            |
       Agent action plan
            |
  Active rejection / speed change /
       derating / safe stop
            |
     Independent verification
            |
     Recovery or escalation
            +---- feedback to monitoring
```

## Main capabilities

- **Simulation:** rotating-machine dynamics, structural response and configurable fault injection.
- **Signal processing:** preprocessing, principal-axis fusion, FFT/order features, RMS, kurtosis, crest factor and envelope features.
- **Anomaly detection:** healthy-baseline modelling and online monitoring.
- **Fault diagnosis:** Random Forest classification combined with physics-informed rules.
- **Active mitigation:** harmonic feed-forward FxLMS rejection and operating-speed interventions.
- **Agentic workflow:** monitor, detect, probe, diagnose, plan, act, verify, recover/escalate and safe-stop states.
- **Dashboard:** interactive Streamlit interface for scenario runs, batch experiments, plots and exports.

## Fault scenarios

The simulator supports healthy operation and six injected fault classes:

- Imbalance
- Misalignment
- Resonance
- Looseness
- Bearing outer-race defect
- Bearing inner-race defect

## Repository structure

```text
VIBRA_GUARD/
├── main.py
├── dashboard.py
├── requirements.txt
├── vibeagent/
│   ├── agent.py
│   ├── anomaly.py
│   ├── config.py
│   ├── control.py
│   ├── diagnosis.py
│   ├── dsp.py
│   └── simulator.py
├── experiments/
│   ├── robust_validation.py
│   ├── robust_validation_v5_1.py
│   └── ... supporting experiments and figure generators
└── results/
    ├── outcome figures
    └── randomized validation CSVs
```

## Setup

Python 3.10+ is recommended.

### Linux / Ubuntu / WSL

```bash
git clone https://github.com/<your-username>/<your-repository>.git
cd <your-repository>

python3 -m venv .venv
source .venv/bin/activate

python -m pip install --upgrade pip
pip install -r requirements.txt
```

### Run the command-line experiment

```bash
python main.py --quick
```

For the full experiment:

```bash
python main.py
```

### Launch the dashboard

```bash
streamlit run dashboard.py
```

Open the local URL printed by Streamlit (usually `http://localhost:8501`).

## Randomized validation

The validation scripts are kept separate from the main application:

```bash
python -m experiments.robust_validation --trials 5 --quiet
python -m experiments.robust_validation_v5_1 --trials 5 --quiet
```

Run larger trial counts for more informative statistics:

```bash
python -m experiments.robust_validation_v5_1 --trials 20 --quiet
```

The scripts write validation CSV files under `results/`. These are simulation experiments; report trial counts and limitations alongside any performance percentages. The corrected V5.1 validation script is an experimental evaluation tool and does not change the agent implementation.

## Important limitations

- No physical IMU, motor rig or actuator has been tested as part of this software demonstrator.
- Synthetic signals and simulator assumptions may not represent all real machines, sensor mounting conditions or fault severities.
- The single-mode/secondary-path assumptions limit generalization to complex multi-mode structures.
- Bearing-impact components are broadband/impulsive; harmonic FxLMS rejection is not expected to cancel all such energy.
- Safety thresholds and mitigation policies are simulation parameters, not certified machine-protection settings.
- Real deployment requires sensor calibration, hardware-in-the-loop testing, independent safety engineering and validation on representative machinery.

## Technology

Python, NumPy, SciPy, scikit-learn, Matplotlib, Pandas and Streamlit.

## Acknowledgements / references

See the project presentation and the technical references listed there. Add dataset citations if real public vibration datasets are incorporated in future versions.


## 🌐 Online Resources

| Resource | Link |
|---|---|
| Project Portfolio | https://suresh-vlsi.github.io/VIBRA-GUARD/ |
| Live Dashboard | https://vibra-guard.streamlit.app/ |
| Source Code | https://github.com/suresh-vlsi/VIBRA-GUARD |

## Project Status

VIBRA-GUARD is currently a software-based simulation and research prototype.
The live dashboard operates on simulated IMU data. Physical sensor integration
and hardware-based validation are planned future extensions.
