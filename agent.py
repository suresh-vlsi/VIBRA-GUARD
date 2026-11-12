"""Agentic decision layer: sense -> detect -> probe -> diagnose -> plan -> act -> verify -> learn."""
import json
from collections import deque
import numpy as np
from .config import *
from .simulator import H_mag
from .dsp import preprocess, features

COST = {"ACTIVE_REJECT": 0.0, "SHIFT_SPEED": 0.05, "DERATE": 0.25, "SAFE_STOP": 1.0}
# prior expected RMS reduction of each action per fault (refined online from outcomes)
PRIOR = {
    "imbalance":     {"ACTIVE_REJECT": .85, "DERATE": .55},
    "misalignment":  {"ACTIVE_REJECT": .80, "DERATE": .55},
    "resonance":     {"SHIFT_SPEED": .85, "ACTIVE_REJECT": .70, "DERATE": .50},
    "looseness":     {"ACTIVE_REJECT": .20, "DERATE": .55},
    "bearing_outer": {"DERATE": .50},
    "bearing_inner": {"DERATE": .50},
}
WAIT = {"ACTIVE_REJECT": 4, "SHIFT_SPEED": 2, "DERATE": 2}
SUCCESS_REDUCTION = 0.35        # >= ~3.7 dB RMS drop counts as success


