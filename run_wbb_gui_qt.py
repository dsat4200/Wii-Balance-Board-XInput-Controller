import sys
import json
import vgamepad as vg # --- Import for XInput ---
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QFrame, QGraphicsView, QGraphicsScene, QGraphicsEllipseItem,
    QDoubleSpinBox, QGridLayout, QComboBox
)
from PyQt6.QtCore import Qt, QPointF, QThread, QRectF
from PyQt6.QtGui import (
    QFont, QColor, QPen, QBrush, QPainter
)
from WiiBalanceBoard_qt import WiiBalanceBoard # Import the Qt-enabled API

# --- STYLESHEETS ---

DARK_STYLESHEET = """
QWidget {
    background-color: #282a36;
    color: #f8f8f2;
}
QPushButton {
    background-color: #44475a;
    border: 1px solid #6272a4;
    padding: 5px;
    border-radius: 3px;
}
QPushButton:hover {
    background-color: #4f5368;
}
QPushButton:pressed {
    background-color: #3b3e51;
}
QPushButton:disabled {
    background-color: #3b3e51;
    color: #6272a4;
}
QFrame {
    border: 1px solid #44475a;
    border-radius: 4px;
}
QComboBox {
    background-color: #44475a;
    border: 1px solid #6272a4;
    border-radius: 3px;
    padding: 3px;
}
QComboBox::drop-down {
    border-left: 1px solid #6272a4;
}
QComboBox QAbstractItemView {
    background-color: #44475a;
    border: 1px solid #6272a4;
    selection-background-color: #6272a4;
}
QDoubleSpinBox {
    background-color: #44475a;
    border: 1px solid #6272a4;
    border-radius: 3px;
    padding: 3px;
}
QLabel {
    background-color: transparent;
    border: none;
}
#total_weight_label {
    color: #50fa7b;
}
#status_label {
    color: #bd93f9;
    border-top: 1px solid #44475a;
}
"""

LIGHT_STYLESHEET = """
QWidget {
    background-color: #f0f0f0;
    color: #000000;
}
QPushButton {
    background-color: #e1e1e1;
    border: 1px solid #adadad;
    padding: 5px;
    border-radius: 3px;
}
QPushButton:hover {
    background-color: #cacaca;
}
QPushButton:pressed {
    background-color: #b0b0b0;
}
QPushButton:disabled {
    background-color: #dcdcdc;
    color: #888888;
}
QFrame {
    border: 1px solid #cccccc;
    border-radius: 4px;
}
QComboBox {
    background-color: #ffffff;
    border: 1px solid #adadad;
    border-radius: 3px;
    padding: 3px;
}
QComboBox::drop-down {
    border-left: 1px solid #adadad;
}
QComboBox QAbstractItemView {
    background-color: #ffffff;
    border: 1px solid #adadad;
    selection-background-color: #d3d3d3;
}
QDoubleSpinBox {
    background-color: #ffffff;
    border: 1px solid #adadad;
    border-radius: 3px;
    padding: 3px;
}
QLabel {
    background-color: transparent;
    border: none;
}
#total_weight_label {
    color: #007ACC;
}
#status_label {
    color: #000000;
    border-top: 1px solid #CCC;
}
"""


