#!/usr/bin/env python3
"""
Physical model of a 3-plate capacitive force sensor read by an Arduino Uno
with the CapacitiveSensor library (send pin -- R -- receive pin -- electrode).

Stack (top to bottom):

    ============  top ground plate
    upper dielectric   (default: solid, rigid -> acrylic)
    ------------  sensed electrode (middle)  -> receive pin
    lower dielectric   (default: Dragon Skin 10 Very Fast, treated as PDMS)
    ============  bottom ground plate

Both grounded plates see the middle electrode, so the two layer capacitances
add in PARALLEL:   C_sense = C_upper + C_lower + C_stray

Force -> pressure -> layer compression -> thinner dielectric -> larger C
-> longer RC time -> more loop iterations ("timesteps") in the library.

What the CapacitiveSensor library actually counts (per sample):
  1. receive pin driven LOW, then floated; send pin HIGH
     -> count loop iterations until receive pin reads HIGH   (charge phase)
  2. receive pin driven HIGH, then floated; send pin LOW
     -> count loop iterations until receive pin reads LOW    (discharge phase)
  cycle count = charge counts + discharge counts
  capacitiveSensor(N) returns the SUM over N samples.

Usage:
    python force_cap_sensor_model.py                      # defaults, table
    python force_cap_sensor_model.py --plot
    python force_cap_sensor_model.py --lower ecoflex0030 --lower-t 3 --R 4.7M
    python force_cap_sensor_model.py --list-materials
    python force_cap_sensor_model.py --measured-baseline 3500   # calibrate loop time
Or import it and edit/replace a SensorConfig.

All numbers are ESTIMATES. Material eps_r and modulus values are typical
datasheet-level figures -- measure your own if you can.
"""
from __future__ import annotations

import argparse
import math
from dataclasses import dataclass, field, replace

import numpy as np

EPS0 = 8.8541878128e-12  # F/m
PSI = 6894.757           # Pa per psi
MAX_STRAIN = 0.90        # numerical clamp for compression


# --------------------------------------------------------------------------- #
# Materials
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Material:
    name: str
    eps_r: float             # relative permittivity (~ at 1 kHz - 1 MHz)
    E: float                 # Young's modulus [Pa]
    hyperelastic: bool = False  # True: neo-Hookean rubber; False: linear elastic
    K: float = 1.0e9         # bulk modulus [Pa] (only used for rubbers)


def _silicone(name: str, eps_r: float, modulus_100_psi: float) -> Material:
    """Rubber from its datasheet 100 % modulus.
    Neo-Hookean, uniaxial tension at stretch 2:  sigma = G (2 - 1/4) = 1.75 G
    -> G = M100 / 1.75,   E = 3 G."""
    G = modulus_100_psi * PSI / 1.75
    return Material(name, eps_r, 3.0 * G, hyperelastic=True)


MATERIALS: dict[str, Material] = {
    # --- soft silicones (compressible, nonlinear) ---
    "dragonskin10vf": _silicone("Dragon Skin 10 Very Fast (PDMS-like silicone)", 2.8, 22.0),
    "dragonskin30":   _silicone("Dragon Skin 30", 2.8, 86.0),
    "ecoflex0030":    _silicone("Ecoflex 00-30", 2.8, 10.0),
    "sylgard184":     Material("Sylgard 184 PDMS (10:1)", 2.75, 1.8e6, hyperelastic=True),
    # --- rigid solids (linear, barely compress) ---
    "acrylic":        Material("Acrylic (PMMA)", 3.0, 3.0e9),
    "pet":            Material("PET / Mylar", 3.2, 3.0e9),
    "kapton":         Material("Polyimide (Kapton)", 3.4, 2.5e9),
    "polycarbonate":  Material("Polycarbonate", 2.9, 2.3e9),
    "ptfe":           Material("PTFE", 2.1, 0.5e9),
    "fr4":            Material("FR4", 4.4, 20.0e9),
    "glass":          Material("Glass", 5.5, 70.0e9),
    "air":            Material("Air gap (treated as non-compressible)", 1.0006, 1.0e15),
}
MATERIALS["pdms"] = MATERIALS["dragonskin10vf"]  # alias