class Agent:
    def __init__(self, machine, baseline, diagnoser, rejector, log_path=None, verbose=True):
        self.m, self.base, self.diag, self.rej = machine, baseline, diagnoser, rejector
        self.verbose, self.log_path = verbose, log_path
        self.mem = {}                       # learned (fault, action) -> expected reduction
        self.state = "MONITOR"
        self.win, self.fn_est = 0, FN_HEALTHY
        self.over = deque(maxlen=3)
        self.buf = deque(maxlen=3)
        self.rows, self.events, self.sigs = [], [], []
        self.plan, self.cur, self.failed = [], None, set()
        self.fault = None
        self.action_applied = False
        self.minor_rms = None
        self.quiet = 0
        self.mit_rms, self.bad = None, 0
        if log_path:
            open(log_path, "w").close()

    # ---- utilities -------------------------------------------------------
    def calibrate(self):
        self.fn_est = self.rej.identify(self.m)
        self._ev("CALIBRATE", f"identified structural fn = {self.fn_est:.1f} Hz")

    def _ev(self, kind, msg):
        e = {"win": self.win, "t": round(self.m.time, 2), "type": kind, "msg": msg}
        self.events.append(e)
        if self.verbose:
            print(f"  [w{self.win:03d} t={self.m.time:5.1f}s] {kind:<11} {msg}")
        if self.log_path:
            with open(self.log_path, "a") as fh:
                fh.write(json.dumps(e) + "\n")

    def _score(self, a, fault):
        pri = self.mem.get((fault, a), PRIOR[fault].get(a, 0.0))
        return pri - COST[a]

    # ---- main loop step ---------------------------------------------------
    def tick(self, truth=None):
        m = self.m
        act = self.rej.output(m, WIN) if self.rej.enabled else None
        raw = m.step(WIN, act)
        if self.rej.enabled:
            self.rej.update(raw[:, 0])
        self.win += 1
        s = preprocess(raw)
        F = features(s, m.rpm, self.fn_est)
        d, _ = self.base.score(F)
        over = d > self.base.thr
        self.over.append(over)
        self.buf.append((s, m.rpm, over))
        self.sigs.append(s)
        row = dict(win=self.win, t=m.time, rpm=m.rpm, rms=F["rms"], score=d / self.base.thr,
                   state=self.state, truth=truth, action=self.cur)
        self.rows.append(row)

        if self.state == "STOPPED":
            return row
        if F["rms"] > RMS_TRIP and self.state != "VERIFY":
            self._ev("TRIP", f"RMS {F['rms']:.2f} g above safety limit")
            self._safe_stop("hard limit exceeded"); return row

        if self.state == "MONITOR":
            trigger = sum(self.over) >= 2 and over
            if self.minor_rms and F["rms"] < 1.5 * self.minor_rms:
                trigger = False
            if trigger:
                self._open_incident(F)
            elif not over and d < 0.7 * self.base.thr and not self.action_applied:
                self.base.update(F)          # continual learning of the healthy baseline
        elif self.state == "VERIFY":
            self.wait -= 1
            if self.wait <= 0:
                self._verify(F, d)
        elif self.state == "MITIGATED":
            self.quiet = self.quiet + 1 if not over else 0
            self.bad = self.bad + 1 if F["rms"] > 1.5 * self.mit_rms else 0
            if self.bad >= 2:
                self._ev("DEGRADED", "vibration rising again after mitigation -> escalating")
                self.bad = 0
                self.failed.add(self.cur)
                self._next_action(F["rms"])
            elif self.quiet >= 6:
                self._ev("RECOVERED", "vibration back inside healthy envelope; continuing to monitor")
                self.state = "MONITOR"; self.minor_rms = None
        return row

    # ---- incident handling ------------------------------------------------
    def _open_incident(self, F):
        self._ev("ANOMALY", f"score {self.rows[-1]['score']:.1f}x threshold; top deviations "
                 f"{self.base.explain(F)}")
        self._ev("PROBE", "running actuator probe to refresh structural model")
        self.fn_est = self.rej.identify(self.m)
        wins = [(s, r) for s, r, o in self.buf if o] or [(self.buf[-1][0], self.buf[-1][1])]
        feats = [features(s, r, self.fn_est) for s, r in wins]
        fault, conf, why = self.diag.diagnose(feats)
        self.fault = fault
        rms = float(np.mean([f["rms"] for f in feats]))
        ratio = rms / self.base.rms0
        sev = "minor" if ratio < 2.0 else ("moderate" if ratio < 6 else "severe")
        self._ev("DIAGNOSE", f"{fault} (conf {conf:.2f}, severity {sev}, RMS {rms:.3f} g = {ratio:.1f}x baseline) | {why}")
        if fault == "healthy":
            self._ev("DECISION", "false alarm -> keep monitoring, absorb window into baseline")
            self.base.update(feats[-1]); self.over.clear(); return
        if sev == "minor":
            self._ev("DECISION", "minor deviation -> log and keep monitoring (no intervention)")
            self.minor_rms = rms; self.over.clear(); return
        self.rms_before, self.failed, self.cur = rms, set(), None
        self._next_action(rms)

    def _next_action(self, rms_ref):
        fault = self.fault
        cands = [a for a in PRIOR[fault] if a not in self.failed]
        cands = [a for a in cands if self._score(a, fault) > 0]
        cands.sort(key=lambda a: -self._score(a, fault))
        if not cands:
            self._safe_stop("no remaining mitigation options"); return
        self.rms_before = rms_ref
        a = cands[0]
        self._execute(a)

    def _execute(self, a):
        m, fault = self.m, self.fault
        self.cur, self.action_applied = a, True
        if a == "ACTIVE_REJECT":
            harm = (1,) if fault == "imbalance" else (1, 2)
            self.rej.enable(harm)
            self._ev("ACTION", f"ACTIVE_REJECT: FxLMS cancelling orders {harm} (secondary path refreshed)")
        elif a == "SHIFT_SPEED":
            new = self._plan_speed()
            if new is None or abs(new - m.rpm) < 10:
                self._ev("ACTION", "SHIFT_SPEED: no better speed available"); self.failed.add(a)
                self._next_action(self.rms_before); return
            self._ev("ACTION", f"SHIFT_SPEED: {m.rpm:.0f} -> {new:.0f} rpm (steering orders away from fn={self.fn_est:.0f} Hz)")
            m.set_rpm(new); self.rej.reset()
        elif a == "DERATE":
            new = max(RPM_MIN, m.rpm * 0.7)
            self._ev("ACTION", f"DERATE: {m.rpm:.0f} -> {new:.0f} rpm")
            m.set_rpm(new); self.rej.reset()
        self._ev("ALERT", f"maintenance notified: suspected {fault}; action={a}")
        self.state, self.wait = "VERIFY", WAIT[a]

    def _plan_speed(self):
        """Pick the speed closest to the setpoint whose predicted vibration is acceptable."""
        grid = np.arange(RPM_MIN, RPM_MAX + 1, 25)
        pred = []
        for rpm in grid:
            fr, sc = rpm / 60, (rpm / RPM_NOM) ** 2
            pred.append(np.sqrt((0.3 * H_mag(fr, self.fn_est)) ** 2 + (0.05 * H_mag(2 * fr, self.fn_est)) ** 2
                                + (0.01 * H_mag(3 * fr, self.fn_est)) ** 2) * sc)
        pred = np.array(pred)
        ok = np.where(pred <= max(1.5 * pred.min(), 0.05))[0]
        return float(grid[ok[np.argmin(np.abs(grid[ok] - RPM_NOM))]])

    def _verify(self, F, d):
        red = 1 - F["rms"] / max(self.rms_before, 1e-9)
        ok = red >= SUCCESS_REDUCTION or d < self.base.thr
        key = (self.fault, self.cur)
        prior = self.mem.get(key, PRIOR[self.fault].get(self.cur, 0.5))
        self.mem[key] = 0.6 * prior + 0.4 * float(np.clip(red, 0, 1))      # learn from outcome
        db = 20 * np.log10(self.rms_before / max(F["rms"], 1e-9))
        if ok:
            self._ev("VERIFY", f"{self.cur} succeeded: RMS {self.rms_before:.3f} -> {F['rms']:.3f} g ({db:.1f} dB)")
            self.state, self.mit_rms = "MITIGATED", F["rms"]
            self.quiet = self.bad = 0
        else:
            self._ev("VERIFY", f"{self.cur} insufficient: only {db:.1f} dB -> escalating")
            if self.cur == "ACTIVE_REJECT":
                self.rej.disable()
            self.failed.add(self.cur)
            self._next_action(F["rms"])

    def _safe_stop(self, why):
        self._ev("ACTION", f"SAFE_STOP: {why}")
        self._ev("ALERT", f"maintenance REQUIRED: suspected {self.fault}; machine stopped")
        self.m.stopped = True; self.rej.disable()
        self.state, self.cur = "STOPPED", "SAFE_STOP"
