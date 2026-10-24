"""Shared task/library selection outline and bottom-up fill animation."""
import math
import time
from ui_common import ACCENT, rounded


class SelectionEffects:
    def __init__(self):
        self.states = {}
        self.active = False

    def begin(self, active):
        self.now = time.monotonic()
        self.visible = set()
        self.animating = False
        self.entering = active and not self.active
        self.active = active

    def _amount(self, state):
        value, start, initial, delay, entering = state
        elapsed = max(0, self.now-start)
        progress = min(1, max(0, (elapsed-delay)/.16))
        eased = (1-math.cos(progress*math.pi))/2
        return initial+(float(value)-initial)*eased, min(1, elapsed/.1) if entering else 1

    def draw(self, canvas, key, x, y, checked):
        self.visible.add(key)
        state = self.states.get(key)
        if state is None:
            state = (checked, self.now, 0, .1, True) if self.entering else (checked, self.now-.26, float(checked), 0, False)
        elif state[0] != checked:
            state = (checked, self.now, self._amount(state)[0], 0, False)
        self.states[key] = state
        fill, alpha = self._amount(state)
        self.animating |= self.now-state[1] < state[3]+.16
        color = '#'+''.join(f'{round(255+(int(ACCENT[i:i+2],16)-255)*alpha):02x}' for i in (1,3,5))
        if fill > 0:
            rounded(canvas,x,y+20*(1-fill),20,20*fill,2,fill=color,outline='',tags='selection-effect')
        rounded(canvas,x,y,20,20,2,fill='',outline=color,width=1.5,tags='selection-effect')

    def end(self):
        self.states = {key:state for key,state in self.states.items() if key in self.visible}
        return self.animating
