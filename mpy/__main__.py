import time

try:
    import ujson as json
except ImportError:
    import json

import audio_service
import micropyxel as pyxel
import mpy_button as touch_events
from maopaoBleApp import BleAppService
from pyxel_prompt_sound import PromptSoundPlayer


APP = None

FPS = 20
SCREEN_W = 32
SCREEN_H = 16

ASSET_PATH = "assets/pixels.png"
CONFIG_PATH = "pomodoro_config.json"
PROMPT_SOUND_VOLUME = 100
PROMPT_SOUND_DEBUG = True
PROMPT_SOUND_PACKETS_PER_UPDATE = 4

BUSY_U = 0
BUSY_V = 0
BUSY_BG_U = 32
BUSY_BG_V = 0
REST_U = 0
REST_V = 32
REST_BG_U = 32
REST_BG_V = 32
BUSY_TO_REST_U = 0
BUSY_TO_REST_V = 16
REST_TO_BUSY_U = 0
REST_TO_BUSY_V = 48
FRAME_W = 32
FRAME_H = 10
BUSY_TO_REST_FRAMES = 5
REST_TO_BUSY_FRAMES = 5
TRANSITION_FRAME_TICKS = 5
TRANSITION_FLASH_FRAME_TICKS = 5
TRANSITION_FLASH_TOTAL_TICKS = FPS * 4

COUNTER_Y = 11
COLKEY = 0
TEXT_COLOR = 7
DIM_TEXT_COLOR = 6
TOUCH_CLICK_EVENTS = ("click", "single", "single_click", "tap", "hit")
TOUCH_DOUBLE_EVENTS = ("double", "double_click", "double click")

STATE_READY = "P1"
STATE_WORK = "P2-W"
STATE_REST = "P2-R"
STATE_DONE = "P3-D"
STATE_STOP = "P3-S"
STATE_TRANSITION = "TRANS"

PROMPT_SOUND_FILES = {
    "focus_start": "focus_start.ogg",
    "break_start": "break_start.ogg",
}

DEFAULT_CONFIG = {
    "focusMin": 2,
    "autoStartNext": False,
    "cycleCount": 1,
    "shortBreakMin": 1,
    "longBreakMin": 2,
    "soundEnabled": True,
    "theme": "pulse",
}

DIGITS = {
    "0": (0b111, 0b101, 0b101, 0b101, 0b111),
    "1": (0b010, 0b110, 0b010, 0b010, 0b111),
    "2": (0b111, 0b001, 0b111, 0b100, 0b111),
    "3": (0b111, 0b001, 0b111, 0b001, 0b111),
    "4": (0b101, 0b101, 0b111, 0b001, 0b001),
    "5": (0b111, 0b100, 0b111, 0b001, 0b111),
    "6": (0b111, 0b100, 0b111, 0b101, 0b111),
    "7": (0b111, 0b001, 0b001, 0b001, 0b001),
    "8": (0b111, 0b101, 0b111, 0b101, 0b111),
    "9": (0b111, 0b101, 0b111, 0b001, 0b111),
}


def clone_config(src):
    dst = {}
    for key in DEFAULT_CONFIG:
        dst[key] = src.get(key, DEFAULT_CONFIG[key])
    return dst


def clamp_int(value, min_value, max_value, default_value):
    try:
        value = int(value)
    except Exception:
        return default_value
    if value < min_value:
        return min_value
    if value > max_value:
        return max_value
    return value


def is_bool(value):
    return value is True or value is False


def load_config():
    try:
        with open(CONFIG_PATH, "r") as fp:
            data = json.loads(fp.read())
        cfg = clone_config(data)
        ok, cfg_or_error = validate_config(cfg)
        if ok:
            return cfg_or_error
    except Exception:
        pass
    return clone_config(DEFAULT_CONFIG)


def save_config(config):
    with open(CONFIG_PATH, "w") as fp:
        fp.write(json.dumps(config))


