"""Tests for readable report chart labels in generated PDF figures."""

from types import SimpleNamespace

from app.routers import admin as admin_router

LONG_PARAMETER_NAMES = [
    "LEFT_MAIN_LANDING_GEAR_SHOCK_STRUT_PRESSURE_TRANSDUCER_ENGINEERING_CHANNEL",
    "RIGHT_MAIN_LANDING_GEAR_SHOCK_STRUT_PRESSURE_TRANSDUCER_ENGINEERING_CHANNEL",
    "ENGINE_NUMBER_ONE_EXHAUST_GAS_TEMPERATURE_AVERAGE_LONG_DURATION_CHANNEL",
    "ENGINE_NUMBER_TWO_EXHAUST_GAS_TEMPERATURE_AVERAGE_LONG_DURATION_CHANNEL",
    "FLIGHT_CONTROL_COMPUTER_PRIMARY_AILERON_COMMAND_MONITOR_CHANNEL",
    "FLIGHT_CONTROL_COMPUTER_PRIMARY_ELEVATOR_COMMAND_MONITOR_CHANNEL",
]


def _stats_rows():
    rows = []
    for index, name in enumerate(LONG_PARAMETER_NAMES, start=1):
        rows.append(
            {
                "name": name,
                "unit": "psi",
                "min_val": float(index),
                "max_val": float(index * 10),
                "avg_val": float(index * 5),
                "std_val": 0.5,
                "sample_count": 1000 - index,
            }
        )
    return rows


def _axis_category_names(figure_blocks):
    labels = []
    for _title, drawing, _caption in figure_blocks:
        for item in getattr(drawing, "contents", []):
            category_axis = getattr(item, "categoryAxis", None)
            category_names = getattr(category_axis, "categoryNames", None)
            if category_names:
                labels.extend(category_names)
    return labels


def test_chart_label_helper_shortens_deterministically_and_preserves_mapping():
    long_name = LONG_PARAMETER_NAMES[0]

    shortened = admin_router._shorten_chart_label(long_name, max_len=32)
    label_map = admin_router._build_chart_label_map([long_name], max_len=32)

    assert shortened == "LEFT_MAIN_LANDING_GEAR_SHOCK..."
    assert len(shortened) <= 32
    assert label_map == [
        {
            "code": "P1",
            "display": shortened,
            "axis_label": f"P1 {shortened}",
            "full": long_name,
        }
    ]


def test_stats_figures_use_compact_axis_labels_and_caption_full_names():
    figure_blocks = admin_router._build_stats_figures(_stats_rows())

    assert figure_blocks
    axis_labels = _axis_category_names(figure_blocks)
    captions = " ".join(caption for _title, _drawing, caption in figure_blocks)

    assert axis_labels
    assert all(len(label) <= 34 for label in axis_labels)
    for long_name in LONG_PARAMETER_NAMES:
        assert long_name not in axis_labels
        assert long_name in captions
    assert "Chart parameter labels:" in captions


def test_pdf_report_generation_succeeds_with_long_parameter_names():
    flight_test = SimpleNamespace(
        id=42,
        test_name="Long Label Export",
        aircraft_type="F-16",
        test_date=None,
        description=None,
    )

    pdf_bytes = admin_router._build_pdf(
        flight_test=flight_test,
        stats_snapshot=_stats_rows(),
        analysis_text="## Findings\nLong-label report generation smoke test.",
        generated_by="admin",
        analysis_job=None,
    )

    assert pdf_bytes.startswith(b"%PDF")
    assert b"Chart parameter labels:" in pdf_bytes
    assert LONG_PARAMETER_NAMES[0].encode() in pdf_bytes
