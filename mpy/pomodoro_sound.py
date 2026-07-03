import time

import audio_service


ASSET_ROOT = "assets"
SOUND_THEMES = ("classic", "gentle")
PROMPT_PRIME_PACKETS = 8
PROMPT_PACKETS_PER_UPDATE = 4
PROMPT_DRAIN_TIMEOUT_MS = 8000
PROMPT_EAGAIN_SLEEP_MS = 3
PROMPT_EAGAIN_RETRIES_PER_PACKET = 3
PROMPT_SOUND_DEBUG = True
PROMPT_DEBUG_INTERVAL_MS = 500

def debug_log(*args):
    if PROMPT_SOUND_DEBUG:
        try:
            print("[PomodoroSound]", *args)
        except Exception:
            pass

def sleep_ms(ms):
    try:
        time.sleep_ms(ms)
    except AttributeError:
        time.sleep(ms / 1000)

def opus_packet_duration_ms(packet):
    if not packet:
        return 20

    config = packet[0] >> 3
    code = packet[0] & 0x03

    if config < 12:
        frame_ms = (10, 20, 40, 60)[config & 0x03]
    elif config < 16:
        frame_ms = (10, 20)[config & 0x01]
    else:
        frame_ms = (3, 5, 10, 20)[config & 0x03]

    if code == 0:
        frames = 1
    elif code == 1 or code == 2:
        frames = 2
    elif len(packet) > 1:
        frames = packet[1] & 0x3f
    else:
        frames = 1

    duration = frame_ms * frames
    if duration <= 0:
        return 20
    return duration

class OggOpusPacketReader:
    def __init__(self, path):
        self.path = path
        self.file = None
        self.sample_rate = 16000
        self.seen_head = False
        self.seen_tags = False
        self.partial = bytearray()
        self.packet_queue = []

    def open(self):
        self.close()
        self.file = open(self.path, "rb")

    def close(self):
        if self.file is not None:
            try:
                self.file.close()
            except Exception:
                pass
            self.file = None
        self.partial = bytearray()
        self.packet_queue = []

    def next_packet(self):
        if self.packet_queue:
            return self.packet_queue.pop(0)

        f = self.file
        if f is None:
            return None

        while True:
            sig = f.read(4)
            if not sig:
                return None
            if sig != b"OggS":
                f.seek(-3, 1)
                continue

            hdr = f.read(23)
            if len(hdr) < 23:
                return None

            version = hdr[0]
            header_type_flag = hdr[1]
            seg_cnt = hdr[22]
            if version != 0:
                return None

            seg_table = f.read(seg_cnt)
            if len(seg_table) < seg_cnt:
                return None

            body_size = 0
            for b in seg_table:
                body_size += b

            body = f.read(body_size)
            if len(body) < body_size:
                return None

            continued = (header_type_flag & 0x01) != 0
            if continued and len(self.partial) == 0:
                continued = False

            pkt = self.partial if continued else bytearray()
            self.partial = bytearray()
            cur = 0

            for length in seg_table:
                if length:
                    pkt.extend(body[cur:cur + length])
                cur += length

                if length < 255:
                    if len(pkt) > 0:
                        result = self._packet_or_none(pkt)
                        pkt = bytearray()
                        if result is not None:
                            self.packet_queue.append(result)
                    else:
                        pkt = bytearray()

            if len(pkt) > 0:
                self.partial = pkt

            if self.packet_queue:
                return self.packet_queue.pop(0)

    def _packet_or_none(self, pkt):
        if not self.seen_head:
            if len(pkt) >= 16 and pkt[:8] == b"OpusHead":
                self.seen_head = True
                self.sample_rate = (
                    pkt[12] |
                    (pkt[13] << 8) |
                    (pkt[14] << 16) |
                    (pkt[15] << 24)
                )
            return None

        if not self.seen_tags:
            if len(pkt) >= 8 and pkt[:8] == b"OpusTags":
                self.seen_tags = True
            return None

        return bytes(pkt), self.sample_rate


