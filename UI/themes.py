from PyQt6.QtGui import QPalette, QColor

THEMES = {
    "dark": {
        "primary": "#8088F8",
        "bg_dark": "#181818",
        "bg_medium": "#202020",
        "bg_light": "#303030",
        "text_main": "#F0F8F8",
        "text_muted": "#B8C8D0",
        "border": "#484848",
        "box_selected": "#FFFFFF",
        "fusion_window": "#1E1E1E",     # Window background
        "fusion_base": "#181818",       # Inner (Textbox, Scrollbar
        "fusion_button": "#343434",     # Tab
    },
    "light": {
        "primary": "#5058C8",
        "bg_dark": "#E0E0E0",
        "bg_medium": "#E8E8E8",
        "bg_light": "#F8F8F8",
        "text_main": "#101828",
        "text_muted": "#586068",
        "border": "#C8C8C8",
        "box_selected": "#5058C8",
        "fusion_window": "#F0F0F0",
        "fusion_base": "#FFFFFF",
        "fusion_button": "#DCDCDC",
    }
}


def apply_theme(app, theme_name="dark"):
    t = THEMES[theme_name]
    app.setStyle("Fusion")

    # Global theme token
    app.active_theme = t

    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor(t["fusion_window"]))
    palette.setColor(QPalette.ColorRole.WindowText, QColor(t["text_main"]))
    palette.setColor(QPalette.ColorRole.Base, QColor(t["fusion_base"]))
    palette.setColor(QPalette.ColorRole.Text, QColor(t["text_main"]))
    palette.setColor(QPalette.ColorRole.Button, QColor(t["fusion_button"]))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor(t["text_main"]))
    palette.setColor(QPalette.ColorRole.Highlight, QColor(t["primary"]))
    app.setPalette(palette)

    # The last item that uses bg_light should use a new intermediary color
    QSS = f"""
        QLabel#headerLabel {{
            color: {t["text_muted"]};
            font-size: 18px;
            font-weight: bold;
        }}

        QLabel#infoLabel {{
            color: {t["text_muted"]};
            font-size: 14px;
            font-weight: bold;
        }}

        QLabel#dropZone {{
            font-size: 16px;
            font-weight: bold;
            color: {t["text_muted"]};
            border: 2px dashed {t["primary"]};
            border-radius: 8px;
            background-color: {t["bg_medium"]};
        }}
        
        QGroupBox#ControlsGroup {{
            background-color: transparent;
        }}
    """
    app.setStyleSheet(QSS)
