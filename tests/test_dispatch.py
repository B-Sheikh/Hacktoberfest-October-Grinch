from app.dispatch_reference import run


def test_golden_dispatch():
    assert run(1)[0] == [('T1','S3',.197),('T2','S1',2.689)]
    assert run(2)[0] == [('T2','S1',2.597)]
