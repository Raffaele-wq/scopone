import random
import uuid
import asyncio
from itertools import combinations
from typing import List, Dict, Optional
from fastapi import WebSocket
import scopone_scientifico as sc
import db

class PlayerConn:
    def __init__(self, ws: WebSocket, user_id: str):
        self.ws = ws
        self.user_id = user_id
        self.ready = False

class Room:
    def __init__(self, is_private: bool, bet: int):
        self.id = str(uuid.uuid4())[:6].upper() # 6-char code
        self.is_private = is_private
        self.bet = bet
        self.conns: List[PlayerConn] = []
        self.game_state = sc.GameState()
        self.scores = {0: 0, 1: 0} # Accumulator for multiple rounds up to 21
        self.is_playing = False
        
    async def broadcast(self, message: dict):
        for c in self.conns:
            if c:
                try:
                    await c.ws.send_json(message)
                except:
                    pass

    async def send_to(self, player_idx: int, message: dict):
        if self.conns[player_idx]:
            try:
                await self.conns[player_idx].ws.send_json(message)
            except:
                pass

    async def send_to(self, player_idx: int, message: dict):
        try:
            await self.conns[player_idx].ws.send_json(message)
        except:
            pass

    async def start_match(self, new_round=False):
        self.is_playing = True
        
        # Deduct bets only on first round
        if not new_round:
            for c in self.conns:
                if not c.user_id.startswith("bot_"):
                    db.update_user(c.user_id, {"coins": -self.bet})
            
        # Reset table, played cards, and hands, but keep scores and players
        self.game_state.table = []
        self.game_state.played_cards = []
        self.game_state.absence_memory = {0: set(), 1: set(), 2: set(), 3: set()}
        self.game_state.presence_memory = {0: set(), 1: set(), 2: set(), 3: set()}
        
        for p in self.game_state.players:
            p.captured = []
            p.scopas = 0
            
        deck = [sc.Card(v, s) for s in sc.SUITS for v in sc.VALUES]
        random.shuffle(deck)
        
        for i in range(4):
            self.game_state.players[i].hand = deck[i*10 : (i+1)*10]
            
        if not hasattr(self, 'current_dealer'):
            self.current_dealer = 3
        else:
            self.current_dealer = (self.current_dealer + 1) % 4
            
        self.game_state.turn = (self.current_dealer + 1) % 4
        
        # Send starting hands
        for i in range(4):
            hand_json = [{"value": c.value, "suit": c.suit} for c in self.game_state.players[i].hand]
            usernames = [c.user_id for c in self.conns] # In a real app we'd fetch usernames
            await self.send_to(i, {
                "type": "game_start",
                "hand": hand_json,
                "turn": self.game_state.turn,
                "players": usernames,
                "my_idx": i,
                "scores": self.scores
            })
            
        await self.check_bot_turn()
            
    async def check_bot_turn(self):
        if self.is_playing and self.conns[self.game_state.turn].user_id.startswith("bot_"):
            asyncio.create_task(self.bot_play(self.game_state.turn))
            
    async def bot_play(self, idx: int):
        await asyncio.sleep(1.5)
        # Verify it's still their turn
        if not self.is_playing or self.game_state.turn != idx: return
        
        target_player = self.game_state.players[idx]
        best_c, best_cap, _, _, _ = sc.get_best_move(target_player, self.game_state)
        if best_c:
            await self.process_move(idx, best_c.value, best_c.suit, [cap.value for cap in best_cap], [cap.suit for cap in best_cap])

    async def process_move(self, player_idx: int, card_val: int, card_suit: str, capture_vals: List[int], capture_suits: List[str]):
        if self.game_state.turn != player_idx:
            return False # Not their turn
            
        c = sc.Card(card_val, card_suit)
        caps = [sc.Card(v, s) for v, s in zip(capture_vals, capture_suits)]
        
        # SERVER-SIDE VALIDATION (Anti-Cheat)
        # 1. Check if player has the card
        has_card = any(hc.value == c.value and hc.suit == c.suit for hc in self.game_state.players[player_idx].hand)
        if not has_card:
            return False # Cheat: card not in hand
            
        # 2. Check if capture is legal
        possible_caps = sc.get_possible_captures(c, self.game_state.table)
        
        is_legal_capture = False
        if not possible_caps and not caps:
            is_legal_capture = True
        else:
            for p_cap in possible_caps:
                if len(p_cap) == len(caps) and all(any(pc.value == c_played.value and pc.suit == c_played.suit for pc in p_cap) for c_played in caps):
                    is_legal_capture = True
                    break
                    
        if not is_legal_capture:
            return False # Cheat: illegal capture
        
        # Apply move
        self.game_state.players[player_idx].hand = [hc for hc in self.game_state.players[player_idx].hand if hc.value != c.value or hc.suit != c.suit]
        
        if not hasattr(self.game_state, 'absence_memory'):
            self.game_state.absence_memory = {0: set(), 1: set(), 2: set(), 3: set()}
            self.game_state.presence_memory = {0: set(), 1: set(), 2: set(), 3: set()}
            
        if len(caps) == 0:
            self.game_state.presence_memory[player_idx].add(c.value)
            for r in range(1, len(self.game_state.table) + 1):
                for combo in combinations(self.game_state.table, r):
                    if len(combo) < len(self.game_state.table):
                        tsum = sum(tc.value for tc in combo)
                        if 0 < tsum <= 10: self.game_state.absence_memory[player_idx].add(tsum)
        else:
            if c.value in self.game_state.presence_memory[player_idx]:
                self.game_state.presence_memory[player_idx].remove(c.value)
        
        if len(caps) > 0:
            self.game_state.players[player_idx].captured.append(c)
            self.game_state.players[player_idx].captured.extend(caps)
            
            # Remove from table
            new_table = []
            for tc in self.game_state.table:
                found = False
                for cap in caps:
                    if tc.value == cap.value and tc.suit == cap.suit:
                        found = True
                        break
                if not found:
                    new_table.append(tc)
            self.game_state.table = new_table
            
            # Scopa check
            if len(self.game_state.table) == 0 and len(self.game_state.players[player_idx].hand) > 0:
                self.game_state.players[player_idx].scopas += 1
                
        else:
            self.game_state.table.append(c)
            
        self.game_state.played_cards.append(c)
        
        # Next turn
        self.game_state.turn = (self.game_state.turn + 1) % 4
        
        # Broadcast move
        await self.broadcast({
            "type": "move_played",
            "player_idx": player_idx,
            "card": {"value": c.value, "suit": c.suit},
            "captures": [{"value": cap.value, "suit": cap.suit} for cap in caps],
            "next_turn": self.game_state.turn
        })
        
        # Check end game
        if sum(len(p.hand) for p in self.game_state.players) == 0:
            await self.end_match()
        else:
            await self.check_bot_turn()
            
        return True
        
    async def end_match(self):
        # Calculate points
        t0_caps = self.game_state.players[0].captured + self.game_state.players[2].captured
        t1_caps = self.game_state.players[1].captured + self.game_state.players[3].captured
        
        def get_points(cards, scopas):
            denari = sum(1 for c in cards if c.suit == 'Denari')
            settebello = any(c.value == 7 and c.suit == 'Denari' for c in cards)
            
            primiera = 0
            best_per_suit = {'Denari':0, 'Coppe':0, 'Spade':0, 'Bastoni':0}
            for c in cards:
                if c.value in sc.PRIMIERA_VALUES and sc.PRIMIERA_VALUES[c.value] > best_per_suit[c.suit]:
                    best_per_suit[c.suit] = sc.PRIMIERA_VALUES[c.value]
            primiera = sum(best_per_suit.values())
            
            return len(cards), denari, settebello, primiera, scopas
            
        c0, d0, s0, p0, sc0 = get_points(t0_caps, self.game_state.players[0].scopas + self.game_state.players[2].scopas)
        c1, d1, s1, p1, sc1 = get_points(t1_caps, self.game_state.players[1].scopas + self.game_state.players[3].scopas)
        
        points0 = sc0
        points1 = sc1
        
        if c0 > c1: points0 += 1
        elif c1 > c0: points1 += 1
        
        if d0 > d1: points0 += 1
        elif d1 > d0: points1 += 1
        
        if s0: points0 += 1
        if s1: points1 += 1
        
        if p0 > p1: points0 += 1
        elif p1 > p0: points1 += 1
        
        self.scores[0] += points0
        self.scores[1] += points1
        
        # Distribute pool only if game ends (21 points)
        if self.scores[0] >= 21 or self.scores[1] >= 21:
            pool = self.bet * 4
            winners = []
            if self.scores[0] > self.scores[1]:
                winners = [0, 2]
                win_amount = pool // 2
            elif self.scores[1] > self.scores[0]:
                winners = [1, 3]
                win_amount = pool // 2
            else: # Tie
                winners = [0,1,2,3]
                win_amount = self.bet # Refund
                
            # ELO calculation
            avg_elo0 = sum(db.get_user(self.conns[i].user_id).get("elo", 1200) for i in [0,2] if not self.conns[i].user_id.startswith("bot_")) / 2
            avg_elo1 = sum(db.get_user(self.conns[i].user_id).get("elo", 1200) for i in [1,3] if not self.conns[i].user_id.startswith("bot_")) / 2
            
            expected0 = 1 / (1 + 10 ** ((avg_elo1 - avg_elo0) / 400))
            expected1 = 1 - expected0
            
            K = 32
            elo_delta0, elo_delta1 = 0, 0
            if self.scores[0] > self.scores[1]:
                elo_delta0 = int(K * (1 - expected0))
                elo_delta1 = int(K * (0 - expected1))
            elif self.scores[1] > self.scores[0]:
                elo_delta0 = int(K * (0 - expected0))
                elo_delta1 = int(K * (1 - expected1))
                
            for w in winners:
                if not self.conns[w].user_id.startswith("bot_"):
                    delta = elo_delta0 if w in [0, 2] else elo_delta1
                    user_data = db.get_user(self.conns[w].user_id)
                    db.update_user(self.conns[w].user_id, {"coins": win_amount, "wins": user_data["wins"] + 1, "elo": user_data.get("elo", 1200) + delta})
                
            losers = [i for i in range(4) if i not in winners]
            for l in losers:
                if not self.conns[l].user_id.startswith("bot_"):
                    delta = elo_delta0 if l in [0, 2] else elo_delta1
                    user_data = db.get_user(self.conns[l].user_id)
                    db.update_user(self.conns[l].user_id, {"losses": user_data["losses"] + 1, "elo": max(0, user_data.get("elo", 1200) + delta)})
                
            await self.broadcast({
                "type": "game_over",
                "scores": self.scores,
                "winners": winners,
                "win_amount": win_amount
            })
            self.is_playing = False
        else:
            await self.broadcast({
                "type": "round_over",
                "round_points": {0: points0, 1: points1},
                "total_scores": self.scores
            })
            await asyncio.sleep(3)
            await self.start_match(new_round=True)