@dataclass
class Layer:
    material: Material
    thickness: float  # [m]


# --------------------------------------------------------------------------- #
# Configuration (edit defaults here or override via CLI)
# --------------------------------------------------------------------------- #
@dataclass
class SensorConfig:
    # Geometry
    width: float = 4e-3                 # electrode width  [m]
    length: float = 27e-3                # electrode length [m]
    probe_area: float | None = None      # loaded area [m^2]; None = whole electrode

    # Dielectrics
    upper: Layer = field(default_factory=lambda: Layer(MATERIALS["acrylic"], 3.0e-3))
    lower: Layer = field(default_factory=lambda: Layer(MATERIALS["dragonskin10vf"], 4.5e-3))

    # Mechanics / field options
    bonded: bool = True      # rubber bonded to plates -> stiffer (shape-factor effect)
    fringing: bool = True    # add (roughly constant) edge-field capacitance

    # Electronics
    resistance: float = 1.0e6   # send->receive resistor [ohm]
    r_pin: float = 25.0         # ATmega output pin resistance [ohm]
    c_stray: float = 15e-12     # pin + wiring + breadboard capacitance [F]
    vcc: float = 5.0            # [V] (only ratios matter, kept for display)
    vih_frac: float = 0.60      # input reads HIGH above this fraction of Vcc
    vil_frac: float = 0.30      # input reads LOW below this fraction of Vcc

    # Arduino / library
    loop_time: float = 0.60e-6  # duration of one library while-loop iteration [s]
    samples: int = 30           # argument to capacitiveSensor(samples)
    timeout_counts: int = 620000  # library CS_Timeout_Millis at 16 MHz
    noise_counts: float = 0.0   # 1-sigma jitter per cycle [counts] (optional)

    @property
    def area(self) -> float:
        return self.width * self.length

    @property
    def pressed_area(self) -> float:
        return min(self.probe_area, self.area) if self.probe_area else self.area


# --------------------------------------------------------------------------- #
# Mechanics
# --------------------------------------------------------------------------- #
def _shape_factor(pressed_area: float, t0: float) -> float:
    """S = loaded area / bulge (free) area, using a square-equivalent perimeter."""
    perimeter = 4.0 * math.sqrt(pressed_area)
    return pressed_area / (perimeter * t0)


def compressed_thickness(layer: Layer, pressure: float, pressed_area: float,
                         bonded: bool) -> float:
    """Thickness of the loaded region of a layer under uniform pressure [Pa]."""
    t0 = layer.thickness
    if pressure <= 0:
        return t0
    m = layer.material

    if not m.hyperelastic:                       # rigid solid: Hooke
        return t0 * (1.0 - min(pressure / m.E, MAX_STRAIN))

    G = m.E / 3.0                                # rubber: neo-Hookean
    if bonded:
        S = _shape_factor(pressed_area, t0)
        Ec = m.E * (1.0 + 2.0 * S * S)           # compression modulus of bonded pad
        Ec = 1.0 / (1.0 / Ec + 1.0 / m.K)        # cap by bulk modulus
        G = Ec / 3.0

    # Uniaxial compression: P = G (lam^-2 - lam), lam = t/t0 in (0,1]
    lo, hi = 1.0 - MAX_STRAIN, 1.0
    if G * (lo ** -2 - lo) <= pressure:
        return t0 * lo
    for _ in range(80):                          # bisection (monotonic)
        mid = 0.5 * (lo + hi)
        if G * (mid ** -2 - mid) > pressure:
            lo = mid
        else:
            hi = mid
    return t0 * 0.5 * (lo + hi)