class CoMWidget(QGraphicsView):
    """
    A custom widget to display the Center of Mass,
    replacing the tkinter canvas.
    """
    def __init__(self):
        super().__init__()
        self.scene = QGraphicsScene(self)
        self.setScene(self.scene)
        self.scene.setSceneRect(-100, -100, 200, 200)
        self.setFixedSize(202, 202)
        
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        
        # --- Define pens/brushes for state changes ---
        self.inactive_pressure_brush = QBrush(QColor(0, 0, 255, 120))
        self.inactive_pressure_pen = QPen(QColor(0, 0, 255, 180), 1)
        self.active_pressure_brush = QBrush(QColor(220, 0, 0, 120)) # Red
        self.active_pressure_pen = QPen(QColor(220, 0, 0, 180), 1) # Red

        # --- Theme-aware colors ---
        self.bg_color = QColor(255, 255, 255)
        self.grid_pen = QPen(QColor(230, 230, 230), 1, Qt.PenStyle.SolidLine)
        self.axis_pen = QPen(Qt.GlobalColor.lightGray, 1, Qt.PenStyle.DashLine)
        self.label_font_color = QColor(0, 0, 0)
        self.thresh_pen = QPen(QColor(100, 100, 100), 1, Qt.PenStyle.DashLine)
        
        self.setBackgroundBrush(self.bg_color)
        
        # --- Store scene items to update colors ---
        self.grid_lines = []
        self.axis_lines = []
        self.text_items = []
        
        # --- Draw grid lines (axes) ---
        self.grid_pen.setCosmetic(True) # Keep it 1px
        for i in range(-10, 11):
            if i == 0: continue # Main crosshairs will draw over this
            coord = i * 10 # e.g., -90, -80... 80, 90
            self.grid_lines.append(self.scene.addLine(-100, coord, 100, coord, self.grid_pen))
            self.grid_lines.append(self.scene.addLine(coord, -100, coord, 100, self.grid_pen))
            self.grid_lines[-1].setZValue(-10)
            self.grid_lines[-2].setZValue(-10)

        # Draw main crosshairs (on top of grid)
        self.axis_lines.append(self.scene.addLine(-100, 0, 100, 0, self.axis_pen))
        self.axis_lines.append(self.scene.addLine(0, -100, 0, 100, self.axis_pen))
        self.axis_lines[0].setZValue(-5)
        self.axis_lines[1].setZValue(-5)
        
        # Draw labels
        font = QFont("Helvetica", 8)
        top_label = self.scene.addText("Top (+Y)", font)
        top_label.setPos(-top_label.boundingRect().width() / 2, -100)
        
        bottom_label = self.scene.addText("Bottom (-Y)", font)
        bottom_label.setPos(-bottom_label.boundingRect().width() / 2, 90)

        left_label = self.scene.addText("L\n(-X)", font)
        left_label.setPos(-98, -left_label.boundingRect().height() / 2)
        
        right_label = self.scene.addText("R\n(+X)", font)
        right_label.setPos(98 - right_label.boundingRect().width(), -right_label.boundingRect().height() / 2)
        
        self.text_items.extend([top_label, bottom_label, left_label, right_label])
        
        # --- Create pressure dots ---
        min_r = self._map_weight_to_radius(0)
        
        self.tl_dot = self.scene.addEllipse(0, 0, min_r * 2, min_r * 2, self.inactive_pressure_pen, self.inactive_pressure_brush)
        self.tl_dot.setPos(-90, -90); self.tl_dot.setZValue(5)
        
        self.tr_dot = self.scene.addEllipse(0, 0, min_r * 2, min_r * 2, self.inactive_pressure_pen, self.inactive_pressure_brush)
        self.tr_dot.setPos(90, -90); self.tr_dot.setZValue(5)
        
        self.bl_dot = self.scene.addEllipse(0, 0, min_r * 2, min_r * 2, self.inactive_pressure_pen, self.inactive_pressure_brush)
        self.bl_dot.setPos(-90, 90); self.bl_dot.setZValue(5)
        
        self.br_dot = self.scene.addEllipse(0, 0, min_r * 2, min_r * 2, self.inactive_pressure_pen, self.inactive_pressure_brush)
        self.br_dot.setPos(90, 90); self.br_dot.setZValue(5)

        # --- Create threshold indicators ---
        self.thresh_pen.setCosmetic(True)
        thresh_brush = QBrush(Qt.BrushStyle.NoBrush)
        
        self.tl_thresh = self.scene.addEllipse(0, 0, 0, 0, self.thresh_pen, thresh_brush)
        self.tl_thresh.setPos(-90, -90); self.tl_thresh.setZValue(3)

        self.tr_thresh = self.scene.addEllipse(0, 0, 0, 0, self.thresh_pen, thresh_brush)
        self.tr_thresh.setPos(90, -90); self.tr_thresh.setZValue(3)

        self.bl_thresh = self.scene.addEllipse(0, 0, 0, 0, self.thresh_pen, thresh_brush)
        self.bl_thresh.setPos(-90, 90); self.bl_thresh.setZValue(3)

        self.br_thresh = self.scene.addEllipse(0, 0, 0, 0, self.thresh_pen, thresh_brush)
        self.br_thresh.setPos(90, 90); self.br_thresh.setZValue(3)

        # --- Add Button labels ---
        self.label_font = QFont("Helvetica", 16, QFont.Weight.Bold)
        
        def create_button_label(text, pos_x, pos_y):
            label = self.scene.addText(text, self.label_font)
            label.setDefaultTextColor(QColor(255, 255, 255, 200)) # Semi-transparent white
            rect = label.boundingRect()
            label.setPos(pos_x - rect.width() / 2, pos_y - rect.height() / 2)
            label.setZValue(6) 
            return label

        self.tl_label = create_button_label("", -90, -90)
        self.bl_label = create_button_label("", -90, 90)
        self.tr_label = create_button_label("", 90, -90)
        self.br_label = create_button_label("", 90, 90)

        # --- Create main CoM dot ---
        self.com_dot = QGraphicsEllipseItem(-2, -2, 4, 4)
        self.com_dot.setBrush(QBrush(Qt.GlobalColor.red))
        self.com_dot.setPen(QPen(Qt.GlobalColor.red))
        self.com_dot.setZValue(10) # On top of everything
        self.scene.addItem(self.com_dot)
        
        self.setRenderHint(QPainter.RenderHint.Antialiasing)

    def set_theme(self, is_dark_mode):
        """NEW: Updates the internal drawing colors for the scene."""
        if is_dark_mode:
            self.bg_color = QColor("#282a36")
            self.grid_pen = QPen(QColor("#44475a"), 1, Qt.PenStyle.SolidLine)
            self.axis_pen = QPen(QColor("#6272a4"), 1, Qt.PenStyle.DashLine)
            self.label_font_color = QColor("#f8f8f2")
            self.thresh_pen = QPen(QColor("#bd93f9"), 1, Qt.PenStyle.DashLine)
        else:
            self.bg_color = QColor(255, 255, 255)
            self.grid_pen = QPen(QColor(230, 230, 230), 1, Qt.PenStyle.SolidLine)
            self.axis_pen = QPen(Qt.GlobalColor.lightGray, 1, Qt.PenStyle.DashLine)
            self.label_font_color = QColor(0, 0, 0)
            self.thresh_pen = QPen(QColor(100, 100, 100), 1, Qt.PenStyle.DashLine)
            
        self.grid_pen.setCosmetic(True)
        self.thresh_pen.setCosmetic(True)

        self.setBackgroundBrush(self.bg_color)
        
        for item in self.grid_lines:
            item.setPen(self.grid_pen)
        
        for item in self.axis_lines:
            item.setPen(self.axis_pen)
            
        for item in self.text_items:
            item.setDefaultTextColor(self.label_font_color)
            
        self.tl_thresh.setPen(self.thresh_pen)
        self.tr_thresh.setPen(self.thresh_pen)
        self.bl_thresh.setPen(self.thresh_pen)
        self.br_thresh.setPen(self.thresh_pen)

    def _map_weight_to_radius(self, weight):
        """Helper to map a weight (kg) to a circle radius (px)."""
        min_weight = 0.5
        max_weight = 80.0
        min_radius = 3
        max_radius = 25
        
        if weight <= min_weight: return min_radius
        if weight >= max_weight: return max_radius
        
        percent = (weight - min_weight) / (max_weight - min_weight)
        radius = min_radius + (percent * (max_radius - min_radius))
        return radius

    def resizeEvent(self, event):
        """Called when the widget is resized."""
        self.fitInView(self.scene.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)
        super().resizeEvent(event)

    def update_label(self, key, mapping_text, mode):
        """
        NEW: Updates a single label (tl, tr, bl, br) based on the mapping text
        and the view mode (xbox/ps).
        """
        
        def set_label_text(label_item, text, font, center_x, center_y):
            """Internal helper to set text, font, and re-center."""
            label_item.setFont(font)
            label_item.setPlainText(text)
            rect = label_item.boundingRect()
            label_item.setPos(center_x - rect.width() / 2, center_y - rect.height() / 2)

        text_to_display = ""
        # Start with default font
        font = QFont("Helvetica", 16, QFont.Weight.Bold)

        if not mapping_text or mapping_text == "None":
            text_to_display = ""
        else:
            # Check if it's a face button
            is_face_button = True
            if "A (Cross ✕)" in mapping_text:
                xbox_char, ps_char = "A", "✕"
            elif "B (Circle ○)" in mapping_text:
                xbox_char, ps_char = "B", "○"
            elif "X (Square □)" in mapping_text:
                xbox_char, ps_char = "X", "□"
            elif "Y (Triangle △)" in mapping_text:
                xbox_char, ps_char = "Y", "△"
            else:
                is_face_button = False

            if mode == "ps":
                if is_face_button:
                    font.setFamily("Segoe UI Symbol")
                    font.setPointSize(20) # Larger PS symbols
                    text_to_display = ps_char
                else:
                    # Not a face button, show text (LB, L3, etc.)
                    font.setFamily("Helvetica")
                    font.setPointSize(10) # Smaller font for text
                    if "Bumper" in mapping_text: text_to_display = "LB" if "Left" in mapping_text else "RB"
                    elif "Stick" in mapping_text: text_to_display = "L3" if "Left" in mapping_text else "R3"
                    elif "Start" in mapping_text: text_to_display = "Start"
                    elif "Back" in mapping_text: text_to_display = "Back"
                    else: text_to_display = "?"
            else: # mode == "xbox"
                if is_face_button:
                    font.setFamily("Helvetica")
                    font.setPointSize(16) # Larger Xbox letters
                    text_to_display = xbox_char
                else:
                    # Not a face button, show text (LB, L3, etc.)
                    font.setFamily("Helvetica")
                    font.setPointSize(10) # Smaller font for text
                    if "Bumper" in mapping_text: text_to_display = "LB" if "Left" in mapping_text else "RB"
                    elif "Stick" in mapping_text: text_to_display = "L3" if "Left" in mapping_text else "R3"
                    elif "Start" in mapping_text: text_to_display = "Start"
                    elif "Back" in mapping_text: text_to_display = "Back"
                    else: text_to_display = "?"
        
        # Apply the text and font to the correct label
        if key == "top_left":
            set_label_text(self.tl_label, text_to_display, font, -90, -90)
        elif key == "top_right":
            set_label_text(self.tr_label, text_to_display, font, 90, -90)
        elif key == "bottom_left":
            set_label_text(self.bl_label, text_to_display, font, -90, 90)
        elif key == "bottom_right":
            set_label_text(self.br_label, text_to_display, font, 90, 90)

    def update_threshold_indicators(self, thresholds_dict):
        """Updates the size of the gray dashed threshold rings."""
        tl_r = self._map_weight_to_radius(thresholds_dict.get('top_left', 0))
        tr_r = self._map_weight_to_radius(thresholds_dict.get('top_right', 0))
        bl_r = self._map_weight_to_radius(thresholds_dict.get('bottom_left', 0))
        br_r = self._map_weight_to_radius(thresholds_dict.get('bottom_right', 0))
        
        self.tl_thresh.setRect(-tl_r, -tl_r, tl_r * 2, tl_r * 2)
        self.tr_thresh.setRect(-tr_r, -tr_r, tr_r * 2, tr_r * 2)
        self.bl_thresh.setRect(-bl_r, -bl_r, bl_r * 2, bl_r * 2)
        self.br_thresh.setRect(-br_r, -br_r, br_r * 2, br_r * 2)

    def update_dot(self, x, y, quadrants, press_states):
        """
        Updates the dot position and corner pressure circles.
        Signature changed to accept press_states dict.
        """
        canvas_x = x * 90 
        canvas_y = y * -90
        self.com_dot.setPos(canvas_x, canvas_y)
        
        tl_r = self._map_weight_to_radius(quadrants['top_left'])
        tr_r = self._map_weight_to_radius(quadrants['top_right'])
        bl_r = self._map_weight_to_radius(quadrants['bottom_left'])
        br_r = self._map_weight_to_radius(quadrants['bottom_right'])
        
        # --- Update colors based on press state ---
        tl_pressed = press_states['top_left']
        self.tl_dot.setBrush(self.active_pressure_brush if tl_pressed else self.inactive_pressure_brush)
        self.tl_dot.setPen(self.active_pressure_pen if tl_pressed else self.inactive_pressure_pen)
        
        tr_pressed = press_states['top_right']
        self.tr_dot.setBrush(self.active_pressure_brush if tr_pressed else self.inactive_pressure_brush)
        self.tr_dot.setPen(self.active_pressure_pen if tr_pressed else self.inactive_pressure_pen)
        
        bl_pressed = press_states['bottom_left']
        self.bl_dot.setBrush(self.active_pressure_brush if bl_pressed else self.inactive_pressure_brush)
        self.bl_dot.setPen(self.active_pressure_pen if bl_pressed else self.inactive_pressure_pen)

        br_pressed = press_states['bottom_right']
        self.br_dot.setBrush(self.active_pressure_brush if br_pressed else self.inactive_pressure_brush)
        self.br_dot.setPen(self.active_pressure_pen if br_pressed else self.inactive_pressure_pen)

        # --- Update rects (size) ---
        self.tl_dot.setRect(-tl_r, -tl_r, tl_r * 2, tl_r * 2)
        self.tr_dot.setRect(-tr_r, -tr_r, tr_r * 2, tr_r * 2)
        self.bl_dot.setRect(-bl_r, -bl_r, bl_r * 2, bl_r * 2)
        self.br_dot.setRect(-br_r, -br_r, br_r * 2, br_r * 2)

