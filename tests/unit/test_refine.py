from ai_shopping_bot.contracts.product import Product
from ai_shopping_bot.stages.refine import apply, detect_with_regex


def test_detects_price_ceiling():
    c = detect_with_regex("which of these is under $50?")
    assert c and c.is_refinement and c.price_max == 50


def test_detects_features_with_pointer():
    c = detect_with_regex("show me the ones with usb-c")
    assert c and c.features == ["usb-c"]


def test_no_refinement_for_fresh_query():
    assert detect_with_regex("I need a new tent") is None


def test_apply_filters_price_and_feature():
    items = [
        Product(title="A", price=30, description="usb-c"),
        Product(title="B", price=80, description="usb-c"),
        Product(title="C", price=20, description="micro usb"),
    ]
    c = detect_with_regex("from those, under $50 with usb-c")
    assert c is not None
    assert [p.title for p in apply(items, c)] == ["A"]
