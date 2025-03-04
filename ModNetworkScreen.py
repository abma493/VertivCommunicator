from common_term import *
import asyncio
from syncprims import queue_cond, comm_queue, sem_UI
from QuitScreen import QuitScreen
from ntwk_ops import NetworkOptions
from RestartScreenPrompt import PushChangesScreen
from logger import Logger

class NetworkDataResourcesMsg(Message):
    def __init__(self, dhcp, ip, subnet):
        super().__init__()
        self.dhcp = dhcp
        self.ip = ip
        self.subnet = subnet

class ModNetworkScreen(ModalScreen):
    
    CSS_PATH="./assets/modntwk_screen.css"
    BINDINGS = [
        ("q", "quit_app"),
        ("b", "back_menu"),
    ]

    async def _on_mount(self):
        Logger.log("Loading ModNetworkScreen resources...")
        self.dhcp_checkbox: Checkbox = self.query_one("#dhcp-checkbox")
        self.current_ip = self.query_one("#current-ip", Static)
        self.current_subnet = self.query_one("#current-subnet", Static)
        self.dhcp_checkbox.disabled = True
        self.dhcp_changed = False #flag to track if dhcp was modded, not the value itself
        self.pending_dhcp_change = self.dhcp_changed #by default
        
        task = asyncio.create_task(self.load_resources())
        task.add_done_callback(self._handle_task_result)

    def _handle_task_result(self, task):
        # Check for exceptions
        if task.cancelled():
            Logger.log("Network data task was cancelled")
        elif task.exception():
            Logger.log(f"Network data task failed: {task.exception()}")

    # send a request and receive a response
    async def send_request(self, request_type: str, message=None) -> tuple:
        request = {
                                'request': request_type,
                                'message': message
        } 
        Logger.log(f"requesting: req -> {request.get("request")} msg -> {request.get("message")}")
        with queue_cond:
            comm_queue.put(request)
            queue_cond.notify() # let listen() know there's a request-- let go of lock too!
                
        sem_UI.acquire()
        response = dict(comm_queue.get()).get("message")
        return response

    # Pre-populate current Network settings 
    async def load_resources(self):
        try: 

            dhcp, ip, subnet = await self.send_request("GET_NTWK_OPS_R")        
            Logger.log(f"received: [IP: {ip}], [subnet: {subnet}], [dhcp: {dhcp}]")
    
            self.current_ip.update(f"Current IP: {ip}" if ip else "Current IP: ERROR")
            self.current_subnet.update(f"Current subnet: {subnet}" if subnet else "Current subnet: ERROR")
            self.dhcp_checkbox.label = "Set DHCP (Currently: ON)" if dhcp else "Set DHCP (Currently: OFF)"
            self.dhcp_checkbox.disabled = False
            
        except Exception as e:
            Logger.log(f"Error fetching network data {e}")


    def compose(self) -> ComposeResult:
        yield Grid(
            Container(
                Label("IP Modification Options"),
                Checkbox(f"Set DHCP (Currently: LOADING)", id="dhcp-checkbox"), 
                Horizontal(
                    Static("IP address:", id="ip-label"),
                    Input(placeholder="IP address", id="ip-field"),
                id="ip-field-container"),
                Horizontal(
                    Static("Subnet mask:", id="subnet-label"),
                    Input(placeholder="Subnet mask", id="subnet-mask-field"),
                id="subnet-field-container"),
                Button("SET", id="set-button"),
                Vertical(
                        Static(f"Current IP: LOADING", id="current-ip"),
                        Static(f"Current subnet: LOADING", id="current-subnet"),
                id="current-network-settings"),
            id="configurations"),
            ListView(id="devices-update"),
            Horizontal(
                       Button("Q - Quit", id="quit-button"),
                       Button("B - Back", id="back-button"),
                       Label("Mode: Single (Default)", id="status-label"),
                 id="options"),
        id="ntwk-config-grid")

    def action_quit_app(self) -> None:
        self.app.push_screen(QuitScreen())

    def action_back_menu(self) -> None:
        self.app.pop_screen()

    @on(Button.Pressed, "#set-button")
    async def on_set_pressed(self):
        ip_field = self.query_one("#ip-field", Input)
        subnet_mask_field = self.query_one("#subnet-mask-field", Input)
        
        # We need to make sure the DHCP checkbox was modified
        passed_in_dhcp_val = self.pending_dhcp_change
        if not self.dhcp_changed: # if it wasn't then no change request is needed
            passed_in_dhcp_val = None

        self.app.push_screen(PushChangesScreen(ip_field.value, subnet_mask_field.value, passed_in_dhcp_val))

    @on(Checkbox.Changed, "#dhcp-checkbox")
    def handle_dhcp_checkbox(self, event: Checkbox.Changed):
        # save the value here, True for clicked, False for unclicked
        self.dhcp_changed = True 
        self.pending_dhcp_change = event.value

        