# --------------------------------------------------------------------------- #
# Electrostatics
# --------------------------------------------------------------------------- #
def layer_capacitance(cfg: SensorConfig, layer: Layer, d_pressed: float) -> float:
    A, Ap, d0 = cfg.area, cfg.pressed_area, layer.thickness
    eps = EPS0 * layer.material.eps_r
    C = eps * ((A - Ap) / d0 + Ap / d_pressed)   # unloaded part + loaded part
    if cfg.fringing:
        # Palmer-type edge term, evaluated at the nominal thickness (kept constant)
        w = min(cfg.width, cfg.length)
        C += eps * (A / w) / math.pi * (1.0 + math.log(2.0 * math.pi * w / d0))
    return C


# --------------------------------------------------------------------------- #
# RC + Arduino counting
# --------------------------------------------------------------------------- #
def rc_response(C: float, cfg: SensorConfig):
    tau = (cfg.resistance + cfg.r_pin) * C
    t_charge = -tau * math.log(1.0 - cfg.vih_frac)   # 0 -> VIH
    t_discharge = -tau * math.log(cfg.vil_frac)      # Vcc -> VIL
    n_charge = int(t_charge / cfg.loop_time)
    n_discharge = int(t_discharge / cfg.loop_time)
    return tau, t_charge, t_discharge, n_charge, n_discharge


def evaluate(cfg: SensorConfig, force: float, rng=None) -> dict:
    Ap = cfg.pressed_area
    P = max(force, 0.0) / Ap
    du = compressed_thickness(cfg.upper, P, Ap, cfg.bonded)
    dl = compressed_thickness(cfg.lower, P, Ap, cfg.bonded)
    Cu = layer_capacitance(cfg, cfg.upper, du)
    Cl = layer_capacitance(cfg, cfg.lower, dl)
    C = Cu + Cl + cfg.c_stray

    tau, tc, td, nc, nd = rc_response(C, cfg)
    per_cycle = nc + nd
    if cfg.noise_counts > 0:
        rng = rng or np.random.default_rng()
        reading = float(np.sum(per_cycle + rng.normal(0, cfg.noise_counts, cfg.samples)))
    else:
        reading = float(per_cycle * cfg.samples)
    if per_cycle > cfg.timeout_counts:           # library returns -2 on timeout
        reading = float("nan")

    return dict(
        force=force, pressure=P,
        d_upper=du, d_lower=dl,
        strain_lower=1.0 - dl / cfg.lower.thickness,
        C_upper=Cu, C_lower=Cl, C_total=C,
        tau=tau, t_charge=tc, t_discharge=td,
        n_charge=nc, n_discharge=nd, per_cycle=per_cycle, reading=reading,
    )


def simulate(cfg: SensorConfig, forces, seed: int | None = None) -> dict:
    rng = np.random.default_rng(seed)
    rows = [evaluate(cfg, float(f), rng) for f in np.atleast_1d(forces)]
    return {k: np.array([r[k] for r in rows]) for k in rows[0]}


def fit_loop_time(cfg: SensorConfig, measured_reading_at_zero_force: float) -> float:
    """Loop time that makes the model match one measured baseline reading.
    Note: this lumps loop-speed error AND stray-capacitance error into one number."""
    _, tc, td, *_ = rc_response(evaluate(cfg, 0.0)["C_total"], cfg)
    per_cycle_measured = measured_reading_at_zero_force / cfg.samples
    return (tc + td) / per_cycle_measured


