"""Waterline reference physics (verified). All lengths metres, time minutes, mass kg."""
import math, statistics as st

# ---------- 1. reference table: height of feature above ground (min,max) ----------
REFS = {
 "tyre_center_car":   (0.28, 0.36), "car_roof": (1.40, 1.75), "car_door_sill": (0.30, 0.45),
 "bus_tyre_center":   (0.45, 0.58), "motorbike_wheel_center": (0.22, 0.33), "motorbike_seat": (0.75, 0.85),
 "kerb_top":          (0.10, 0.20), "stair_riser": (0.15, 0.19), "door_threshold": (0.00, 0.05),
 "door_handle":       (0.90, 1.10), "door_top": (1.95, 2.15), "window_sill": (0.80, 1.05),
 "wall_socket_low":   (0.30, 0.45), "person_knee": (0.42, 0.55), "person_waist": (0.90, 1.10),
 "person_chest":      (1.15, 1.40),
}
# bins: fraction of ground->feature span that is submerged
BINS = ["none", "q1", "q2", "q3", "q4", "over"]
BIN_FR = {"none": (0.0, 0.0), "q1": (0.0, .25), "q2": (.25, .5), "q3": (.5, .75), "q4": (.75, 1.0), "over": (1.0, None)}
DRY_ABS = 0.03

def ref_interval(ref_id, b):
    hmin, hmax = REFS[ref_id]
    if b == "none": return (0.0, DRY_ABS)
    fl, fu = BIN_FR[b]
    return (fl * hmin, None if fu is None else fu * hmax)

