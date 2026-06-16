import pygame
from typing import List, Tuple, Optional
from src.utils.colors import Colors

_PAD     = 10
_SB_W    = 6    # scrollbar width
_INPUT_H = 38


class Console:
    def __init__(self, rect: pygame.Rect, font: pygame.font.Font):
        self.rect    = rect
        self.font    = font
        self.line_h  = font.get_linesize()

        self.lines: List[Tuple[str, tuple]] = []
        self.scroll_offset = 0

        self.input_text  = ""
        self._cursor_on  = True
        self._cursor_ms  = 0

        # Command history (like a real shell)
        self._history:    List[str] = []
        self._hist_idx:   int       = -1   # -1 = at live input
        self._saved_input: str      = ""   # buffer while navigating history

        # Sub-areas
        self._log_rect   = pygame.Rect(rect.x, rect.y, rect.width, rect.height - _INPUT_H)
        self._input_rect = pygame.Rect(rect.x, rect.bottom - _INPUT_H, rect.width, _INPUT_H)

        self._text_rect = pygame.Rect(
            self._log_rect.x + _PAD,
            self._log_rect.y + _PAD,
            self._log_rect.width - _PAD * 2 - _SB_W - 6,
            self._log_rect.height - _PAD * 2,
        )
        self.max_visible = self._text_rect.height // self.line_h

    # ─── public API ─────────────────────────────────────────────────────────

    def add_line(self, text: str, color: tuple = None):
        self.lines.append((text, color or Colors.CONSOLE_TEXT))
        n = len(self.lines)
        if n > self.max_visible:
            self.scroll_offset = n - self.max_visible

    def scroll(self, delta: int):
        max_off = max(0, len(self.lines) - self.max_visible)
        self.scroll_offset = max(0, min(self.scroll_offset + delta, max_off))

    def handle_keydown(self, event: pygame.event.Event) -> Optional[str]:
        """
        Process a KEYDOWN event.
        Returns the entered command string when Enter is pressed, else None.
        UP / DOWN navigate command history.
        """
        k = event.key

        if k == pygame.K_RETURN:
            cmd = self.input_text.strip()
            if cmd:
                self._history.append(cmd)
                self.add_line(f"$ {cmd}", Colors.CONSOLE_TEXT)
            self.input_text  = ""
            self._hist_idx   = -1
            self._saved_input = ""
            return cmd or None

        elif k == pygame.K_UP:
            if not self._history:
                return None
            if self._hist_idx == -1:
                self._saved_input = self.input_text
                self._hist_idx    = len(self._history) - 1
            elif self._hist_idx > 0:
                self._hist_idx -= 1
            self.input_text = self._history[self._hist_idx]

        elif k == pygame.K_DOWN:
            if self._hist_idx == -1:
                return None
            self._hist_idx += 1
            if self._hist_idx >= len(self._history):
                self._hist_idx  = -1
                self.input_text = self._saved_input
            else:
                self.input_text = self._history[self._hist_idx]

        elif k in (pygame.K_LEFT, pygame.K_RIGHT):
            pass  # cursor movement not supported — input is append-only

        elif k == pygame.K_BACKSPACE:
            self.input_text  = self.input_text[:-1]
            self._hist_idx   = -1

        elif event.unicode and event.unicode.isprintable():
            self.input_text  += event.unicode
            self._hist_idx   = -1

        return None

    def update(self, dt_ms: int):
        self._cursor_ms += dt_ms
        if self._cursor_ms >= 530:
            self._cursor_on = not self._cursor_on
            self._cursor_ms = 0

    # ─── drawing ────────────────────────────────────────────────────────────

    def draw(self, surface: pygame.Surface):
        # Log area
        pygame.draw.rect(surface, Colors.CONSOLE_BG, self._log_rect)

        visible = self.lines[self.scroll_offset: self.scroll_offset + self.max_visible]
        for i, (text, color) in enumerate(visible):
            surf = self.font.render(text, True, color)
            surface.blit(surf, (self._text_rect.x, self._text_rect.y + i * self.line_h))

        self._draw_scrollbar(surface)

        # Input separator line
        pygame.draw.line(
            surface, Colors.DIVIDER,
            (self._input_rect.left,  self._input_rect.top),
            (self._input_rect.right, self._input_rect.top), 1,
        )

        # Input area
        pygame.draw.rect(surface, Colors.CONSOLE_INPUT_BG, self._input_rect)
        cursor  = "█" if self._cursor_on else " "
        display = f"$ {self.input_text}{cursor}"
        ts = self.font.render(display, True, Colors.CONSOLE_TEXT)
        ty = self._input_rect.y + (_INPUT_H - self.line_h) // 2
        surface.blit(ts, (self._input_rect.x + _PAD, ty))

    def _draw_scrollbar(self, surface: pygame.Surface):
        total = len(self.lines)
        if total <= self.max_visible:
            return

        tx = self._log_rect.right - _SB_W - 4
        ty = self._log_rect.y + _PAD
        th = self._log_rect.height - _PAD * 2

        pygame.draw.rect(surface, Colors.CONSOLE_SCROLLBAR_BG,
                         pygame.Rect(tx, ty, _SB_W, th), border_radius=3)

        ratio    = self.max_visible / total
        thumb_h  = max(16, int(th * ratio))
        scroll_r = self.scroll_offset / (total - self.max_visible)
        thumb_y  = ty + int((th - thumb_h) * scroll_r)
        pygame.draw.rect(surface, Colors.CONSOLE_SCROLLBAR_FG,
                         pygame.Rect(tx, thumb_y, _SB_W, thumb_h), border_radius=3)