# --------------------------------------------------------------------------- #
# Output
# --------------------------------------------------------------------------- #
def print_summary(cfg: SensorConfig, res: dict) -> None:
    r0 = evaluate(cfg, 0.0)
    print("=" * 78)
    print(f"Electrode      : {cfg.width*1e3:.1f} x {cfg.length*1e3:.1f} mm   "
          f"loaded area {cfg.pressed_area*1e6:.0f} mm^2")
    print(f"Upper dielectric: {cfg.upper.material.name}, {cfg.upper.thickness*1e3:.2f} mm, "
          f"eps_r={cfg.upper.material.eps_r}")
    print(f"Lower dielectric: {cfg.lower.material.name}, {cfg.lower.thickness*1e3:.2f} mm, "
          f"eps_r={cfg.lower.material.eps_r}, "
          f"{'bonded' if cfg.bonded else 'free-slip'}")
    print(f"R = {cfg.resistance/1e6:.3g} Mohm, C_stray = {cfg.c_stray*1e12:.1f} pF, "
          f"loop = {cfg.loop_time*1e6:.3f} us, samples = {cfg.samples}")
    print(f"Baseline (0 N): C = {r0['C_total']*1e12:.2f} pF "
          f"(upper {r0['C_upper']*1e12:.2f}, lower {r0['C_lower']*1e12:.2f}), "
          f"tau = {r0['tau']*1e6:.1f} us, reading = {r0['reading']:.0f}")
    print("=" * 78)
    hdr = (f"{'F [N]':>7} {'P [kPa]':>8} {'d_up [mm]':>10} {'d_low [mm]':>10} {'C [pF]':>8} "
           f"{'t_chg [us]':>10} {'t_dis [us]':>10} {'cnt/cycle':>10} {'reading':>10}")
    print(hdr)
    print("-" * len(hdr))
    for i in range(len(res["force"])):
        print(f"{res['force'][i]:7.2f} {res['pressure'][i]/1e3:8.1f} "
              f"{res['d_upper'][i]*1e3:10.5f} {res['d_lower'][i]*1e3:10.4f} {res['C_total'][i]*1e12:8.3f} "
              f"{res['t_charge'][i]*1e6:10.2f} {res['t_discharge'][i]*1e6:10.2f} "
              f"{res['per_cycle'][i]:10.0f} {res['reading'][i]:10.0f}")
    dC = (res["C_total"][-1] - res["C_total"][0]) * 1e12
    dR = res["reading"][-1] - res["reading"][0]
    span = res["force"][-1] - res["force"][0]
    print("-" * len(hdr))
    print(f"Full-scale change: dC = {dC:.3f} pF, d(reading) = {dR:.0f} counts "
          f"({dR/span:.1f} counts/N)")
    if cfg.noise_counts == 0 and abs(dR) < 3 * cfg.samples:
        print("NOTE: change is only a few counts per sample -> hard to resolve. "
              "Try larger R, thinner/softer lower layer, unbonded, or more samples.")