def ensemble_bin(bins):  # 3 model runs for the same ref -> (bin_lo_idx, bin_hi_idx)
    idx = sorted(BINS.index(b) for b in bins)
    med = idx[len(idx)//2]
    return (idx[0], idx[-1]) if idx[-1] - idx[0] >= 2 else (med, med)

def fuse(intervals):
    """Intersect intervals; hi=None means open-ended. Returns dict."""
    lo = max(i[0] for i in intervals)
    his = [i[1] for i in intervals if i[1] is not None]
    hi = min(his) if his else None
    flag = []
    if hi is not None and lo > hi:                      # inconsistent
        lo, hi = hi, lo; flag.append("inconsistent")
    if hi is None:                                      # only 'over' bins
        hi = lo * 1.5 + 0.1; flag.append("open_ended")
    return {"lo": lo, "hi": hi, "mid": (lo + hi) / 2, "flags": flag}

# ---------- 2. rise rate ----------
RATE_PRIOR = {"receding": (-0.005, 0.0), "steady": (0.0, 0.001), "slow": (0.001, 0.003),
              "moderate": (0.003, 0.010), "rapid": (0.010, 0.030)}      # m/min  (ASSUMPTIONS)

def fit_rate(ts, mids, halfw):
    """ts minutes, mids m, halfw = interval half widths m. returns (rate, sigma) m/min"""
    n = len(ts); sm = (sum(halfw) / n) / math.sqrt(3)
    slopes = [(mids[j]-mids[i])/(ts[j]-ts[i]) for i in range(n) for j in range(i+1, n) if ts[j]-ts[i] >= 2]
    if not slopes: return None
    m = st.median(slopes)
    if n == 2: return m, math.sqrt(2)*sm/(ts[1]-ts[0])
    b = st.median([y - m*t for t, y in zip(ts, mids)])
    res = [y-(b+m*t) for t, y in zip(ts, mids)]
    mad = st.median([abs(r-st.median(res)) for r in res])
    s = max(1.4826*mad, sm); tb = sum(ts)/n
    return m, s/math.sqrt(sum((t-tb)**2 for t in ts))

D_CAP = 3.0
def depth_at(d0, rate, t, cap=D_CAP): return max(0.0, min(cap, d0 + rate*t))

# ---------- 3. hazard to people (Defra/EA FD2320: HR = d*(v+0.5)+DF) ----------
V_CLASS = {"still": 0.0, "slow": 0.5, "moderate": 1.5, "rapid": 3.0}
def debris_factor(d, debris):  # debris: none|some|heavy
    return 0.0 if (d < 0.25 or debris == "none") else (0.5 if debris == "some" else 1.0)
def hazard_rating(d, vclass, debris="none"):
    return d*(V_CLASS[vclass]+0.5) + debris_factor(d, debris)
def severity(d, vclass, debris="none"):
    """0..1. depth floor so deep STILL water is not under-rated."""
    return min(1.0, max(hazard_rating(d, vclass, debris)/2.5, d/2.0))
def hr_class(hr): return "low" if hr < .75 else "some" if hr < 1.25 else "most" if hr < 2.5 else "all"

# ---------- 4. time to threshold ----------
def time_to(thr, d0, rate):
    if d0 >= thr: return 0.0
    return None if rate <= 0 else (thr - d0)/rate

# ---------- 5. benefit of arriving at T (flood): mean severity over [T, H] ----------
def flood_benefit(P, M, d0, rate, vclass, debris, T, H=180):
    if T >= H: return 0.0
    xs = range(int(T), H+1)
    s = [severity(depth_at(d0, rate, t), vclass, debris) for t in xs]
    return P*M*sum(s)/len(s)*((H-T)/H)           # severity averaged over exposure, scaled by exposure share

# ---------- 6. collapse ----------
def void_fit(h_mid):  # 0 at <=0.15 m, 1 at >=0.50 m
    return max(0.0, min(1.0, (h_mid-0.15)/(0.50-0.15)))
TYPE_F = {"lean_to": .9, "v_shape": .9, "a_frame": .7, "cantilever": .7, "pancake": .25, "rubble_pile": .35, "unknown": .4}
def zone_score(h_mid, ctype, W=0.0, L=0.0, access=1.0):
    return void_fit(h_mid)*TYPE_F[ctype]*(0.6+0.2*W+0.2*L)*access
SURV = [(0,.95),(24,.90),(48,.80),(72,.37),(96,.33),(120,.20),(240,.05)]   # hours, ILLUSTRATIVE
def p_surv(h):
    for (h0,p0),(h1,p1) in zip(SURV, SURV[1:]):
        if h <= h1: return p0 + (p1-p0)*(max(h,h0)-h0)/(h1-h0)
    return SURV[-1][1]
RHO = {"rcc": 2400, "brick": 1900}
def slab_mass(L, W, t, rho=2400): return L*W*t*rho
def crew_for_mass(m): return "manual_cribbing" if m <= 500 else "airbags_hydraulic" if m <= 5000 else "crane_heavy"
T_EXT = {"manual_cribbing": 90, "airbags_hydraulic": 240, "crane_heavy": 480}   # minutes, ASSUMPTION
def collapse_benefit(N, Z, t_since_collapse_h, T_arr_min, crew):
    return N*Z*p_surv(t_since_collapse_h + (T_arr_min + T_EXT[crew])/60)

# ---------- 7. travel ----------
def haversine(a, b):
    R=6371.0088; p1,p2=math.radians(a[0]),math.radians(b[0]); dl=math.radians(b[1]-a[1]); dp=p2-p1
    h=math.sin(dp/2)**2+math.cos(p1)*math.cos(p2)*math.sin(dl/2)**2
    return 2*R*math.asin(math.sqrt(h))

# ---------- 2b. Bayesian blend of fitted rate with class prior ----------
def blend_rate(prior_class, fit=None):
    lo, hi = RATE_PRIOR[prior_class]; mu = (lo+hi)/2; sp = max((hi-lo)/math.sqrt(12), 1e-4)
    if fit is None: return mu, sp
    r, s = fit; s = max(s, 1e-4)
    w1, w2 = 1/sp**2, 1/s**2
    return (mu*w1 + r*w2)/(w1+w2), math.sqrt(1/(w1+w2))

# hazard floor for moving water (rule-of-thumb: ~15 cm of fast water can topple an adult)
_hr_orig = hazard_rating
def hazard_rating(d, vclass, debris="none"):
    hr = _hr_orig(d, vclass, debris)
    if vclass in ("moderate", "rapid") and d >= 0.15: hr = max(hr, 0.75)
    return hr

# ---------- 7b. dispatch ----------
TEAMS_SPEC = {  # type: (speed_kmh, max_depth_m, caps)
 "boat":      (12, None, {"water"}),            # needs depth >= 0.5
 "rescue_4x4":(30, 0.45, {"road"}),
 "heavy_usar":(25, 0.60, {"road","heavy_lift","shoring"}),
 "light_crew":(4,  0.30, {"foot"}),
}
def travel_min(team_type, dist_km, d_site, mobilise=10, detour=1.4):
    spd, dmax, _ = TEAMS_SPEC[team_type]
    if dmax: spd = spd*max(0.25, 1-d_site/dmax)
    return mobilise + dist_km*detour/spd*60
def feasible(team_type, d_site, vclass):
    spd, dmax, _ = TEAMS_SPEC[team_type]
    if team_type == "boat": return d_site >= 0.5 and (vclass != "rapid")
    return d_site <= dmax
