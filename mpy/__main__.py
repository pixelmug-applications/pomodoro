import time

try:
    import ujson as json
except ImportError:
    import json

import audio_service
import maopaoBle
import micropyxel as pyxel
import mpy_button as touch_events
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

DEFAULT_CONFIG = {
    "focusMin": 2,
    "autoStartNext": False,
    "cycleCount": 1,
    "shortBreakMin": 1,
    "longBreakMin": 2,
    "soundEnabled": True,
    "soundTheme": "classic",
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


@maopaoBle.on_connect
def ble_handle_connect(conn):
    if APP is not None:
        APP.ble_on_connect(conn)


@maopaoBle.on_disconnect
def ble_handle_disconnect(conn, reason):
    if APP is not None:
        APP.ble_on_disconnect(conn, reason)


@maopaoBle.on_receive
def ble_handle_receive(conn, data):
    if APP is not None:
        APP.ble_on_receive(conn, data)


@maopaoBle.on_error
def ble_handle_error(err):
    if APP is not None:
        APP.ble_on_error(err)


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
    if "soundTheme" not in config and "endSound" in config:
        cfg["soundTheme"] = config.get("endSound")
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
    if cfg["soundTheme"] not in ("classic", "gentle"):
        return False, "soundTheme"
    if cfg["theme"] not in ("pulse", "retro"):
        return False, "theme"

    return True, cfg


class PomodoroMpyApp:
    def __init__(self):
        self.config = load_config()
        self.conn = None
        self.connected = False
        self.last_error = None

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
        maopaoBle.init()
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

    def update(self, rt):
        maopaoBle.poll()
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
        self.play_prompt_sound("start")

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
            self.play_prompt_sound("start")
        elif self.state == STATE_REST:
            self.play_prompt_sound("end")

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
        print("[Pomodoro] play_prompt_sound", "kind=", kind, "enabled=", self.config["soundEnabled"], "theme=", self.config["soundTheme"], "state=", self.state, "phase=", self.phase)
        if not self.config["soundEnabled"]:
            print("[Pomodoro] prompt sound skipped: disabled")
            return
        if not self.ensure_audio():
            return
        ok = self.prompt_sound.play_theme(self.config["soundTheme"], kind, interrupt=True)
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
        self.connected = True
        self.send_state_event()

    def ble_on_disconnect(self, conn, reason):
        if self.conn == conn:
            self.conn = None
        self.connected = False

    def ble_on_error(self, err):
        self.last_error = err
        print("[Pomodoro] ble error:", err)

    def ble_on_receive(self, conn, data):
        self.conn = conn
        self.connected = True

        try:
            if isinstance(data, bytes):
                text = data.decode("utf-8")
            else:
                text = str(data)
            msg = json.loads(text)
        except Exception as exc:
            self.send_error(None, None, "invalid_json", str(exc))
            return

        if msg.get("type") != "cmd":
            self.send_error(msg.get("id"), msg.get("cmd"), "invalid_type", "expected cmd")
            return

        cmd = msg.get("cmd")
        req_id = msg.get("id")
        payload = msg.get("payload") or {}

        if cmd == "hello":
            self.send_ack(req_id, cmd, True, {
                "app": "pomodoro",
                "protocol": 1,
                "state": self.state_payload(),
            })
        elif cmd == "open":
            self.enter_ready()
            self.send_ack(req_id, cmd, True, {"state": self.state_payload()})
        elif cmd == "sync_config":
            self.handle_sync_config(req_id, cmd, payload)
        elif cmd == "get_state":
            self.send_ack(req_id, cmd, True, {"state": self.state_payload()})
        elif cmd == "control":
            self.handle_control(req_id, cmd, payload)
        else:
            self.send_error(req_id, cmd, "unknown_cmd", str(cmd))

    def handle_sync_config(self, req_id, cmd, payload):
        config = payload.get("config") or {}
        ok, result = validate_config(config)
        if not ok:
            self.send_ack(req_id, cmd, False, {}, "invalid_config", result)
            return

        self.config = result
        try:
            save_config(self.config)
        except Exception as exc:
            self.send_ack(req_id, cmd, False, {}, "persist_failed", str(exc))
            return

        apply_mode = payload.get("applyMode", "ready")
        if apply_mode == "defer" and (self.state == STATE_WORK or self.state == STATE_REST):
            pass
        elif apply_mode == "start":
            self.enter_ready(emit=False)
            self.start_work_with_transition()
        else:
            self.enter_ready()

        self.send_ack(req_id, cmd, True, {"state": self.state_payload()})

    def handle_control(self, req_id, cmd, payload):
        action = payload.get("action")
        if action == "start":
            if self.state == STATE_READY:
                self.start_work_with_transition()
            self.send_ack(req_id, cmd, True, {"state": self.state_payload()})
        elif action == "toggle_pause":
            if self.state == STATE_WORK or self.state == STATE_REST:
                self.paused = not self.paused
                self.last_timer_ms = time.ticks_ms()
            self.send_ack(req_id, cmd, True, {"state": self.state_payload()})
        elif action == "stop":
            if self.state == STATE_WORK or self.state == STATE_REST:
                self.enter_stop_feedback()
            self.send_ack(req_id, cmd, True, {"state": self.state_payload()})
        elif action == "reset_ready":
            self.enter_ready()
            self.send_ack(req_id, cmd, True, {"state": self.state_payload()})
        elif action == "next_duration":
            if self.state == STATE_READY:
                self.next_focus_duration()
            self.send_ack(req_id, cmd, True, {"state": self.state_payload()})
        else:
            self.send_ack(req_id, cmd, False, {}, "invalid_action", str(action))

    def send_state_event(self):
        self.send_event("state", self.state_payload())

    def send_event(self, event, payload):
        self.send_json({
            "v": 1,
            "type": "event",
            "event": event,
            "payload": payload,
        })

    def send_ack(self, req_id, cmd, ok, payload, error=None, message=None):
        msg = {
            "v": 1,
            "id": req_id,
            "type": "ack",
            "cmd": cmd,
            "ok": ok,
            "payload": payload,
        }
        if error is not None:
            msg["error"] = error
        if message is not None:
            msg["message"] = message
        self.send_json(msg)

    def send_error(self, req_id, cmd, error, message):
        self.send_ack(req_id, cmd, False, {}, error, message)

    def send_json(self, msg):
        if not self.connected or self.conn is None:
            return
        try:
            maopaoBle.send(json.dumps(msg).encode("utf-8"), conn=self.conn)
        except Exception as exc:
            print("[Pomodoro] send failed:", exc)


def appMain():
    global APP
    APP = PomodoroMpyApp()
    APP.run()


if __name__ == "__main__":
    appMain()
