"""Active vibration rejection: harmonic feed-forward FxLMS (frequency-domain block form)."""
import numpy as np
from scipy import signal
from scipy.optimize import least_squares
from .simulator import _accel_tf


def model_eval(p, f):
    fn, z, K, tau = p
    b, a = _accel_tf(fn, z)
    _, h = signal.freqz(b, a, worN=np.atleast_1d(2 * np.pi * f / FS))
    return (K * h * np.exp(-2j * np.pi * f * tau / FS))[0]

from .config import *


class ActiveRejector:
    def __init__(self, mu=0.7):
        self.mu = mu
        self.enabled = False
        self.harm = (1, 2)
        self.w = {}
        self._ph = None
        self.fn_est = FN_HEALTHY

    # ---- secondary-path identification (actuator -> IMU) ----------------
    def identify(self, machine):
        """Probe the structure and fit a single-mode model S(f) of the actuator->IMU path.

        1) Welch cross-spectrum FRF  H = Pxy/Pxx  (uncorrelated disturbances average out)
        2) least-squares fit of (fn, zeta, gain, delay) around the resonance, where the SNR is high.
        """
        u, y = machine.probe()
        f, Pxy = signal.csd(u, y, fs=FS, nperseg=2048)
        _, Pxx = signal.welch(u, fs=FS, nperseg=2048)
        H = Pxy / Pxx
        band = (f > 30) & (f < 140)
        fn0 = float(f[band][np.argmax(np.abs(H[band]))])

        def model(p, ff):
            fn, z, K, tau = p
            b, a = _accel_tf(fn, z)
            _, h = signal.freqz(b, a, worN=2 * np.pi * ff / FS)
            return K * h * np.exp(-2j * np.pi * ff * tau / FS)

        def res(p):
            r = model(p, f[band]) - H[band]
            return np.r_[r.real, r.imag]

        sol = least_squares(res, [fn0, 0.03, 1.0, 0.0],
                            bounds=([20, 0.003, 0.2, -2], [200, 0.3, 5, 3]))
        self.p = sol.x
        self.fn_est = float(self.p[0])
        return self.fn_est

    def S(self, f):
        return complex(model_eval(self.p, f))

    # ---- control ---------------------------------------------------------
    def enable(self, harmonics=(1, 2)):
        self.harm, self.enabled = tuple(harmonics), True
        self.w = {k: 0j for k in self.harm}

    def disable(self):
        self.enabled, self.w = False, {}

    def reset(self):
        self.w = {k: 0j for k in self.harm}

    def output(self, machine, n):
        """Anti-vibration force for the next block (uses tacho phase)."""
        self._ph = machine.peek_phase(n)
        self._fr = machine.rpm / 60
        y = np.zeros(n)
        for k, w in self.w.items():
            y += w.real * np.cos(k * self._ph) - w.imag * np.sin(k * self._ph)
        return y

    def update(self, e):
        """Adapt from the IMU error signal of the block just played."""
        e = e - e.mean()
        n = len(e)
        for k in self.harm:
            if self._fr <= 0:
                continue
            E = 2.0 / n * np.sum(e * np.exp(-1j * k * self._ph))
            Sk = self.S(k * self._fr)
            if abs(Sk) < 1e-3:
                continue
            self.w[k] = 0.999 * self.w[k] - self.mu * E / Sk
