import logging
import sys

from PySide6.QtWidgets import QApplication

from subscripts.crashReports import release
from subscripts.logSetup import configure_logging, install_excepthook

from ui.branding import APP_VERSION, app_icon
from ui.diagnostics import arm_diagnostics, environment_banner, show_crash_notice
from ui.mainWindow import MainWindow
from subscripts.modOverride import apply_overrides
from subscripts.workspace import default_workspace_root


def _verify_catalog_bundle() -> bool:
    from data.items import CATALOG_GAME_VERSION, CATALOG_SELECTABLE_ITEM_COUNT

    # The curated fallback is about 70 items, so any bundled catalog clears this floor and a missing
    # one fails it. The Valheim 1.0.12 catalog has 941 selectable items; review at each refresh.
    return bool(CATALOG_GAME_VERSION) and CATALOG_SELECTABLE_ITEM_COUNT >= 800


def _verify_brand_bundle() -> bool:
    from ui.branding import banner_is_usable

    return banner_is_usable()


def _verify_glyph_bundle() -> bool:
    from ui.glyphs import appearance_bundle_is_usable, glyph_bundle_is_usable

    return glyph_bundle_is_usable() and appearance_bundle_is_usable()


def main():
    if "--version" in sys.argv:
        print(APP_VERSION)
        return 0
    log_file = configure_logging()
    install_excepthook()
    smoke = "--smoke-test" in sys.argv
    reports, report_path = arm_diagnostics()
    logger = logging.getLogger(__name__)
    logger.info("Wulfpack Forge %s starting; log file: %s", APP_VERSION, log_file)
    logger.info("%s", environment_banner(report_path))
    try:
        apply_overrides(default_workspace_root())  # scanned mod names and icons, if the user ran a mod scan
        app = QApplication(sys.argv)
        app.setWindowIcon(app_icon())
        window = MainWindow(startup_warning=not smoke)

        if smoke:
            if not (_verify_catalog_bundle() and _verify_brand_bundle() and _verify_glyph_bundle()):
                window.close()
                return 2
            window.show()
            app.processEvents()
            window.close()
            return 0

        window.show()
        show_crash_notice(window, reports)
        return app.exec()
    finally:
        release()


if __name__ == "__main__":
    sys.exit(main())