def validate_config(config):
    if not isinstance(config, dict):
        return False, "config_not_object"

    cfg = clone_config(config)
    for key in ("focusMin", "shortBreakMin", "longBreakMin"):
        try:
            value = int(cfg[key])
        except Exception:
            return False, key
        if value < 1 or value > 60:
            return False, key
        cfg[key] = value

    try:
        cycle_count = int(cfg["cycleCount"])
    except Exception:
        return False, "cycleCount"
    if cycle_count < 1 or cycle_count > 12:
        return False, "cycleCount"
    cfg["cycleCount"] = cycle_count

    if not is_bool(cfg["autoStartNext"]):
        return False, "autoStartNext"
    if not is_bool(cfg["soundEnabled"]):
        return False, "soundEnabled"
    if cfg["theme"] not in ("pulse", "retro"):
        return False, "theme"

    return True, cfg


class PomodoroMpyApp:
    def __init__(self):
        self.config = load_config()
        self.conn = None
        self.connected = False
        self.last_error = None

        self.ble = BleAppService("Pomodoro", app_version="1.0.0", max_message=384)
        self.ble.command("hello", self.ble_cmd_hello, priority=0, mutates=False)
        self.ble.command("open", self.ble_cmd_open, priority=1, mutates=False)
        self.ble.command("sync_config", self.ble_cmd_sync_config, priority=1, mutates=False)
        self.ble.command("get_state", self.ble_cmd_get_state, priority=0, mutates=False)
        self.ble.command("control", self.ble_cmd_control, priority=1, mutates=False)
        self.ble.set_state_provider(self.wire_state_payload)
        self.ble.on_connect(self.ble_on_connect)
        self.ble.on_ready(self.ble_on_ready)
        self.ble.on_disconnect(self.ble_on_disconnect)
        self.ble.on_error(self.ble_on_error)

        self.state = STATE_READY
        self.visual = "busy"
        self.phase = "ready"
        self.paused = False
        self.duration_sec = self.config["focusMin"] * 60
        self.time_left_sec = self.duration_sec
        self.completed_cycles = 0
        self.done_from_phase = None

        self.transition_kind = None
        self.transition_start_frame = 0
        self.transition_target = None
        self.transition_phase = None
        self.transition_duration_sec = 0

        self.feedback_until_ms = 0
        self.last_timer_ms = time.ticks_ms()
        self.last_tick_event_ms = 0

        self.audio = audio_service.audio
        self.audio_initialized = False
        self.prompt_sound = PromptSoundPlayer(
            audio=self.audio,
            asset_root="assets",
            debug=PROMPT_SOUND_DEBUG,
            log_prefix="[PomodoroSound]",
            stop_handler=self.stop_prompt_sound,
        )

        pyxel.init(start_audio=False)
        self.clear_touch_events()
        pyxel.images(0).load_from_png(0, 0, ASSET_PATH, True)

    def run(self):
        self.ble.start()
        pyxel.run(self.update, self.draw, fps=FPS, on_exit=self.on_exit)

    def on_exit(self, rt, reason, exc):
        try:
            self.prompt_sound.deinit()
        except Exception:
            pass
        if self.audio_initialized:
            try:
                self.audio.deinit()
            except Exception:
                pass
            self.audio_initialized = False
        try:
            pyxel.destroy()
        except Exception:
            pass
        self.ble.deinit()

    def update(self, rt):
        self.ble.poll(budget_ms=3, max_messages=4)
        self.handle_touch_events()

        now = time.ticks_ms()
        if self.state == STATE_TRANSITION:
            self.update_transition()
        elif self.state == STATE_WORK or self.state == STATE_REST:
            self.update_timer(now)
        elif self.state == STATE_DONE or self.state == STATE_STOP:
            if time.ticks_diff(now, self.feedback_until_ms) >= 0:
                if self.state == STATE_DONE:
                    self.finish_done_feedback()
                else:
                    self.enter_ready()

        self.prompt_sound.update(budget_packets=PROMPT_SOUND_PACKETS_PER_UPDATE)

    def draw(self, rt):
        pyxel.cls(0)
        self.draw_status_art()
        self.draw_counter()

    def clear_touch_events(self):
        try:
            touch_events.clear()
        except Exception as exc:
            print("[Pomodoro] touch clear failed:", exc)

    def handle_touch_events(self):
        while True:
            event = touch_events.get()
            if event is None:
                return
            action = self.normalize_touch_event(event)
            if action is None:
                continue
            before = self.state
            if action == "click":
                if self.prompt_sound.is_playing():
                    self.prompt_sound.stop()
                else:
                    self.on_click()
            elif action == "double":
                self.on_double()
            self.send_event("touch", {
                "action": action,
                "stateBefore": before,
                "stateAfter": self.state,
            })

    def on_click(self):
        if self.state == STATE_READY and self.visual == "busy":
            self.start_work_with_transition()

    def on_double(self):
        self.reset_to_busy_ready()

    def normalize_touch_event(self, event):
        try:
            event_name = str(event).strip().lower()
        except Exception:
            return None
        if event_name in TOUCH_CLICK_EVENTS:
            return "click"
        if event_name in TOUCH_DOUBLE_EVENTS:
            return "double"
        print("[Pomodoro] unknown touch event:", event_name)
        return None

    def next_focus_duration(self):
        current = self.config["focusMin"]
        if current == 25:
            next_value = 45
        elif current == 45:
            next_value = 15
        else:
            next_value = 25

        self.config["focusMin"] = next_value
        try:
            save_config(self.config)
        except Exception as exc:
            print("[Pomodoro] save config failed:", exc)

        self.duration_sec = next_value * 60
        self.time_left_sec = self.duration_sec
        self.send_event("config_changed", {
            "config": {"focusMin": next_value},
            "source": "touch",
        })
        self.send_state_event()

    def start_work_with_transition(self):
        if self.visual == "busy":
            self.start_work()
        else:
            self.start_transition("rest_to_busy", STATE_WORK, "work", self.config["focusMin"] * 60)

    def start_work(self):
        self.state = STATE_WORK
        self.visual = "busy"
        self.phase = "work"
        self.paused = False
        self.duration_sec = self.config["focusMin"] * 60
        self.time_left_sec = self.duration_sec
        self.last_timer_ms = time.ticks_ms()
        self.send_state_event()
        self.play_prompt_sound("focus_start")

    def start_rest_with_transition(self):
        if self.completed_cycles >= self.config["cycleCount"]:
            phase = "long_break"
            duration_sec = self.config["longBreakMin"] * 60
            self.completed_cycles = 0
        else:
            phase = "short_break"
            duration_sec = self.config["shortBreakMin"] * 60
        self.start_transition("busy_to_rest", STATE_REST, phase, duration_sec)

    def start_transition(self, kind, target_state, target_phase, target_duration_sec):
        self.state = STATE_TRANSITION
        self.transition_kind = kind
        self.transition_target = target_state
        self.transition_phase = target_phase
        self.transition_duration_sec = target_duration_sec
        self.transition_start_frame = pyxel.frame_count
        self.paused = False
        self.duration_sec = target_duration_sec
        self.time_left_sec = target_duration_sec
        self.send_state_event()

    def update_transition(self):
        elapsed = pyxel.frame_count - self.transition_start_frame
        transition_ticks = TRANSITION_FLASH_TOTAL_TICKS + self.transition_frame_count() * TRANSITION_FRAME_TICKS
        if elapsed < transition_ticks:
            return

        self.state = self.transition_target
        self.phase = self.transition_phase
        self.visual = "busy" if self.state == STATE_WORK else "rest"
        self.duration_sec = self.transition_duration_sec
        self.time_left_sec = self.duration_sec
        self.paused = False
        self.last_timer_ms = time.ticks_ms()
        self.send_state_event()
        if self.state == STATE_WORK:
            self.play_prompt_sound("focus_start")
        elif self.state == STATE_REST:
            self.play_prompt_sound("break_start")

    def update_timer(self, now):
        if self.paused:
            self.last_timer_ms = now
            return

        diff = time.ticks_diff(now, self.last_timer_ms)
        if diff < 1000:
            return

        step = diff // 1000
        self.last_timer_ms = time.ticks_add(self.last_timer_ms, step * 1000)
        self.time_left_sec -= step
        if self.time_left_sec <= 0:
            self.time_left_sec = 0
            if self.state == STATE_WORK:
                self.completed_cycles += 1
                self.enter_done_feedback("work")
            else:
                self.enter_done_feedback(self.phase)
            return

        if time.ticks_diff(now, self.last_tick_event_ms) >= 5000:
            self.last_tick_event_ms = now
            self.send_event("tick", self.state_payload(light=True))

    def enter_done_feedback(self, from_phase):
        self.state = STATE_DONE
        self.done_from_phase = from_phase
        self.feedback_until_ms = time.ticks_ms()
        self.send_state_event()

    def finish_done_feedback(self):
        if self.done_from_phase == "work":
            self.start_rest_with_transition()
        elif self.config["autoStartNext"]:
            self.start_work_with_transition()
        else:
            self.enter_ready()

    def enter_stop_feedback(self):
        self.prompt_sound.stop()
        self.state = STATE_STOP
        self.phase = "stop"
        self.paused = False
        self.feedback_until_ms = time.ticks_add(time.ticks_ms(), 3000)
        self.send_state_event()

    def enter_ready(self, emit=True):
        self.prompt_sound.stop()
        self.state = STATE_READY
        self.visual = "busy"
        self.phase = "ready"
        self.paused = False
        self.duration_sec = self.config["focusMin"] * 60
        self.time_left_sec = self.duration_sec
        self.done_from_phase = None
        if emit:
            self.send_state_event()

    def reset_to_busy_ready(self):
        self.completed_cycles = 0
        self.transition_kind = None
        self.transition_target = None
        self.transition_phase = None
        self.transition_duration_sec = 0
        self.enter_ready()

    def play_prompt_sound(self, kind):
        print("[Pomodoro] play_prompt_sound", "kind=", kind, "enabled=", self.config["soundEnabled"], "state=", self.state, "phase=", self.phase)
        if not self.config["soundEnabled"]:
            print("[Pomodoro] prompt sound skipped: disabled")
            return
        filename = PROMPT_SOUND_FILES.get(kind)
        if filename is None:
            print("[Pomodoro] prompt sound skipped: invalid kind", kind)
            return
        if not self.ensure_audio():
            return
        ok = self.prompt_sound.play(filename, interrupt=True)
        print("[Pomodoro] prompt sound start result:", ok)

    def stop_prompt_sound(self, player=None):
        if player is None:
            player = self.prompt_sound
        return player.cancel()

    def ensure_audio(self):
        if self.audio_initialized:
            print("[PomodoroSound] audio already initialized")
            return True
        try:
            print("[PomodoroSound] audio init begin")
            self.audio.init(
                enable_input=False,
                enable_output=True,
                with_opus_encoder=False,
                with_opus_decoder=True,
            )
            self.audio.configure(output_volume=PROMPT_SOUND_VOLUME, input_gain=1.0)
            self.audio_initialized = True
            print("[PomodoroSound] audio init ok", "volume=", PROMPT_SOUND_VOLUME)
            return True
        except Exception as exc:
            print("[Pomodoro] audio init failed:", exc)
            return False

    def draw_status_art(self):
        if self.state == STATE_TRANSITION:
            elapsed = pyxel.frame_count - self.transition_start_frame
            if elapsed < TRANSITION_FLASH_TOTAL_TICKS:
                self.draw_transition_flash(elapsed)
                return

            transition_elapsed = elapsed - TRANSITION_FLASH_TOTAL_TICKS
            frame = transition_elapsed // TRANSITION_FRAME_TICKS
            if frame < 0:
                frame = 0
            frame_count = self.transition_frame_count()
            if frame >= frame_count:
                frame = frame_count - 1
            u = frame * FRAME_W
            if self.transition_kind == "rest_to_busy":
                pyxel.blt(0, 0, 0, u, REST_TO_BUSY_V, FRAME_W, FRAME_H, COLKEY)
            else:
                pyxel.blt(0, 0, 0, u, BUSY_TO_REST_V, FRAME_W, FRAME_H, COLKEY)
            return

        if self.visual == "busy" or self.state == STATE_WORK:
            pyxel.blt(0, 0, 0, BUSY_U, BUSY_V, FRAME_W, FRAME_H, COLKEY)
        else:
            pyxel.blt(0, 0, 0, REST_U, REST_V, FRAME_W, FRAME_H, COLKEY)

    def draw_transition_flash(self, elapsed):
        phase = elapsed // TRANSITION_FLASH_FRAME_TICKS
        show_background = (phase % 2) == 0
        if self.transition_kind == "rest_to_busy":
            if show_background:
                pyxel.blt(0, 0, 0, REST_BG_U, REST_BG_V, FRAME_W, FRAME_H, COLKEY)
            else:
                pyxel.blt(0, 0, 0, REST_U, REST_V, FRAME_W, FRAME_H, COLKEY)
        else:
            if show_background:
                pyxel.blt(0, 0, 0, BUSY_BG_U, BUSY_BG_V, FRAME_W, FRAME_H, COLKEY)
            else:
                pyxel.blt(0, 0, 0, BUSY_U, BUSY_V, FRAME_W, FRAME_H, COLKEY)

    def transition_frame_count(self):
        if self.transition_kind == "rest_to_busy":
            return REST_TO_BUSY_FRAMES
        return BUSY_TO_REST_FRAMES

    def draw_counter(self):
        total = self.time_left_sec
        if total < 0:
            total = 0
        minutes = total // 60
        seconds = total % 60
        text = "%02d%02d" % (minutes % 100, seconds)
        color = DIM_TEXT_COLOR if self.paused and ((pyxel.frame_count // 10) & 1) else TEXT_COLOR

        self.draw_digit(8, COUNTER_Y, text[0], color)
        self.draw_digit(12, COUNTER_Y, text[1], color)
        self.draw_colon(16, COUNTER_Y, color)
        self.draw_digit(18, COUNTER_Y, text[2], color)
        self.draw_digit(22, COUNTER_Y, text[3], color)

    def draw_digit(self, x, y, digit, color):
        rows = DIGITS.get(digit)
        if rows is None:
            return
        for dy in range(5):
            bits = rows[dy]
            for dx in range(3):
                if bits & (1 << (2 - dx)):
                    pyxel.pset(x + dx, y + dy, color)

    def draw_colon(self, x, y, color):
        pyxel.pset(x, y + 1, color)
        pyxel.pset(x, y + 3, color)

    def state_payload(self, light=False):
        payload = {
            "state": self.public_state(),
            "phase": self.phase_for_payload(),
            "paused": self.paused,
            "durationSec": self.duration_sec,
            "timeLeftSec": self.time_left_sec,
            "progress": self.progress(),
        }
        if not light:
            payload["completedCycles"] = self.completed_cycles
            payload["nextRestType"] = self.next_rest_type()
            payload["config"] = clone_config(self.config)
        return payload

    def public_state(self):
        if self.state == STATE_TRANSITION:
            return self.transition_target
        return self.state

    def phase_for_payload(self):
        if self.state == STATE_TRANSITION:
            return self.transition_phase
        return self.phase

    def progress(self):
        if self.duration_sec <= 0:
            return 0
        return self.time_left_sec / self.duration_sec

    def next_rest_type(self):
        if self.completed_cycles + 1 >= self.config["cycleCount"]:
            return "long"
        return "short"

    def ble_on_connect(self, conn):
        self.conn = conn
        self.connected = False

    def ble_on_ready(self, conn, session_id):
        self.conn = conn
        self.connected = True

    def ble_on_disconnect(self, conn, reason):
        if self.conn == conn:
            self.conn = None
        self.connected = False

    def ble_on_error(self, err):
        self.last_error = err
        print("[Pomodoro] ble error:", err)

    def ble_cmd_hello(self, params, message=None):
        return {
            "app": "pomodoro",
            "protocol": 1,
            "state": self.wire_state_payload(),
        }

    def ble_cmd_open(self, params, message=None):
        self.enter_ready()
        return {"state": self.wire_state_payload()}

    def ble_cmd_get_state(self, params, message=None):
        return {"state": self.wire_state_payload()}

    def ble_cmd_sync_config(self, params, message=None):
        config = params.get("config") or {}
        ok, result = validate_config(config)
        if not ok:
            raise ValueError("invalid_config: %s" % result)

        self.config = result
        try:
            save_config(self.config)
        except Exception as exc:
            raise ValueError("persist_failed: %s" % exc)

        apply_mode = params.get("applyMode", "ready")
        if apply_mode == "defer" and (self.state == STATE_WORK or self.state == STATE_REST):
            self.send_state_event()
        elif apply_mode == "start":
            self.enter_ready(emit=False)
            self.start_work_with_transition()
        else:
            self.enter_ready()

        # State changes publish separately; keep the command response small
        # enough for the encrypted F150 envelope.
        return {"ok": True}

    def ble_cmd_control(self, params, message=None):
        action = params.get("action")
        if action == "start":
            if self.state == STATE_READY:
                self.start_work_with_transition()
        elif action == "toggle_pause":
            if self.state == STATE_WORK or self.state == STATE_REST:
                self.paused = not self.paused
                self.last_timer_ms = time.ticks_ms()
                self.send_state_event()
        elif action == "stop":
            if self.state == STATE_WORK or self.state == STATE_REST:
                self.enter_stop_feedback()
        elif action == "reset_ready":
            self.enter_ready()
        elif action == "next_duration":
            if self.state == STATE_READY:
                self.next_focus_duration()
        else:
            raise ValueError("invalid_action: %s" % action)
        return {"state": self.wire_state_payload()}

    def send_state_event(self):
        if self.ble.ready:
            self.ble.publish_state(self.wire_state_payload(), event="stateChanged")

    def send_event(self, event, payload):
        if not self.ble.ready:
            return
        if isinstance(payload, dict) and "state" in payload and "phase" in payload:
            payload = self.wire_state_payload(payload)
        self.ble.send_event(event, payload)

    def wire_state_payload(self, state=None):
        if state is None:
            state = self.state_payload()
        wire = {
            "s": state.get("state"),
            "p": state.get("phase"),
            "z": bool(state.get("paused", False)),
            "d": state.get("durationSec", 0),
            "l": state.get("timeLeftSec", 0),
            "g": state.get("progress", 0),
        }
        if "completedCycles" in state:
            wire["c"] = state.get("completedCycles", 0)
        if "nextRestType" in state:
            wire["n"] = state.get("nextRestType")
        config = state.get("config")
        if isinstance(config, dict):
            wire["f"] = {
                "f": config.get("focusMin"),
                "a": bool(config.get("autoStartNext", False)),
                "c": config.get("cycleCount"),
                "s": config.get("shortBreakMin"),
                "l": config.get("longBreakMin"),
                "e": bool(config.get("soundEnabled", False)),
            }
        return wire


def appMain():
    global APP
    APP = PomodoroMpyApp()
    APP.run()


if __name__ == "__main__":
    appMain()
