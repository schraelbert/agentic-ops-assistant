from app.domain_registry import get_domain


def test_renewable_domain_is_registered():
    domain = get_domain("renewable_ops")
    assert domain["display_name"] == "Renewable Asset Operations"
    assert "get_asset_status" in domain["tool_specs"]
