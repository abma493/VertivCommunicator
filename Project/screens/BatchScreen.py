from common.common_term import *
from playwright.async_api import async_playwright, expect, Page, BrowserContext, TimeoutError as PlaywrightTimeoutError
from common.common_imports import default_timeout
from textual.widgets import Select
from logger import Logger
from login import login
import asyncio
from asyncio import Task
from logger import Logger
from enum import Enum, auto

class Mode(Enum):
    EXPORT = auto()
    IMPORT = auto()
    FIRMWARE = auto()

class BatchScreen(Screen):
    
    CSS_PATH = "../assets/batchops.css"

    def __init__(self, path_to_batch: str, path_to_config: str, path_to_firmware: str, credentials):
        self.jobs = self.parse_to_list(path_to_batch)
        self.path_to_config = path_to_config 
        self.path_to_firmware = path_to_firmware
        self.job_tasks: Task = []
        self.credentials = credentials 
        self.running = False   
        self.mode = Mode.EXPORT
        self.success_count = 0 # num of jobs completed successfully
        super().__init__()

    # parse the IPs in the batch file to a list of jobs 
    # A job entry in the list is comprised of an IP and an ID
    # IP is used to navigate to webcard website
    # ID is used to provide a selector identifier to the widgets on screen
    def parse_to_list(self, path_to_batch: str) -> list:
        jobs = []

        with open(path_to_batch, 'r') as file:

            lines = [line.strip() for line in file.readlines() if line.strip()]
            for i, ip in enumerate(lines, 1):
                entry = {
                    "ip": ip,
                    "id": f'job-entry{i}'
                }
                Logger.log(f'appending {entry["ip"]}/{entry["id"]}')
                jobs.append(entry)

        return jobs


    def compose(self) -> ComposeResult:
        
        with Grid(id="batch-screen-grid"):
            yield Static("Batch Queue", id="title")
            
            yield ListView(
                *[ListItem(
                    Container(
                        Static(f"Job {i}"),
                        Static(f"IP: {job['ip']}"),  
                        ProgressBar(id=job['id'], total=100, show_eta=False),
                        Static(f"Status: READY", id=f"{job['id']}-stat"),
                    classes="job-container"
                    )
                ) for i, job in enumerate(self.jobs, 1)],
            id="list-of-jobs")
            
            with Horizontal(classes="buttons-container"):
                yield Button("<Abort All>", id="abort-all")
                yield Button("<Kill Job>", id="kill-button")  
                yield Button("<Run>", id="run-button")
                yield Select(
                    ((option, option) for option in ["Export", "Import", "Firmware Update"]),
                    value="Export",
                    prompt="",
                    id="mode-select"                    
                )

    @on(Button.Pressed, "#return-button")
    def on_return_pressed(self) -> None:
        self.app.pop_screen()

    @on(Button.Pressed, "#abort-all")
    async def on_abort_pressed(self) -> None:

        if self.running:
            current = asyncio.current_task()
            for i, task in enumerate(self.job_tasks):

                if task != current:
                    job_id = self.jobs[i]["id"]
                    self.mark_job_aborted(job_id)
                    task.cancel()
            self.running = False


    @on(Button.Pressed, "#run-button")
    async def on_run_pressed(self) -> None:
        self.run_worker(self.run_batch_ops(), exclusive=True)

    @on(Select.Changed, "#mode-select")
    def on_mode_changed(self, event: Select.Changed) -> None:
        
        mode: Mode = Mode.EXPORT if event.value == "Export" else Mode.IMPORT
        mode = Mode.FIRMWARE if event.value == "Firmware Update" else mode

        self.mode = mode

    # ancillary function to handle job labels and progress bar
    def mark_job_aborted(self, job_id: str) -> None:
        stat_label = self.query_one(f"#{job_id}-stat", Static)
        progress_bar: ProgressBar = self.query_one(f"#{job_id}", ProgressBar)
        stat_label.update("ABORTED")
        progress_bar.update(total=100, progress=0)
    
    # amalgamates all the tasks to run concurrently
    async def run_batch_ops(self):

        tasks = [asyncio.create_task(self.run_job(job["ip"], job["id"], self.credentials)) for job in self.jobs]
        self.job_tasks = tasks

        # all jobs run in parallel, asyncio reaps them when completed/terminated
        await asyncio.gather(*tasks)
        
        # jobs are done processing
        self.running = False

        # Pop the buttons off the stack to leave only the return button when all is done
        buttons_container = self.query_one(".buttons-container")
        buttons_container.remove_children()
        return_button = Button("RETURN", id="return-button", variant="primary")
        final_stat = Static(f"jobs succeeded: ({self.success_count}/{len(self.jobs)})", id="final-stat")
        buttons_container.mount(return_button)
        buttons_container.mount(final_stat)

    # runs an individual job
    async def run_job(self, ip: str, id: str,  credentials: tuple, max_retries: int = 3):
        stat_label = self.query_one(f"#{id}-stat", Static)
        prog_bar = self.query_one(f"#{id}", ProgressBar)
        retry = 0
        self.running = True 

        while retry < max_retries:
            try:
                stat_label.update("Connecting...")
                playwright = await async_playwright().start()
                browser = await playwright.firefox.launch(headless=False)
                context = await browser.new_context() 
                url = f"http://{ip}/web/initialize.htm"
                page = await context.new_page()
                await page.goto(url)
                
                login_success = await login(page, credentials[0], credentials[1])
                if login_success:
                    # Navigate to the communications tab
                    prog_bar.advance(30)
                    stat_label.update("Accessing config folder...")
        
                    # Find and switch to the tabArea frame
                    frame = page.frame("tabArea")

                    # Find and click the communications tab within the frame
                    comms_tab = await frame.wait_for_selector("#tab4", timeout=default_timeout)
                    await comms_tab.click()

                    # go to the nav frame
                    navigation_frame = page.frame("navigationFrame")
                    await page.wait_for_timeout(1000)
                    
                    # access the Support folder
                    support_folder = await navigation_frame.wait_for_selector("#report164190", timeout=10000)
                    await support_folder.click()

                    if self.mode != Mode.FIRMWARE:
                        # access the Configuration Export/Import
                        config_folder = await navigation_frame.wait_for_selector("#report164400", timeout=10000)
                        await config_folder.click()

                        # Click the enable button 
                        detail_frame = page.frame("detailArea")
                        enable_button = await detail_frame.wait_for_selector("#enableComms")
                        await enable_button.click() 

                        if self.mode == Mode.EXPORT:
                            prog_bar.advance(40)
                            stat_label.update("Retrieving file...")   

                            # download the file by clicking the "Export" button
                            async with page.expect_download() as download:
                                export_button = await detail_frame.wait_for_selector("#commBtn244")
                                await export_button.click() 
                            
                            download_val = await download.value
                            stat_label.update(f"Saving to {download_val.suggested_filename}")
                            # save the file (by default it downloads on the current working folder)
                            await download_val.save_as(download_val.suggested_filename)
                        else: 
                            prog_bar.advance(20)
                            stat_label.update("Setting up...")
                            
                            # Select the import button
                            import_button = await detail_frame.wait_for_selector("#commBtn272")
                            await import_button.click()
                            
                            try:
                                await self.perform_import(detail_frame, page, stat_label, ip, id)
                            except Exception:
                                raise # raise ANY fail with job for a retry in outer except block (TODO: Handle fail_by_import separately, like maybe no retry?)
                    else:
                        try:
                            # Select the firmware update folder                       
                            firmware_folder = await navigation_frame.wait_for_selector("#report164380", timeout=10000)
                            await firmware_folder.click()
                            
                            # Click the enable button 
                            detail_frame = page.frame("detailArea")
                            enable_button = await detail_frame.wait_for_selector("#enableComms")
                            await enable_button.click() 

                            # Select the web option for firmware update
                            web_button = await detail_frame.wait_for_selector("#webFwUpdateBtn")
                            await web_button.click()
                            
                            # handle firmware update
                            await self.perform_firmware_update(page, stat_label, ip, id)
                        except Exception:
                            raise
                    prog_bar.advance(30) 
                    stat_label.update("DONE") 
                    self.success_count += 1
                    break # break off because if we get here, this job is complete!

            except Exception as e:
                retry += 1
                Logger.log(f"An error occured with job {id} [{ip}] : {e}")
                prog_bar.update(total=100, progress=0)
                stat_label.update(f"Job failed. Retry: {retry}/{max_retries}")  
                await asyncio.sleep(5) # let the message show          
            finally: # close the playwright elements before exiting the job
                if context:
                    await context.close()
                if browser:
                    await browser.close()
                if playwright:
                    await playwright.stop()
        

    # When user selects Import, then upload the import file and wait for reboot and completion
    async def perform_import(self, detail_frame, page: Page, stat_label, ip, id, status_element=None):
        
        try:
            detail_frame.locator('div[id="modal-dialog-cfgImport"][class*="active"]').wait_for(state="visible")
            detail_frame.locator('form[name="ImportConfiguration"]').wait_for(state="visible")
            
            #  Click the Browse button and upload the file
            async with page.expect_file_chooser() as fc_info:
                await detail_frame.locator('form[name="ImportConfiguration"] input[value="Browse..."]').click()
            
            # Upload the file
            stat_label.update("Uploading file...")
            self.query_one(f"#{id}", ProgressBar).advance(10) 
            file_chooser = await fc_info.value
            await file_chooser.set_files(self.path_to_config)      
            await detail_frame.evaluate('document.getElementById("ImportCfg").click()')

            # wait for the import status element to be visible
            status_element = detail_frame.locator('div#importCfgStatus')
            await status_element.wait_for(state="visible", timeout=10000)

            # Await a log message
            stat_label.update("Importing configuration changes...")
            await expect(status_element).to_contain_text("Importing configuration settings", timeout=10000, ignore_case=True)

            # Wait for text to indicate a REBOOT (4 min timeout)
            await expect(status_element).to_contain_text("reboot", timeout=240000, ignore_case=True)
            stat_label.update("Rebooting...")
            self.query_one(f"#{id}", ProgressBar).advance(10) 

            #TODO Assuming that like any reboot, it takes you back to http://ip/web/initialize.htm?mode=reboot
            await page.wait_for_url(f"http://{ip}/web/initialize.htm?mode=reboot", timeout=600000)

        except Exception as e:
            
            content = await status_element.text_content()
            if "failed" in content.lower():
                stat_label.update("Import failed. CHK SITE IMPORT LOG.")
                await asyncio.sleep(5)
            Logger.log(f"An error has occured during import operation: {e}")
            raise

    async def perform_firmware_update(self, page: Page, stat_label, ip, id):
        try:
            # wait for the web url to show
            await page.wait_for_url(
                lambda url: url.startswith(f"http://{ip}/protected/firmware/httpFwUpdate.html"), timeout=30000
            )
            
            # wait for the detail panel and form to render
            page.locator('div[id="DetailPanelAreaFwUpdate"][style*="visibility: visible"]').wait_for(state="visible")
            page.locator('form[name="firmwareHttpForm"]').wait_for(state="visible")

            #  Click the Browse button and prep to select file
            async with page.expect_file_chooser() as fc_info:
                await page.locator('form[name="firmwareHttpForm"] input[id="Firmware File Upload"]').click()
            
            stat_label.update("Uploading file...")
            self.query_one(f"#{id}", ProgressBar).advance(5) 
            
            # upload the file
            file_chooser = await fc_info.value
            await file_chooser.set_files(self.path_to_firmware)       
            
            # submit the firmware
            update_button = await page.wait_for_selector("#Submit")
            await update_button.click()

            # Check the stat element when available
            stat_element = page.locator("#updProgressString2")
            await stat_element.wait_for(state="visible", timeout=50000)

            # writing is ready
            await expect(stat_element).to_contain_text("Writing", timeout=600000, ignore_case=True)
            stat_label.update("Writing...")
            self.query_one(f"#{id}", ProgressBar).advance(5)

            # rebooting is set (card firmware successful) May take up to 10 minutes
            await expect(stat_element).to_contain_text("rebooting", timeout=600000, ignore_case=True)
            stat_label.update("Rebooting card...")
            self.query_one(f"#{id}", ProgressBar).advance(10)

            # click on the return button once its enabled (this is the end of operation)
            await page.locator("#GoHomeB").click(timeout=600000)

        except Exception as e:
            
            # multiple errors may occur. for instance,
            # Error: 503 Service Unavailable 
            #    > accompanied by a Message field: (No filename, etc.)
            # Unathorized <h1>, look for single <p> elem to display
            Logger.log(f"An error has occured during firmware update: {e}")
            raise