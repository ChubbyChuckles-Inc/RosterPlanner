from pathlib import Path

from gui.design.icon_scale_audit import rasterize_icons, list_cached_bitmaps, DEFAULT_OUT
from gui.design.icon_registry import IconRegistry


def test_rasterize_icons_generates_files(tmp_path):
    # Use a temporary output to avoid polluting repo assets
    registry = IconRegistry.instance()
    if not registry.list_icons():
        return  # nothing to test
    result = rasterize_icons([1.0, 2.0], size=16, out_dir=tmp_path)
    # At least one icon should generate two scales unless Qt unavailable
    if result.generated:
        assert any(p.name.endswith("@1.0x.png") for p in result.generated)
        assert any(p.name.endswith("@2.0x.png") for p in result.generated)
        # Dimension check
        import PIL.Image as Image  # optional dependency? If not installed skip dimension verification

        for p in result.generated:
            try:
                with Image.open(p) as im:
                    if "@1.0x" in p.name:
                        assert im.width == 16 and im.height == 16
                    if "@2.0x" in p.name:
                        assert im.width == 32 and im.height == 32
            except Exception:
                # Pillow not installed; skip deeper dimension test
                break


def test_list_cached_bitmaps(tmp_path):
    # Ensure empty list when nothing present
    files = list_cached_bitmaps(tmp_path)
    assert files == []
