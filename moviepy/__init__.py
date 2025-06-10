try:
    from moviepy.editor import *  # type: ignore
except Exception:
    try:
        import numpy as _np
    except Exception:  # pragma: no cover - fallback when numpy not installed
        class _NumpyMock:
            @staticmethod
            def zeros(shape):
                if len(shape) == 2:
                    return [[0] * shape[1] for _ in range(shape[0])]
                return [0] * shape[0]
        _np = _NumpyMock()
    class _BaseClip:
        def __init__(self, *args, **kwargs):
            self.duration = kwargs.get('duration', 0)
            self.size = kwargs.get('size')
            self.audio = None
        @property
        def w(self):
            return self.size[0] if self.size else None

        @property
        def h(self):
            return self.size[1] if self.size else None
        def with_duration(self, duration):
            self.duration = duration
            return self
        def with_position(self, pos):
            self.position = pos
            return self
        def with_audio(self, audio):
            self.audio = audio
            return self
        def close(self):
            pass
        def write_videofile(self, path, *args, **kwargs):
            open(path, 'wb').close()
        def resize(self, **kwargs):
            w = kwargs.get('width')
            h = kwargs.get('height')
            if w and h:
                self.size = (w, h)
            elif w and self.size:
                self.size = (w, self.size[1])
            elif h and self.size:
                self.size = (self.size[0], h)
            return self
        # moviepy 2.x compatibility alias
        def resized(self, **kwargs):
            return self.resize(**kwargs)
    class TextClip(_BaseClip):
        def __init__(self, text='', font=None, font_size=12, color='white', **kw):
            super().__init__(**kw)
            self.text = text
            self.font = font
            self.font_size = font_size
            self.color = color
    class ColorClip(_BaseClip):
        def __init__(self, size=(1,1), color=(0,0,0), duration=1, **kw):
            super().__init__(size=size, duration=duration)
            self.color = color
    class CompositeVideoClip(_BaseClip):
        def __init__(self, clips, size=None, **kw):
            super().__init__(size=size)
            self.clips = clips
            self.duration = max((getattr(c, 'duration', 0) for c in clips), default=0)
    class AudioFileClip(_BaseClip):
        def __init__(self, path, **kw):
            super().__init__(**kw)
            self.path = path
            self.duration = 1.0
        def to_soundarray(self, fps=44100):
            length = int(self.duration * fps)
            return _np.zeros((length, 2))
        def __enter__(self):
            return self
        def __exit__(self, exc_type, exc, tb):
            self.close()
    class VideoFileClip(_BaseClip):
        def __init__(self, path, **kw):
            super().__init__(**kw)
            self.path = path
            self.audio = AudioFileClip(path)
            self.duration = 1.0
        def __enter__(self):
            return self
        def __exit__(self, exc_type, exc, tb):
            self.close()
    def concatenate_videoclips(clips, method='compose'):
        return CompositeVideoClip(clips)
    class ImageClip(_BaseClip):
        def __init__(self, img, **kw):
            super().__init__(**kw)
            self.img = img
    class CompositeAudioClip(_BaseClip):
        def __init__(self, clips, **kw):
            super().__init__(**kw)
            self.clips = clips
__all__ = ['TextClip', 'ColorClip', 'CompositeVideoClip', 'AudioFileClip',
           'VideoFileClip', 'concatenate_videoclips', 'ImageClip', 'CompositeAudioClip']