class PromptSoundPlayer:
    def __init__(self, output_volume=100, frame_ms=60,
                 prime_packets=PROMPT_PRIME_PACKETS,
                 packets_per_update=PROMPT_PACKETS_PER_UPDATE):
        self.audio = audio_service.audio
        self.output_volume = output_volume
        self.frame_ms = frame_ms
        self.prime_packets = int(prime_packets)
        self.packets_per_update = int(packets_per_update)
        self.initialized = False
        self.reader = None
        self.session = None
        self.pending_packet = None
        self.kind = None
        self.theme = None
        self.ending = False
        self.done = True
        self.last_error = None
        self.packets_sent = 0
        self.eagain_count = 0
        self.drain_started_ms = 0
        self.last_debug_ms = 0

    def start(self, theme, kind):
        debug_log("start requested", "theme=", theme, "kind=", kind)
        self.stop()
        theme = self.normalize_theme(theme)
        if kind not in ("start", "end"):
            debug_log("invalid kind", kind)
            return False

        if not self._ensure_audio():
            debug_log("ensure audio failed", self.last_error)
            return False

        path = "%s/%s-%s.ogg" % (ASSET_ROOT, theme, kind)
        debug_log("opening", path)
        try:
            reader = OggOpusPacketReader(path)
            reader.open()
            first_packet = reader.next_packet()
            if first_packet is None:
                raise RuntimeError("no opus audio packet")
            try:
                debug_log("first packet", "len=", len(first_packet[0]), "sample_rate=", first_packet[1])
            except Exception:
                pass
            player = self.audio.player("opus")
            session = player.open_stream(mode="replace")
            try:
                debug_log("stream opened", "id=", session.id(), "state=", session.state())
            except Exception as exc:
                debug_log("stream opened, state unavailable", exc)
        except Exception as exc:
            self.last_error = exc
            try:
                reader.close()
            except Exception:
                pass
            debug_log("open failed", exc)
            print("[Pomodoro] prompt sound open failed:", exc)
            return False

        self.reader = reader
        self.session = session
        self.kind = kind
        self.theme = theme
        self.ending = False
        self.done = False
        self.pending_packet = first_packet
        self.packets_sent = 0
        self.eagain_count = 0
        self.drain_started_ms = 0
        debug_log("prime begin", "budget=", self.prime_packets)
        self.update(budget_packets=self.prime_packets, prime=True)
        debug_log("prime done", "packets=", self.packets_sent, "eagain=", self.eagain_count, "pending=", self.pending_packet is not None, "done=", self.done)
        return True

    def update(self, budget_packets=None, prime=False):
        if self.done:
            return
        if budget_packets is None:
            budget_packets = self.packets_per_update

        try:
            self.audio.poll()
        except Exception:
            pass

        if self.session is None:
            self._finish()
            return

        if self.ending:
            self._finish_if_session_ended()
            return

        sent = 0
        while sent < budget_packets:
            if self.pending_packet is not None:
                packet = self.pending_packet
                self.pending_packet = None
            else:
                packet = self.reader.next_packet() if self.reader is not None else None
            if packet is None:
                self._end_session()
                break

            pkt, _sample_rate = packet
            retries = 0
            while True:
                try:
                    wait = prime and self.packets_sent < self.prime_packets
                    self.session.write(pkt, wait=wait)
                    sent += 1
                    self.packets_sent += 1
                    try:
                        self.audio.poll()
                    except Exception:
                        pass
                    if prime or self.packets_sent <= 3:
                        debug_log("write ok", "packet=", self.packets_sent, "len=", len(pkt), "wait=", wait)
                    break
                except OSError:
                    self.eagain_count += 1
                    retries += 1
                    try:
                        self.audio.poll()
                    except Exception:
                        pass
                    debug_log("write eagain", "packet=", self.packets_sent + 1, "retry=", retries)
                    if retries >= PROMPT_EAGAIN_RETRIES_PER_PACKET:
                        self.pending_packet = packet
                        debug_log("write deferred", "packets=", self.packets_sent, "eagain=", self.eagain_count)
                        return
                    sleep_ms(PROMPT_EAGAIN_SLEEP_MS)
                except Exception as exc:
                    self.last_error = exc
                    debug_log("write failed", exc)
                    print("[Pomodoro] prompt sound write failed:", exc)
                    self.stop()
                    return

    def stop(self):
        if self.session is not None:
            debug_log("stop", "packets=", self.packets_sent, "eagain=", self.eagain_count)
            try:
                self.session.cancel()
            except Exception:
                pass
        self._finish()

    def is_playing(self):
        return not self.done

    def deinit(self):
        self.stop()
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

    def _ensure_audio(self):
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

    def _end_session(self):
        debug_log("end session", "packets=", self.packets_sent, "eagain=", self.eagain_count)
        if self.session is not None:
            try:
                self.session.end()
            except Exception:
                pass
        self.ending = True
        self.drain_started_ms = time.ticks_ms()
        self._finish_if_session_ended()

    def _finish_if_session_ended(self):
        try:
            self.audio.poll()
            state = self.session.state()
            now = time.ticks_ms()
            if time.ticks_diff(now, self.last_debug_ms) >= PROMPT_DEBUG_INTERVAL_MS:
                self.last_debug_ms = now
                debug_log("session drain", "state=", state, "packets=", self.packets_sent, "eagain=", self.eagain_count)
            if state == "ended" or state == "canceled" or state == "error":
                debug_log("session finished", state)
                self._finish()
                return
            if (self.drain_started_ms and
                    time.ticks_diff(time.ticks_ms(), self.drain_started_ms) >
                    PROMPT_DRAIN_TIMEOUT_MS):
                self.stop()
        except Exception:
            self._finish()

    def _finish(self):
        if not self.done:
            debug_log("finish", "packets=", self.packets_sent, "eagain=", self.eagain_count)
        if self.reader is not None:
            self.reader.close()
        self.reader = None
        self.session = None
        self.pending_packet = None
        self.kind = None
        self.ending = False
        self.done = True
        self.packets_sent = 0
        self.eagain_count = 0
        self.drain_started_ms = 0
