import requests
import logging
import re
from typing import Optional, Tuple
from bs4 import BeautifulSoup

logger = logging.getLogger('geforce_presence')

class SteamScraper: 
    def __init__(self, steam_cookie: Optional[str], test_rich_url: str):
        self.test_rich_url = test_rich_url
        self.session = requests.Session()
        if steam_cookie:
            self.session.cookies.set('steamLoginSecure', steam_cookie, domain='steamcommunity.com')
        
        # Basic headers to look like a browser
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept-Language': 'en-US,en;q=0.9',
        })
        self._last_presence = None
        self._last_group_size = None
        
    def set_cookie(self, steam_cookie: str):
        if steam_cookie:
            self.session.cookies.set('steamLoginSecure', steam_cookie, domain='steamcommunity.com')
            self._steam_expired_warned = False
            logger.info("🍪 Steam cookie updated in Scraper.")


    def get_rich_presence(self) -> Tuple[Optional[str], Optional[int]]:
        """
        Returns a tuple of (rich_presence_text, group_size)
        """
        rich_presence_text = None
        group_size = None
        
        # Extract Steam ID from cookie to enable miniprofile fallback
        steam_id = None
        for cookie in self.session.cookies:
            if cookie.name == 'steamLoginSecure':
                val = cookie.value
                try:
                    if '%7C%7C' in val:
                        steam_id = val.split('%7C%7C')[0].replace('%7C', '')
                    elif '%7C' in val:
                        steam_id = val.split('%7C')[0]
                    else:
                        steam_id = val
                except Exception:
                    pass
                break

        # Attempt 1: Try the testrichpresence page
        if self.test_rich_url:
            try:
                resp = self.session.get(self.test_rich_url, timeout=10)
                if resp.status_code == 200 and "Sign In" not in resp.text and "login" not in resp.url.lower():
                    if getattr(self, "_steam_expired_warned", False):
                        logger.info("✅ Steam session restored.")
                        self._steam_expired_warned = False

                    soup = BeautifulSoup(resp.text, 'html.parser')
                    
                    # 1. Get Rich Presence text
                    b = soup.find('b', string=re.compile(r'Localized Rich Presence Result', re.IGNORECASE))
                    if b:
                        text = (b.next_sibling or "").strip()
                        if text and '#' not in text and "No rich presence keys set" not in text:
                            rich_presence_text = text

                    if not rich_presence_text:
                        rows = soup.find_all('tr')
                        for row in rows:
                            cells = row.find_all('td')
                            if len(cells) >= 2:
                                key = cells[0].get_text().strip().lower()
                                if key == 'status':
                                    val = cells[1].get_text().strip()
                                    if val and '#' not in val:
                                        rich_presence_text = val
                                        logger.debug(f"✅ Rich Presence found via status fallback: {val}")
                                        break
                    
                    group_size = self._extract_group_size(soup)
                else:
                    if not getattr(self, "_steam_expired_warned", False):
                        logger.debug("🔒 Steam developer page session expired or requires login. Using miniprofile fallback.")
            except Exception as e:
                logger.debug(f"⚠️ Error dev page scrape: {e}")

        # Attempt 2: Fallback to scraping miniprofile directly (fully public and robust!)
        if not rich_presence_text and steam_id:
            try:
                miniprofile_url = f"https://steamcommunity.com/miniprofile/{steam_id}"
                r_mini = self.session.get(miniprofile_url, timeout=5)
                if r_mini.status_code == 200:
                    soup_mini = BeautifulSoup(r_mini.text, 'html.parser')
                    rp_span = soup_mini.find('span', class_='rich_presence')
                    if rp_span:
                        val = rp_span.get_text().strip()
                        if val and "No rich presence keys set" not in val:
                            rich_presence_text = val
                            logger.debug(f"✅ Rich Presence obtained via miniprofile: {val}")
                    
                    # Parse group size from rich presence text if available (e.g. "(2 of 4)" or "(2/4)")
                    if rich_presence_text:
                        match = re.search(r'\((\d+)\s*(?:of|/)\s*\d+\)', rich_presence_text, re.IGNORECASE)
                        if match:
                            try:
                                group_size = int(match.group(1))
                            except Exception:
                                pass
            except Exception as e:
                logger.debug(f"⚠️ Error miniprofile fallback scrape: {e}")

        if rich_presence_text:
            if rich_presence_text != self._last_presence:
                self._last_presence = rich_presence_text
                logger.info(f"🎮 Rich Presence (Steam): {rich_presence_text}")
        
        return rich_presence_text, group_size

    
    def _extract_group_size(self, soup) -> Optional[int]:
        """
        Extracts the steam_player_group_size value from the HTML table
        """
        group_size = None
        try:
            # Find row containing 'steam_player_group_size'
            rows = soup.find_all('tr')
            for row in rows:
                cells = row.find_all('td')
                if len(cells) >= 2:
                    first_cell_text = cells[0].get_text().strip()
                    if 'steam_player_group_size' in first_cell_text:
                        # Value is in second cell
                        group_size_text = cells[1].get_text().strip()
                        if group_size_text.isdigit():
                            group_size = int(group_size_text)
                            if group_size != self._last_group_size:
                                self._last_group_size = group_size
                                logger.info(f"👥 Group size detected: {group_size}")
                            return group_size
            
            # If steam_player_group_size not found, check alternative patterns
            #group_size = self._find_alternative_group_size(soup)
            return group_size
            
        except Exception as e:
            logger.debug(f"Error extracting group size: {e}")
            return None
    
    def _find_alternative_group_size(self, soup) -> Optional[int]:
        """
        Looks for group size using alternative methods (XPath simulation)
        """
        try:
            # Method 1: Search in all cells that may contain party sizes
            cells = soup.find_all('td')
            for cell in cells:
                text = cell.get_text().strip()
                # Find patterns like "1/4", "2 players", etc.
                if '/' in text and text.replace('/', '').isdigit():
                    parts = text.split('/')
                    if len(parts) == 2 and parts[0].isdigit():
                        current_players = int(parts[0])
                        logger.info(f"👥 Alternative group size detected: {current_players}")
                        return current_players
            
            # Method 2: Search numbers representing player count
            for cell in cells:
                text = cell.get_text().strip()
                if text.isdigit():
                    num = int(text)
                    if 1 <= num <= 16:  # Rango razonable para grupos de juego
                        logger.info(f"👥 Numeric group size detected: {num}")
                        return num
            
            return None
        except Exception as e:
            logger.debug(f"Error in alternative group size search: {e}")
            return None
            
def find_steam_appid_by_name(game_name: str) -> Optional[str]:
    try:
        url = f"https://steamcommunity.com/actions/SearchApps/{game_name}"
        resp = requests.get(url, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            if data and isinstance(data, list):
                for app in data:
                    if app.get("name", "").lower() == game_name.lower():
                        return str(app.get("appid"))
                if data:    
                    return str(data[0].get("appid"))
    except Exception as e:
        logger.error(f"Error searching Steam AppID: {e}")
    return None
