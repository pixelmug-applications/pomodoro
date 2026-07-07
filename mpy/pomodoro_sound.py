import audio_service
from pyxel_prompt_sound import PromptSoundPlayer as OggPromptSoundPlayer


ASSET_ROOT = "assets"
SOUND_THEMES = ("classic", "gentle")
PROMPT_SOUND_DEBUG = True


def debug_log(*args):
    if PROMPT_SOUND_DEBUG:
        try:
            print("[PomodoroSound]", *args)
        except Exception:
            pass


class PromptSoundPlayer:
    def __init__(self, output_volume=100, asset_root=ASSET_ROOT, debug=PROMPT_SOUND_DEBUG):
        self.audio = audio_service.audio
        self.output_volume = output_volume
        self.initialized = False
        self.last_error = None
        self.player = OggPromptSoundPlayer(
            audio=self.audio,
            asset_root=asset_root,
            debug=debug,
            log_prefix="[PomodoroSound]",
            stop_handler=lambda player: player.cancel(),
        )

    def start(self, theme, kind):
        theme = self.normalize_theme(theme)
        if kind not in ("start", "end"):
            debug_log("invalid kind", kind)
            return False
        if not self.ensure_audio():
            debug_log("ensure audio failed", self.last_error)
            return False
        return self.player.play_theme(theme, kind, interrupt=True)

    def update(self, budget_packets=None):
        self.player.update(budget_packets=budget_packets)

    def stop(self):
        return self.player.stop()

    def cancel(self):
        return self.player.cancel()

    def is_playing(self):
        return self.player.is_playing()

    def deinit(self):
        self.player.deinit()
        if self.initialized:
            try:
                self.audio.deinit()
            except Exception:
                pass
            self.initialized = False

    def normalize_theme(self, theme):
        theme = str(theme).lower()
        if theme not in SOUND_THEMES:
            return "classic"
        return theme

    def ensure_audio(self):
        if self.initialized:
            debug_log("audio already initialized")
            return True
        try:
            debug_log("audio init begin")
            self.audio.init(
                enable_input=False,
                enable_output=True,
                with_opus_encoder=False,
                with_opus_decoder=True,
            )
            self.audio.configure(output_volume=self.output_volume, input_gain=1.0)
            self.initialized = True
            debug_log("audio init ok", "volume=", self.output_volume)
            return True
        except Exception as exc:
            self.last_error = exc
            debug_log("audio init failed", exc)
            print("[Pomodoro] audio init failed:", exc)
            return False