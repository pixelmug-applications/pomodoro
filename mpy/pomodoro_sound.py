import audio_service
from pyxel_prompt_sound import PromptSoundPlayer as OggPromptSoundPlayer


ASSET_ROOT = "assets"
PROMPT_SOUND_DEBUG = True
PROMPT_SOUND_FILES = {
    "focus_start": "focus_start.ogg",
    "break_start": "break_start.ogg",
}


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

    def start(self, kind):
        filename = PROMPT_SOUND_FILES.get(kind)
        if filename is None:
            debug_log("invalid kind", kind)
            return False
        if not self.ensure_audio():
            debug_log("ensure audio failed", self.last_error)
            return False
        return self.player.play(filename, interrupt=True)

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