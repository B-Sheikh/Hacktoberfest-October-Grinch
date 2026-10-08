import pytest
from app import physics as p


def test_reference_intervals():
    assert p.ref_interval('tyre_center_car', 'q4') == pytest.approx((.21, .36))
    x = p.fuse([p.ref_interval('tyre_center_car', 'q4'), p.ref_interval('kerb_top', 'over')])
    assert (x['lo'], x['hi'], x['mid']) == pytest.approx((.21, .36, .285))
    assert x['flags'] == []
    x = p.fuse([p.ref_interval('tyre_center_car', 'q4'), p.ref_interval('kerb_top', 'q2')])
    assert (x['lo'], x['hi']) == pytest.approx((.1, .21))
    assert x['flags'] == ['inconsistent']
    x = p.fuse([p.ref_interval('person_knee', 'over')])
    assert (x['lo'], x['hi'], x['mid']) == pytest.approx((.42, .73, .575))
    assert x['flags'] == ['open_ended']


@pytest.mark.parametrize('bins,expected', [(['q3','q4','q4'],(4,4)), (['q2','q4','q3'],(2,4)), (['q1','q4','q3'],(1,4))])
def test_ensemble(bins, expected):
    assert p.ensemble_bin(bins) == expected


def test_rates():
    assert p.fit_rate([0,10], [.285,.3375], [.075,.1125]) == pytest.approx((.00525,.00765), abs=1e-5)
    assert p.fit_rate([0,10,20,30], [.28,.37,.45,.58], [.075]*4) == pytest.approx((.0095,.00194), abs=1e-5)
    assert p.blend_rate('moderate', (.00525,.00765)) == pytest.approx((.00642,.00195), abs=1e-5)
    assert p.blend_rate('moderate', (.0095,.00194)) == pytest.approx((.00806,.00140), abs=1e-5)
    assert p.blend_rate('rapid') == pytest.approx((.02,.00577), abs=1e-5)


def test_projection_and_hazard():
    assert p.depth_at(.375,.009,40) == pytest.approx(.735)
    assert p.time_to(.6,.375,.009) == pytest.approx(25)
    assert p.time_to(2,.375,.009) == pytest.approx(180.56, abs=.01)
    assert p.time_to(.6,.4,0) is None
    assert p.hazard_rating(.735,'moderate','some') == pytest.approx(1.97)
    assert p.hr_class(1.97) == 'most'
    assert p.severity(.735,'moderate','some') == pytest.approx(.788)
    assert [p.severity(d,v) for d,v in [(1.4,'moderate'),(.8,'moderate'),(1.2,'still'),(.15,'rapid'),(.5,'slow')]] == pytest.approx([1,.64,.6,.3,.25])


@pytest.mark.parametrize('depth,rate,expected', [(.4,.02,[1.731,1.555,1.111,.667]),(.8,0,[1.138,.996,.711,.427])])
def test_flood_benefit_monotone(depth, rate, expected):
    values = [p.flood_benefit(2,1,depth,rate,'moderate','none',t) for t in [20,40,80,120]]
    assert values == pytest.approx(expected, abs=.001)
    assert all(a > b for a,b in zip(values,values[1:]))


def test_collapse():
    assert [p.void_fit(h) for h in [.1,.15,.3,.35,.5,.8]] == pytest.approx([0,0,.4286,.5714,1,1],abs=.0001)
    assert p.zone_score(.35,'lean_to',W=1,L=1) == pytest.approx(.5143, abs=.0001)
    assert p.zone_score(.12,'pancake') == 0
    assert [p.slab_mass(*x) for x in [(3,2.5,.12),(4,3,.15),(5,3.5,.2)]] == [2160,4320,8400]
    assert [p.crew_for_mass(m) for m in [300,4320,8400]] == ['manual_cribbing','airbags_hydraulic','crane_heavy']
    assert [p.p_surv(h) for h in [0,6,24,36,60,72,100,300]] == pytest.approx([.95,.9375,.9,.85,.585,.37,.3083,.05],abs=.0001)
    assert p.collapse_benefit(2,.58,2,30,'airbags_hydraulic') == pytest.approx(1.0863,abs=.0001)
    assert p.collapse_benefit(2,.58,2,120,'airbags_hydraulic') == pytest.approx(1.0827,abs=.0001)
    assert p.collapse_benefit(2,.58,70,30,'airbags_hydraulic') == pytest.approx(.4244,abs=.0001)
    values = [p.collapse_benefit(2,.58,2,t,'airbags_hydraulic') for t in [20,40,80,120]]
    assert all(a > b for a,b in zip(values,values[1:]))
    assert p.haversine((10.19,76.39),(10.20,76.40)) == pytest.approx(1.56,abs=.01)
