import hid
import time
import struct
from PyQt6.QtCore import QObject, pyqtSignal, QThread
from collections import deque # Import deque for efficient rolling average

# --- Constants ---
NINTENDO_VID = 0x057e
WIIMOTE_PID = 0x0306
READ_CALIBRATION_CMD = [0x17, 0x04, 0xA4, 0x00, 0x20, 0x00, 0x20]
SET_DATA_MODE_REPORT = [0x12, 0x00, 0x32]
SET_LED_REPORT = [0x11, 0x00]

def _unpack_s16(byte1, byte2):
    return struct.unpack('>h', bytes([byte1, byte2]))[0]

class WiiBalanceBoard(QObject):
    """
    API for the Wii Balance Board, refactored as a QObject to run in a QThread
    and emit signals for data, status, and errors.
    """
    
    # --- Signals ---
    # Emits processed weight data
    data_received = pyqtSignal(dict) 
    # Emits status messages for the GUI
    status_update = pyqtSignal(str)
    # Emits when the board is connected and calibrated, ready for tare
    ready_to_tare = pyqtSignal()
    # Emits when the tare process is complete
    tare_complete = pyqtSignal(bool)
    # Emits critical errors
    error_occurred = pyqtSignal(str)
    # Signal emitted when the processing loop is truly finished
    finished = pyqtSignal()

    def __init__(self, config):
        super().__init__()
        self.device = None
        self.calibration = []
        self.zero_point = []
        self.running = True
        self.is_tared = False
        
        # Load settings from config
        self.READ_TIMEOUT_MS = 20
        self.TARE_DURATION = config.get("tare_duration_sec", 3.0)
        self.averaging_samples = config.get("averaging_samples", 5)
        
        # --- MODIFIED: Load new auto-tare and dead zone settings ---
        self.dead_zone_kg = config.get("dead_zone_kg", 0.2)
        self.auto_tare_drift_multiplier = config.get("auto_tare_drift_multiplier", 2.0)
        self.auto_tare_drift_sec = config.get("auto_tare_drift_sec", 5.0)
        
        # --- MODIFIED: Timer for auto-tare (renamed for clarity) ---
        self.drift_timer_start = None # Timestamp of when weight first entered the drift range
        
        # --- NEW: Timer for auto-tare check frequency ---
        self.last_auto_tare_check = time.time()
        
        # --- For smoothing ---
        self.tr_samples = deque(maxlen=self.averaging_samples)
        self.br_samples = deque(maxlen=self.averaging_samples)
        self.tl_samples = deque(maxlen=self.averaging_samples)
        self.bl_samples = deque(maxlen=self.averaging_samples)

    def _connect(self):
        """Attempts to connect to the Balance Board."""
        try:
            self.device = hid.device()
            self.device.open(NINTENDO_VID, WIIMOTE_PID)
            self.device.set_nonblocking(1)
            return True
        except (IOError, hid.HIDException, Exception) as e:
            self.status_update.emit(f"Connection failed: {e}")
            return False

    def _set_led(self, status=True):
        """Sets the board's blue 'Player 1' LED on or off."""
        if not self.device: return False
        try:
            payload = 0x10 if status else 0x00
            self.device.write([0x11, payload])
            return True
        except Exception as e:
            self.status_update.emit(f"Warning: Could not set LED. {e}")
            return False

    def _read_calibration(self):
        """Reads and parses the 32-byte factory calibration data."""
        if not self.device: return False
        try:
            self.device.write(READ_CALIBRATION_CMD)
            data_packets = {}
            start_time = time.time()
            
            while len(data_packets) < 2 and (time.time() - start_time) < 5.0:
                data = self.device.read(64, timeout_ms=self.READ_TIMEOUT_MS) 
                if not data or data[0] != 0x21:
                    continue
                
                error_code = data[3] & 0x0F
                if error_code != 0: return False
                
                address = (data[4] << 8) | data[5]
                if address == 0x0020:
                    data_packets[0] = data[6:22]
                elif address == 0x0030:
                    data_packets[1] = data[6:22]
            
            if len(data_packets) != 2: return False

            full_data = data_packets[0] + data_packets[1]
            self._parse_calibration(full_data)
            return True
        except Exception as e:
            self.status_update.emit(f"Calibration read failed: {e}")
            return False

    def _parse_calibration(self, data):
        """Parses the 32-byte data into 3 calibration sets."""
        cal_0kg = [
            _unpack_s16(data[4], data[5]), _unpack_s16(data[6], data[7]),
            _unpack_s16(data[8], data[9]), _unpack_s16(data[10], data[11])
        ]
        cal_17kg = [
            _unpack_s16(data[12], data[13]), _unpack_s16(data[14], data[15]),
            _unpack_s16(data[16], data[17]), _unpack_s16(data[18], data[19])
        ]
        cal_34kg = [
            _unpack_s16(data[20], data[21]), _unpack_s16(data[22], data[23]),
            _unpack_s16(data[24], data[25]), _unpack_s16(data[26], data[27])
        ]
        self.calibration = [cal_0kg, cal_17kg, cal_34kg]

    def _set_data_mode(self):
        """Tells the board to start streaming sensor data."""
        if not self.device: return False
        try:
            self.device.write(SET_DATA_MODE_REPORT)
            return True
        except Exception:
            return False

    def _parse_sensor_data(self, data):
        """Parses a 0x32 report and returns 4 raw sensor values."""
        if data[0] != 0x32:
            return None
        
        top_right = _unpack_s16(data[3], data[4])
        bottom_right = _unpack_s16(data[5], data[6])
        top_left = _unpack_s16(data[7], data[8])
        bottom_left = _unpack_s16(data[9], data[10])
        
        return [top_right, bottom_right, top_left, bottom_left]

    def _calculate_weights(self, raw_values):
        """Interpolates raw sensor values to kg using calibration data."""
        weights_kg = [0.0] * 4
        
        for i in range(4):
            raw_diff = raw_values[i] - self.zero_point[i]
            
            cal_0 = self.calibration[0][i]
            cal_17 = self.calibration[1][i]
            cal_34 = self.calibration[2][i]
            
            delta_17 = cal_17 - cal_0
            delta_34 = cal_34 - cal_0
            
            if delta_17 != 0:
                if raw_diff < delta_17:
                    weights_kg[i] = 17.0 * (raw_diff / delta_17)
                elif (delta_34 - delta_17) != 0:
                    weights_kg[i] = 17.0 + 17.0 * ((raw_diff - delta_17) / (delta_34 - delta_17))
                else:
                    weights_kg[i] = 0
            else:
                 weights_kg[i] = 0

            if weights_kg[i] < 0:
                weights_kg[i] = 0.0
        
        return weights_kg

    def _get_processed_data(self, weights):
        """Calculates Total Weight and CoM from the provided weights."""
        tr, br, tl, bl = weights
        total_kg = sum(weights)
        
        # --- MODIFIED: Use dead_zone_kg from config ---
        if total_kg < self.dead_zone_kg:
            total_kg = 0.0
            tr = br = tl = bl = 0.0
            x_pos, y_pos = 0.0, 0.0
        else:
            x_pos = ((tr + br) - (tl + bl)) / total_kg
            y_pos = ((tr + tl) - (br + bl)) / total_kg
        
        return {
            "total_kg": total_kg,
            "quadrants_kg": {
                "top_right": tr, "bottom_right": br,
                "top_left": tl, "bottom_left": bl,
            },
            "center_of_mass": (x_pos, y_pos)
        }

    # --- Public Slots ---
    
    def _clear_samples(self):
        """Helper to clear sample buffers, e.g., after taring."""
        self.tr_samples.clear()
        self.br_samples.clear()
        self.tl_samples.clear()
        self.bl_samples.clear()

    def perform_tare(self):
        """
        Public slot to be called to perform the "zeroing" (tare) operation.
        Emits tare_complete(bool) signal when done.
        """
        # Reset auto-tare timer whenever a tare starts
        self.drift_timer_start = None 
        
        if not self.device:
            self.tare_complete.emit(False)
            return

        self.is_tared = False
        self._clear_samples() # Clear old samples
        samples = [[], [], [], []]
        
        start_time = time.time()
        while (time.time() - start_time) < self.TARE_DURATION and self.running:
            data = self.device.read(64, timeout_ms=self.READ_TIMEOUT_MS)
            if not data:
                continue
            
            sensor_data = self._parse_sensor_data(data)
            if sensor_data:
                for i in range(4):
                    samples[i].append(sensor_data[i])
        
        if not samples[0]:
            self.is_tared = False
            self.tare_complete.emit(False)
            return

        self.zero_point = [sum(s) / len(s) for s in samples]
        self.is_tared = True
        self.tare_complete.emit(True)

    def start_processing_loop(self):
        """
        The main loop for the thread. Connects, calibrates, and then
        enters the weighing loop, emitting data signals.
        """
        try:
            # --- 1. Connect ---
            self.status_update.emit("Connecting to Wii Balance Board...")
            if not self._connect():
                self.error_occurred.emit("❌ Connection failed. Please restart.")
                return
            
            # --- 2. Set LED ---
            self.status_update.emit("Connected. Setting LED...")
            self._set_led(True)
            
            # --- 3. Calibrate ---
            self.status_update.emit("Reading calibration data...")
            if not self._read_calibration():
                self.error_occurred.emit("❌ Failed to read calibration. Please restart.")
                return

            # --- 4. Set Mode ---
            self.status_update.emit("Setting data mode...")
            if not self._set_data_mode():
                self.error_occurred.emit("❌ Failed to set data mode. Please restart.")
                return
            
            # --- 5. Ready to Tare ---
            self.status_update.emit("Board ready. Click 'Tare (Zero)' to begin.")
            self.ready_to_tare.emit()

            # --- 6. Weighing Loop ---
            while self.running:
                if self.is_tared and self.device:
                    data = self.device.read(64, timeout_ms=self.READ_TIMEOUT_MS)
                    if not data:
                        continue
                    
                    sensor_data = self._parse_sensor_data(data)
                    if sensor_data:
                        # --- Smoothing ---
                        raw_weights_kg = self._calculate_weights(sensor_data)
                        self.tr_samples.append(raw_weights_kg[0])
                        self.br_samples.append(raw_weights_kg[1])
                        self.tl_samples.append(raw_weights_kg[2])
                        self.bl_samples.append(raw_weights_kg[3])
                        
                        averaged_weights = [
                            sum(self.tr_samples) / len(self.tr_samples),
                            sum(self.br_samples) / len(self.br_samples),
                            sum(self.tl_samples) / len(self.tl_samples),
                            sum(self.bl_samples) / len(self.bl_samples)
                        ]
                        
                        processed_data = self._get_processed_data(averaged_weights)
                        self.data_received.emit(processed_data)
                        
                        # --- MODIFIED: New Auto-Tare Logic (with 1-second check) ---
                        
                        current_time = time.time()
                        if (current_time - self.last_auto_tare_check) > 1.0:
                            # Only run this check once per second
                            self.last_auto_tare_check = current_time
                            
                            total_weight = processed_data['total_kg']
                            drift_upper_limit = self.dead_zone_kg * self.auto_tare_drift_multiplier

                            if self.dead_zone_kg < total_weight < drift_upper_limit:
                                # Weight is in the "drift" range (e.g., 0.2kg < weight < 0.4kg)
                                if self.drift_timer_start is None:
                                    # Start the timer
                                    self.drift_timer_start = time.time()
                                else:
                                    # Timer is running, check if it expired
                                    elapsed = time.time() - self.drift_timer_start
                                    if elapsed > self.auto_tare_drift_sec:
                                        self.status_update.emit("Auto-taring to correct drift...")
                                        self.perform_tare() 
                                        # perform_tare() resets the timer
                            else:
                                # Weight is either 0 (good) or high (in use), so reset the timer
                                self.drift_timer_start = None
                else:
                    # Sleep if not tared to prevent busy-looping
                    time.sleep(0.1)

        except Exception as e:
            if self.running:
                self.error_occurred.emit(f"❌ Error: {e}")
        finally:
            if self.device:
                self._set_led(False)
                self.device.close()
            self.status_update.emit("Disconnected.")
            self.finished.emit() # Tell the thread we are done

    def stop_processing(self):
        """Stops the processing loop."""
        self.running = False