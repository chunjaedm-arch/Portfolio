from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QPalette, QColor
from PyQt6.QtCore import Qt

class StyleManager:
    @staticmethod
    def apply_theme(app: QApplication):
        """애플리케이션에 다크 테마(Fusion 스타일)를 적용합니다."""
        app.setStyle("Fusion")
        palette = QPalette()
        palette.setColor(QPalette.ColorRole.Window, QColor("#2b2b2b"))
        palette.setColor(QPalette.ColorRole.WindowText, QColor("#e0e0e0"))
        palette.setColor(QPalette.ColorRole.Base, QColor("#1e1e1e"))
        palette.setColor(QPalette.ColorRole.AlternateBase, QColor("#353535"))
        palette.setColor(QPalette.ColorRole.ToolTipBase, QColor("#e0e0e0"))
        palette.setColor(QPalette.ColorRole.ToolTipText, QColor("#e0e0e0"))
        palette.setColor(QPalette.ColorRole.Text, QColor("#e0e0e0"))
        palette.setColor(QPalette.ColorRole.Button, QColor("#2b2b2b"))
        palette.setColor(QPalette.ColorRole.ButtonText, QColor("#e0e0e0"))
        palette.setColor(QPalette.ColorRole.Link, QColor(42, 130, 218))
        palette.setColor(QPalette.ColorRole.Highlight, QColor(42, 130, 218))
        palette.setColor(QPalette.ColorRole.HighlightedText, Qt.GlobalColor.black)
        app.setPalette(palette)