"""!Unit tests for system contract catalog endpoint."""

from apps.api.main import get_contract_catalog


def test_contract_catalog_exposes_expected_contracts() -> None:
    """!Contract catalog should list request/result schemas for non-Python runtimes."""
    result = get_contract_catalog()
    assert "contracts" in result
    names = {row["name"] for row in result["contracts"]}
    assert names == {"simulation_request.v1", "simulation_result.v1"}

    paths = {row["name"]: row["schema_path"] for row in result["contracts"]}
    assert paths["simulation_request.v1"].endswith("simulation_request.v1.schema.json")
    assert paths["simulation_result.v1"].endswith("simulation_result.v1.schema.json")
    assert result["missing_contracts"] == 0
    assert all(row["schema_exists"] is True for row in result["contracts"])
