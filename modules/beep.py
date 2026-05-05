import threading
import sys

def _play(freq, duration):
    try:
        if sys.platform == "win32":
            import winsound
            winsound.Beep(freq, duration)
        else:
            import os
            os.system(f"play -nq -t alsa synth {duration/1000} sine {freq} 2>/dev/null || "
                      f"ffplay -f lavfi -i 'sine=frequency={freq}:duration={duration/1000}' -autoexit -nodisp 2>/dev/null")
    except Exception:
        pass

def beep_start():
    """Beep agudo corto — indica inicio de grabación"""
    threading.Thread(target=_play, args=(880, 120), daemon=True).start()

def beep_stop():
    """Dos beeps descendentes — indica fin de grabación"""
    def _seq():
        _play(880, 100)
        _play(440, 180)
    threading.Thread(target=_seq, daemon=True).start()

def beep_error():
    """Beep grave — indica error"""
    threading.Thread(target=_play, args=(220, 300), daemon=True).start()
