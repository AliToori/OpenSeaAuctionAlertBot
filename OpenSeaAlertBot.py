#!/usr/bin/env python3
"""
    *******************************************************************************************
    OpenSeaAlertBot: An OpenSea NFT Auction Price Alert Bot
    Author: Ali Toori, Python Developer, Bot Builder
    *******************************************************************************************
"""
import json
import logging.config
import os
import pickle
import random
from datetime import datetime
from multiprocessing import freeze_support
from pathlib import Path
import ntplib
import time
from time import sleep
import concurrent.futures
import requests
import pandas as pd
import pyfiglet
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from selenium import webdriver
from selenium.common.exceptions import WebDriverException
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait


class OpenSeaAlertBot:
    def __init__(self):
        self.PROJECT_ROOT = Path(os.path.abspath(os.path.dirname(__file__)))
        self.file_settings = str(self.PROJECT_ROOT / 'BotRes/Settings.json')
        self.file_nft_alerts = self.PROJECT_ROOT / 'BotRes/NFTAlerts.csv.csv'
        self.OPENSEA_HOME_URL = "https://opensea.io/"
        self.settings = self.get_settings()
        self.client_secret_file_name = self.settings['settings']['ClientSecretFileName']
        self.api_token_chatbot = self.settings['settings']['ChatBotToken']
        self.chat_id = self.settings['settings']['ChatID']
        self.spread_sheet = self.settings['settings']['SpreadSheet']
        self.work_sheet = self.settings['settings']['WorkSheet']
        self.ratio = float(self.settings['settings']['Ratio'])
        self.busd_price = self.settings['settings']['BUSDPrice']
        self.file_client_secret = str(self.PROJECT_ROOT / f'BotRes/{self.client_secret_file_name}')
        self.LOGGER = self.get_logger()
        self.driver = None
        self.spreadsheet_auth = self.get_spreadsheet_auth(spread_sheet=self.spread_sheet)

    # Get self.LOGGER
    @staticmethod
    def get_logger():
        """
        Get logger file handler
        :return: LOGGER
        """
        logging.config.dictConfig({
            "version": 1,
            "disable_existing_loggers": False,
            'formatters': {
                'colored': {
                    '()': 'colorlog.ColoredFormatter',  # colored output
                    # --> %(log_color)s is very important, that's what colors the line
                    'format': '[%(asctime)s,%(lineno)s] %(log_color)s[%(message)s]',
                    'log_colors': {
                        'DEBUG': 'green',
                        'INFO': 'cyan',
                        'WARNING': 'yellow',
                        'ERROR': 'red',
                        'CRITICAL': 'bold_red',
                    },
                },
                'simple': {
                    'format': '[%(asctime)s,%(lineno)s] [%(message)s]',
                },
            },
            "handlers": {
                "console": {
                    "class": "colorlog.StreamHandler",
                    "level": "INFO",
                    "formatter": "colored",
                    "stream": "ext://sys.stdout"
                },
                "file": {
                    "class": "logging.handlers.RotatingFileHandler",
                    "level": "INFO",
                    "formatter": "simple",
                    "filename": "OpenSeaAlertBot.log",
                    "maxBytes": 5 * 1024 * 1024,
                    "backupCount": 3
                },
            },
            "root": {"level": "INFO",
                     "handlers": ["console", "file"]
                     }
        })
        return logging.getLogger()

    @staticmethod
    def enable_cmd_colors():
        # Enables Windows New ANSI Support for Colored Printing on CMD
        from sys import platform
        if platform == "win32":
            import ctypes
            kernel32 = ctypes.windll.kernel32
            kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7)

    @staticmethod
    def banner():
        pyfiglet.print_figlet(text='___________ OpenSeaAlertBot\n', colors='RED')
        print('Author: AliToori, Full-Stack Python Developer\n'
              'Website: https://boteaz.com\n'
              '************************************************************************')

    def get_settings(self):
        """
        Creates default or loads existing settings file.
        :return: settings
        """
        if os.path.isfile(self.file_settings):
            with open(self.file_settings, 'r') as f:
                settings = json.load(f)
            return settings
        settings = {"Settings": {
            "ThreadsCount": 5
        }}
        with open(self.file_settings, 'w') as f:
            json.dump(settings, f, indent=4)
        with open(self.file_settings, 'r') as f:
            settings = json.load(f)
        return settings

    # Get random user-agent
    def get_user_agent(self):
        file_uagents = self.PROJECT_ROOT / 'BotRes/user_agents.txt'
        with open(file_uagents) as f:
            content = f.readlines()
        u_agents_list = [x.strip() for x in content]
        return random.choice(u_agents_list)

    # Get random user-agent
    def get_proxy(self):
        file_proxies = self.PROJECT_ROOT / 'BotRes/proxies.txt'
        with open(file_proxies) as f:
            content = f.readlines()
        proxy_list = [x.strip() for x in content]
        proxy = random.choice(proxy_list)
        self.LOGGER.info(f'Proxy selected: {proxy}')
        return proxy

    # Send Telegram message
    def send_telegram_msg(self, msg):
        self.LOGGER.info(f'Sending Telegram message: {msg}')
        send_text = f'https://api.telegram.org/bot{self.api_token_chatbot}/sendMessage?chat_id={self.chat_id}&text={msg}'
        response = requests.get(str(send_text))
        self.LOGGER.info(f"Telegram message has been sent")
        return response.json()

    # Get web driver
    def get_driver(self, proxy=False, headless=False):
        driver_bin = str(self.PROJECT_ROOT / "BotRes/bin/chromedriver.exe")
        # BRAVE_BIN = str(Path(os.path.abspath("C:/Program Files/BraveSoftware/Brave-Browser/Application/brave.exe")))
        # MAC brave browser exe path
        BRAVE_BIN = "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser"
        service = Service(executable_path=driver_bin)
        options = webdriver.ChromeOptions()
        # Set Brave browser binary chromedriver and Brave browser versions must be compatible
        options.binary_location = BRAVE_BIN
        options.add_argument("--start-maximized")
        options.add_argument("--disable-extensions")
        options.add_argument("--disable-notifications")
        options.add_argument("--disable-blink-features")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-gpu")
        options.add_argument("--dns-prefetch-disable")
        options.add_argument('--ignore-ssl-errors')
        options.add_argument('--ignore-certificate-errors')
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_experimental_option('excludeSwitches', ['enable-logging'])
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option('useAutomationExtension', False)
        prefs = {"profile.default_content_setting_values.geolocation": 2,
                 "profile.managed_default_content_setting_values.images": 2}
        options.add_experimental_option("prefs", prefs)
        options.add_argument(F'--user-agent={self.get_user_agent()}')
        if proxy:
            options.add_argument(f"--proxy-server={self.get_proxy()}")
        if headless:
            options.add_argument('--headless')
        driver = webdriver.Chrome(service=service, options=options)
        return driver

    # Finish and quit browser
    def finish(self, driver):
        try:
            self.LOGGER.info(f'Closing browser')
            driver.close()
            driver.quit()
        except WebDriverException as exc:
            self.LOGGER.info(f'Issue while closing browser: {exc.args}')

    # Check if the page is loaded
    def page_has_loaded(self, driver):
        self.log.info(f"Checking if {driver.current_url} page is loaded.")
        page_state = driver.execute_script('return document.readyState;')
        return page_state == 'complete'

    @staticmethod
    def wait_until_visible(driver, css_selector=None, element_id=None, name=None, class_name=None, tag_name=None, duration=10000, frequency=0.01):
        if css_selector:
            WebDriverWait(driver, duration, frequency).until(EC.visibility_of_element_located((By.CSS_SELECTOR, css_selector)))
        elif element_id:
            WebDriverWait(driver, duration, frequency).until(EC.visibility_of_element_located((By.ID, element_id)))
        elif name:
            WebDriverWait(driver, duration, frequency).until(EC.visibility_of_element_located((By.NAME, name)))
        elif class_name:
            WebDriverWait(driver, duration, frequency).until(
                EC.visibility_of_element_located((By.CLASS_NAME, class_name)))
        elif tag_name:
            WebDriverWait(driver, duration, frequency).until(EC.visibility_of_element_located((By.TAG_NAME, tag_name)))

    # Authenticate to the Google SpreadSheet
    def get_spreadsheet_auth(self, spread_sheet="YN Ratio Sheet"):
        self.LOGGER.info(f'Getting SpreadSheet Auth: {spread_sheet}')
        scope = ["https://spreadsheets.google.com/feeds", 'https://www.googleapis.com/auth/spreadsheets', "https://www.googleapis.com/auth/drive.file", "https://www.googleapis.com/auth/drive"]
        credentials = ServiceAccountCredentials.from_json_keyfile_name(self.file_client_secret, scope)
        spreadsheet_auth = gspread.authorize(credentials)
        return spreadsheet_auth

    # Gets NFT collection information from SpreadSheet
    def get_nft_info(self, spreadsheet_auth, spread_sheet, work_sheet="Sheet1"):
        spreadsheet = spreadsheet_auth.open(spread_sheet)
        worksheet = spreadsheet.worksheet(work_sheet)
        df = pd.DataFrame(worksheet.get_all_records())
        return [profile["Profile"] for profile in df.iloc]

    # Updates Twitter handles in the SpreadSheet using Google Drive API
    def update_spreadsheet(self, df, spread_sheet, work_sheet="Sheet1"):
        self.LOGGER.info(f"Updating Spreadsheet: {spread_sheet}")
        spreadsheet = self.spreadsheet_auth.open(spread_sheet)
        worksheet = spreadsheet.worksheet(work_sheet)

        # Convert DataFrame to String
        # df = df.applymap(str)

        # Get values from each column of the DataFrame
        listing_prices = df["Listing Price"].values.tolist()
        trait_balances = df["Account Value"].values.tolist()
        listing_urls = df["Link"].values.tolist()

        # Select a range of cells of the first three columns to update
        cell_list_column_1 = worksheet.range(f'A2:A{len(listing_prices) + 1}')
        cell_list_column_2 = worksheet.range(f'B2:B{len(listing_prices) + 1}')
        cell_list_column_3 = worksheet.range(f'C2:C{len(listing_prices) + 1}')

        # Assign the values to the cells
        for i, cell_column_1 in enumerate(cell_list_column_1):
            cell_column_1.value = listing_prices[i]
            cell_list_column_2[i].value = trait_balances[i]
            cell_list_column_3[i].value = listing_urls[i]

        # Update in batch
        worksheet.update_cells(cell_list_column_1)
        worksheet.update_cells(cell_list_column_2)
        worksheet.update_cells(cell_list_column_3)

        self.LOGGER.info(f'Updated SpreadSheet: {spread_sheet}: WorkSheet: {work_sheet}')

    def get_nft_alerts(self, collection_url):
        # OpenSea filter to get NFTs on auction or sale
        auction_filer = '?search[toggles][0]=ON_AUCTION'

        self.LOGGER.info(f"Monitoring NFT Collection: {collection_url}")
        driver = self.get_driver()

        # Go to the collection's auction
        driver.get(collection_url + auction_filer)
        sleep(3)

        # Wait for the collection to load
        try:
            self.LOGGER.info(f"Waiting for collection")
            self.wait_until_visible(driver=driver, css_selector='[data-testid="phoenix-header"]', duration=10)
            sleep(3)
            # Scroll to the bottom to view the trait Balance into view
            driver.find_element(By.TAG_NAME, 'html').send_keys(Keys.END)
            driver.find_element(By.TAG_NAME, 'html').send_keys(Keys.END)
        except:
            return

        # Toggle collection to list view
        # try:
        #     sleep(500)
        #     self.LOGGER.info(f"Toggle list view")
        #     self.wait_until_visible(driver=driver, css_selector='[data-testid="list-view-toggle"]', duration=10)
        #     # Click list-view toggle
        #     driver.find_element(By.CSS_SELECTOR, '[data-testid="list-view-toggle"]').click()
        # except:
        #     pass

        # Monitor the NFT prices
        while True:
            # Wait for trait balance
            try:
                self.LOGGER.info(f"Getting trait balance")
                self.wait_until_visible(driver=driver, css_selector='[id="Header trait-filter-balance"] [class="sc-29427738-0 sc-bgqQcB cKdnBO hktnSP"]', duration=10)
                # self.wait_until_visible(driver=driver, css_selector='[id="Header trait-filter-Beard"] [class="sc-29427738-0 sc-bgqQcB cKdnBO hktnSP"]', duration=10)
                sleep(5)
            except:
                return

            # Get trait balance
            trait_balance = int(driver.find_element(By.CSS_SELECTOR, '[id="Header trait-filter-balance"] [class="sc-29427738-0 sc-bgqQcB cKdnBO hktnSP"]').text)
            # trait_balance = float(driver.find_element(By.CSS_SELECTOR, '[id="Header trait-filter-Beard"] [class="sc-29427738-0 sc-bgqQcB cKdnBO hktnSP"]').text.replace(',', ''))

            trait_balances = []
            listing_prices = []
            listing_urls = []

            # Wait for the listing items
            try:
                # Get collection prices
                self.LOGGER.info(f"Waiting for items")
                self.wait_until_visible(driver=driver, tag_name='article', duration=20)
                sleep(3)
            except:
                self.LOGGER.info(f"No item found, going to next cycle")
                sleep(3)
                continue

            # Loop through all the listing prices, send notification if condition is matched
            # for listing_item in driver.find_elements(By.CSS_SELECTOR, '[role="listitem"]'):
            for listing_item in driver.find_elements(By.TAG_NAME, 'article'):
                # Wait and get the listing price
                # self.wait_until_visible(driver=driver, css_selector='[class="sc-8a1b6610-0 irKuNm Price--fiat-amount"]', duration=10)
                self.wait_until_visible(driver=driver, css_selector='[data-testid="ItemCardPrice"] span span', duration=10)
                listing_price = float(listing_item.find_element(By.CSS_SELECTOR, '[data-testid="ItemCardPrice"] span span').text.replace(',', '')) * self.busd_price
                # self.LOGGER.info(f"Listing price: {listing_price}")

                # Get the listing url
                # listing_url = listing_item.find_element(By.CSS_SELECTOR, '[class="sc-1f719d57-0 eiItIQ sc-8421f217-0 ewDElI"]').get_attribute('href')
                # listing_url = listing_item.find_element(By.CSS_SELECTOR, '[data-testid="ItemCardFooter-name"]').get_attribute('href')
                listing_url = listing_item.find_element(By.TAG_NAME, 'a').get_attribute('href')

                # Calculate ratio and send to the spreadsheet along with the listing URL and trait balance
                ratio = round(trait_balance / listing_price, 2)
                self.LOGGER.info(f"Set Ratio: {self.ratio}")
                collection_stats = {"Listing Price": listing_price, "Account Value": trait_balance, "Ratio": ratio, "Link": listing_url}

                # Check if the ratio between trait_balance and listing_price >= 20
                self.LOGGER.info(f"{collection_stats} Condition matched: {ratio >= self.ratio}")
                if ratio >= self.ratio:
                    # Send the dictionary to Telegram ChatBot
                    self.send_telegram_msg(msg=collection_stats)

                # Append values to their respective lists
                listing_prices.append(listing_price)
                trait_balances.append(trait_balance)
                listing_urls.append(listing_url)
            # Create a dictionary of the stats
            collection_stats = {"Listing Price": listing_prices, "Account Value": trait_balances, "Link": listing_urls}
            # self.LOGGER.info(f'Collection Stats: {str(collection_stats)}')
            df = pd.DataFrame(collection_stats)
            # Update the spreadsheet
            self.update_spreadsheet(df=df, spread_sheet=self.spread_sheet, work_sheet=self.work_sheet)
            self.LOGGER.info(f"collection stats have been updated in Spreadsheet: {self.spread_sheet}")

    def main(self):
        freeze_support()
        self.enable_cmd_colors()
        self.banner()
        self.LOGGER.info(f'OpenSeaAlertBot launched')
        collection_url = self.settings["settings"]["CollectionURL"]
        self.get_nft_alerts(collection_url=collection_url)


if __name__ == '__main__':
    OpenSeaAlertBot().main()
