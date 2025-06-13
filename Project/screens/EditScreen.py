from textual import on
from textual.app import ComposeResult, App
from textual.containers import Container, Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, Select


class EditScreen(ModalScreen):
    
    CSS_PATH = "../assets/editscreen.css"

    def __init__(self): 
        super().__init__()
        self.batch_mode = False
        self.firmware_label = "IS-UNITY"
    
    def compose(self) -> ComposeResult:
        
        with Container(id="edit-modal"):
            yield Label("Edit Mode", id="title")
            yield Label("Current Mode: Single", id="mode-label")
            yield Select(
                ((option, option) for option in ["Single", "Batch (RDU101)", "Batch (IS-UNITY)"]),
                value="Single",
                prompt="<Select Mode>",
                id="mode-select"
            )
            
            yield Input(id="path-batch", placeholder="Path to batch file", disabled=True)
            yield Input(id="path-config", placeholder="Path to config file", disabled=True)
            # Should be available on both modes, optional unless attempting to push firmware
            yield Input(id="path-firmware", placeholder="Path to firmware file", disabled=False)
            
            yield Button("OK", variant="primary", id="ok-button")
        
    
    def on_mount(self) -> None:
        self.query_one("#mode-select").focus()
    
    @on(Select.Changed, "#mode-select")
    def on_mode_changed(self, event: Select.Changed) -> None:
        
        self.batch_mode = "Batch" in event.value
        path_batch = self.query_one("#path-batch")
        path_config = self.query_one("#path-config")
        mode_label = self.query_one("#mode-label")
        
        # Update the label to show the currently selected mode
        mode_label.update(f"Current Mode: {event.value}")
        
        if self.batch_mode:
            path_batch.disabled = False
            path_config.disabled = False
        else:
            path_batch.disabled = True
            path_config.disabled = True
    
    @on(Button.Pressed, "#firmware-button")
    async def on_firmware_pressed(self) -> None:
        button: Button = self.query_one("#firmware-button")
        updated_label: str = ""

        if button.label == "IS-UNITY":
            updated_label = "RDU101"
        else:
            updated_label = "IS-UNITY"
        button.remove()
        new_button = Button(updated_label, id="firmware-button")
        self.query_one("#firmware-container").mount(new_button)

    @on(Button.Pressed, "#ok-button")
    def on_ok_pressed(self) -> None:

        mode = self.query_one("#mode-select").value
        path_batch = self.query_one("#path-batch").value
        path_config = self.query_one("#path-config").value
        path_firmware = self.query_one("#path-firmware").value

        self.dismiss((mode, path_batch, path_config, path_firmware))
