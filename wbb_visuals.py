from PyQt6.QtWidgets import QGraphicsView, QGraphicsScene, QGraphicsEllipseItem
from PyQt6.QtCore import Qt, QPointF, QRectF
from PyQt6.QtGui import QFont, QColor, QPen, QBrush, QPainter

# --- STYLESHEETS REMOVED ---
# They are now in the themes/ folder as .json files

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
        
        self.inactive_pressure_brush = QBrush(QColor(0, 0, 255, 120))
        self.inactive_pressure_pen = QPen(QColor(0, 0, 255, 180), 1)
        self.active_pressure_brush = QBrush(QColor(220, 0, 0, 120)) # Red
        self.active_pressure_pen = QPen(QColor(220, 0, 0, 180), 1) # Red

        self.bg_color = QColor(255, 255, 255)
        self.grid_pen = QPen(QColor(230, 230, 230), 1, Qt.PenStyle.SolidLine)
        self.axis_pen = QPen(Qt.GlobalColor.lightGray, 1, Qt.PenStyle.DashLine)
        self.label_font_color = QColor(0, 0, 0)
        self.thresh_pen = QPen(QColor(100, 100, 100), 1, Qt.PenStyle.DashLine)
        
        self.setBackgroundBrush(self.bg_color)
        
        self.grid_lines = []
        self.axis_lines = []
        self.text_items = []
        
        self.grid_pen.setCosmetic(True) # Keep it 1px
        for i in range(-10, 11):
            if i == 0: continue
            coord = i * 10
            self.grid_lines.append(self.scene.addLine(-100, coord, 100, coord, self.grid_pen))
            self.grid_lines.append(self.scene.addLine(coord, -100, coord, 100, self.grid_pen))
            self.grid_lines[-1].setZValue(-10)
            self.grid_lines[-2].setZValue(-10)

        self.axis_lines.append(self.scene.addLine(-100, 0, 100, 0, self.axis_pen))
        self.axis_lines.append(self.scene.addLine(0, -100, 0, 100, self.axis_pen))
        self.axis_lines[0].setZValue(-5)
        self.axis_lines[1].setZValue(-5)
        
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
        
        min_r = self._map_weight_to_radius(0)
        
        self.tl_dot = self.scene.addEllipse(0, 0, min_r * 2, min_r * 2, self.inactive_pressure_pen, self.inactive_pressure_brush)
        self.tl_dot.setPos(-90, -90); self.tl_dot.setZValue(5)
        
        self.tr_dot = self.scene.addEllipse(0, 0, min_r * 2, min_r * 2, self.inactive_pressure_pen, self.inactive_pressure_brush)
        self.tr_dot.setPos(90, -90); self.tr_dot.setZValue(5)
        
        self.bl_dot = self.scene.addEllipse(0, 0, min_r * 2, min_r * 2, self.inactive_pressure_pen, self.inactive_pressure_brush)
        self.bl_dot.setPos(-90, 90); self.bl_dot.setZValue(5)
        
        self.br_dot = self.scene.addEllipse(0, 0, min_r * 2, min_r * 2, self.inactive_pressure_pen, self.inactive_pressure_brush)
        self.br_dot.setPos(90, 90); self.br_dot.setZValue(5)

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

        self.com_dot = QGraphicsEllipseItem(-2, -2, 4, 4)
        self.com_dot.setBrush(QBrush(Qt.GlobalColor.red))
        self.com_dot.setPen(QPen(Qt.GlobalColor.red))
        self.com_dot.setZValue(10)
        self.scene.addItem(self.com_dot)
        
        self.setRenderHint(QPainter.RenderHint.Antialiasing)

    def set_theme(self, is_dark_mode):
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
        self.fitInView(self.scene.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)
        super().resizeEvent(event)

    def update_label(self, key, mapping_text, mode):
        
        def set_label_text(label_item, text, font, center_x, center_y):
            label_item.setFont(font)
            label_item.setPlainText(text)
            rect = label_item.boundingRect()
            label_item.setPos(center_x - rect.width() / 2, center_y - rect.height() / 2)

        text_to_display = ""
        font = QFont("Helvetica", 16, QFont.Weight.Bold)

        if not mapping_text or mapping_text == "None":
            text_to_display = ""
        else:
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
                    font.setPointSize(20)
                    text_to_display = ps_char
                else:
                    font.setFamily("Helvetica")
                    font.setPointSize(10)
                    if "Bumper" in mapping_text: text_to_display = "LB" if "Left" in mapping_text else "RB"
                    elif "Stick" in mapping_text: text_to_display = "L3" if "Left" in mapping_text else "R3"
                    elif "Start" in mapping_text: text_to_display = "Start"
                    elif "Back" in mapping_text: text_to_display = "Back"
                    else: text_to_display = "?"
            else: # mode == "xbox"
                if is_face_button:
                    font.setFamily("Helvetica")
                    font.setPointSize(16)
                    text_to_display = xbox_char
                else:
                    font.setFamily("Helvetica")
                    font.setPointSize(10)
                    if "Bumper" in mapping_text: text_to_display = "LB" if "Left" in mapping_text else "RB"
                    elif "Stick" in mapping_text: text_to_display = "L3" if "Left" in mapping_text else "R3"
                    elif "Start" in mapping_text: text_to_display = "Start"
                    elif "Back" in mapping_text: text_to_display = "Back"
                    else: text_to_display = "?"
        
        if key == "top_left":
            set_label_text(self.tl_label, text_to_display, font, -90, -90)
        elif key == "top_right":
            set_label_text(self.tr_label, text_to_display, font, 90, -90)
        elif key == "bottom_left":
            set_label_text(self.bl_label, text_to_display, font, -90, 90)
        elif key == "bottom_right":
            set_label_text(self.br_label, text_to_display, font, 90, 90)

    def update_threshold_indicators(self, thresholds_dict):
        tl_r = self._map_weight_to_radius(thresholds_dict.get('top_left', 0))
        tr_r = self._map_weight_to_radius(thresholds_dict.get('top_right', 0))
        bl_r = self._map_weight_to_radius(thresholds_dict.get('bottom_left', 0))
        br_r = self._map_weight_to_radius(thresholds_dict.get('bottom_right', 0))
        
        self.tl_thresh.setRect(-tl_r, -tl_r, tl_r * 2, tl_r * 2)
        self.tr_thresh.setRect(-tr_r, -tr_r, tr_r * 2, tr_r * 2)
        self.bl_thresh.setRect(-bl_r, -bl_r, bl_r * 2, bl_r * 2)
        self.br_thresh.setRect(-br_r, -br_r, br_r * 2, br_r * 2)

    def update_dot(self, x, y, quadrants, press_states):
        canvas_x = x * 90 
        canvas_y = y * -90
        self.com_dot.setPos(canvas_x, canvas_y)
        
        tl_r = self._map_weight_to_radius(quadrants['top_left'])
        tr_r = self._map_weight_to_radius(quadrants['top_right'])
        bl_r = self._map_weight_to_radius(quadrants['bottom_left'])
        br_r = self._map_weight_to_radius(quadrants['bottom_right'])
        
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

        self.tl_dot.setRect(-tl_r, -tl_r, tl_r * 2, tl_r * 2)
        self.tr_dot.setRect(-tr_r, -tr_r, tr_r * 2, tr_r * 2)
        self.bl_dot.setRect(-bl_r, -bl_r, bl_r * 2, bl_r * 2)
        self.br_dot.setRect(-br_r, -br_r, br_r * 2, br_r * 2)