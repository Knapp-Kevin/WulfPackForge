import logging
import sys

from PySide6.QtWidgets import QApplication

from subscripts.logSetup import configure_logging

from ui.branding import app_icon
from ui.mainWindow import MainWindow


def _verify_catalog_bundle() -> bool:
    from data.items import CATALOG_GAME_VERSION, CATALOG_SELECTABLE_ITEM_COUNT

    return bool(CATALOG_GAME_VERSION) and CATALOG_SELECTABLE_ITEM_COUNT >= 900


def _verify_brand_bundle() -> bool:
    from ui.branding import banner_is_usable

    return banner_is_usable()


def _verify_glyph_bundle() -> bool:
    from ui.glyphs import appearance_bundle_is_usable, glyph_bundle_is_usable

    return glyph_bundle_is_usable() and appearance_bundle_is_usable()


def main():
    log_file = configure_logging()
    logging.getLogger(__name__).info("Wulfpack Forge starting; log file: %s", log_file)
    app = QApplication(sys.argv)
    app.setWindowIcon(app_icon())
    window = MainWindow(startup_warning="--smoke-test" not in sys.argv)

    if "--smoke-test" in sys.argv:
        if not (_verify_catalog_bundle() and _verify_brand_bundle() and _verify_glyph_bundle()):
            window.close()
            return 2
        window.show()
        app.processEvents()
        window.close()
        return 0

    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
