import sys
import json
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
    QPushButton, QFrame, QGraphicsView, QGraphicsScene, QGraphicsEllipseItem,
    QDoubleSpinBox, QGridLayout, QGraphicsPolygonItem
)
from PyQt6.QtCore import Qt, QPointF, QThread, QRectF, QSize
from PyQt6.QtGui import (
    QFont, QColor, QPen, QBrush, QPainter, QPolygonF
)
from WiiBalanceBoard_qt import WiiBalanceBoard # Import the Qt-enabled API

class ButtonIndicator(QWidget):
    """
    A custom widget that is a circle with a text label.
    It can be set to an 'active' state (red) or 'inactive' state (gray).
    """
    def __init__(self, label_text):
        super().__init__()
        self.label = label_text
        self.is_active = False
        self.setFixedSize(50, 50) # Fixed size for the circle

        self.active_color = QColor(220, 0, 0)
        self.inactive_color = QColor(200, 200, 200)

    def set_active(self, active):
        if active != self.is_active:
            self.is_active = active
            self.update() # Trigger a repaint

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Set brush color based on state
        color = self.active_color if self.is_active else self.inactive_color
        painter.setBrush(QBrush(color))
        
        # No outline
        painter.setPen(Qt.PenStyle.NoPen)
        
        # Draw circle in the center
        rect = self.rect()
        # Inset by 1px to avoid clipping
        painter.drawEllipse(rect.adjusted(1, 1, -1, -1))
        
        # Draw label text
        painter.setPen(Qt.GlobalColor.black)
        font = QFont("Helvetica", 12, QFont.Weight.Bold)
        painter.setFont(font)
        painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, self.label)

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
        
        self.setBackgroundBrush(QColor(255, 255, 255))
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        
        # --- NEW: Draw grid lines (axes) ---
        grid_pen = QPen(QColor(230, 230, 230), 1, Qt.PenStyle.SolidLine)
        grid_pen.setCosmetic(True) # Keep it 1px
        for i in range(-10, 11):
            if i == 0: continue # Main crosshairs will draw over this
            coord = i * 10 # e.g., -90, -80... 80, 90
            self.scene.addLine(-100, coord, 100, coord, grid_pen).setZValue(-10)
            self.scene.addLine(coord, -100, coord, 100, grid_pen).setZValue(-10)

        # Draw main crosshairs (on top of grid)
        self.scene.addLine(-100, 0, 100, 0, QPen(Qt.GlobalColor.lightGray, 1, Qt.PenStyle.DashLine)).setZValue(-5)
        self.scene.addLine(0, -100, 0, 100, QPen(Qt.GlobalColor.lightGray, 1, Qt.PenStyle.DashLine)).setZValue(-5)
        
        # Draw labels
        font = QFont("Helvetica", 9)
        top_label = self.scene.addText("Top (+Y)", font)
        top_label.setPos(-top_label.boundingRect().width() / 2, -100)
        
        bottom_label = self.scene.addText("Bottom (-Y)", font)
        bottom_label.setPos(-bottom_label.boundingRect().width() / 2, 90)

        left_label = self.scene.addText("L\n(-X)", font)
        left_label.setPos(-98, -left_label.boundingRect().height() / 2)
        
        right_label = self.scene.addText("R\n(+X)", font)
        right_label.setPos(98 - right_label.boundingRect().width(), -right_label.boundingRect().height() / 2)
        
        # --- NEW: Bounding Box Polygon ---
        self.bounding_box = QGraphicsPolygonItem()
        self.bounding_box.setBrush(QBrush(QColor(0, 0, 255, 40))) # Transparent blue
        self.bounding_box.setPen(QPen(QColor(0, 0, 255, 100), 1))
        self.bounding_box.setZValue(-1) # Behind dots
        self.scene.addItem(self.bounding_box)
        
        # --- Create pressure dots ---
        pressure_brush = QBrush(QColor(0, 0, 255, 120)) # Semi-transparent blue
        pressure_pen = QPen(QColor(0, 0, 255, 180), 1)
        min_r = self._map_weight_to_radius(0)
        
        self.tl_dot = self.scene.addEllipse(0, 0, min_r * 2, min_r * 2, pressure_pen, pressure_brush)
        self.tl_dot.setPos(-90, -90); self.tl_dot.setZValue(5)
        
        self.tr_dot = self.scene.addEllipse(0, 0, min_r * 2, min_r * 2, pressure_pen, pressure_brush)
        self.tr_dot.setPos(90, -90); self.tr_dot.setZValue(5)
        
        self.bl_dot = self.scene.addEllipse(0, 0, min_r * 2, min_r * 2, pressure_pen, pressure_brush)
        self.bl_dot.setPos(-90, 90); self.bl_dot.setZValue(5)
        
        self.br_dot = self.scene.addEllipse(0, 0, min_r * 2, min_r * 2, pressure_pen, pressure_brush)
        self.br_dot.setPos(90, 90); self.br_dot.setZValue(5)

        self.com_dot = QGraphicsEllipseItem(-2, -2, 4, 4)
        self.com_dot.setBrush(QBrush(Qt.GlobalColor.red))
        self.com_dot.setPen(QPen(Qt.GlobalColor.red))
        self.com_dot.setZValue(10) # On top of everything
        self.scene.addItem(self.com_dot)
        
        self.setRenderHint(QPainter.RenderHint.Antialiasing)

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

    def set_target_box(self, box_coords_dict):
        """
        Updates the blue bounding box from a dict of CoM coordinates.
        e.g., {'top': 0.5, 'bottom': -0.5, 'left': -0.5, 'right': 0.5}
        """
        # Map CoM coords (-1 to 1) to Scene coords (-90 to 90)
        # Y is inverted
        top_y = box_coords_dict.get('top', 0.5) * -90
        bottom_y = box_coords_dict.get('bottom', -0.5) * -90
        left_x = box_coords_dict.get('left', -0.5) * 90
        right_x = box_coords_dict.get('right', 0.5) * 90
        
        # Create polygon
        polygon = QPolygonF([
            QPointF(left_x, top_y),
            QPointF(right_x, top_y),
            QPointF(right_x, bottom_y),
            QPointF(left_x, bottom_y)
        ])
        self.bounding_box.setPolygon(polygon)

    def update_dot(self, x, y, quadrants):
        """Updates the dot position and corner pressure circles."""
        canvas_x = x * 90 
        canvas_y = y * -90
        self.com_dot.setPos(canvas_x, canvas_y)
        
        tl_r = self._map_weight_to_radius(quadrants['top_left'])
        tr_r = self._map_weight_to_radius(quadrants['top_right'])
        bl_r = self._map_weight_to_radius(quadrants['bottom_left'])
        br_r = self._map_weight_to_radius(quadrants['bottom_right'])
        
        self.tl_dot.setRect(-tl_r, -tl_r, tl_r * 2, tl_r * 2)
        self.tr_dot.setRect(-tr_r, -tr_r, tr_r * 2, tr_r * 2)
        self.bl_dot.setRect(-bl_r, -bl_r, bl_r * 2, bl_r * 2)
        self.br_dot.setRect(-br_r, -br_r, br_r * 2, br_r * 2)

