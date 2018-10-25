import os, sys
from PyQt5.QtWidgets import QApplication, QDialog, QGraphicsView, QGraphicsScene
from PyQt5.QtGui import QPixmap, QImage
from PyQt5.QtCore import QSize, Qt, QThread, QTimer, pyqtSignal
from PIL import Image
# Insert GUI library here (Converted with pyuic5)
import ravengui
import requests
from bs4 import BeautifulSoup
import re

class WebPage(QThread):
    signal = pyqtSignal(bool)

    def __init__(self, url, parser="lxml"):
        super().__init__()

        self.url = url
        self.parser = parser
        self.page_text = ""
        self.page_soup = ""
        self.logo = None
        self.loaded = False

    def run(self):
        while True:
            res = self.downloadPage()
            if res:
                self.loaded = True
                self.signal.emit(True)
            else:
                self.loaded = False
            self.sleep(10)

    def downloadPage(self):
        self.page_text = requests.get(self.url).text

        if not len(self.page_text) > 0:
            return False
        else:
            self.page_soup = BeautifulSoup(self.page_text, features=self.parser)
            big_image = self.page_soup.select("meta[property=og:image]")[0]["content"]
            
            if self.logo == None:
                self.logo = requests.get(big_image).content
            
            # Get price and rank
            self.price = self.page_soup.select("span#quote_price")[0].span.text
            self.rank = self.page_soup.select("span.label-success")[0].text.strip().strip("Rank ")

            # First find the section with the pricing information.
            # Then, whittle it down to the sections we need
            details_pane = self.page_soup.select("div.details-panel-item--price")
            price_changes = details_pane[0].select("span[data-format-percentage]")
            self.usd_change = price_changes[0].text + "%"
            self.btc_change = price_changes[1].text + "%"
            # Set the direction variables based on value of class ('positive_change' vs. 'negative_change')
            self.usd_direction = price_changes[0].find_parent()["class"].count("positive_change")
            self.btc_direction = price_changes[1].find_parent()["class"].count("positive_change")

            self.btc_price = self.page_soup.select("span[data-format-price-crypto]")[0].text.strip()
            self.market_cap = self.page_soup.select("span[data-currency-market-cap]")[0]["data-usd"]
            self.volume = self.page_soup.select("span[data-currency-volume]")[0]["data-usd"]
            self.circ_supply = self.page_soup.select("span[data-format-supply]")[0]["data-format-value"]

            self.market_btc = self.page_soup.select("span[data-format-market-cap]")[0].text
            self.volume_btc = self.page_soup.select("span[data-format-volume-crypto]")[0].text

            # TODO: Get network statistics from ravencoin.network
            # TODO: Ravencoin.network uses javascript to load data
            # Cannot get it with requests, but can with selenium.
            # Selenium's requirement to open a browser doesn't work.

            return True


class Window(QDialog):
    def __init__(self):
        super().__init__()

        self.logoDisplayed = False
        self.lastPrice = 0.00

        self.initUI()

        self.cmc_raven = WebPage("https://coinmarketcap.com/currencies/ravencoin/")
        self.cmc_raven.start()

        self.setupEvents()

    def initUI(self):
        self.ui = ravengui.Ui_Dialog()
        self.ui.setupUi(self)
        self.setWindowTitle("The Raven Monitor")
        self.show()

    def setupEvents(self):
        self.cmc_raven.signal.connect(self.dispData)

    def dispLogo(self):           
        scene_pic = QGraphicsScene()
        self.ui.logo.setScene(scene_pic)

        t = QPixmap()
        t.loadFromData(self.cmc_raven.logo)
        t = t.scaled(QSize(70,70), Image.ANTIALIAS)
        scene_pic.addPixmap(t)

    def dispData(self, res="True"):
        if not res:
            return
        if not self.logoDisplayed:
            self.dispLogo()
            self.logoDisplayed = True

        # Get text and display
        price_text = self.cmc_raven.price
        self.ui.price_usd.setText(price_text)
        rank = self.cmc_raven.rank
        self.ui.rank_number.setText(rank)

        # USD % change and coloring
        self.ui.perc_change.setText(self.cmc_raven.usd_change)
        if self.cmc_raven.usd_direction:
            self.ui.perc_change.setStyleSheet("color: green; font-size: 15px;")
        else:
            self.ui.perc_change.setStyleSheet("color: red; font-size: 15px;")

        # BTC price
        self.ui.price_btc.setText(self.cmc_raven.btc_price)


        #TODO: Market cap, volume, and supply percentage
        self.ui.market_cap.setText("${:,.0f}".format(float(self.cmc_raven.market_cap)))
        self.ui.volume.setText("${:,.0f}".format(float(self.cmc_raven.volume)))
        self.ui.supply_amount.setText("{:,.0f}".format(float(self.cmc_raven.circ_supply)))
        self.ui.supply_percent.setValue(float(self.cmc_raven.circ_supply) / 10)

        self.ui.market_btc.setText(self.cmc_raven.market_btc.strip() + " BTC")
        self.ui.volume_btc.setText(self.cmc_raven.volume_btc.strip() + " BTC")

        # Get stylesheet ready for price color change
        price_stylesheet = self.ui.price_usd.styleSheet()
        col_loc = re.search(r"color:.+?;", price_stylesheet)

        if float(price_text) > self.lastPrice:
            self.ui.price_usd.setStyleSheet(price_stylesheet[:col_loc.start()] + "color: green;" + price_stylesheet[col_loc.end():])
        elif float(price_text) < self.lastPrice:
            self.ui.price_usd.setStyleSheet(price_stylesheet[:col_loc.start()] + "color: red;" + price_stylesheet[col_loc.end():])
        else:
            self.ui.price_usd.setStyleSheet(price_stylesheet[:col_loc.start()] + "color: white;" + price_stylesheet[col_loc.end():])

        self.lastPrice = float(price_text)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    gui = Window()
    sys.exit(app.exec_())