class BalanceBoardApp(QWidget):
    
    # --- UPDATED: Map includes PS hints ---
    VGAMEPAD_BUTTON_MAP = {
        "A (Cross ✕)": "XUSB_GAMEPAD_A",
        "B (Circle ○)": "XUSB_GAMEPAD_B",
        "X (Square □)": "XUSB_GAMEPAD_X",
        "Y (Triangle △)": "XUSB_GAMEPAD_Y",
        "Left Bumper (LB)": "XUSB_GAMEPAD_LEFT_SHOULDER",
        "Right Bumper (RB)": "XUSB_GAMEPAD_RIGHT_SHOULDER",
        "Left Stick (L3)": "XUSB_GAMEPAD_LEFT_THUMB",
        "Right Stick (R3)": "XUSB_GAMEPAD_RIGHT_THUMB",
        "Start": "XUSB_GAMEPAD_START",
        "Back": "XUSB_GAMEPAD_BACK",
        "None": "None" # Option to disable a sensor
    }
    
    # --- NEW: Map for combination inputs (joystick/d-pad) ---
    VGAMEPAD_COMBO_MAP = {
        "None": "None",
        "Left Stick Up": "LS_UP",
        "Left Stick Down": "LS_DOWN",
        "Left Stick Left": "LS_LEFT",
        "Left Stick Right": "LS_RIGHT",
        "D-Pad Up": "DPAD_UP",
        "D-Pad Down": "DPAD_DOWN",
        "D-Pad Left": "DPAD_LEFT",
        "D-Pad Right": "DPAD_RIGHT",
    }
    # --- NEW: All possible D-Pad buttons for release logic ---
    ALL_DPAD_BUTTONS = {
        "DPAD_UP", "DPAD_DOWN", "DPAD_LEFT", "DPAD_RIGHT"
    }

    
    def __init__(self, config):
        super().__init__()
        self.config = config
        
        # --- Create reverse map for populating UI ---
        self.REVERSE_VGAMEPAD_MAP = {v: k for k, v in self.VGAMEPAD_BUTTON_MAP.items()}
        # --- NEW: Reverse map for combos ---
        self.REVERSE_VGAMEPAD_COMBO_MAP = {v: k for k, v in self.VGAMEPAD_COMBO_MAP.items()}
        
        # --- Load thresholds ---
        self.thresholds = self.config.get("button_thresholds_kg", {
            "top_left": 10.0, "bottom_left": 10.0,
            "top_right": 10.0, "bottom_right": 10.0
        })
        
        # --- Load button mappings ---
        default_mappings = {
            "top_left": "XUSB_GAMEPAD_A",
            "bottom_left": "XUSB_GAMEPAD_B",
            "top_right": "XUSB_GAMEPAD_X",
            "bottom_right": "XUSB_GAMEPAD_Y"
        }
        self.button_mappings = self.config.get("button_mappings", default_mappings)

        # --- NEW: Load combination mappings ---
        default_combo_mappings = {
            "top_left_top_right": "None",
            "bottom_left_bottom_right": "None",
            "top_left_bottom_left": "None",
            "top_right_bottom_right": "None",
            "top_left_bottom_right": "None",
            "top_right_bottom_left": "None"
        }
        self.combination_mappings = self.config.get("combination_mappings", default_combo_mappings)
        
        # --- Track visual button state ---
        self.button_view_mode = "xbox"
        
        # --- NEW: Track theme state ---
        self.is_dark_mode = self.config.get("theme", "light") == "dark"
        
        # --- NEW: Board/Thread placeholders ---
        self.processing_thread = None
        self.board = None
        
        self.init_ui()
        self.apply_theme() # Apply loaded theme on startup
        self.update_all_com_labels()
        self._create_and_start_thread() # Start the board connection
        
        # --- Initialize virtual gamepad ---
        try:
            self.gamepad = vg.VX360Gamepad()
            print("Virtual Xbox 360 gamepad initialized.")
        except Exception as e:
            print(f"Could not initialize virtual gamepad: {e}")
            print("Please ensure ViGEmBus driver is installed.")
            self.gamepad = None

    def init_ui(self):
        self.setWindowTitle("Wii Balance Board Monitor (PyQt6)")
        # Adjusted height for new controls
        self.setGeometry(100, 100, 420, 990) # Increased height for new buttons
        
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(15, 15, 15, 15)
        main_layout.setSpacing(10)
        
        # --- Total Weight ---
        total_weight_header = QLabel("Total Weight")
        total_weight_header.setFont(QFont("Helvetica", 15, QFont.Weight.Bold))
        total_weight_header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        self.total_weight_label = QLabel("--.- kg")
        self.total_weight_label.setObjectName("total_weight_label") # Set object name for QSS
        self.total_weight_label.setFont(QFont("Helvetica", 26, QFont.Weight.Bold))
        self.total_weight_label.setStyleSheet("color: #007ACC;") # Default
        self.total_weight_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # --- Quadrant Labels ---
        quad_layout = QHBoxLayout()
        quad_frame = QFrame()
        quad_frame.setLayout(quad_layout)
        
        self.tl_label = QLabel("TL: --.- kg")
        self.tr_label = QLabel("TR: --.- kg")
        self.bl_label = QLabel("BL: --.- kg")
        self.br_label = QLabel("BR: --.- kg")
        
        for label in [self.tl_label, self.tr_label, self.bl_label, self.br_label]:
            label.setFont(QFont("Helvetica", 11))

        v_layout_left = QVBoxLayout()
        v_layout_left.addWidget(self.tl_label)
        v_layout_left.addWidget(self.bl_label)
        
        v_layout_right = QVBoxLayout()
        v_layout_right.addWidget(self.tr_label)
        v_layout_right.addWidget(self.br_label)
        
        quad_layout.addLayout(v_layout_left)
        quad_layout.addLayout(v_layout_right)
        
        # --- Center of Mass ---
        self.com_widget = CoMWidget()
        # Update threshold indicators on init
        self.com_widget.update_threshold_indicators(self.thresholds)
        
        com_widget_layout = QHBoxLayout()
        com_widget_layout.addStretch()
        com_widget_layout.addWidget(self.com_widget)
        com_widget_layout.addStretch()

        # --- View Toggle Button ---
        self.toggle_view_button = QPushButton("Show PlayStation Icons (△, ○, ✕, □)")
        self.toggle_view_button.setFont(QFont("Helvetica", 10))
        self.toggle_view_button.clicked.connect(self.on_toggle_view)
        
        # --- Threshold Spinners ---
        threshold_frame = QFrame()
        threshold_frame.setFrameShape(QFrame.Shape.StyledPanel)
        threshold_layout = QGridLayout(threshold_frame)
        threshold_layout.setSpacing(8)
        threshold_layout.setContentsMargins(8, 8, 8, 8)
        threshold_layout.addWidget(QLabel("Button Thresholds:"), 0, 0, 1, 4)

        # Create spinners
        self.spin_tl = QDoubleSpinBox(decimals=1, minimum=0.1, maximum=100.0, singleStep=0.5, suffix=" kg")
        self.spin_bl = QDoubleSpinBox(decimals=1, minimum=0.1, maximum=100.0, singleStep=0.5, suffix=" kg")
        self.spin_tr = QDoubleSpinBox(decimals=1, minimum=0.1, maximum=100.0, singleStep=0.5, suffix=" kg")
        self.spin_br = QDoubleSpinBox(decimals=1, minimum=0.1, maximum=100.0, singleStep=0.5, suffix=" kg")

        # Set initial values from config
        self.spin_tl.setValue(self.thresholds.get("top_left", 10.0))
        self.spin_bl.setValue(self.thresholds.get("bottom_left", 10.0))
        self.spin_tr.setValue(self.thresholds.get("top_right", 10.0))
        self.spin_br.setValue(self.thresholds.get("bottom_right", 10.0))

        # Connect signals
        self.spin_tl.valueChanged.connect(lambda v: self.on_threshold_changed("top_left", v))
        self.spin_bl.valueChanged.connect(lambda v: self.on_threshold_changed("bottom_left", v))
        self.spin_tr.valueChanged.connect(lambda v: self.on_threshold_changed("top_right", v))
        self.spin_br.valueChanged.connect(lambda v: self.on_threshold_changed("bottom_right", v))

        # Helper for creating labels
        def create_mapping_label(text):
            lbl = QLabel(text)
            lbl.setFont(QFont("Helvetica", 10))
            return lbl

        # Add to layout
        threshold_layout.addWidget(create_mapping_label("Top-Left:"), 1, 0)
        threshold_layout.addWidget(self.spin_tl, 1, 1)
        threshold_layout.addWidget(create_mapping_label("Bottom-Left:"), 2, 0)
        threshold_layout.addWidget(self.spin_bl, 2, 1)
        threshold_layout.addWidget(create_mapping_label("Top-Right:"), 1, 2)
        threshold_layout.addWidget(self.spin_tr, 1, 3)
        threshold_layout.addWidget(create_mapping_label("Bottom-Right:"), 2, 2)
        threshold_layout.addWidget(self.spin_br, 2, 3)

        # --- Button Mapping Controls ---
        mapping_frame = QFrame()
        mapping_frame.setFrameShape(QFrame.Shape.StyledPanel)
        mapping_layout = QGridLayout(mapping_frame)
        mapping_layout.setSpacing(8)
        mapping_layout.setContentsMargins(8, 8, 8, 8)
        mapping_layout.addWidget(QLabel("Button Mappings (Individual):"), 0, 0, 1, 4)
        
        # Create combo boxes
        self.combo_tl = QComboBox()
        self.combo_tr = QComboBox()
        self.combo_bl = QComboBox()
        self.combo_br = QComboBox()
        
        combos = [self.combo_tl, self.combo_tr, self.combo_bl, self.combo_br]
        keys = ["top_left", "top_right", "bottom_left", "bottom_right"]
        
        for combo, key in zip(combos, keys):
            # UPDATED: Adds items with new hint text
            combo.addItems(self.VGAMEPAD_BUTTON_MAP.keys())
            # Set initial value from config
            mapped_button_str = self.button_mappings.get(key)
            display_text = self.REVERSE_VGAMEPAD_MAP.get(mapped_button_str, "None")
            combo.setCurrentText(display_text)

        # Connect signals
        self.combo_tl.currentTextChanged.connect(lambda text: self.on_mapping_changed("top_left", text))
        self.combo_tr.currentTextChanged.connect(lambda text: self.on_mapping_changed("top_right", text))
        self.combo_bl.currentTextChanged.connect(lambda text: self.on_mapping_changed("bottom_left", text))
        self.combo_br.currentTextChanged.connect(lambda text: self.on_mapping_changed("bottom_right", text))

        # Add to layout
        mapping_layout.addWidget(create_mapping_label("Top-Left:"), 1, 0)
        mapping_layout.addWidget(self.combo_tl, 1, 1)
        mapping_layout.addWidget(create_mapping_label("Top-Right:"), 1, 2)
        mapping_layout.addWidget(self.combo_tr, 1, 3)
        mapping_layout.addWidget(create_mapping_label("Bottom-Left:"), 2, 0)
        mapping_layout.addWidget(self.combo_bl, 2, 1)
        mapping_layout.addWidget(create_mapping_label("Bottom-Right:"), 2, 2)
        mapping_layout.addWidget(self.combo_br, 2, 3)
        
        # --- NEW: Combination Mapping Controls ---
        combo_mapping_frame = QFrame()
        combo_mapping_frame.setFrameShape(QFrame.Shape.StyledPanel)
        combo_mapping_layout = QGridLayout(combo_mapping_frame)
        combo_mapping_layout.setSpacing(8)
        combo_mapping_layout.setContentsMargins(8, 8, 8, 8)
        combo_mapping_layout.addWidget(QLabel("Combination Mappings (Joystick/D-Pad):"), 0, 0, 1, 4)

        # Create combo boxes
        self.combo_tl_tr = QComboBox()
        self.combo_bl_br = QComboBox()
        self.combo_tl_bl = QComboBox()
        self.combo_tr_br = QComboBox()
        self.combo_tl_br = QComboBox()
        self.combo_tr_bl = QComboBox()

        combo_combos = [
            self.combo_tl_tr, self.combo_bl_br, self.combo_tl_bl,
            self.combo_tr_br, self.combo_tl_br, self.combo_tr_bl
        ]
        combo_keys = [
            "top_left_top_right", "bottom_left_bottom_right", "top_left_bottom_left",
            "top_right_bottom_right", "top_left_bottom_right", "top_right_bottom_left"
        ]

        for combo, key in zip(combo_combos, combo_keys):
            combo.addItems(self.VGAMEPAD_COMBO_MAP.keys())
            # Set initial value from config
            mapped_combo_str = self.combination_mappings.get(key, "None")
            display_text = self.REVERSE_VGAMEPAD_COMBO_MAP.get(mapped_combo_str, "None")
            combo.setCurrentText(display_text)
        
        # Connect signals
        self.combo_tl_tr.currentTextChanged.connect(lambda text: self.on_combo_mapping_changed("top_left_top_right", text))
        self.combo_bl_br.currentTextChanged.connect(lambda text: self.on_combo_mapping_changed("bottom_left_bottom_right", text))
        self.combo_tl_bl.currentTextChanged.connect(lambda text: self.on_combo_mapping_changed("top_left_bottom_left", text))
        self.combo_tr_br.currentTextChanged.connect(lambda text: self.on_combo_mapping_changed("top_right_bottom_right", text))
        self.combo_tl_br.currentTextChanged.connect(lambda text: self.on_combo_mapping_changed("top_left_bottom_right", text))
        self.combo_tr_bl.currentTextChanged.connect(lambda text: self.on_combo_mapping_changed("top_right_bottom_left", text))

        # Add to layout
        combo_mapping_layout.addWidget(create_mapping_label("Top-Left + Top-Right:"), 1, 0)
        combo_mapping_layout.addWidget(self.combo_tl_tr, 1, 1)
        combo_mapping_layout.addWidget(create_mapping_label("Bottom-Left + Bottom-Right:"), 2, 0)
        combo_mapping_layout.addWidget(self.combo_bl_br, 2, 1)
        combo_mapping_layout.addWidget(create_mapping_label("Top-Left + Bottom-Left:"), 3, 0)
        combo_mapping_layout.addWidget(self.combo_tl_bl, 3, 1)
        combo_mapping_layout.addWidget(create_mapping_label("Top-Right + Bottom-Right:"), 4, 0)
        combo_mapping_layout.addWidget(self.combo_tr_br, 4, 1)
        combo_mapping_layout.addWidget(create_mapping_label("Top-Left + Bottom-Right:"), 5, 0)
        combo_mapping_layout.addWidget(self.combo_tl_br, 5, 1)
        combo_mapping_layout.addWidget(create_mapping_label("Top-Right + Bottom-Left:"), 6, 0)
        combo_mapping_layout.addWidget(self.combo_tr_bl, 6, 1)

        # --- Control Buttons ---
        self.tare_button = QPushButton("Tare (Zero)")
        self.tare_button.setFont(QFont("Helvetica", 11, QFont.Weight.Bold))
        self.tare_button.setEnabled(False)
        self.tare_button.setMinimumHeight(35)
        
        self.save_button = QPushButton("Save Config")
        self.save_button.setFont(QFont("Helvetica", 11, QFont.Weight.Bold))
        self.save_button.setMinimumHeight(35)
        
        self.rescan_button = QPushButton("Rescan for Board")
        self.rescan_button.setFont(QFont("Helvetica", 11, QFont.Weight.Bold))
        self.rescan_button.setMinimumHeight(35)
        
        self.toggle_theme_button = QPushButton("Toggle Dark Mode")
        self.toggle_theme_button.setFont(QFont("Helvetica", 11, QFont.Weight.Bold))
        self.toggle_theme_button.setMinimumHeight(35)

        # --- Button Layout ---
        button_layout_1 = QHBoxLayout()
        button_layout_1.addWidget(self.tare_button)
        button_layout_1.addWidget(self.save_button)
        
        button_layout_2 = QHBoxLayout()
        button_layout_2.addWidget(self.rescan_button)
        button_layout_2.addWidget(self.toggle_theme_button)
        
        # --- Status Bar ---
        self.status_label = QLabel("Initializing...")
        self.status_label.setObjectName("status_label") # Set object name for QSS
        self.status_label.setFont(QFont("Helvetica", 10))
        self.status_label.setStyleSheet("border-top: 1px solid #CCC; padding: 5px;") # Default
        
        # --- Add widgets to main layout ---
        main_layout.addWidget(total_weight_header)
        main_layout.addWidget(self.total_weight_label)
        main_layout.addWidget(quad_frame)
        main_layout.addSpacing(10)
        main_layout.addLayout(com_widget_layout) # Add CoM graph
        main_layout.addWidget(self.toggle_view_button) # Add toggle button
        main_layout.addSpacing(10)
        main_layout.addWidget(threshold_frame) # Add threshold controls
        main_layout.addWidget(mapping_frame) # Add mapping controls
        main_layout.addWidget(combo_mapping_frame) # NEW: Add combo mapping controls
        main_layout.addStretch()
        main_layout.addLayout(button_layout_1) # Add button row 1
        main_layout.addLayout(button_layout_2) # Add button row 2
        main_layout.addWidget(self.status_label)
        
        # --- Connect button signals ---
        self.tare_button.clicked.connect(self.on_tare_click)
        self.save_button.clicked.connect(self.save_config)
        self.rescan_button.clicked.connect(self.on_rescan_click)
        self.toggle_theme_button.clicked.connect(self.on_toggle_theme)

    def _create_and_start_thread(self):
        """
        NEW: Creates and starts a new board worker and thread.
        This is now the single point of entry for starting/restarting the connection.
        """
        # Disconnect old slot if it exists, to prevent multiple connections
        if self.processing_thread:
             self.processing_thread.finished.disconnect(self._create_and_start_thread)

        self.processing_thread = QThread()
        self.board = WiiBalanceBoard(self.config)
        
        self.board.moveToThread(self.processing_thread)
        
        # Connect signals
        self.board.data_received.connect(self.update_gui)
        self.board.status_update.connect(self.set_status)
        self.board.error_occurred.connect(self.handle_error)
        
        self.board.ready_to_tare.connect(lambda: self.tare_button.setEnabled(True))
        self.board.ready_to_tare.connect(lambda: self.rescan_button.setEnabled(True)) # Re-enable rescan
        self.board.tare_complete.connect(self.on_tare_complete)
        
        # Thread lifetime management
        self.processing_thread.started.connect(self.board.start_processing_loop)
        self.board.finished.connect(self.processing_thread.quit) # Tell thread to quit when worker is done
        self.board.finished.connect(self.board.deleteLater) # Schedule worker for deletion
        self.processing_thread.finished.connect(self.processing_thread.deleteLater) # Schedule thread for deletion
        
        self.processing_thread.start()
        self.rescan_button.setEnabled(True) # Allow scanning even if it fails

    # --- GUI Slots ---
    
    def on_rescan_click(self):
        """
        NEW: Safely stops the current board thread and starts a new scan.
        """
        self.set_status("Rescanning...")
        self.tare_button.setEnabled(False)
        self.rescan_button.setEnabled(False) # Disable to prevent spamming
        
        if self.processing_thread and self.processing_thread.isRunning():
            # Connect the thread's finished signal to start a new scan
            self.processing_thread.finished.connect(self._create_and_start_thread, Qt.ConnectionType.SingleShotConnection)
            # Tell the worker to stop, which will emit 'finished' and stop the thread
            self.board.stop_processing()
        else:
            # No thread running, just start a new one
            self._create_and_start_thread()

    def on_toggle_theme(self):
        """NEW: Toggles the application's theme."""
        self.is_dark_mode = not self.is_dark_mode
        self.config["theme"] = "dark" if self.is_dark_mode else "light"
        self.apply_theme()

    def apply_theme(self):
        """NEW: Applies the currently selected theme."""
        if self.is_dark_mode:
            self.setStyleSheet(DARK_STYLESHEET)
            self.toggle_theme_button.setText("Toggle Light Mode")
        else:
            self.setStyleSheet(LIGHT_STYLESHEET)
            self.toggle_theme_button.setText("Toggle Dark Mode")
        
        # Update the CoM widget's theme
        self.com_widget.set_theme(self.is_dark_mode)

    def update_all_com_labels(self):
        """
        NEW: Updates all four labels on the CoM widget based on the current
        mappings and view mode.
        """
        tl_text = self.REVERSE_VGAMEPAD_MAP.get(self.button_mappings.get("top_left"))
        tr_text = self.REVERSE_VGAMEPAD_MAP.get(self.button_mappings.get("top_right"))
        bl_text = self.REVERSE_VGAMEPAD_MAP.get(self.button_mappings.get("bottom_left"))
        br_text = self.REVERSE_VGAMEPAD_MAP.get(self.button_mappings.get("bottom_right"))

        self.com_widget.update_label("top_left", tl_text, self.button_view_mode)
        self.com_widget.update_label("top_right", tr_text, self.button_view_mode)
        self.com_widget.update_label("bottom_left", bl_text, self.button_view_mode)
        self.com_widget.update_label("bottom_right", br_text, self.button_view_mode)
    
    def on_toggle_view(self):
        """
        UPDATED: Slot to toggle the button icons in the CoM widget
        and refresh all labels.
        """
        if self.button_view_mode == "xbox":
            self.button_view_mode = "ps"
            self.toggle_view_button.setText("Show Xbox Icons (A, B, X, Y)")
        else:
            self.button_view_mode = "xbox"
            self.toggle_view_button.setText("Show PlayStation Icons (△, ○, ✕, □)")
        
        # Refresh all labels with the new mode
        self.update_all_com_labels()

    def on_threshold_changed(self, key, value):
        """Slot to update the internal threshold when a spinner is changed."""
        self.thresholds[key] = value
        # Update the visual indicators
        self.com_widget.update_threshold_indicators(self.thresholds)

    def on_mapping_changed(self, key, text):
        """
        UPDATED: Slot to update the internal button mapping and
        immediately update the CoM widget label.
        """
        vgamepad_string = self.VGAMEPAD_BUTTON_MAP[text]
        self.button_mappings[key] = vgamepad_string
        print(f"Mapping changed: {key} -> {vgamepad_string}")
        
        # NEW: Update the specific label on the CoM widget
        self.com_widget.update_label(key, text, self.button_view_mode)

    def on_combo_mapping_changed(self, key, text):
        """NEW: Slot to update the internal combination button mapping."""
        vgamepad_string = self.VGAMEPAD_COMBO_MAP[text]
        self.combination_mappings[key] = vgamepad_string
        print(f"Combination Mapping changed: {key} -> {vgamepad_string}")

    def _apply_combo_mapping(self, mapping_str, x, y, dpad_set):
        """
        Helper to apply a combo mapping (joystick or dpad)
        Returns updated x, y, and dpad_set
        """
        if mapping_str == "LS_UP":
            y = 32767
        elif mapping_str == "LS_DOWN":
            y = -32768
        elif mapping_str == "LS_LEFT":
            x = -32768
        elif mapping_str == "LS_RIGHT":
            x = 32767
        elif mapping_str in self.ALL_DPAD_BUTTONS:
            dpad_set.add(mapping_str)
        
        return x, y, dpad_set

    def update_gui(self, data):
        """Slot to update all GUI elements with new data."""
        quads = data['quadrants_kg']
        
        self.total_weight_label.setText(f"{data['total_kg']:.2f} kg")
        self.tr_label.setText(f"TR: {quads['top_right']:.2f} kg")
        self.tl_label.setText(f"TL: {quads['top_left']:.2f} kg")
        self.br_label.setText(f"BR: {quads['bottom_right']:.2f} kg")
        self.bl_label.setText(f"BL: {quads['bottom_left']:.2f} kg")
        
        x, y = data['center_of_mass']
        
        # --- NEW: Layered Button Logic ---
        
        # 1. Determine base press states
        press_states = {
            'top_left': quads['top_left'] > self.thresholds['top_left'],
            'top_right': quads['top_right'] > self.thresholds['top_right'],
            'bottom_left': quads['bottom_left'] > self.thresholds['bottom_left'],
            'bottom_right': quads['bottom_right'] > self.thresholds['bottom_right'],
        }
        
        # 2. Initialize gamepad outputs
        l_stick_x, l_stick_y = 0, 0
        buttons_to_press_str = set()
        dpad_buttons_to_press_str = set()
        suppressed_buttons = set() # e.g., {'top_left', 'top_right'}
        
        tl = press_states['top_left']
        tr = press_states['top_right']
        bl = press_states['bottom_left']
        br = press_states['bottom_right']

        # 3. Check combinations (Priority 1)
        # This dict simplifies checking all 6 pairs
        combo_pairs = {
            'top_left_top_right': (tl and tr),
            'bottom_left_bottom_right': (bl and br),
            'top_left_bottom_left': (tl and bl),
            'top_right_bottom_right': (tr and br),
            'top_left_bottom_right': (tl and br),
            'top_right_bottom_left': (tr and bl)
        }
        
        for combo_key, is_active in combo_pairs.items():
            if is_active:
                mapping_str = self.combination_mappings.get(combo_key)
                if mapping_str and mapping_str != "None":
                    # Apply the combo mapping (e.g., set l_stick_y)
                    l_stick_x, l_stick_y, dpad_buttons_to_press_str = self._apply_combo_mapping(
                        mapping_str, l_stick_x, l_stick_y, dpad_buttons_to_press_str
                    )
                    
                    # Suppress the two buttons that make up this combo
                    btn1 = combo_key[0:8] # 'top_left'
                    btn2 = combo_key[9:100] # 'top_right'
                    
                    # Correctly split keys like 'top_left_bottom_left'
                    parts = combo_key.split('_')
                    btn1 = f"{parts[0]}_{parts[1]}" # 'top_left'
                    btn2 = f"{parts[2]}_{parts[3]}" # 'bottom_left'
                    
                    suppressed_buttons.add(btn1)
                    suppressed_buttons.add(btn2)

        # 4. Check individual buttons (Priority 2)
        for btn_key, is_active in press_states.items():
            if is_active and btn_key not in suppressed_buttons:
                mapping_str = self.button_mappings.get(btn_key)
                if mapping_str and mapping_str != "None":
                    buttons_to_press_str.add(mapping_str)

        # 5. Update virtual gamepad
        if self.gamepad:
            
            # --- 5a. Individual Buttons (A, B, X, Y, etc.) ---
            # Get all buttons managed by the *individual* mappings
            managed_buttons_str = set(self.button_mappings.values())
            if "None" in managed_buttons_str:
                managed_buttons_str.remove("None")

            # Determine which managed buttons to release
            buttons_to_release_str = managed_buttons_str - buttons_to_press_str

            for button_str in buttons_to_press_str:
                button_enum = getattr(vg.XUSB_BUTTON, button_str, None)
                if button_enum:
                    self.gamepad.press_button(button=button_enum)

            for button_str in buttons_to_release_str:
                button_enum = getattr(vg.XUSB_BUTTON, button_str, None)
                if button_enum:
                    self.gamepad.release_button(button=button_enum)

            # --- 5b. D-Pad ---
            dpad_buttons_to_release_str = self.ALL_DPAD_BUTTONS - dpad_buttons_to_press_str

            for dpad_str in dpad_buttons_to_press_str:
                # e.g., vg.XUSB_BUTTON.XUSB_GAMEPAD_DPAD_UP
                button_enum = getattr(vg.XUSB_BUTTON, 'XUSB_GAMEPAD_' + dpad_str)
                self.gamepad.press_button(button=button_enum)

            for dpad_str in dpad_buttons_to_release_str:
                button_enum = getattr(vg.XUSB_BUTTON, 'XUSB_GAMEPAD_' + dpad_str)
                self.gamepad.release_button(button=button_enum)

            # --- 5c. Left Stick ---
            self.gamepad.left_joystick(x_value=l_stick_x, y_value=l_stick_y)
            
            # --- 5d. Send all updates ---
            self.gamepad.update() 

        # Pass states to widget for visualization
        self.com_widget.update_dot(x, y, quads, press_states)
        
    def set_status(self, text):
        """Slot to update the status bar."""
        self.status_label.setText(text)

    def handle_error(self, text):
        """Slot to show an error. Disables tare button."""
        self.set_status(text)
        self.tare_button.setEnabled(False)
        self.rescan_button.setEnabled(True) # Allow user to rescan on error

    def on_tare_click(self):
        """Slot for when the tare button is clicked."""
        self.set_status("🔵 Taring... Please step OFF the board.")
        self.tare_button.setEnabled(False)
        self.board.perform_tare() 

    def on_tare_complete(self, success):
        """Slot for when the board signals tare is complete."""
        if success:
            self.set_status("✅ Ready! Please step ON the board.")
        else:
            self.set_status("❌ Tare failed. No data. Try again.")
        self.tare_button.setEnabled(True)

    def save_config(self):
        """Saves current settings to user_config.json"""
        print("Saving user_config.json...")
        self.config["button_thresholds_kg"] = self.thresholds
        self.config["button_mappings"] = self.button_mappings
        self.config["combination_mappings"] = self.combination_mappings
        self.config["theme"] = "dark" if self.is_dark_mode else "light"
        
        try:
            with open("user_config.json", "w") as f:
                json.dump(self.config, f, indent=4)
            print("Config saved.")
            self.set_status("✅ Config saved to user_config.json")
        except Exception as e:
            print(f"Error saving config: {e}")
            self.set_status(f"❌ Error saving config: {e}")

    def closeEvent(self, event):
        """Overrides the window close event to safely shut down the thread."""
        print("Closing application...")
        
        # --- REMOVED: save_config() ---
        # User must save manually now
        
        if self.processing_thread and self.processing_thread.isRunning():
            self.board.stop_processing()
            self.processing_thread.quit()
            self.processing_thread.wait(3000)
        
        if self.gamepad:
            print("Releasing virtual gamepad...")
            self.gamepad.reset() # Reset all buttons/axes
            self.gamepad.update() # Send the reset state
            del self.gamepad
            
        event.accept()