class BalanceBoardApp(QWidget):
    def __init__(self, config):
        super().__init__()
        self.config = config
        
        # --- Load thresholds ---
        self.thresholds = self.config.get("button_thresholds_kg", {
            "top_left": 10.0, "bottom_left": 10.0,
            "top_right": 10.0, "bottom_right": 10.0
        })
        
        self.init_ui()
        self.init_board()

    def init_ui(self):
        self.setWindowTitle("Wii Balance Board Monitor (PyQt6)")
        self.setGeometry(100, 100, 450, 800) # Made window taller
        
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(15)
        
        # --- Total Weight ---
        total_weight_header = QLabel("Total Weight")
        total_weight_header.setFont(QFont("Helvetica", 16, QFont.Weight.Bold))
        total_weight_header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        self.total_weight_label = QLabel("--.- kg")
        self.total_weight_label.setFont(QFont("Helvetica", 28, QFont.Weight.Bold))
        self.total_weight_label.setStyleSheet("color: #007ACC;")
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
            label.setFont(QFont("Helvetica", 12))
            label.setMinimumWidth(100)

        v_layout_left = QVBoxLayout()
        v_layout_left.addWidget(self.tl_label)
        v_layout_left.addWidget(self.bl_label)
        
        v_layout_right = QVBoxLayout()
        v_layout_right.addWidget(self.tr_label)
        v_layout_right.addWidget(self.br_label)
        
        quad_layout.addLayout(v_layout_left)
        quad_layout.addLayout(v_layout_right)

        # --- NEW: Button Indicators ---
        button_layout = QHBoxLayout()
        button_layout.setSpacing(15)
        self.button_a = ButtonIndicator("A") # TL
        self.button_b = ButtonIndicator("B") # BL
        self.button_x = ButtonIndicator("X") # TR
        self.button_y = ButtonIndicator("Y") # BR
        
        button_layout.addStretch()
        button_layout.addWidget(self.button_a)
        button_layout.addWidget(self.button_b)
        button_layout.addStretch()
        button_layout.addWidget(self.button_x)
        button_layout.addWidget(self.button_y)
        button_layout.addStretch()

        # --- Center of Mass ---
        com_header = QLabel("Center of Mass")
        com_header.setFont(QFont("Helvetica", 16, QFont.Weight.Bold))
        com_header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        self.com_widget = CoMWidget()
        # Load the target box from config
        self.com_widget.set_target_box(self.config.get("com_target_box", {}))
        
        com_widget_layout = QHBoxLayout()
        com_widget_layout.addStretch()
        com_widget_layout.addWidget(self.com_widget)
        com_widget_layout.addStretch()
        
        # --- NEW: Threshold Spinners ---
        threshold_frame = QFrame()
        threshold_frame.setFrameShape(QFrame.Shape.StyledPanel)
        threshold_layout = QGridLayout(threshold_frame)
        threshold_layout.setSpacing(10)
        threshold_layout.setContentsMargins(10, 10, 10, 10)

        # Create spinners
        self.spin_tl = QDoubleSpinBox(decimals=1, minimum=0.1, maximum=100.0, singleStep=0.5, suffix=" kg")
        self.spin_bl = QDoubleSpinBox(decimals=1, minimum=0.1, maximum=100.0, singleStep=0.5, suffix=" kg")
        self.spin_tr = QDoubleSpinBox(decimals=1, minimum=0.1, maximum=100.0, singleStep=0.5, suffix=" kg")
        self.spin_br = QDoubleSpinBox(decimals=1, minimum=0.1, maximum=100.0, singleStep=0.5, suffix=" kg")

        # Set initial values from config
        self.spin_tl.setValue(self.thresholds["top_left"])
        self.spin_bl.setValue(self.thresholds["bottom_left"])
        self.spin_tr.setValue(self.thresholds["top_right"])
        self.spin_br.setValue(self.thresholds["bottom_right"])

        # Connect signals
        self.spin_tl.valueChanged.connect(lambda v: self.on_threshold_changed("top_left", v))
        self.spin_bl.valueChanged.connect(lambda v: self.on_threshold_changed("bottom_left", v))
        self.spin_tr.valueChanged.connect(lambda v: self.on_threshold_changed("top_right", v))
        self.spin_br.valueChanged.connect(lambda v: self.on_threshold_changed("bottom_right", v))

        # Add to layout
        threshold_layout.addWidget(QLabel("A (Top-Left):"), 0, 0)
        threshold_layout.addWidget(self.spin_tl, 0, 1)
        threshold_layout.addWidget(QLabel("B (Bottom-Left):"), 1, 0)
        threshold_layout.addWidget(self.spin_bl, 1, 1)
        threshold_layout.addWidget(QLabel("X (Top-Right):"), 0, 2)
        threshold_layout.addWidget(self.spin_tr, 0, 3)
        threshold_layout.addWidget(QLabel("Y (Bottom-Right):"), 1, 2)
        threshold_layout.addWidget(self.spin_br, 1, 3)

        # --- Tare Button ---
        self.tare_button = QPushButton("Tare (Zero)")
        self.tare_button.setFont(QFont("Helvetica", 12, QFont.Weight.Bold))
        self.tare_button.setEnabled(False)
        self.tare_button.setMinimumHeight(40)
        
        # --- Status Bar ---
        self.status_label = QLabel("Initializing...")
        self.status_label.setFont(QFont("Helvetica", 10))
        self.status_label.setStyleSheet("border-top: 1px solid #CCC; padding: 5px;")
        
        # --- Add widgets to main layout ---
        main_layout.addWidget(total_weight_header)
        main_layout.addWidget(self.total_weight_label)
        main_layout.addWidget(quad_frame)
        main_layout.addSpacing(10)
        main_layout.addWidget(com_header)
        main_layout.addLayout(button_layout) # Add buttons
        main_layout.addLayout(com_widget_layout) # Add CoM graph
        main_layout.addSpacing(10)
        main_layout.addWidget(QLabel("Button Thresholds:"))
        main_layout.addWidget(threshold_frame) # Add threshold controls
        main_layout.addStretch()
        main_layout.addWidget(self.tare_button)
        main_layout.addWidget(self.status_label)

    def init_board(self):
        """Create the thread and the board worker object."""
        self.processing_thread = QThread()
        self.board = WiiBalanceBoard(self.config)
        
        self.board.moveToThread(self.processing_thread)
        
        self.board.data_received.connect(self.update_gui)
        self.board.status_update.connect(self.set_status)
        self.board.error_occurred.connect(self.handle_error)
        
        self.board.ready_to_tare.connect(lambda: self.tare_button.setEnabled(True))
        self.board.tare_complete.connect(self.on_tare_complete)
        
        self.processing_thread.started.connect(self.board.start_processing_loop)
        self.processing_thread.finished.connect(self.processing_thread.deleteLater)
        self.board.finished.connect(self.processing_thread.quit)
        
        self.tare_button.clicked.connect(self.on_tare_click)
        
        self.processing_thread.start()

    # --- GUI Slots ---
    
    def on_threshold_changed(self, key, value):
        """Slot to update the internal threshold when a spinner is changed."""
        self.thresholds[key] = value

    def update_gui(self, data):
        """Slot to update all GUI elements with new data."""
        quads = data['quadrants_kg']
        
        self.total_weight_label.setText(f"{data['total_kg']:.2f} kg")
        self.tr_label.setText(f"TR: {quads['top_right']:.2f} kg")
        self.tl_label.setText(f"TL: {quads['top_left']:.2f} kg")
        self.br_label.setText(f"BR: {quads['bottom_right']:.2f} kg")
        self.bl_label.setText(f"BL: {quads['bottom_left']:.2f} kg")
        
        x, y = data['center_of_mass']
        self.com_widget.update_dot(x, y, quads)
        
        # Update button active states
        self.button_a.set_active(quads['top_left'] > self.thresholds['top_left'])
        self.button_b.set_active(quads['bottom_left'] > self.thresholds['bottom_left'])
        self.button_x.set_active(quads['top_right'] > self.thresholds['top_right'])
        self.button_y.set_active(quads['bottom_right'] > self.thresholds['bottom_right'])

    def set_status(self, text):
        """Slot to update the status bar."""
        self.status_label.setText(text)

    def handle_error(self, text):
        """Slot to show an error. Disables tare button."""
        self.set_status(text)
        self.tare_button.setEnabled(False)

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

    def closeEvent(self, event):
        """Overrides the window close event to safely shut down the thread."""
        print("Closing application...")
        if self.processing_thread.isRunning():
            self.board.stop_processing()
            self.processing_thread.quit()
            self.processing_thread.wait(3000)
        event.accept()

def load_config():
    """Loads the config.json file."""
    try:
        with open("config.json", "r") as f:
            return json.load(f)
    except FileNotFoundError:
        print("config.json not found, using defaults.")
        # Create a more complete default config
        return {
            "tare_duration_sec": 3.0,
            "polling_rate_hz": 30,
            "averaging_samples": 5,
            "dead_zone_kg": 0.2,
            "auto_tare_drift_multiplier": 2.0,
            "auto_tare_drift_sec": 5.0,
            "button_thresholds_kg": {
                "top_left": 10.0, "bottom_left": 10.0,
                "top_right": 10.0, "bottom_right": 10.0
            },
            "com_target_box": {
                "top": 0.5, "bottom": -0.5, "left": -0.5, "right": 0.5
            }
        }
    except Exception as e:
        print(f"Error loading config: {e}")
        return {}

if __name__ == "__main__":
    config = load_config()
    
    app = QApplication(sys.argv)
    window = BalanceBoardApp(config)
    window.show()
    sys.exit(app.exec())