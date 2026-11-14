"""An MCP server with one tool: the hryvnia exchange rate set by the National Bank of Ukraine.

    python week10/rates_server.py        # from the repository root; stop with Ctrl+C

It serves http://127.0.0.1:8001/mcp over streamable HTTP. The tool is the agent's
exchange_rate from week9/agent_stack.py, with the same description and the same body:
FastMCP's @mcp.tool takes the place of LangChain's @tool. It needs only an internet
connection.
"""

import logging
import os
from pathlib import Path
from urllib.parse import quote

import requests
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations
from pydantic import Field

PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_ROOT / ".env")


# On Windows, asyncio logs every connection a client resets as an error with a long
# traceback. It is harmless, so it is kept out of the server's log.
logging.getLogger("asyncio").addFilter(
    lambda record: not (record.exc_info and record.exc_info[0] is ConnectionResetError))

mcp = FastMCP("clash-tools", port=8001)


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True))
def battle_damage_calculator(cards, princess_tower, king_tower, dt=0.1):
    """
    Розраховує потенційну шкоду та результат атаки (чи буде 3 корони).
    
    Параметри:
    cards: список кортежів [(dps, hp, count), ...]
    princess_tower: кортеж (dps, hp) для вежі принцеси
    king_tower: кортеж (dps, hp) для вежі короля
    dt: крок симуляції в секундах (0.1 с забезпечує точний розрахунок смерті юнітів)
    """
    # Розгортаємо список карт в окремих юнітів зі збереженням порядку (черги танкування)
    units = []
    for dps, hp, count in cards:
        for _ in range(count):
            units.append({'dps': dps, 'hp': float(hp)})
            
    p_dps, p_hp = princess_tower[0], float(princess_tower[1])
    k_dps, k_hp = king_tower[0], float(king_tower[1])
    
    # Зберігаємо початкове ХП для підрахунку загальної нанесеної шкоди
    initial_p_hp = p_hp
    initial_k_hp = k_hp
    
    princess_alive = True
    time_elapsed = 0.0
    
    # Симуляція триває, поки живі юніти і не впала вежа короля
    while units and k_hp > 0:
        time_elapsed += dt
        
        # 1. Рахуємо сумарний DPS усіх живих юнітів на полі
        total_army_dps = sum(u['dps'] for u in units)
        damage_dealt_this_tick = total_army_dps * dt
        
        # 2. Юніти атакують поточну ціль
        if princess_alive:
            p_hp -= damage_dealt_this_tick
            if p_hp <= 0:
                # Надлишковий урон (overkill) не переноситься, вежа падає
                p_hp = 0
                princess_alive = False
        else:
            k_hp -= damage_dealt_this_tick
            if k_hp <= 0:
                k_hp = 0
                break  # Вежа короля знищена (Three Crown)
                
        # 3. Вежі атакують першого живого юніта в черзі
        if princess_alive:
            incoming_dps = p_dps
        else:
            # Коли перша вежа впала: б'є вежа короля + друга вежа принцеси
            incoming_dps = k_dps + p_dps
            
        damage_taken_this_tick = incoming_dps * dt
        
        # Розподіляємо вхідний урон по черзі юнітів (якщо перший помирає, залишок урону йде наступному)
        while damage_taken_this_tick > 0 and units:
            front_unit = units[0]
            if front_unit['hp'] > damage_taken_this_tick:
                front_unit['hp'] -= damage_taken_this_tick
                damage_taken_this_tick = 0
            else:
                damage_taken_this_tick -= front_unit['hp']
                units.pop(0)  # Юніт вибуває зі списку
                
    # Підрахунок результатів
    damage_to_princess = initial_p_hp - p_hp
    damage_to_king = initial_k_hp - k_hp
    total_damage = damage_to_princess + damage_to_king
    is_three_crown = (k_hp == 0)
    
    return {
        "total_damage": round(total_damage, 1),
        "princess_tower_damage": round(damage_to_princess, 1),
        "king_tower_damage": round(damage_to_king, 1),
        "princess_tower_destroyed": not princess_alive,
        "three_crown": is_three_crown,
        "surviving_units": len(units),
        "battle_duration_sec": round(time_elapsed, 1)
    }


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True))
def get_clash_royale_player(player_tag: str):
    """
    Отримує актуальну інформацію про гравця з офіційного Clash Royale API.
    
    :param player_tag: Тег гравця (наприклад, '#2P0Q8JCUV' або '2P0Q8JCUV')
    :return: Словник з даними гравця або None у разі помилки
    """
    api_key = os.environ.get("ROYALE_API", "").strip()
    if not api_key:
        return {"error": "Змінна середовища ROYALE_API не налаштована на сервері."}
    if api_key.lower().startswith("bearer "):
        api_key = api_key[7:].strip()
    # Очищуємо тег від зайвих пробілів та замінюємо '#' на '%23' для URL
    cleaned_tag = player_tag.strip().upper()
    if not cleaned_tag.startswith("#"):
        cleaned_tag = f"#{cleaned_tag}"
    encoded_tag = quote(cleaned_tag, safe="")
        
    url = f"https://api.clashroyale.com/v1/players/{encoded_tag}"
    
    headers = {
        "Accept": "application/json",
        "Authorization": f"Bearer {api_key}"
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=20)
        
        # Обробка статусів відповіді сервера
        if response.status_code == 200:
            return response.json()
        elif response.status_code == 400:
            return {"error": "400: неправильний формат тегу гравця."}
        elif response.status_code == 403:
            return {
                "error": (
                    "403: API key rejected. Check that the key is active and that "
                    "the MCP server's public IP is allowed in the Clash Royale "
                    "Developer Portal."
                )
            }
        elif response.status_code == 404:
            return {"error": "404: гравця з таким тегом не знайдено."}
        else:
            return {
                "error": f"Clash Royale API returned HTTP {response.status_code}.",
                "details": response.text[:500],
            }
            
    except requests.exceptions.RequestException as e:
        return {"error": f"Помилка мережі під час запиту до Clash Royale API: {e}"}
        
    return {"error": "Clash Royale API returned an empty response."}

if __name__ == "__main__":
    mcp.run(transport="streamable-http")