def load_config():
    """
    Loads config, prioritizing user_config.json,
    then default_config.json, then built-in defaults.
    """
    user_config_path = "user_config.json"
    default_config_path = "default_config.json"
    
    config_to_load = None
    
    # 1. Try to load user_config.json
    try:
        with open(user_config_path, "r") as f:
            print(f"Loading user config from {user_config_path}")
            return json.load(f)
    except FileNotFoundError:
        print(f"{user_config_path} not found.")
    except Exception as e:
        print(f"Error loading {user_config_path}: {e}")

    # 2. Try to load default_config.json
    try:
        with open(default_config_path, "r") as f:
            print(f"Loading default config from {default_config_path}")
            return json.load(f)
    except FileNotFoundError:
        print(f"{default_config_path} not found.")
    except Exception as e:
        print(f"Error loading {default_config_path}: {e}")

    # 3. Use built-in defaults as a last resort
    print("Using built-in defaults.")
    # Create a more complete default config
    return {
        "tare_duration_sec": 3.0,
            "polling_rate_hz": 30,
            "averaging_samples": 5,
            "dead_zone_kg": 0.2,
            "theme": "light", # --- NEW ---
            "button_thresholds_kg": {
                "top_left": 10.0, "bottom_left": 10.0,
                "top_right": 10.0, "bottom_right": 10.0
            },
            "button_mappings": {
              "top_left": "XUSB_GAMEPAD_A",
              "bottom_left": "XUSB_GAMEPAD_B",
              "top_right": "XUSB_GAMEPAD_X",
              "bottom_right": "XUSB_GAMEPAD_Y"
            },
            # --- NEW: Default combo mappings ---
            "combination_mappings": {
            "top_left_top_right": "None",
            "bottom_left_bottom_right": "None",
                "top_left_bottom_left": "None",
                "top_right_bottom_right": "None",
                "top_left_bottom_right": "None",
                "top_right_bottom_left": "None"
        }
    }

if __name__ == "__main__":
    config = load_config()
    
    app = QApplication(sys.argv)
    window = BalanceBoardApp(config)
    window.show()
    sys.exit(app.exec())