def plot(res: dict) -> None:
    import matplotlib.pyplot as plt
    fig, axs = plt.subplots(2, 2, figsize=(12, 8))
    F = res["force"]

    # 1) Plate distances (the quantity that actually changes in the sensor).
    #    Upper (solid) and lower (rubber) live on separate y-axes because the
    #    solid barely moves compared with the rubber.
    a = axs[0, 0]
    l1, = a.plot(F, res["d_lower"] * 1e3, "o-", color="tab:blue",
                 label="electrode <-> bottom ground (lower dielectric)")
    a.set(xlabel="Force [N]", ylabel="Lower gap [mm]", title="Distance between plates")
    a.yaxis.label.set_color("tab:blue")
    a2 = a.twinx()
    l2, = a2.plot(F, res["d_upper"] * 1e3, "s--", color="tab:red",
                  label="top ground <-> electrode (upper dielectric)")
    a2.set_ylabel("Upper gap [mm]", color="tab:red")
    a.legend(handles=[l1, l2], loc="lower left", fontsize=8)

    # 2) Capacitance, split by layer
    a = axs[0, 1]
    a.plot(F, res["C_total"] * 1e12, "o-", label="total (incl. stray)")
    a.plot(F, res["C_lower"] * 1e12, "--", label="lower layer")
    a.plot(F, res["C_upper"] * 1e12, "--", label="upper layer")
    a.set(xlabel="Force [N]", ylabel="C [pF]", title="Capacitance")
    a.legend(fontsize=8)

    # 3) RC times
    a = axs[1, 0]
    a.plot(F, res["t_charge"] * 1e6, label="charge")
    a.plot(F, res["t_discharge"] * 1e6, label="discharge")
    a.set(xlabel="Force [N]", ylabel="Time [us]", title="RC times")
    a.legend(fontsize=8)

    # 4) Library output
    a = axs[1, 1]
    a.plot(F, res["reading"], "o-")
    a.set(xlabel="Force [N]", ylabel="Reading [counts]", title="capacitiveSensor() output")

    for a in axs.flat:
        a.grid(alpha=0.3)
    fig.tight_layout()
    plt.show()


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def parse_si(s: str) -> float:
    mult = {"k": 1e3, "K": 1e3, "M": 1e6, "G": 1e9, "u": 1e-6, "n": 1e-9, "p": 1e-12}
    s = str(s).strip()
    return float(s[:-1]) * mult[s[-1]] if s[-1] in mult else float(s)


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--list-materials", action="store_true")
    p.add_argument("--upper", default="acrylic", choices=MATERIALS)
    p.add_argument("--lower", default="dragonskin10vf", choices=MATERIALS)
    p.add_argument("--upper-t", type=float, default=1.0, help="upper thickness [mm]")
    p.add_argument("--lower-t", type=float, default=2.0, help="lower thickness [mm]")
    p.add_argument("--upper-eps", type=float, help="override upper eps_r")
    p.add_argument("--lower-eps", type=float, help="override lower eps_r")
    p.add_argument("--width", type=float, default=20.0, help="electrode width [mm]")
    p.add_argument("--length", type=float, default=20.0, help="electrode length [mm]")
    p.add_argument("--probe-area", type=float, help="loaded area [mm^2] (default: full electrode)")
    p.add_argument("--R", default="1M", help="resistor, e.g. 470k, 4.7M")
    p.add_argument("--stray", type=float, default=15.0, help="stray capacitance [pF]")
    p.add_argument("--samples", type=int, default=30)
    p.add_argument("--loop-time-us", type=float, default=0.6)
    p.add_argument("--measured-baseline", type=float,
                   help="measured 0 N reading -> fits loop time to it")
    p.add_argument("--noise", type=float, default=0.0, help="per-cycle jitter [counts]")
    p.add_argument("--unbonded", action="store_true", help="free-slip rubber (softer)")
    p.add_argument("--no-fringe", action="store_true")
    p.add_argument("--fmax", type=float, default=20.0, help="max force [N]")
    p.add_argument("--steps", type=int, default=11)
    p.add_argument("--csv", help="write results to CSV")
    p.add_argument("--plot", action="store_true")
    a = p.parse_args()

    if a.list_materials:
        for k, m in MATERIALS.items():
            kind = "rubber" if m.hyperelastic else "rigid"
            print(f"{k:16s} eps_r={m.eps_r:<7} E={m.E/1e6:10.2f} MPa  [{kind}]  {m.name}")
        return

    up, lo = MATERIALS[a.upper], MATERIALS[a.lower]
    if a.upper_eps:
        up = replace(up, eps_r=a.upper_eps)
    if a.lower_eps:
        lo = replace(lo, eps_r=a.lower_eps)

    cfg = SensorConfig(
        width=a.width * 1e-3, length=a.length * 1e-3,
        probe_area=a.probe_area * 1e-6 if a.probe_area else None,
        upper=Layer(up, a.upper_t * 1e-3), lower=Layer(lo, a.lower_t * 1e-3),
        bonded=not a.unbonded, fringing=not a.no_fringe,
        resistance=parse_si(a.R), c_stray=a.stray * 1e-12,
        samples=a.samples, loop_time=a.loop_time_us * 1e-6, noise_counts=a.noise,
    )
    if a.measured_baseline:
        cfg.loop_time = fit_loop_time(cfg, a.measured_baseline)
        print(f"[calibration] fitted loop time = {cfg.loop_time*1e6:.3f} us")

    forces = np.linspace(0, a.fmax, a.steps)
    res = simulate(cfg, forces)
    print_summary(cfg, res)

    if a.csv:
        keys = list(res)
        np.savetxt(a.csv, np.column_stack([res[k] for k in keys]),
                   delimiter=",", header=",".join(keys), comments="")
        print(f"wrote {a.csv}")
    if a.plot:
        plot(res)


if __name__ == "__main__":
    main()