class RoomManager:
    def __init__(self):
        self.rooms: Dict[str, Room] = {}
        
    def create_room(self, is_private: bool, bet: int) -> Room:
        r = Room(is_private, bet)
        self.rooms[r.id] = r
        return r
        
    async def join_room(self, ws: WebSocket, user_id: str, is_private: bool, bet: int, room_code: str = ""):
        target_room = None
        if is_private:
            if room_code in self.rooms:
                target_room = self.rooms[room_code]
            else:
                target_room = self.create_room(True, bet)
                # Override ID to requested if it's the host creating it? Actually, wait for client logic.
                # If they pass room_code, try to join. If not found, fail.
                # We need a separate create_private_room flow.
        else:
            # Find public room with same bet and similar ELO
            user_data = db.get_user(user_id) if not user_id.startswith("bot_") else {"elo": 1200}
            user_elo = user_data.get("elo", 1200)
            
            for rid, r in self.rooms.items():
                if not r.is_private and not r.is_playing and len(r.conns) < 4 and r.bet == bet:
                    room_elos = [db.get_user(c.user_id).get("elo", 1200) for c in r.conns if not c.user_id.startswith("bot_")]
                    avg_room_elo = sum(room_elos) / len(room_elos) if room_elos else 1200
                    if abs(avg_room_elo - user_elo) <= 300: # ±300 ELO range for skill-aware matchmaking
                        target_room = r
                        break
            if not target_room:
                target_room = self.create_room(False, bet)
                
        if target_room and not target_room.is_playing and len(target_room.conns) < 4:
            c = PlayerConn(ws, user_id)
            target_room.conns.append(c)
            await target_room.broadcast({
                "type": "room_update",
                "room_id": target_room.id,
                "players": len(target_room.conns)
            })
            
            if len(target_room.conns) == 4:
                await target_room.start_match()
            return target_room
        return None
        
    async def fill_bots(self, room: Room):
        if not room.is_playing and len(room.conns) < 4:
            needed = 4 - len(room.conns)
            for i in range(needed):
                bot_conn = PlayerConn(None, f"bot_{len(room.conns) + 1}")
                room.conns.append(bot_conn)
            
            await room.broadcast({
                "type": "room_update",
                "room_id": room.id,
                "players": len(room.conns)
            })
            await room.start_match()
        
    def disconnect(self, ws: WebSocket):
        for rid, r in list(self.rooms.items()):
            for c in r.conns:
                if c.ws == ws:
                    r.conns.remove(c)
                    if len(r.conns) == 0:
                        del self.rooms[rid]
                    break
