import sys
import json
import vgamepad as vg
import glob
import os
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QFrame, QDoubleSpinBox, QGridLayout, QComboBox, QScrollArea
)
from PyQt6.QtCore import Qt, QThread
from PyQt6.QtGui import QFont
from WiiBalanceBoard_qt import WiiBalanceBoard # Import the Qt-enabled API
from wbb_visuals import CoMWidget # Stylesheets are removed from here

# --- Folder Constants ---
PROFILES_DIR = "profiles"
THEMES_DIR = "themes"

class BalanceBoardApp(QWidget):
    
    # --- Data for Mappings ---
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
        "None": None
    }
    
    VGAMEPAD_COMBO_MAP = {
        "Left Stick Up": "LS_UP", "Left Stick Down": "LS_DOWN",
        "Left Stick Left": "LS_LEFT", "Left Stick Right": "LS_RIGHT",
        "Left Stick Up-Left": "LS_UP_LEFT", "Left Stick Up-Right": "LS_UP_RIGHT",
        "Left Stick Down-Left": "LS_DOWN_LEFT", "Left Stick Down-Right": "LS_DOWN_RIGHT",
        "D-Pad Up": "DPAD_UP", "D-Pad Down": "DPAD_DOWN",
        "D-Pad Left": "DPAD_LEFT", "D-Pad Right": "DPAD_RIGHT",
        "None": None
    }
    
    ALL_DPAD_BUTTONS = {
        "DPAD_UP", "DPAD_DOWN", "DPAD_LEFT", "DPAD_RIGHT"
    }

    # --- Data for Loops ---
    QUADRANT_KEYS = ("top_left", "bottom_left", "top_right", "bottom_right")
    
    COMBO_MAPPING_KEYS = (
        "top_left_top_right", "bottom_left_bottom_right", 
        "top_left_bottom_left", "top_right_bottom_right",
        "top_left_bottom_right", "top_right_bottom_left"
    )

    COMBO_DEFINITIONS = [
        ({"top_left", "top_right"}, "top_left_top_right"),
        ({"bottom_left", "bottom_right"}, "bottom_left_bottom_right"),
        ({"top_left", "bottom_left"}, "top_left_bottom_left"),
        ({"top_right", "bottom_right"}, "top_right_bottom_right"),
        ({"top_left", "bottom_right"}, "top_left_bottom_right"),
        ({"top_right", "bottom_left"}, "top_right_bottom_left"),
    ]

    COMBO_ACTIONS = {
        "LS_UP": (0, 32767, None),
        "LS_DOWN": (0, -32767, None),
        "LS_LEFT": (-32767, 0, None),
        "LS_RIGHT": (32767, 0, None),
        "LS_UP_LEFT": (-32767, 32767, None),
        "LS_UP_RIGHT": (32767, 32767, None),
        "LS_DOWN_LEFT": (-32767, -32767, None),
        "LS_DOWN_RIGHT": (32767, -32767, None),
        "DPAD_UP": (0, 0, "DPAD_UP"),
        "DPAD_DOWN": (0, 0, "DPAD_DOWN"),
        "DPAD_LEFT": (0, 0, "DPAD_LEFT"),
        "DPAD_RIGHT": (0, 0, "DPAD_RIGHT"),
    }
    
    def __init__(self):
        super().__init__()
        self.config = {}
        self.thresholds = {}
        self.button_mappings = {}
        self.combination_mappings = {}
        
        self.profile_files = []
        self.current_profile_file = ""
        
        self.themes = {} 
        self.current_theme_name = "light"
        
        self.REVERSE_VGAMEPAD_MAP = {v: k for k, v in self.VGAMEPAD_BUTTON_MAP.items()}
        self.REVERSE_VGAMEPAD_COMBO_MAP = {v: k for k, v in self.VGAMEPAD_COMBO_MAP.items()}
        
        self.button_view_mode = "xbox"
        
        self.processing_thread = None
        self.board = None
        
        self.ensure_folders_exist() # Create profiles/ and themes/
        
        self.init_ui()
        
        self.scan_and_load_themes()
        self.scan_and_load_profiles() # Loads config, which sets theme
        
        self.update_all_com_labels()
        self._create_and_start_thread()
        
        try:
            self.gamepad = vg.VX360Gamepad()
            print("Virtual Xbox 360 gamepad initialized.")
        except Exception as e:
            print(f"Could not initialize virtual gamepad: {e}")
            print("Please ensure ViGEmBus driver is installed.")
            self.gamepad = None

    def init_ui(self):
        self.setWindowTitle("Wii Balance Board Monitor (PyQt6)")
        self.setGeometry(100, 100, 420, 900) 
        
        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.setSpacing(0)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        scroll_widget = QWidget()
        main_layout = QVBoxLayout(scroll_widget)
        main_layout.setContentsMargins(15, 15, 15, 15)
        main_layout.setSpacing(10)
        
        # --- Profile (Config) Selection ---
        profile_frame = QFrame()
        profile_frame.setFrameShape(QFrame.Shape.StyledPanel)
        profile_layout = QHBoxLayout(profile_frame)
        profile_layout.addWidget(QLabel("Profile:"))
        self.profile_combo = QComboBox()
        profile_layout.addWidget(self.profile_combo, 1)
        
        # --- Theme Selection ---
        theme_frame = QFrame()
        theme_frame.setFrameShape(QFrame.Shape.StyledPanel)
        theme_layout = QHBoxLayout(theme_frame)
        theme_layout.addWidget(QLabel("Theme:"))
        self.theme_combo = QComboBox()
        theme_layout.addWidget(self.theme_combo, 1)

        
        total_weight_header = QLabel("Total Weight")
        total_weight_header.setFont(QFont("Helvetica", 15, QFont.Weight.Bold))
        total_weight_header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        self.total_weight_label = QLabel("--.- kg")
        self.total_weight_label.setObjectName("total_weight_label") # Set object name for QSS
        self.total_weight_label.setFont(QFont("Helvetica", 26, QFont.Weight.Bold))
        self.total_weight_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Quadrant Labels
        quad_frame = QFrame()
        quad_layout = QGridLayout(quad_frame)
        self.tl_label = QLabel("TL: --.- kg")
        self.tr_label = QLabel("TR: --.- kg")
        self.bl_label = QLabel("BL: --.- kg")
        self.br_label = QLabel("BR: --.- kg")
        
        quad_layout.addWidget(self.tl_label, 0, 0)
        quad_layout.addWidget(self.tr_label, 0, 1)
        quad_layout.addWidget(self.bl_label, 1, 0)
        quad_layout.addWidget(self.br_label, 1, 1)
        
        for label in [self.tl_label, self.tr_label, self.bl_label, self.br_label]:
            label.setFont(QFont("Helvetica", 11))
        
        self.com_widget = CoMWidget()
        com_widget_layout = QHBoxLayout()
        com_widget_layout.addStretch()
        com_widget_layout.addWidget(self.com_widget)
        com_widget_layout.addStretch()

        self.toggle_view_button = QPushButton("Show PlayStation Icons (△, ○, ✕, □)")
        self.toggle_view_button.setFont(QFont("Helvetica", 10))
        
        # --- Threshold Frame ---
        threshold_frame = QFrame()
        threshold_frame.setFrameShape(QFrame.Shape.StyledPanel)
        threshold_layout = QGridLayout(threshold_frame)
        threshold_layout.setSpacing(8)
        threshold_layout.setContentsMargins(8, 8, 8, 8)
        threshold_layout.addWidget(QLabel("Button Thresholds:"), 0, 0, 1, 4)

        self.spin_tl = QDoubleSpinBox(decimals=1, minimum=0.1, maximum=100.0, singleStep=0.5, suffix=" kg")
        self.spin_bl = QDoubleSpinBox(decimals=1, minimum=0.1, maximum=100.0, singleStep=0.5, suffix=" kg")
        self.spin_tr = QDoubleSpinBox(decimals=1, minimum=0.1, maximum=100.0, singleStep=0.5, suffix=" kg")
        self.spin_br = QDoubleSpinBox(decimals=1, minimum=0.1, maximum=100.0, singleStep=0.5, suffix=" kg")

        self.spin_widgets = {
            "top_left": self.spin_tl, "bottom_left": self.spin_bl,
            "top_right": self.spin_tr, "bottom_right": self.spin_br
        }

        def create_label(text):
            lbl = QLabel(text)
            lbl.setFont(QFont("Helvetica", 10))
            return lbl

        threshold_layout.addWidget(create_label("Top-Left:"), 1, 0)
        threshold_layout.addWidget(self.spin_tl, 1, 1)
        threshold_layout.addWidget(create_label("Top-Right:"), 1, 2)
        threshold_layout.addWidget(self.spin_tr, 1, 3)
        threshold_layout.addWidget(create_label("Bottom-Left:"), 2, 0)
        threshold_layout.addWidget(self.spin_bl, 2, 1)
        threshold_layout.addWidget(create_label("Bottom-Right:"), 2, 2)
        threshold_layout.addWidget(self.spin_br, 2, 3)

        for key, spin_box in self.spin_widgets.items():
            spin_box.valueChanged.connect(lambda v, k=key: self.on_threshold_changed(k, v))

        # --- Button Mapping Frame ---
        mapping_frame = QFrame()
        mapping_frame.setFrameShape(QFrame.Shape.StyledPanel)
        mapping_layout = QGridLayout(mapping_frame)
        mapping_layout.setSpacing(8)
        mapping_layout.setContentsMargins(8, 8, 8, 8)
        mapping_layout.addWidget(QLabel("Button Mappings:"), 0, 0, 1, 4)
        
        self.combo_tl = QComboBox()
        self.combo_tr = QComboBox()
        self.combo_bl = QComboBox()
        self.combo_br = QComboBox()
        
        self.mapping_combos = {
            "top_left": self.combo_tl, "top_right": self.combo_tr,
            "bottom_left": self.combo_bl, "bottom_right": self.combo_br
        }
        
        for key, combo in self.mapping_combos.items():
            combo.addItems(self.VGAMEPAD_BUTTON_MAP.keys())
            combo.currentTextChanged.connect(lambda text, k=key: self.on_mapping_changed(k, text))

        mapping_layout.addWidget(create_label("Top-Left:"), 1, 0)
        mapping_layout.addWidget(self.combo_tl, 1, 1)
        mapping_layout.addWidget(create_label("Top-Right:"), 1, 2)
        mapping_layout.addWidget(self.combo_tr, 1, 3)
        mapping_layout.addWidget(create_label("Bottom-Left:"), 2, 0)
        mapping_layout.addWidget(self.combo_bl, 2, 1)
        mapping_layout.addWidget(create_label("Bottom-Right:"), 2, 2)
        mapping_layout.addWidget(self.combo_br, 2, 3)

        # --- Combination Mapping Frame ---
        combo_mapping_frame = QFrame()
        combo_mapping_frame.setFrameShape(QFrame.Shape.StyledPanel)
        combo_mapping_layout = QGridLayout(combo_mapping_frame)
        combo_mapping_layout.setSpacing(8)
        combo_mapping_layout.setContentsMargins(8, 8, 8, 8)
        combo_mapping_layout.addWidget(QLabel("Combination Mappings:"), 0, 0, 1, 4)

        self.combo_tl_tr = QComboBox()
        self.combo_bl_br = QComboBox()
        self.combo_tl_bl = QComboBox()
        self.combo_tr_br = QComboBox()
        self.combo_tl_br = QComboBox()
        self.combo_tr_bl = QComboBox()
        
        self.combo_combos_widgets = {
            "top_left_top_right": self.combo_tl_tr, "bottom_left_bottom_right": self.combo_bl_br,
            "top_left_bottom_left": self.combo_tl_bl, "top_right_bottom_right": self.combo_tr_br,
            "top_left_bottom_right": self.combo_tl_br, "top_right_bottom_left": self.combo_tr_bl
        }

        for key, combo in self.combo_combos_widgets.items():
            combo.addItems(self.VGAMEPAD_COMBO_MAP.keys())
            combo.currentTextChanged.connect(lambda text, k=key: self.on_combo_mapping_changed(k, text))

        combo_mapping_layout.addWidget(create_label("Top-Left + Top-Right:"), 1, 0)
        combo_mapping_layout.addWidget(self.combo_tl_tr, 1, 1)
        combo_mapping_layout.addWidget(create_label("Bottom-Left + Bottom-Right:"), 2, 0)
        combo_mapping_layout.addWidget(self.combo_bl_br, 2, 1)
        combo_mapping_layout.addWidget(create_label("Top-Left + Bottom-Left:"), 3, 0)
        combo_mapping_layout.addWidget(self.combo_tl_bl, 3, 1)
        combo_mapping_layout.addWidget(create_label("Top-Right + Bottom-Right:"), 4, 0)
        combo_mapping_layout.addWidget(self.combo_tr_br, 4, 1)
        combo_mapping_layout.addWidget(create_label("Top-Left + Bottom-Right:"), 5, 0)
        combo_mapping_layout.addWidget(self.combo_tl_br, 5, 1)
        combo_mapping_layout.addWidget(create_label("Top-Right + Bottom-Left:"), 6, 0)
        combo_mapping_layout.addWidget(self.combo_tr_bl, 6, 1)

        # --- Main Buttons ---
        self.tare_button = QPushButton("Tare (Zero)")
        self.save_button = QPushButton("Save Profile")
        self.rescan_button = QPushButton("Rescan for Board")
        
        for btn in [self.tare_button, self.save_button, self.rescan_button]:
            btn.setFont(QFont("Helvetica", 11, QFont.Weight.Bold))
            btn.setMinimumHeight(35)
            
        self.tare_button.setEnabled(False)

        button_layout_1 = QHBoxLayout()
        button_layout_1.addWidget(self.tare_button)
        button_layout_1.addWidget(self.save_button)
        
        button_layout_2 = QHBoxLayout()
        button_layout_2.addWidget(self.rescan_button)
        
        self.status_label = QLabel("Initializing...")
        self.status_label.setObjectName("status_label") # Set object name for QSS
        self.status_label.setFont(QFont("Helvetica", 10))
        self.status_label.setStyleSheet("border-top: 1px solid #CCC; padding: 5px;")
        
        # --- Add Widgets to Layout ---
        main_layout.addWidget(profile_frame) 
        main_layout.addWidget(theme_frame)   
        main_layout.addWidget(total_weight_header)
        main_layout.addWidget(self.total_weight_label)
        main_layout.addWidget(quad_frame)
        main_layout.addSpacing(10)
        main_layout.addLayout(com_widget_layout)
        main_layout.addWidget(self.toggle_view_button)
        main_layout.addSpacing(10)
        main_layout.addWidget(threshold_frame)
        main_layout.addWidget(mapping_frame)
        main_layout.addWidget(combo_mapping_frame)
        main_layout.addStretch()
        main_layout.addLayout(button_layout_1)
        main_layout.addLayout(button_layout_2)
        main_layout.addWidget(self.status_label)

        scroll_area.setWidget(scroll_widget)
        outer_layout.addWidget(scroll_area)
        
        # --- Connections ---
        self.tare_button.clicked.connect(self.on_tare_click)
        self.save_button.clicked.connect(self.save_profile)
        self.rescan_button.clicked.connect(self.on_rescan_click)
        self.toggle_view_button.clicked.connect(self.on_toggle_view)
        
        self.profile_combo.currentTextChanged.connect(self.on_profile_selected)
        self.theme_combo.currentTextChanged.connect(self.on_theme_selected)
        

    def _create_and_start_thread(self):
        if self.processing_thread:
             self.processing_thread.finished.disconnect(self._create_and_start_thread)

        self.processing_thread = QThread()
        # Pass the whole config dict to the board
        self.board = WiiBalanceBoard(self.config)
        
        self.board.moveToThread(self.processing_thread)
        
        self.board.data_received.connect(self.update_gui)
        self.board.status_update.connect(self.set_status)
        self.board.error_occurred.connect(self.handle_error)
        
        self.board.ready_to_tare.connect(lambda: self.tare_button.setEnabled(True))
        self.board.ready_to_tare.connect(lambda: self.rescan_button.setEnabled(True))
        self.board.tare_complete.connect(self.on_tare_complete)
        
        self.processing_thread.started.connect(self.board.start_processing_loop)
        self.board.finished.connect(self.processing_thread.quit)
        self.board.finished.connect(self.board.deleteLater)
        self.processing_thread.finished.connect(self.processing_thread.deleteLater)
        
        self.processing_thread.start()
        self.rescan_button.setEnabled(True)

    
    def _create_file_if_not_exists(self, path, data, is_json=True):
        """Helper to create a default file."""
        if not os.path.exists(path):
            print(f"Creating default file: {path}")
            try:
                with open(path, "w") as f:
                    if is_json:
                        json.dump(data, f, indent=4)
                    else:
                        f.write(data)
            except Exception as e:
                print(f"Failed to write default file {path}: {e}")

    def ensure_folders_exist(self):
        """Creates profiles and themes folders and populates them if empty."""
        os.makedirs(PROFILES_DIR, exist_ok=True)
        os.makedirs(THEMES_DIR, exist_ok=True)
        
        # Create default profile
        default_profile_path = os.path.join(PROFILES_DIR, "default_config.json")
        self._create_file_if_not_exists(default_profile_path, self._get_built_in_defaults())

        # Create default light theme
        light_theme_path = os.path.join(THEMES_DIR, "light.json")
        light_theme = {
            "base": "light",
            "stylesheet": "QWidget {\n    background-color: #f0f0f0;\n    color: #000000;\n}\nQPushButton {\n    background-color: #e1e1e1;\n    border: 1px solid #adadad;\n    padding: 5px;\n    border-radius: 3px;\n}\nQPushButton:hover {\n    background-color: #cacaca;\n}\nQPushButton:pressed {\n    background-color: #b0b0b0;\n}\nQPushButton:disabled {\n    background-color: #dcdcdc;\n    color: #888888;\n}\nQFrame {\n    border: 1px solid #cccccc;\n    border-radius: 4px;\n}\nQComboBox {\n    background-color: #ffffff;\n    border: 1px solid #adadad;\n    border-radius: 3px;\n    padding: 3px;\n}\nQComboBox::drop-down {\n    border-left: 1px solid #adadad;\n}\nQComboBox QAbstractItemView {\n    background-color: #ffffff;\n    border: 1px solid #adadad;\n    selection-background-color: #d3d3d3;\n}\nQDoubleSpinBox {\n    background-color: #ffffff;\n    border: 1px solid #adadad;\n    border-radius: 3px;\n    padding: 3px;\n}\nQLabel {\n    background-color: transparent;\n    border: none;\n}\n#total_weight_label {\n    color: #007ACC;\n}\n#status_label {\n    color: #000000;\n    border-top: 1px solid #CCC;\n}\nQScrollArea {\n    border: none;\n}\nQScrollBar:vertical {\n    background: #f0f0f0;\n    width: 12px;\n    margin: 0px;\n    border-radius: 6px;\n}\nQScrollBar::handle:vertical {\n    background: #c0c0c0;\n    min-height: 20px;\n    border-radius: 6px;\n}\nQScrollBar::handle:vertical:hover {\n    background: #a0a0a0;\n}\nQScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {\n    background: none;\n    height: 0px;\n    subcontrol-position: top;\n    subcontrol-origin: margin;\n}\n"
        }
        self._create_file_if_not_exists(light_theme_path, light_theme)
                
        # Create default dark theme
        dark_theme_path = os.path.join(THEMES_DIR, "dark.json")
        dark_theme = {
            "base": "dark",
            "stylesheet": "QWidget {\n    background-color: #282a36;\n    color: #f8f8f2;\n}\nQPushButton {\n    background-color: #44475a;\n    border: 1px solid #6272a4;\n    padding: 5px;\n    border-radius: 3px;\n}\nQPushButton:hover {\n    background-color: #4f5368;\n}\nQPushButton:pressed {\n    background-color: #3b3e51;\n}\nQPushButton:disabled {\n    background-color: #3b3e51;\n    color: #6272a4;\n}\nQFrame {\n    border: 1px solid #44475a;\n    border-radius: 4px;\n}\nQComboBox {\n    background-color: #44475a;\n    border: 1px solid #6272a4;\n    border-radius: 3px;\n    padding: 3px;\n}\nQComboBox::drop-down {\n    border-left: 1px solid #6272a4;\n}\nQComboBox QAbstractItemView {\n    background-color: #44475a;\n    border: 1px solid #6272a4;\n    selection-background-color: #6272a4;\n}\nQDoubleSpinBox {\n    background-color: #44475a;\n    border: 1px solid #6272a4;\n    border-radius: 3px;\n    padding: 3px;\n}\nQLabel {\n    background-color: transparent;\n    border: none;\n}\n#total_weight_label {\n    color: #50fa7b;\n}\n#status_label {\n    color: #bd93f9;\n    border-top: 1px solid #44475a;\n}\nQScrollArea {\n    border: none;\n}\nQScrollBar:vertical {\n    background: #282a36;\n    width: 12px;\n    margin: 0px;\n    border-radius: 6px;\n}\nQScrollBar::handle:vertical {\n    background: #44475a;\n    min-height: 20px;\n    border-radius: 6px;\n}\nQScrollBar::handle:vertical:hover {\n    background: #6272a4;\n}\nQScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {\n    background: none;\n    height: 0px;\n    subcontrol-position: top;\n    subcontrol-origin: margin;\n}\n"
        }
        self._create_file_if_not_exists(dark_theme_path, dark_theme)

    def scan_and_load_themes(self):
        """Scans the themes/ folder and populates the theme dropdown."""
        self.themes = {}
        theme_files = sorted(glob.glob(os.path.join(THEMES_DIR, "*.json")))
        
        theme_names = []
        for f_path in theme_files:
            theme_name = os.path.basename(f_path).replace(".json", "")
            try:
                with open(f_path, "r") as f:
                    self.themes[theme_name] = json.load(f)
                theme_names.append(theme_name)
            except Exception as e:
                print(f"Failed to load theme {f_path}: {e}")
        
        self.theme_combo.addItems(theme_names)

    def scan_and_load_profiles(self):
        """Scans the profiles/ folder and loads the initial profile."""
        self.profile_files = sorted(glob.glob(os.path.join(PROFILES_DIR, "*.json")))
        
        try:
            self.profile_combo.currentTextChanged.disconnect(self.on_profile_selected)
        except TypeError:
            pass
            
        self.profile_combo.clear()
        
        basenames = [os.path.basename(f) for f in self.profile_files]
        self.profile_combo.addItems(basenames)
        
        user_profile_name = "user_config.json"
        default_profile_name = "default_config.json"
        
        initial_file_name = default_profile_name
        if user_profile_name in basenames:
            initial_file_name = user_profile_name
        elif basenames:
            initial_file_name = basenames[0]
        else:
            self.set_status(f"❌ ERROR: No profiles found in /{PROFILES_DIR}!")
            self.config = self._get_built_in_defaults()
            self.update_ui_from_config()
            return
            
        self.profile_combo.setCurrentText(initial_file_name)
        
        self.current_profile_file = os.path.join(PROFILES_DIR, initial_file_name) 
        self.config = self.load_config_file(self.current_profile_file)
        self.update_ui_from_config()
        
        self.profile_combo.currentTextChanged.connect(self.on_profile_selected)

    def load_config_file(self, full_path):
        """Loads a profile JSON file from its full path."""
        if not os.path.exists(full_path):
            self.set_status(f"❌ ERROR: {full_path} not found! Using built-in defaults.")
            return self._get_built_in_defaults()
            
        try:
            with open(full_path, "r") as f:
                return json.load(f)
        except Exception as e:
            self.set_status(f"❌ Error loading {full_path}: {e}")
            return self._get_built_in_defaults()

    def on_profile_selected(self, filename_basename):
        """Called when user selects a new profile from the dropdown."""
        if not filename_basename:
            return
            
        full_path = os.path.join(PROFILES_DIR, filename_basename)
        print(f"Loading profile: {full_path}")
        self.current_profile_file = full_path
        self.config = self.load_config_file(full_path)
        
        self.update_ui_from_config() 
        self.set_status(f"✅ Loaded {filename_basename}")

    def update_ui_from_config(self):
        """Populates all UI widgets based on the currently loaded self.config."""
        self.thresholds = self.config.get("button_thresholds_kg", {})
        self.button_mappings = self.config.get("button_mappings", {})
        self.combination_mappings = self.config.get("combination_mappings", {})
        
        # --- Theme Handling ---
        theme_name = self.config.get("theme", "light")
        if theme_name not in self.themes:
            print(f"Warning: Theme '{theme_name}' not found. Defaulting to 'light'.")
            theme_name = "light"
            
        self.current_theme_name = theme_name
        
        try:
            self.theme_combo.currentTextChanged.disconnect(self.on_theme_selected)
        except TypeError:
            pass
        self.theme_combo.setCurrentText(theme_name)
        self.theme_combo.currentTextChanged.connect(self.on_theme_selected)
        
        # --- Other UI Elements ---
        for key, spin_box in self.spin_widgets.items():
            spin_box.setValue(self.thresholds.get(key, 10.0))

        for key, combo_box in self.mapping_combos.items():
            combo_box.setCurrentText(self.REVERSE_VGAMEPAD_MAP.get(self.button_mappings.get(key), "None"))

        for key, combo_box in self.combo_combos_widgets.items():
            combo_box.setCurrentText(self.REVERSE_VGAMEPAD_COMBO_MAP.get(self.combination_mappings.get(key), "None"))

        self.apply_theme() # Apply the theme
        self.update_all_com_labels()
        self.com_widget.update_threshold_indicators(self.thresholds)
        
    def _get_built_in_defaults(self):
        """Fallback config if all files are missing/corrupt."""
        print("Using built-in defaults.")
        return {
            "tare_duration_sec": 3.0,
            "polling_rate_hz": 30,
            "averaging_samples": 5,
            "dead_zone_kg": 0.2,
            "theme": "light",
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
            "combination_mappings": {
                "top_left_top_right": "None", "bottom_left_bottom_right": "None",
                "top_left_bottom_left": "None", "top_right_bottom_right": "None",
                "top_left_bottom_right": "None", "top_right_bottom_left": "None"
            }
        }

    
    def on_rescan_click(self):
        self.set_status("Rescanning...")
        self.tare_button.setEnabled(False)
        self.rescan_button.setEnabled(False)
        
        if self.processing_thread and self.processing_thread.isRunning():
            self.processing_thread.finished.connect(self._create_and_start_thread, Qt.ConnectionType.SingleShotConnection)
            self.board.stop_processing()
        else:
            self._create_and_start_thread()

    def on_theme_selected(self, theme_name):
        """Called when user selects a new theme from the dropdown."""
        if not theme_name or theme_name not in self.themes:
            return
            
        self.current_theme_name = theme_name
        self.config["theme"] = theme_name # Save choice to config
        self.apply_theme()

    def apply_theme(self):
        """Applies the stylesheet and updates CoMWidget theme."""
        theme_data = self.themes.get(self.current_theme_name)
        
        if not theme_data:
            print(f"Could not apply theme: {self.current_theme_name} not loaded.")
            return

        stylesheet = theme_data.get("stylesheet", "")
        base_theme = theme_data.get("base", "light")
        
        self.setStyleSheet(stylesheet)
        self.com_widget.set_theme(base_theme == "dark")


    def update_all_com_labels(self):
        for key in self.QUADRANT_KEYS:
            text = self.REVERSE_VGAMEPAD_MAP.get(self.button_mappings.get(key))
            self.com_widget.update_label(key, text, self.button_view_mode)
    
    def on_toggle_view(self):
        if self.button_view_mode == "xbox":
            self.button_view_mode = "ps"
            self.toggle_view_button.setText("Show Xbox Icons (A, B, X, Y)")
        else:
            self.button_view_mode = "xbox"
            self.toggle_view_button.setText("Show PlayStation Icons (△, ○, ✕, □)")
        
        self.update_all_com_labels()

    def on_threshold_changed(self, key, value):
        self.thresholds[key] = value
        self.com_widget.update_threshold_indicators(self.thresholds)

    def on_mapping_changed(self, key, text):
        vgamepad_string = self.VGAMEPAD_BUTTON_MAP.get(text)
        self.button_mappings[key] = vgamepad_string
        print(f"Mapping changed: {key} -> {vgamepad_string}")
        
        self.com_widget.update_label(key, text, self.button_view_mode)

    def on_combo_mapping_changed(self, key, text):
        vgamepad_string = self.VGAMEPAD_COMBO_MAP.get(text)
        self.combination_mappings[key] = vgamepad_string
        print(f"Combination Mapping changed: {key} -> {vgamepad_string}")

    def _apply_combo_mapping(self, mapping_str, x, y, dpad_set):
        """Uses a dispatch dictionary to apply combo actions."""
        action = self.COMBO_ACTIONS.get(mapping_str)
        if action:
            dx, dy, dpad = action
            if dx: x = dx
            if dy: y = dy
            if dpad: dpad_set.add(dpad)
        return x, y, dpad_set

    def _toggle_gamepad_buttons(self, gamepad_func, button_set, enum_base=vg.XUSB_BUTTON, prefix=""):
        """Helper to press or release a set of gamepad buttons."""
        for button_str in button_set:
            if not button_str: continue
            # Handle D-Pad prefixing
            enum_key = f"{prefix}{button_str}" if prefix else button_str
            button_enum = getattr(enum_base, enum_key, None)
            if button_enum:
                gamepad_func(button=button_enum)

    def update_gui(self, data):
        quads = data['quadrants_kg']
        
        self.total_weight_label.setText(f"{data['total_kg']:.2f} kg")
        self.tr_label.setText(f"TR: {quads['top_right']:.2f} kg")
        self.tl_label.setText(f"TL: {quads['top_left']:.2f} kg")
        self.br_label.setText(f"BR: {quads['bottom_right']:.2f} kg")
        self.bl_label.setText(f"BL: {quads['bottom_left']:.2f} kg")
        
        x, y = data['center_of_mass']
        
        press_states = {
            'top_left': quads['top_left'] > self.thresholds.get('top_left', 10.0),
            'top_right': quads['top_right'] > self.thresholds.get('top_right', 10.0),
            'bottom_left': quads['bottom_left'] > self.thresholds.get('bottom_left', 10.0),
            'bottom_right': quads['bottom_right'] > self.thresholds.get('bottom_right', 10.0),
        }
        
        if self.gamepad:
            ls_x, ls_y = 0, 0
            dpad_buttons_to_press = set()
            buttons_to_press_str = set()
            
            pressed_quadrants = {q for q, pressed in press_states.items() if pressed}
            
            # --- Combination Logic (Refactored) ---
            combos_activated = set()
            for quadrants, mapping_key in self.COMBO_DEFINITIONS:
                if quadrants.issubset(pressed_quadrants - combos_activated):
                    mapping = self.combination_mappings.get(mapping_key)
                    if mapping and mapping != "None":
                        ls_x, ls_y, dpad_buttons_to_press = self._apply_combo_mapping(mapping, ls_x, ls_y, dpad_buttons_to_press)
                        combos_activated.update(quadrants)
            
            # --- Individual Button Logic ---
            remaining_pressed = pressed_quadrants - combos_activated
            
            for quad in remaining_pressed:
                mapping = self.button_mappings.get(quad)
                if mapping and mapping != "None":
                    buttons_to_press_str.add(mapping)

            # --- Apply Gamepad State (Refactored) ---
            self.gamepad.left_joystick(x_value=ls_x, y_value=ls_y)
            
            managed_buttons_str = set(self.button_mappings.values())
            buttons_to_release_str = managed_buttons_str - buttons_to_press_str

            # Press/Release main buttons
            self._toggle_gamepad_buttons(self.gamepad.press_button, buttons_to_press_str)
            self._toggle_gamepad_buttons(self.gamepad.release_button, buttons_to_release_str)
            
            # Press/Release D-Pad buttons
            dpad_buttons_to_release = self.ALL_DPAD_BUTTONS - dpad_buttons_to_press
            dpad_prefix = "XUSB_GAMEPAD_"
            self._toggle_gamepad_buttons(self.gamepad.press_button, dpad_buttons_to_press, prefix=dpad_prefix)
            self._toggle_gamepad_buttons(self.gamepad.release_button, dpad_buttons_to_release, prefix=dpad_prefix)

            self.gamepad.update() 

        self.com_widget.update_dot(x, y, quads, press_states)
        
    def set_status(self, text):
        self.status_label.setText(text)

    def handle_error(self, text):
        self.set_status(text)
        self.tare_button.setEnabled(False)
        self.rescan_button.setEnabled(True)

    def on_tare_click(self):
        self.set_status("🔵 Taring... Please step OFF the board.")
        self.tare_button.setEnabled(False)
        if self.board:
            self.board.perform_tare() 

    def on_tare_complete(self, success):
        if success:
            self.set_status("✅ Ready! Please step ON the board.")
        else:
            self.set_status("❌ Tare failed. No data. Try again.")
        self.tare_button.setEnabled(True)

    def save_profile(self):
        """Saves the current settings to the selected profile file."""
        filename_basename = self.profile_combo.currentText()
        if not filename_basename:
            self.set_status("❌ Cannot save: No profile file selected.")
            return
            
        full_path = os.path.join(PROFILES_DIR, filename_basename)

        print(f"Saving profile to {full_path}...")
        
        self.config["button_thresholds_kg"] = self.thresholds
        self.config["button_mappings"] = self.button_mappings
        self.config["combination_mappings"] = self.combination_mappings
        self.config["theme"] = self.current_theme_name # Save the selected theme
        
        try:
            with open(full_path, "w") as f:
                json.dump(self.config, f, indent=4)
            print("Profile saved.")
            self.set_status(f"✅ Profile saved to {filename_basename}")
        except Exception as e:
            print(f"Error saving profile: {e}")
            self.set_status(f"❌ Error saving profile: {e}")

    def closeEvent(self, event):
        print("Closing application...")
        
        if self.processing_thread and self.processing_thread.isRunning():
            self.board.stop_processing()
            self.processing_thread.quit()
            self.processing_thread.wait(3000)
        
        if self.gamepad:
            print("Releasing virtual gamepad...")
            self.gamepad.reset()
            self.gamepad.update()
            del self.gamepad
            
        event.accept()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = BalanceBoardApp()
    window.show()
    sys.exit(app.exec())