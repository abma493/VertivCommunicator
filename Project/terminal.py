from common.common_term import *
from screens.BaseScreen import BaseScreen

      

class ScreenApp(App):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def on_mount(self) -> None:
        self.push_screen(BaseScreen())
