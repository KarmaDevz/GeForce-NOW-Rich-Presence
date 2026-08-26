import requests
import logging
import re
from typing import Optional, Tuple

try:
    from bs4 import BeautifulSoup
except ImportError:
    BeautifulSoup = None

logger = logging.getLogger('geforce_presence')

class SteamScraper: 
    def __init__(self, steam_cookie: Optional[str], test_rich_url: str):
        self.test_rich_url = test_rich_url
        self.session = requests.Session()
        if steam_cookie:
            self.session.cookies.set('steamLoginSecure', steam_cookie, domain='steamcommunity.com')
        
        # Headers básicos para parecer un navegador
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
            logger.info("🍪 Cookie de Steam actualizada en el Scraper.")


    def get_rich_presence(self) -> Tuple[Optional[str], Optional[int]]:
        """
        Retorna una tupla (rich_presence_text, group_size)
        """
        if not self.test_rich_url:
            logger.debug("No TEST_RICH_URL configurada.")
            return None, None
        
        try:
            resp = self.session.get(self.test_rich_url, timeout=10)
            if resp.status_code != 200:
                logger.debug("Status != 200 al obtener rich presence")
                return None, None
            
            if "Sign In" in resp.text or "login" in resp.url.lower():
                if not getattr(self, "_steam_expired_warned", False):
                    logger.warning("🔒 Sesión de Steam expirada.")
                    self._steam_expired_warned = True
                return None, None
            else:
                if getattr(self, "_steam_expired_warned", False):
                    logger.info("✅ Sesión de Steam restaurada.")
                    self._steam_expired_warned = False

            rich_presence_text = None
            group_size = None

            if BeautifulSoup is not None:
                soup = BeautifulSoup(resp.text, 'html.parser')
                
                # 1. Obtener el texto de Rich Presence
                # Intentar primero con "Localized Rich Presence Result"
                b = soup.find('b', string=re.compile(r'Localized Rich Presence Result', re.IGNORECASE))
                if b:
                    text = (b.next_sibling or "").strip()
                    if text and '#' not in text and "No rich presence keys set" not in text:
                        rich_presence_text = text

                # Si falla, intentar buscar "status" en la tabla (fallback mas robusto)
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
                                    logger.debug(f"✅ Rich Presence encontrado via fallback 'status': {val}")
                                    break
                
                # 2. Extraer steam_player_group_size
                group_size = self._extract_group_size(soup)
            else:
                # Fallback con Regex si bs4 no está disponible
                m = re.search(r'Localized Rich Presence Result.*?</b>\s*([^<\r\n]+)', resp.text, re.IGNORECASE)
                if m:
                    text = m.group(1).strip()
                    if text and '#' not in text and "No rich presence keys set" not in text:
                        rich_presence_text = text
                if not rich_presence_text:
                    m2 = re.search(r'<td[^>]*>\s*status\s*</td>\s*<td[^>]*>\s*([^<\r\n]+)\s*</td>', resp.text, re.IGNORECASE)
                    if m2:
                        rich_presence_text = m2.group(1).strip()
                
                m_grp = re.search(r'<td[^>]*>\s*steam_player_group_size\s*</td>\s*<td[^>]*>\s*(\d+)\s*</td>', resp.text, re.IGNORECASE)
                if m_grp:
                    try:
                        group_size = int(m_grp.group(1))
                    except ValueError:
                        pass
            
            if rich_presence_text:
                if rich_presence_text != self._last_presence:
                    self._last_presence = rich_presence_text
                    logger.info(f"🎮 Rich Presence (nuevo): {rich_presence_text}")
            
            return rich_presence_text, group_size
            
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
            raise e
        except Exception as e:
            logger.error(f"⚠️ Error scraping Steam: {e}")
            return None, None
    
    def _extract_group_size(self, soup) -> Optional[int]:
        """
        Extrae el valor de steam_player_group_size de la tabla HTML
        """
        group_size = None
        try:
            # Buscar la fila que contiene 'steam_player_group_size'
            rows = soup.find_all('tr')
            for row in rows:
                cells = row.find_all('td')
                if len(cells) >= 2:
                    first_cell_text = cells[0].get_text().strip()
                    if 'steam_player_group_size' in first_cell_text:
                        # El valor está en la segunda celda
                        group_size_text = cells[1].get_text().strip()
                        if group_size_text.isdigit():
                            group_size = int(group_size_text)
                            if group_size != self._last_group_size:
                                self._last_group_size = group_size
                                logger.info(f"👥 Group size detectado: {group_size}")
                            return group_size
            
            # Si no se encuentra steam_player_group_size, buscar patrones alternativos
            #group_size = self._find_alternative_group_size(soup)
            return group_size
            
        except Exception as e:
            logger.debug(f"Error extrayendo group size: {e}")
            return None
    
    def _find_alternative_group_size(self, soup) -> Optional[int]:
        """
        Busca el group size usando métodos alternativos (XPath simulation)
        """
        try:
            # Método 1: Buscar en todas las celdas que puedan contener números de grupo
            cells = soup.find_all('td')
            for cell in cells:
                text = cell.get_text().strip()
                # Buscar patrones como "1/4", "2 players", etc.
                if '/' in text and text.replace('/', '').isdigit():
                    parts = text.split('/')
                    if len(parts) == 2 and parts[0].isdigit():
                        current_players = int(parts[0])
                        logger.info(f"👥 Group size alternativo detectado: {current_players}")
                        return current_players
            
            # Método 2: Buscar números que representen cantidad de jugadores
            for cell in cells:
                text = cell.get_text().strip()
                if text.isdigit():
                    num = int(text)
                    if 1 <= num <= 16:  # Rango razonable para grupos de juego
                        logger.info(f"👥 Group size numérico detectado: {num}")
                        return num
            
            return None
        except Exception as e:
            logger.debug(f"Error en búsqueda alternativa de group size: {e}")
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
        logger.error(f"Error buscando Steam AppID: {e}")
    return None
