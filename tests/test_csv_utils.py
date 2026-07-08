import csv
import io

from src.utils.csv_utils import generate_ioc_csv


def test_generate_ioc_csv_includes_mallory_columns():
    iocs = [
        {
            "ioc_type": "ip",
            "ioc_value": "1.2.3.4",
            "source": "Mallory",
            "mallory_tags": "botnet, c2",
            "mallory_context": "Observed in active campaign",
        },
        {
            "ioc_type": "domain",
            "ioc_value": "evil.com",
            "source": "OpenPhish",
        },
    ]

    csv_content = generate_ioc_csv(iocs)
    reader = csv.DictReader(io.StringIO(csv_content))

    assert "mallory_tags" in reader.fieldnames
    assert "mallory_context" in reader.fieldnames

    rows = list(reader)
    assert rows[0]["mallory_tags"] == "botnet, c2"
    assert rows[0]["mallory_context"] == "Observed in active campaign"
    assert rows[1]["mallory_tags"] == ""
    assert rows[1]["mallory_context"] == ""
