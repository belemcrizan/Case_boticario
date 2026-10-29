import time
from dataclasses import replace
from unittest.mock import patch

import pytest
from hypothesis import given
from hypothesis import settings as hypothesis_settings
from hypothesis import strategies as st

from otm_guard.engine import reconcile
from platform_api.auth import demo_login, iap_principal
from platform_api.config import Settings
from platform_api.domain import AppError
from tests.helpers import combo_dataset


def cloud_settings():
    return Settings(
        environment="gcp",
        public_origin="https://example.run.app",
        iap_audience="/projects/1/locations/r/services/s",
        identities={"operator@example.com": "operator"},
        bucket="bucket",
        project="p",
        job_name="job",
        sql_instance="p:r:sql",
        sql_user="iam-user",
        initialize_schema=False,
        seed_demo=False,
    )


def test_cloud_configuration_fails_closed():
    with pytest.raises(ValueError):
        Settings(environment="anything")
    with pytest.raises(ValueError):
        Settings(environment="gcp")
    with pytest.raises(ValueError):
        replace(cloud_settings(), public_origin="http://example.com")
    with pytest.raises(ValueError):
        replace(cloud_settings(), seed_demo=True)


def test_iap_validates_identity_issuer_audience_lifetime_and_roles():
    conf = cloud_settings()
    now = time.time()
    valid = {
        "iss": "https://cloud.google.com/iap",
        "aud": conf.iap_audience,
        "iat": now,
        "exp": now + 600,
        "email": "operator@example.com",
        "sub": "subject",
    }
    with patch("platform_api.auth._verify_iap", return_value=valid):
        assert iap_principal("signed-token", conf).role == "operator"
    for change in (
        {"iss": "evil"},
        {"aud": "other"},
        {"exp": now - 60},
        {"iat": now + 60},
        {"exp": now + 1000},
        {"email": "unknown@example.com"},
    ):
        with patch("platform_api.auth._verify_iap", return_value={**valid, **change}):
            with pytest.raises(AppError):
                iap_principal("token", conf)
    with patch("platform_api.auth._verify_iap", side_effect=ValueError("signature")):
        with pytest.raises(AppError):
            iap_principal("forged", conf)


def test_demo_endpoint_disabled_in_cloud():
    with pytest.raises(AppError) as exc:
        demo_login(None, cloud_settings(), "operator")
    assert exc.value.status == 404


@given(
    p=st.integers(1, 12),
    q=st.integers(1, 12),
    m=st.integers(1, 24),
    n=st.integers(1, 24),
    ca=st.integers(0, 120),
    cb=st.integers(0, 120),
    sa=st.integers(0, 120),
    sb=st.integers(0, 120),
)
@hypothesis_settings(max_examples=300, derandomize=True, deadline=None)
def test_property_global_bounds_and_local_optimum(p, q, m, n, ca, cb, sa, sb):
    result = reconcile(combo_dataset(p, q, m, n, ca, cb, sa, sb))
    best = max(
        k
        for k in range(121)
        if k * p <= min(ca, sa) and k * q <= min(cb, sb) and k * p % m == 0 and k * q % n == 0
    )
    assert [r.qtd_final for r in result.decisions] == [best * p, best * q]
    assert all(result.checks.values())
