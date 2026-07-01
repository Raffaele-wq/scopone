import pygame
import accademia
import random
import sys
import os
import math
import threading
import copy
from itertools import combinations

# --- CONFIGURATION ---
WIDTH, HEIGHT = 1200, 800
FPS = 60
CARD_WIDTH, CARD_HEIGHT = 91, 130

# Colors (Dark Elegant)
TEXT_COLOR = (240, 240, 240)
CARD_HIGHLIGHT = (255, 215, 0) # Glowing Gold

# --- CARD & DECK ---
SUITS = ['Denari', 'Coppe', 'Spade', 'Bastoni']
VALUES = list(range(1, 11))
PRIMIERA_VALUES = {7: 21, 6: 18, 1: 16, 5: 15, 4: 14, 3: 13, 2: 12, 8: 10, 9: 10, 10: 10}

WEIGHTS = {
    "BASE_CAPTURE_BONUS": 2.0,
    "PAIR_DISCARD_BONUS": 1.5,
    "SCOPA_BONUS": 30.0,
    "SETTEBELLO_BONUS": 15.0,
    "THREAT_MULTIPLIER": 0.8,
    "SYNERGY_MULTIPLIER": 0.8,
    "PRIMIERA_TIE_MULTIPLIER": 2.0,
    "PRIMIERA_BASE_MULTIPLIER": 0.6
}
NAMES = {1: 'Asso', 2: 'Due', 3: 'Tre', 4: 'Quattro', 5: 'Cinque', 
         6: 'Sei', 7: 'Sette', 8: 'Donna', 9: 'Cavallo', 10: 'Re'}

# --- GLOBALS & CACHE ---
IMAGE_CACHE = {}
BG_SURFACE = None
ANIMATION_STATE = {}

def init_graphics():
    global BG_SURFACE
    BG_SURFACE = pygame.Surface((WIDTH, HEIGHT))
    center_x, center_y = WIDTH // 2, HEIGHT // 2
    max_radius = math.hypot(WIDTH//2, HEIGHT//2)
    
    for r in range(int(max_radius), 0, -2):
        ratio = r / max_radius
        c_r = int(40 * (1 - ratio) + 12 * ratio)
        c_g = int(45 * (1 - ratio) + 12 * ratio)
        c_b = int(55 * (1 - ratio) + 15 * ratio)
        pygame.draw.circle(BG_SURFACE, (c_r, c_g, c_b), (center_x, center_y), r)

def load_images():
    base_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'assets')
    for v in VALUES:
        for s in SUITS:
            filename = f"{v}{s[0].lower()}.jpg"
            full_path = os.path.join(base_path, filename)
            if os.path.exists(full_path):
                img = pygame.image.load(full_path).convert()
                img = pygame.transform.smoothscale(img, (CARD_WIDTH, CARD_HEIGHT))
                IMAGE_CACHE[f"{v}_{s}"] = img

    bg_path = os.path.join(base_path, 'bg.jpg')
    if os.path.exists(bg_path):
        bg_img = pygame.image.load(bg_path).convert()
        IMAGE_CACHE['bg'] = pygame.transform.smoothscale(bg_img, (CARD_WIDTH, CARD_HEIGHT))

def safe_wait(duration_ms, screen=None, state=None):
    start_time = pygame.time.get_ticks()
    clock = pygame.time.Clock()
    btn_pause_rect = pygame.Rect(20, 10, 100, 35)
    btn_xray_rect = pygame.Rect(140, 10, 160, 35)
    btn_tracker_rect = pygame.Rect(320, 10, 160, 35)
    
    while pygame.time.get_ticks() - start_time < duration_ms:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
            if screen and state:
                if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                    show_pause_menu(screen, state)
                    start_time = pygame.time.get_ticks() # Reset wait after unpausing
                elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    if btn_pause_rect.collidepoint(event.pos):
                        show_pause_menu(screen, state)
                        start_time = pygame.time.get_ticks()
                    elif getattr(state, 'game_mode', 'classica') == 'guida':
                        if btn_xray_rect.collidepoint(event.pos):
                            show_xray_popup(screen, state, state.players[0])
                            draw_game_state(screen, state, pygame.mouse.get_pos())
                            pygame.display.flip()
                        elif btn_tracker_rect.collidepoint(event.pos):
                            show_unknown_cards_popup(screen, state.players[0], state)
                            draw_game_state(screen, state, pygame.mouse.get_pos())
                            pygame.display.flip()
        clock.tick(FPS)

def lerp(key, target, speed=0.2):
    current = ANIMATION_STATE.get(key, target)
    if abs(target - current) < 0.5:
        ANIMATION_STATE[key] = target
        return target
    new_val = current + (target - current) * speed
    ANIMATION_STATE[key] = new_val
    return new_val

class Card:
    def __init__(self, value, suit):
        self.value = value
        self.suit = suit
        self.name = f"{NAMES[value]} di {suit}"
        self.uid = f"{value}_{suit}_{id(self)}"
        
    def __repr__(self): return self.name
    def __eq__(self, other): return isinstance(other, Card) and self.value == other.value and self.suit == other.suit
    def __hash__(self): return hash((self.value, self.suit))

class Deck:
    def __init__(self):
        self.cards = [Card(v, s) for s in SUITS for v in VALUES]
        random.shuffle(self.cards)
    def deal(self, players):
        for _ in range(10):
            for p in players: p.hand.append(self.cards.pop())

# --- GAME LOGIC UTILS ---
def get_possible_captures(card, table_cards):
    captures = []
    direct_matches = [c for c in table_cards if c.value == card.value]
    if direct_matches: return [[c] for c in direct_matches]

    for r in range(2, len(table_cards) + 1):
        for combo in combinations(table_cards, r):
            if sum(c.value for c in combo) == card.value:
                captures.append(list(combo))
    return captures

# --- AI & GUIDE ENGINE ---
def get_probability_matrix(state, observer_player, unknown_cards):
    P_matrix = {p.id: {} for p in state.players if p.id != observer_player.id}
    for p_id in P_matrix:
        presence = getattr(state, 'presence_memory', {}).get(p_id, set())
        absence = getattr(state, 'absence_memory', {}).get(p_id, set())
        for c in unknown_cards:
            if c.value in absence: 
                P_matrix[p_id][c] = 0.0 # Absolute mathematical certainty
            else: 
                P_matrix[p_id][c] = 1.0

    for _ in range(20): # Convergenza Sinkhorn-Knopp migliorata
        for p_id in P_matrix:
            row_sum = sum(P_matrix[p_id][c] for c in unknown_cards)
            target = len(state.players[p_id].hand)
            if row_sum > 0:
                for c in unknown_cards: P_matrix[p_id][c] *= (target / row_sum)
        for c in unknown_cards:
            col_sum = sum(P_matrix[p_id][c] for p_id in P_matrix)
            if col_sum > 0:
                for p_id in P_matrix: P_matrix[p_id][c] *= (1.0 / col_sum)
    return P_matrix

def evaluate_move_logic(player, state, card_played, captured, unknown_cards):
    ev = 0
    reasons = []
    new_table = [c for c in state.table if c not in captured]
    
    my_team = player.team
    team_captured = []
    opp_captured = []
    for p in state.players:
        if p.team == my_team:
            team_captured.extend(p.captured)
        else:
            opp_captured.extend(p.captured)
            
    my_7s = sum(1 for c in team_captured if c.value == 7)
    
    my_denari = sum(1 for c in team_captured if c.suit == 'Denari')
    opp_denari = sum(1 for c in opp_captured if c.suit == 'Denari')
    my_cards = len(team_captured)
    opp_cards = len(opp_captured)
    
    if my_denari >= 6 or opp_denari >= 6:
        denari_value = 0.0
    else:
        denari_needed = min(6 - my_denari, 6 - opp_denari)
        if denari_needed <= 1: denari_value = 8.0 
        elif denari_needed <= 2: denari_value = 5.0
        else: denari_value = 3.0
        
    if my_cards >= 21 or opp_cards >= 21:
        cards_value = 0.0
    else:
        cards_needed = min(21 - my_cards, 21 - opp_cards)
        if cards_needed <= 3: cards_value = 1.5
        elif cards_needed <= 6: cards_value = 1.0
        else: cards_value = 0.5

    if not captured:
        old_table_sum = sum(c.value for c in state.table)
        new_table.append(card_played)
        
        P_mat = get_probability_matrix(state, player, unknown_cards)
        next_p_id = (state.turn + 1) % 4
        other_opp_id = (state.turn + 3) % 4
        
        target_val = card_played.value if len(state.table) == 0 else sum(c.value for c in new_table)
        if target_val <= 10:
            exp_next = sum(P_mat[next_p_id].get(c, 0) for c in unknown_cards if c.value == target_val)
            exp_other = sum(P_mat[other_opp_id].get(c, 0) for c in unknown_cards if c.value == target_val)
            opp_capture_prob = min(1.0, exp_next + exp_other - (exp_next * exp_other))
        else:
            opp_capture_prob = 0.0
            
        if card_played.suit == 'Denari':
            if card_played.value == 7:
                penalty = 15.0 + 30.0 * opp_capture_prob
                ev -= penalty
                reasons.append(f"[CONTRO] [SUICIDIO] Scartare il Settebello è vietato! (Rischio immediato: {int(opp_capture_prob*100)}%)")
            else:
                base_penalty = denari_value * 0.8
                risk_penalty = denari_value * 2.0 * opp_capture_prob
                penalty = base_penalty + risk_penalty
                ev -= penalty
                if penalty > 0.5:
                    reasons.append(f"[CONTRO] [PERICOLO DENARI] Scartare {card_played.name} è sempre un malus se i Denari sono contesi (Rischio: {int(opp_capture_prob*100)}%).")
        else:
            if old_table_sum >= 11:
                if card_played.value == 1:
                    ev -= 1.0
                    reasons.append("[CONTRO] [SPRECO DI ASSO] Sbarazzarsi di un Asso non è ottimale.")
                elif card_played.value >= 8:
                    ev -= 2.0
                    reasons.append("[CONTRO] [SPRECO DI SCUDI] Sprechi una figura su un tavolo già sicuro.")
                
        count_in_hand = sum(1 for c in player.hand if c.value == card_played.value)
        if count_in_hand > 1 and len(state.table) > 0:
            ev += WEIGHTS["PAIR_DISCARD_BONUS"]
            reasons.append(f"[PRO] [PARIGLIA] Hai {count_in_hand} carte di {card_played.name}, scarto relativamente sicuro.")
            
        if card_played.value == 7:
            settebello_unknown = any(c.value == 7 and c.suit == 'Denari' for c in unknown_cards)
            base_penalty = 12.0 if settebello_unknown else 3.0
            penalty = base_penalty + (12.0 * opp_capture_prob)
            ev -= penalty
            if settebello_unknown:
                reasons.append(f"[CONTRO] [SANGUE BLU] Scartare un 7 col Settebello in circolo è un suicidio tattico! (Malus: -{penalty:.1f})")
            else:
                reasons.append(f"[CONTRO] [SANGUE BLU] Regali un 7 per la Primiera. (Malus: -{penalty:.1f})")
        elif card_played.value == 6:
            base_penalty = 2.0
            penalty = base_penalty + (6.0 * opp_capture_prob)
            ev -= penalty
            if penalty > 1.0: reasons.append(f"[CONTRO] [RISCHIO PRIMIERA] Lasciare un 6 è pericoloso. (Malus: -{penalty:.1f})")
        elif card_played.value == 1:
            base_penalty = 1.0
            penalty = base_penalty + (4.0 * opp_capture_prob)
            ev -= penalty
            if penalty > 1.0: reasons.append(f"[CONTRO] [RISCHIO PRIMIERA] Lasciare un Asso (Malus: -{penalty:.1f})")
    else:
        ev += len(captured) * cards_value + WEIGHTS["BASE_CAPTURE_BONUS"]
        if len(captured) > 1 and cards_value > 0:
            reasons.append(f"[PRO] [PULIZIA] Catturi {len(captured)} carte contemporaneamente (+EV per il punto delle carte).")
        else:
            reasons.append(f"[PRO] [PRESA] Esegui una presa sicura.")
            
        for c in captured + [card_played]:
            if c.suit == 'Denari':
                ev += denari_value
                if denari_value > 0:
                    reasons.append(f"[PRO] [DENARI] Cattura {c.name} (valore fondamentale per il punto).")
                if c.value == 7: 
                    ev += WEIGHTS["SETTEBELLO_BONUS"]
                    reasons.append("[PRO] [SETTEBELLO] Acquisito il punto più importante del gioco.")
                    
            if c.value in PRIMIERA_VALUES:
                c_val = PRIMIERA_VALUES[c.value]
                
                my_best_suits = {s: max([PRIMIERA_VALUES.get(x.value, 0) for x in team_captured if x.suit == s] + [0]) for s in SUITS}
                opp_best_suits = {s: max([PRIMIERA_VALUES.get(x.value, 0) for x in opp_captured if x.suit == s] + [0]) for s in SUITS}
                
                my_best = my_best_suits[c.suit]
                opp_best = opp_best_suits[c.suit]
                
                direct_gain = max(0, c_val - my_best)
                denial_gain = max(0, c_val - opp_best)
                
                team_captured.append(c)
                
                if direct_gain > 0 or denial_gain > 0:
                    my_best_suits_after = {s: my_best_suits[s] if s != c.suit else max(my_best_suits[s], c_val) for s in SUITS}
                    
                    my_primiera_score = sum(my_best_suits_after.values())
                    opp_primiera_score = sum(opp_best_suits.values())
                    score_diff = my_primiera_score - opp_primiera_score
                    
                    if my_primiera_score >= 84 or opp_primiera_score >= 84:
                        primiera_multiplier = 0.0 # Punto matematicamente deciso
                    elif abs(score_diff) > 25:
                        primiera_multiplier = 0.2 # Vantaggio/svantaggio ormai elevato
                    elif abs(score_diff) > 10:
                        primiera_multiplier = 0.5
                    elif my_primiera_score == opp_primiera_score and my_primiera_score > 60:
                        primiera_multiplier = WEIGHTS.get("PRIMIERA_TIE_MULTIPLIER", 2.0)
                    else:
                        primiera_multiplier = WEIGHTS.get("PRIMIERA_BASE_MULTIPLIER", 1.0)
                        
                    bonus = (direct_gain * 1.0 + denial_gain * 0.8) * primiera_multiplier
                    
                    if my_best == 0:
                        available_in_suit = sum(1 for x in unknown_cards + player.hand if x.suit == c.suit)
                        if available_in_suit <= 2:
                            bonus += 5.0
                            reasons.append(f"[PRO] [SEME MANCANTE CRITICO] Catturi il primo {c.suit}, ne restano solo {available_in_suit}!")
                        elif available_in_suit <= 5:
                            bonus += 2.0
                            reasons.append(f"[PRO] [SEME MANCANTE] Catturi il primo {c.suit}.")
                        else:
                            bonus += 0.5
                            reasons.append(f"[PRO] [SEME MANCANTE] Catturi il primo {c.suit} (ma ce ne sono ancora {available_in_suit}).")
                    
                    if bonus > 0:
                        ev += bonus
                        if direct_gain > 0:
                            reasons.append(f"[PRO] [PRIMIERA] Acquisito {c.name} (Punti primiera netti: +{direct_gain}).")
                        else:
                            reasons.append(f"[PRO] [NEGAZIONE] {c.name} sottratto agli avversari (Danno primiera: {denial_gain}).")
            
        if not new_table and sum(len(p.hand) for p in state.players) > 1:
            ev += WEIGHTS["SCOPA_BONUS"]
            reasons.append("[PRO] [SCOPA] Realizza una Scopa matematica (+1 Punto).")

    table_sum = sum(c.value for c in new_table)
    next_p_id = (state.turn + 1) % 4
    next_is_opp = (state.players[next_p_id].team != player.team)
    
    absence_mem = getattr(state, 'absence_memory', {0:set(), 1:set(), 2:set(), 3:set()})
    presence_mem = getattr(state, 'presence_memory', {0:set(), 1:set(), 2:set(), 3:set()})
    teammate_id = (player.id + 2) % 4
    
    if next_is_opp and len(new_table) > 0:
        if len(state.table) == 0:
            count_in_hand = sum(1 for c in player.hand if c.value == card_played.value)
            
            P_mat = get_probability_matrix(state, player, unknown_cards)
            other_opp_id = (state.turn + 3) % 4
            exp_next = sum(P_mat[next_p_id].get(c, 0) for c in unknown_cards if c.value == card_played.value)
            exp_other = sum(P_mat[other_opp_id].get(c, 0) for c in unknown_cards if c.value == card_played.value)
            total_opp_risk = exp_next + exp_other
            
            if count_in_hand > 1 and total_opp_risk < 0.05 and len(player.hand) < 10:
                ev += 15.0
                reasons.append(f"[PRO] [PALO A TERRA] Crei un palo di {card_played.name}. La memoria deduce che gli avversari non ce l'hanno.")
            elif len(player.hand) == 10:
                risk_discount = max(0.0, 1.0 - total_opp_risk * 3.0)
                ev += (count_in_hand * 15.0 * risk_discount)
                if total_opp_risk > 0.15:
                    ev -= (total_opp_risk * 100 * 0.3)
                    reasons.append(f"[CONTRO] [RISCHIO SCOPA IN APERTURA] Rischio stimato: {int(total_opp_risk*100)}%.")
                else:
                    reasons.append(f"[PRO] [APERTURA] Giocare un {card_played.name} (ne hai {count_in_hand}) è relativamente sicuro (rischio {int(total_opp_risk*100)}%).")
            else:
                if total_opp_risk < 0.02:
                    ev += 8.0
                    reasons.append(f"[PRO] [SCARTO SICURO] Memoria Deduttiva: è quasi impossibile che gli avversari facciano scopa.")
                else:
                    risk_pct = int(total_opp_risk * 100)
                    ev -= (risk_pct * 0.2)
                    reasons.append(f"[CONTRO] [RISCHIO SCOPA DIRETTO] Rischio di Scopa avversaria stimato ({risk_pct}% prob).")
            
            P_mat = get_probability_matrix(state, player, unknown_cards)
            exp_team = sum(P_mat[teammate_id].get(c, 0) for c in unknown_cards if c.value == table_sum)
            if exp_team > 0.15:
                ev += (exp_team * 0.1)
                reasons.append(f"[PRO] [ASSIST] Il compagno ha il {int(exp_team*100)}% di probabilità di avere un {table_sum}.")

        else:
            P_mat = get_probability_matrix(state, player, unknown_cards)
            
            can_be_captured_by = [v for v in range(1, 11) if get_possible_captures(Card(v, 'Denari'), new_table)]
            
            total_threat_ev = 0.0
            num_threats = 0
            for v in can_be_captured_by:
                exp_next = sum(P_mat[next_p_id].get(c, 0) for c in unknown_cards if c.value == v)
                other_opp_id = (state.turn + 3) % 4
                exp_other = sum(P_mat[other_opp_id].get(c, 0) for c in unknown_cards if c.value == v)
                prob = min(1.0, exp_next * 1.0 + exp_other * 0.5)
                
                if prob > 0.02:
                    num_threats += 1
                    threat_severity = 0
                    if any(c.value == v for c in new_table):
                        threat_severity += sum(c.value for c in new_table if c.value == v)
                    else:
                        threat_severity += table_sum
                    
                    if any(c.suit == 'Denari' for c in new_table): threat_severity += 5.0
                    if v == table_sum: threat_severity += WEIGHTS.get("SCOPA_BONUS", 30.0)
                    
                    total_threat_ev += threat_severity * prob
            
            if num_threats > 0:
                risk_penalty = total_threat_ev * WEIGHTS.get("THREAT_MULTIPLIER", 0.8)
                ev -= risk_penalty
                
                if risk_penalty > 1.0:
                    if num_threats > 1:
                        reasons.append(f"[CONTRO] [RISCHIO PRESA MULTIPLA] Il tavolo è vulnerabile a {num_threats} possibili prese avversarie (Malus: -{risk_penalty:.1f}).")
                    else:
                        reasons.append(f"[CONTRO] [RISCHIO SCOPA DIRETTO] Hai esposto il tavolo a una scopa diretta molto probabile (Malus: -{risk_penalty:.1f}).")
            else:
                ev += 5.0
                reasons.append(f"[PRO] [TAVOLO BLINDATO] Il tavolo {table_sum} è matematicamente o probabilisticamente inattaccabile dagli avversari.")

            exp_team = 0
            for v in can_be_captured_by:
                exp_team += sum(P_mat[teammate_id].get(c, 0) for c in unknown_cards if c.value == v)
            if exp_team > 0.2:
                ev += (exp_team * 2.0)
                reasons.append(f"[PRO] [COSTRUZIONE] Stai offrendo in media {exp_team:.1f} carte utili di appoggio al compagno.")

    if not captured:
        my_caffi = sum(1 for c in player.hand if c.value == card_played.value) - 1
        my_caffi += sum(1 for p in state.players if p.team == player.team for c in p.captured if c.value == card_played.value)
        teammate_id = (player.id + 2) % 4
        my_caffi += sum(P_mat[teammate_id].get(c, 0) for c in unknown_cards if c.value == card_played.value)
        
        opp_caffi = sum(1 for p in state.players if p.team != player.team for c in p.captured if c.value == card_played.value)
        # Stima delle carte in mano agli avversari tramite matrice di probabilità
        for p in state.players:
            if p.team != player.team:
                opp_caffi += sum(P_mat[p.id].get(c, 0) for c in unknown_cards if c.value == card_played.value)
                
        diff = my_caffi - opp_caffi
        
        if player.team == getattr(state, 'starting_team', 0): 
            if diff > 0:
                ev += 2.0 * diff
                reasons.append(f"[PRO] [CAFFO] Sei 'Di Mano': sbilanci il tavolo (+{diff} caffi).")
            elif diff < 0:
                ev -= 1.0 * abs(diff)
                reasons.append(f"[CONTRO] [PERDITA CAFFO] Sei 'Di Mano': pareggi {abs(diff)} carte avvantaggiando il Mazziere.")
        else:
            if diff < 0:
                ev += 3.0 * abs(diff)
                reasons.append(f"[PRO] [PAREGGIO MIRATO] Sei 'Mazziere': annulli {abs(diff)} caffi per dominare i resti.")
            elif diff > 0:
                ev -= 1.5 * diff
                reasons.append(f"[CONTRO] [SPARIGLIO] Sei 'Mazziere', ma stai creando {diff} nuovi caffi.")
                
    final_reason = "\n".join(list(dict.fromkeys(reasons)))
    if not final_reason:
        final_reason = "È la mossa statisticamente più sicura e neutra calcolata sulle probabilità residue."
        
    return ev / 10.0, final_reason



def is_endgame(player):
    return len(player.hand) <= 3

def is_critical(state, player):
    if not state.table:
        return True # Aperture sono sempre critiche per il rischio scopa
    table_sum = sum(c.value for c in state.table)
    if table_sum <= 10:
        return True
    if any(c.suit == 'Denari' for c in state.table):
        return True
    primiera_vals = {7: 21, 6: 18, 1: 16, 5: 15, 4: 14, 3: 13, 2: 12}
    if any(c.value in primiera_vals for c in state.table):
        return True
    return False

def fast_policy(player, state, unknown_cards):
    best_card, best_cap, max_ev = None, None, -float('inf')
    for card in player.hand:
        caps = get_possible_captures(card, state.table)
        caps_to_check = caps if caps else [[]]
        for cap in caps_to_check:
            # Using internal evaluate_move_logic (same as ai_v1)
            ev, _ = evaluate_move_logic(player, state, card, cap, unknown_cards)
            if ev > max_ev:
                max_ev = ev
                best_card = card
                best_cap = cap
    return best_card, best_cap

def get_best_move(player, state):
    all_cards = [Card(v, s) for s in SUITS for v in VALUES]
    known_cards = set(player.hand + state.table + state.played_cards)
    unknown_cards = [c for c in all_cards if c not in known_cards]

    # --- LIVELLO 3: PIMC SOLO ENDGAME ---
    if is_endgame(player):
        import ai_v2
        return ai_v2.get_best_move_v2(player, state)
        
    # --- LIVELLO 2: LOOKAHEAD LEGGERO ---
    if is_critical(state, player):
        return get_lookahead_move(player, state)
        
    # --- LIVELLO 1: POLICY BASE ---
    best_c, best_cap = fast_policy(player, state, unknown_cards)
    return best_c, best_cap, 0, "L1_FAST", {}

def get_lookahead_move(player, state):

    best_card, best_capture, max_ev, best_reason = None, None, -float('inf'), ""
    all_cards = [Card(v, s) for s in SUITS for v in VALUES]
    known_cards = set(player.hand + state.table + state.played_cards)
    unknown_cards = [c for c in all_cards if c not in known_cards]

    all_evals = {}
    P_mat = get_probability_matrix(state, player, unknown_cards)
    next_p_id = (state.turn + 1) % 4
    partner_p_id = (state.turn + 2) % 4
    
    for card in player.hand:
        captures = get_possible_captures(card, state.table)
        caps_to_check = captures if captures else [[]]
        
        for cap in caps_to_check:
            ev, reason = evaluate_move_logic(player, state, card, cap, unknown_cards)
            
            # --- DEPTH-2 SIMULATION (Opponent Threat & Partner Synergy) ---
            new_table = [c for c in state.table if c not in cap]
            if not cap: new_table.append(card)
            
            opp_threat = 0.0
            partner_synergy = 0.0
            
            if new_table:
                for uc in unknown_cards:
                    uc_caps = get_possible_captures(uc, new_table)
                    if uc_caps:
                        best_cap_ev = 0.0
                        for ucap in uc_caps:
                            cap_ev = len(ucap) * 0.5 + WEIGHTS["BASE_CAPTURE_BONUS"]
                            if len(new_table) == len(ucap): cap_ev += WEIGHTS["SCOPA_BONUS"] # SCOPA minaccia
                            for c in ucap + [uc]:
                                if c.suit == 'Denari':
                                    cap_ev += 4.0
                                    if c.value == 7: cap_ev += WEIGHTS["SETTEBELLO_BONUS"]
                                if c.value == 7: cap_ev += 3.0
                                elif c.value == 6: cap_ev += 1.5
                                elif c.value == 1: cap_ev += 1.0
                            if cap_ev > best_cap_ev: best_cap_ev = cap_ev
                            
                        best_cap_ev /= 10.0
                        
                        prob_opp_next = min(1.0, P_mat[next_p_id].get(uc, 0.0))
                        other_opp_id = (state.turn + 3) % 4
                        prob_opp_other = min(1.0, P_mat[other_opp_id].get(uc, 0.0))
                        prob_opp_total = min(1.0, prob_opp_next * 1.0 + prob_opp_other * 0.5)
                        prob_partner = min(1.0, P_mat[partner_p_id].get(uc, 0.0))
                        
                        opp_threat += prob_opp_total * best_cap_ev
                        partner_synergy += (1.0 - prob_opp_total) * prob_partner * best_cap_ev
            
            
            total_cards_left = sum(len(p.hand) for p in state.players)
            if total_cards_left > 24: # Inizio partita
                dyn_synergy, dyn_threat = 0.3, 0.3
            elif total_cards_left > 12: # Metà partita
                dyn_synergy, dyn_threat = 0.8, 0.8
            else: # Finale
                dyn_synergy, dyn_threat = 1.3, 1.3
                
            ev = ev - (opp_threat * dyn_threat) + (partner_synergy * dyn_synergy)
            
            reasons_list = [reason] if reason and reason != "È la mossa statisticamente più sicura e neutra calcolata sulle probabilità residue." else []
            if opp_threat > 0.5: reasons_list.append(f"[CONTRO] [MINACCIA] Lasci il tavolo esposto (Rischio: -{opp_threat:.1f} EV).")
            if partner_synergy > 0.5: reasons_list.append(f"[PRO] [SINERGIA COMPAGNO] Prepari il tavolo per il compagno (Potenziale: +{partner_synergy:.1f} EV).")
            
            final_reason = "\n".join(reasons_list)
            if not final_reason: final_reason = "Mossa calcolata bilanciando rischi e sinergie a profondità 2."
            
            all_evals[(card, tuple(cap))] = (ev, final_reason)
            if ev > max_ev: max_ev, best_card, best_capture, best_reason = ev, card, cap, final_reason
                
    return best_card, best_capture, max_ev, best_reason, all_evals


# --- PLAYER CLASSES ---
class Player:
    def __init__(self, name, p_id, team):
        self.name = name
        self.id = p_id
        self.team = team
        self.hand = []
        self.captured = []
        self.scopas = 0
        self.scopas = 0

    def get_hand_pos(self, index, total):
        if self.id == 0: 
            w = total * (CARD_WIDTH + 5)
            start_x = WIDTH//2 - w//2
            return (start_x + index * (CARD_WIDTH + 5), HEIGHT - CARD_HEIGHT - 60)
        elif self.id == 1: return (30, HEIGHT//2 - (total*30)//2 + index*30)
        elif self.id == 2: return (WIDTH//2 - (total*40)//2 + index*40, 60)
        elif self.id == 3: return (WIDTH - 30 - CARD_WIDTH, HEIGHT//2 - (total*30)//2 + index*30)

    def get_pile_pos(self):
        if self.id == 0: return (WIDTH//2, HEIGHT + 100)
        elif self.id == 1: return (-100, HEIGHT//2)
        elif self.id == 2: return (WIDTH//2, -100)
        elif self.id == 3: return (WIDTH + 100, HEIGHT//2)


# --- GAME STATE ---
class GameState:
    def __init__(self):
        self.players = [
            Player("Tu", 0, 0), Player("Bot Sinistra", 1, 1),
            Player("Bot Alleato", 2, 0), Player("Bot Destra", 3, 1)
        ]
        self.table = []
        self.played_cards = []
        self.turn = 0
        self.last_taker = None
        self.scores = {0: 0, 1: 0}
        self.accademia_history = []

    def reset_round(self, starting_player):
        self.deck = Deck()
        self.table, self.played_cards = [], []
        for p in self.players:
            p.hand, p.captured, p.scopas = [], [], 0
        self.deck.deal(self.players)
        self.turn = starting_player
        self.starting_team = self.players[starting_player].team
        self.dealer_team = self.players[(starting_player - 1) % 4].team
        self.last_taker = None
        self.absence_memory = {0: set(), 1: set(), 2: set(), 3: set()}
        self.presence_memory = {0: set(), 1: set(), 2: set(), 3: set()}
        self.unbalanced_values = set()

    def clone(self):
        new_st = GameState()
        new_st.table = [Card(c.value, c.suit) for c in self.table]
        new_st.played_cards = [Card(c.value, c.suit) for c in self.played_cards]
        new_st.turn = self.turn
        new_st.last_taker = self.last_taker
        new_st.starting_team = getattr(self, 'starting_team', 0)
        new_st.absence_memory = {k: set(v) for k, v in getattr(self, 'absence_memory', {0:set(), 1:set(), 2:set(), 3:set()}).items()}
        new_st.presence_memory = {k: set(v) for k, v in getattr(self, 'presence_memory', {0:set(), 1:set(), 2:set(), 3:set()}).items()}
        new_st.unbalanced_values = set(getattr(self, 'unbalanced_values', set()))
        
        for i, p in enumerate(self.players):
            new_st.players[i].hand = [Card(c.value, c.suit) for c in p.hand]
            new_st.players[i].captured = [Card(c.value, c.suit) for c in p.captured]
            new_st.players[i].scopas = p.scopas
        return new_st

    def get_table_pos(self, index, total):
        w = total * (CARD_WIDTH + 15)
        start_x = WIDTH//2 - w//2
        return (start_x + index * (CARD_WIDTH + 15), HEIGHT//2 - CARD_HEIGHT//2 - 15)

    def calculate_round_score(self):
        punti = {0: 0, 1: 0}
        
        scopas_t0 = self.players[0].scopas + self.players[2].scopas
        scopas_t1 = self.players[1].scopas + self.players[3].scopas
        punti[0] += scopas_t0
        punti[1] += scopas_t1
        
        cards_t0 = self.players[0].captured + self.players[2].captured
        cards_t1 = self.players[1].captured + self.players[3].captured

        pt_carte_0 = 1 if len(cards_t0) > 20 else 0
        pt_carte_1 = 1 if len(cards_t1) > 20 else 0
        punti[0] += pt_carte_0; punti[1] += pt_carte_1

        den_t0 = sum(1 for c in cards_t0 if c.suit == 'Denari')
        den_t1 = sum(1 for c in cards_t1 if c.suit == 'Denari')
        pt_den_0 = 1 if den_t0 > 5 else 0
        pt_den_1 = 1 if den_t1 > 5 else 0
        punti[0] += pt_den_0; punti[1] += pt_den_1

        pt_sette_0 = 1 if any(c.value == 7 and c.suit == 'Denari' for c in cards_t0) else 0
        pt_sette_1 = 1 if any(c.value == 7 and c.suit == 'Denari' for c in cards_t1) else 0
        punti[0] += pt_sette_0; punti[1] += pt_sette_1

        def get_primiera(cards):
            best = {'Denari': 0, 'Coppe': 0, 'Spade': 0, 'Bastoni': 0}
            for c in cards:
                if PRIMIERA_VALUES[c.value] > best[c.suit]: best[c.suit] = PRIMIERA_VALUES[c.value]
            return sum(best.values()) if 0 not in best.values() else 0

        prim_t0, prim_t1 = get_primiera(cards_t0), get_primiera(cards_t1)
        pt_prim_0 = 1 if prim_t0 > prim_t1 else 0
        pt_prim_1 = 1 if prim_t1 > prim_t0 else 0
        punti[0] += pt_prim_0; punti[1] += pt_prim_1
        
        self.scores[0] += punti[0]
        self.scores[1] += punti[1]
        
        return {
            0: {'carte': (len(cards_t0), pt_carte_0), 'denari': (den_t0, pt_den_0), 'settebello': pt_sette_0, 'primiera': (prim_t0, pt_prim_0), 'scopas': scopas_t0, 'round_total': punti[0]},
            1: {'carte': (len(cards_t1), pt_carte_1), 'denari': (den_t1, pt_den_1), 'settebello': pt_sette_1, 'primiera': (prim_t1, pt_prim_1), 'scopas': scopas_t1, 'round_total': punti[1]}
        }

# --- UI RENDERING ---
def draw_shadow(surface, rect, radius=8, offset=(5, 5), alpha=100):
    shadow = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
    pygame.draw.rect(shadow, (0, 0, 0, alpha), shadow.get_rect(), border_radius=radius)
    surface.blit(shadow, (rect.x + offset[0], rect.y + offset[1]))

def draw_dynamic_panel(surface, text, center_x, center_y, color=TEXT_COLOR, size=22, bold=False):
    font = pygame.font.SysFont('Segoe UI, San Francisco, Arial', size, bold=bold)
    img = font.render(text, True, color)
    rect = img.get_rect(center=(center_x, center_y))
    
    panel = pygame.Surface((rect.width + 30, rect.height + 20), pygame.SRCALPHA)
    pygame.draw.rect(panel, (20, 25, 30, 200), panel.get_rect(), border_radius=10)
    pygame.draw.rect(panel, (100, 110, 120, 90), panel.get_rect(), border_radius=10, width=1)
    surface.blit(panel, (rect.x - 15, rect.y - 10))
    surface.blit(img, rect)

def draw_top_right_panel(surface, text, right_x, center_y, color=TEXT_COLOR, size=22, bold=False):
    font = pygame.font.SysFont('Segoe UI, San Francisco, Arial', size, bold=bold)
    img = font.render(text, True, color)
    rect = img.get_rect(midright=(right_x - 15, center_y))
    
    panel = pygame.Surface((rect.width + 30, rect.height + 20), pygame.SRCALPHA)
    pygame.draw.rect(panel, (20, 25, 30, 200), panel.get_rect(), border_radius=10)
    pygame.draw.rect(panel, (100, 110, 120, 90), panel.get_rect(), border_radius=10, width=1)
    surface.blit(panel, (rect.x - 15, rect.y - 10))
    surface.blit(img, rect)

def draw_score_panel(surface, state):
    font = pygame.font.SysFont('Segoe UI, San Francisco, Arial', 20, bold=True)
    img1 = font.render(f"Team 0 (Tu/Alleato): {state.scores[0]}", True, CARD_HIGHLIGHT)
    img2 = font.render(f"Team 1 (Avversari): {state.scores[1]}", True, (255, 100, 100))
    
    w = max(img1.get_width(), img2.get_width()) + 30
    h = 80
    
    panel = pygame.Surface((w, h), pygame.SRCALPHA)
    pygame.draw.rect(panel, (20, 25, 30, 200), panel.get_rect(), border_radius=10)
    pygame.draw.rect(panel, (100, 110, 120, 90), panel.get_rect(), border_radius=10, width=1)
    
    surface.blit(panel, (20, 20))
    surface.blit(img1, (35, 35))
    surface.blit(img2, (35, 65))

def draw_card(surface, x, y, card, is_selected=False, is_hovered=False, hidden=False):
    rect = pygame.Rect(x, y, CARD_WIDTH, CARD_HEIGHT)
    shadow_offset = (6, 6) if is_hovered else (4, 4)
    shadow_alpha = 150 if is_hovered else 100
    draw_shadow(surface, rect, radius=8, offset=shadow_offset, alpha=shadow_alpha)
    
    if hidden:
        if 'bg' in IMAGE_CACHE: surface.blit(IMAGE_CACHE['bg'], (x, y))
        else: pygame.draw.rect(surface, (100, 100, 100), rect, border_radius=8)
    else:
        key = f"{card.value}_{card.suit}"
        if key in IMAGE_CACHE: surface.blit(IMAGE_CACHE[key], (x, y))
        else: pygame.draw.rect(surface, (200,200,200), rect)
    
    if is_selected:
        glow = pygame.Surface((CARD_WIDTH+10, CARD_HEIGHT+10), pygame.SRCALPHA)
        pygame.draw.rect(glow, (*CARD_HIGHLIGHT, 200), glow.get_rect(), border_radius=10, width=4)
        surface.blit(glow, (x-5, y-5))
    elif is_hovered:
        glow = pygame.Surface((CARD_WIDTH+6, CARD_HEIGHT+6), pygame.SRCALPHA)
        pygame.draw.rect(glow, (255, 255, 255, 150), glow.get_rect(), border_radius=8, width=2)
        surface.blit(glow, (x-3, y-3))

def draw_modern_button(surface, text, rect, is_hovered, font_size=20):
    color = (255, 225, 50) if is_hovered else (200, 160, 40)
    shadow_rect = rect.copy()
    shadow_rect.y += 3
    pygame.draw.rect(surface, (0, 0, 0, 100), shadow_rect, border_radius=8)
    pygame.draw.rect(surface, color, rect, border_radius=8)
    pygame.draw.rect(surface, (255, 255, 255, 100), rect, border_radius=8, width=1)
    
    font = pygame.font.SysFont('Segoe UI, San Francisco, Arial', font_size, bold=True)
    img = font.render(text, True, (20, 20, 20))
    img_rect = img.get_rect(center=rect.center)
    surface.blit(img, img_rect)

def draw_reasoning_block(screen, font, reason, start_y, base_color=(240,240,240)):
    reasons_list = reason.split(" | ")
    for r_line in reasons_list:
        words = r_line.split(" ")
        lines, current_line = [], ""
        for w in words:
            if len(current_line) + len(w) > 85:
                lines.append(current_line); current_line = w + " "
            else: current_line += w + " "
        lines.append(current_line)
        
        for j, line in enumerate(lines):
            color_txt = base_color if j == 0 else (180, 180, 180)
            prefix = "• " if j == 0 else "  "
            img_line = font.render(prefix + line, True, color_txt)
            screen.blit(img_line, (WIDTH//2 - 380, start_y))
            start_y += 28
        start_y += 12
    return start_y

def show_guide_popup(screen, expected_card, expected_capture, best_reason, played_card, user_reason):
    overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    overlay.fill((0, 0, 0, 240))
    screen.blit(overlay, (0, 0))
    
    panel_rect = pygame.Rect(WIDTH//2 - 450, HEIGHT//2 - 360, 900, 700)
    pygame.draw.rect(screen, (25, 30, 35), panel_rect, border_radius=15)
    pygame.draw.rect(screen, CARD_HIGHLIGHT, panel_rect, border_radius=15, width=2)
    
    draw_dynamic_panel(screen, "REPORT IA - ANALISI MOSSA", WIDTH//2, HEIGHT//2 - 330, color=(255, 170, 100), size=26, bold=True)
    font = pygame.font.SysFont('Segoe UI, San Francisco, Arial', 22)
    
    # -- La tua mossa --
    img_you = font.render(f"La tua mossa: {played_card.name}", True, (255, 100, 100))
    screen.blit(img_you, img_you.get_rect(center=(WIDTH//2, HEIGHT//2 - 270)))
    
    img_user_why = font.render("Analisi della tua mossa:", True, (255, 150, 150))
    screen.blit(img_user_why, img_user_why.get_rect(center=(WIDTH//2, HEIGHT//2 - 230)))
    
    u_pros = [r.replace("[PRO] ", "").replace("[PRO]", "") for r in user_reason.split("\n") if "[PRO]" in r]
    u_cons = [r.replace("[CONTRO] ", "").replace("[CONTRO]", "") for r in user_reason.split("\n") if "[CONTRO]" in r]
    u_neutros = [r.replace("[NEUTRO] ", "").replace("[NEUTRO]", "") for r in user_reason.split("\n") if "[PRO]" not in r and "[CONTRO]" not in r]
    u_pros.extend(u_neutros)
    
    curr_y = HEIGHT//2 - 190
    if u_cons:
        curr_y = draw_reasoning_block(screen, font, " | ".join(u_cons), curr_y, base_color=(255, 150, 150))
    if u_pros:
        img_u_pros = font.render("(Questa mossa aveva dei lati positivi, ma i malus sono superiori):", True, (200, 200, 200))
        screen.blit(img_u_pros, img_u_pros.get_rect(center=(WIDTH//2, curr_y)))
        curr_y = draw_reasoning_block(screen, font, " | ".join(u_pros), curr_y + 40, base_color=(200, 200, 200))
    
    # -- Mossa Ideale --
    cap_str = " + ".join([c.name for c in expected_capture]) if expected_capture else "NESSUNO SCARTO (Tavolo)"
    img_ideal = font.render(f"MOSSA OTTIMALE: {expected_card.name} su {cap_str}", True, (100, 255, 100))
    screen.blit(img_ideal, img_ideal.get_rect(center=(WIDTH//2, curr_y + 10)))
    
    pros = [r.replace("[PRO] ", "").replace("[PRO]", "") for r in best_reason.split("\n") if "[PRO]" in r]
    cons = [r.replace("[CONTRO] ", "").replace("[CONTRO]", "") for r in best_reason.split("\n") if "[CONTRO]" in r]
    neutros = [r.replace("[NEUTRO] ", "").replace("[NEUTRO]", "") for r in best_reason.split("\n") if "[PRO]" not in r and "[CONTRO]" not in r]
    pros.extend(neutros)
    
    curr_y += 50
    if pros:
        img_best_why = font.render("Vantaggi di questa mossa (PRO):", True, (150, 255, 150))
        screen.blit(img_best_why, img_best_why.get_rect(center=(WIDTH//2, curr_y)))
        curr_y = draw_reasoning_block(screen, font, " | ".join(pros), curr_y + 40, base_color=(200, 255, 200))
        
    if cons:
        curr_y += 10
        img_cons = font.render("Rischi calcolati (CONTRO) - Il bilancio è comunque positivo:", True, (255, 200, 100))
        screen.blit(img_cons, img_cons.get_rect(center=(WIDTH//2, curr_y)))
        _ = draw_reasoning_block(screen, font, " | ".join(cons), curr_y + 40, base_color=(255, 220, 150))
    
    btn_rect = pygame.Rect(WIDTH//2 - 120, HEIGHT//2 + 280, 240, 50)
    clock = pygame.time.Clock()
    waiting = True
    while waiting:
        mouse_pos = pygame.mouse.get_pos()
        for event in pygame.event.get():
            if event.type == pygame.QUIT: pygame.quit(); sys.exit()
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                if btn_rect.collidepoint(event.pos): waiting = False
                    
        is_btn_hov = btn_rect.collidepoint(mouse_pos)
        draw_modern_button(screen, "HO CAPITO", btn_rect, is_btn_hov)
        pygame.display.flip()
        clock.tick(FPS)

def draw_game_state(screen, state, mouse_pos=(0,0), selected_card=None, selected_capture=None, exclude_cards=None, message=""):
    if exclude_cards is None: exclude_cards = []
    screen.blit(BG_SURFACE, (0, 0))
    
    draw_score_panel(screen, state)
    
    current_p = state.players[state.turn]
    
    hud_rect = pygame.Rect(0, 0, WIDTH, 55)
    pygame.draw.rect(screen, (20, 25, 30), hud_rect)
    pygame.draw.line(screen, CARD_HIGHLIGHT, (0, 55), (WIDTH, 55), 2)
    
    font_hud = pygame.font.SysFont('Segoe UI, San Francisco, Arial', 22, bold=True)
    img_turno = font_hud.render(f"Turno di: {current_p.name}", True, (255, 255, 255))
    screen.blit(img_turno, (WIDTH - img_turno.get_width() - 20, 15))
    
    btn_pause_rect = pygame.Rect(20, 10, 100, 35)
    is_btn_pause_hov = btn_pause_rect.collidepoint(mouse_pos)
    draw_modern_button(screen, "PAUSA", btn_pause_rect, is_btn_pause_hov, font_size=16)
    
    if getattr(state, 'game_mode', 'classica') == 'guida':
        btn_xray_rect = pygame.Rect(140, 10, 160, 35)
        is_btn_xray_hov = btn_xray_rect.collidepoint(mouse_pos)
        draw_modern_button(screen, "X-RAY", btn_xray_rect, is_btn_xray_hov, font_size=16)
        
        btn_tracker_rect = pygame.Rect(320, 10, 160, 35)
        is_btn_tracker_hov = btn_tracker_rect.collidepoint(mouse_pos)
        draw_modern_button(screen, "CARTE", btn_tracker_rect, is_btn_tracker_hov, font_size=16)
        
        img_mode = font_hud.render("MODALITÀ GUIDA", True, (150, 255, 150))
        screen.blit(img_mode, img_mode.get_rect(center=(WIDTH//2, 27)))
    
    if message:
        draw_dynamic_panel(screen, message, WIDTH//2, 260, color=(150, 255, 150), size=24, bold=True)
    
    for p_id in [1, 2, 3]:
        p = state.players[p_id]
        total = len(p.hand)
        if p_id == 1: 
            draw_dynamic_panel(screen, p.name, 90, HEIGHT//2 - 170, size=20)
        elif p_id == 3: 
            draw_dynamic_panel(screen, p.name, WIDTH - 90, HEIGHT//2 - 170, size=20)
        elif p_id == 2: 
            draw_dynamic_panel(screen, p.name, WIDTH//2, 75, size=20)
            
        for i, card in enumerate(p.hand):
            if card in exclude_cards: continue
            x, y = p.get_hand_pos(i, len(p.hand))
            draw_card(screen, x, y, card, hidden=True if p.id != 0 else False)

    total_table = len(state.table)
    for i, card in enumerate(state.table):
        if card in exclude_cards: continue
        x, base_y = state.get_table_pos(i, total_table)
        rect = pygame.Rect(x, base_y, CARD_WIDTH, CARD_HEIGHT)
        is_sel = (selected_capture is not None) and (card in selected_capture)
        is_hov = rect.collidepoint(mouse_pos)
        target_y = base_y - 10 if is_hov else base_y
        smooth_y = lerp(f"table_{card.uid}", target_y, speed=0.3)
        draw_card(screen, x, smooth_y, card, is_selected=is_sel, is_hovered=is_hov)

    human = state.players[0]
    draw_dynamic_panel(screen, human.name, WIDTH//2, HEIGHT - CARD_HEIGHT - 100, size=22, bold=True)
    
    for i, card in enumerate(human.hand):
        if card in exclude_cards: continue
        x, base_y = human.get_hand_pos(i, len(human.hand))
        rect = pygame.Rect(x, base_y, CARD_WIDTH, CARD_HEIGHT)
        is_sel = (card == selected_card)
        is_hov = rect.collidepoint(mouse_pos)
        target_y = base_y - 25 if is_sel else (base_y - 15 if is_hov else base_y)
        smooth_y = lerp(f"hand_{card.uid}", target_y, speed=0.35)
        draw_card(screen, x, smooth_y, card, is_selected=is_sel, is_hovered=is_hov)

    if state.turn == 0 and selected_card and exclude_cards == []:
        btn_rect = pygame.Rect(WIDTH//2 - 100, HEIGHT - 60, 200, 45)
        is_btn_hov = btn_rect.collidepoint(mouse_pos)
        draw_modern_button(screen, "GIOCA LA CARTA", btn_rect, is_btn_hov)


def animate_movement(screen, state, cards_to_move, start_positions, end_positions, duration=500, reveal=True, message=""):
    start_time = pygame.time.get_ticks()
    clock = pygame.time.Clock()
    while True:
        elapsed = pygame.time.get_ticks() - start_time
        if elapsed >= duration: break
        progress = elapsed / duration
        eased_progress = 1 - (1 - progress) ** 3
        
        for event in pygame.event.get():
            if event.type == pygame.QUIT: pygame.quit(); sys.exit()
        
        draw_game_state(screen, state, pygame.mouse.get_pos(), exclude_cards=cards_to_move, message=message)
        
        for i, card in enumerate(cards_to_move):
            sx, sy = start_positions[i]
            ex, ey = end_positions[i]
            cx = sx + (ex - sx) * eased_progress
            cy = sy + (ey - sy) * eased_progress
            angle = math.sin(progress * math.pi) * 12 * (1 if i%2==0 else -1)
            
            img = IMAGE_CACHE[f"{card.value}_{card.suit}"] if reveal else IMAGE_CACHE.get('bg')
            if not img: img = pygame.Surface((CARD_WIDTH, CARD_HEIGHT)); img.fill((200,200,200))
            
            rotated_img = pygame.transform.rotate(img, angle)
            new_rect = rotated_img.get_rect(center=(cx + CARD_WIDTH//2, cy + CARD_HEIGHT//2))
            shadow_dist = 15 * math.sin(progress * math.pi)
            draw_shadow(screen, new_rect, offset=(5 + shadow_dist, 5 + shadow_dist), alpha=80)
            screen.blit(rotated_img, new_rect.topleft)
            
        pygame.display.flip()
        clock.tick(FPS)

def show_pause_menu(screen, state):
    overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    overlay.fill((0, 0, 0, 220))
    screen.blit(overlay, (0, 0))
    
    panel_rect = pygame.Rect(WIDTH//2 - 200, HEIGHT//2 - 150, 400, 300)
    pygame.draw.rect(screen, (25, 30, 35), panel_rect, border_radius=15)
    pygame.draw.rect(screen, CARD_HIGHLIGHT, panel_rect, border_radius=15, width=2)
    
    draw_dynamic_panel(screen, "GIOCO IN PAUSA", WIDTH//2, HEIGHT//2 - 90, color=(255, 200, 100), size=36, bold=True)
    
    btn_resume = pygame.Rect(WIDTH//2 - 120, HEIGHT//2 - 10, 240, 50)
    btn_quit = pygame.Rect(WIDTH//2 - 120, HEIGHT//2 + 60, 240, 50)
    
    clock = pygame.time.Clock()
    waiting = True
    while waiting:
        mouse_pos = pygame.mouse.get_pos()
        for event in pygame.event.get():
            if event.type == pygame.QUIT: pygame.quit(); sys.exit()
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                waiting = False
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                if btn_resume.collidepoint(event.pos): waiting = False
                if btn_quit.collidepoint(event.pos): pygame.quit(); sys.exit()
                    
        hov_resume = btn_resume.collidepoint(mouse_pos)
        hov_quit = btn_quit.collidepoint(mouse_pos)
        
        draw_modern_button(screen, "RIPRENDI", btn_resume, hov_resume)
        draw_modern_button(screen, "ESCI DAL GIOCO", btn_quit, hov_quit)
        
        pygame.display.flip()
        clock.tick(FPS)
        
    draw_game_state(screen, state, pygame.mouse.get_pos())
    pygame.display.flip()

def show_unknown_cards_popup(screen, player, state):
    all_cards = [Card(v, s) for s in SUITS for v in VALUES]
    known_cards = set(player.hand + state.table + state.played_cards)
    unknown_cards = sorted([c for c in all_cards if c not in known_cards], key=lambda c: (SUITS.index(c.suit), c.value))
    
    overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    overlay.fill((0, 0, 0, 240))
    screen.blit(overlay, (0, 0))
    
    panel_rect = pygame.Rect(WIDTH//2 - 400, HEIGHT//2 - 250, 800, 500)
    pygame.draw.rect(screen, (25, 30, 35), panel_rect, border_radius=15)
    pygame.draw.rect(screen, CARD_HIGHLIGHT, panel_rect, border_radius=15, width=2)
    
    draw_dynamic_panel(screen, "CARTE RIMASTE (SCONOSCIUTE)", WIDTH//2, HEIGHT//2 - 210, color=(150, 200, 255), size=26, bold=True)
    
    start_x = WIDTH//2 - 350
    start_y = HEIGHT//2 - 130
    
    suits_dict = {s: [] for s in SUITS}
    for c in unknown_cards: suits_dict[c.suit].append(c)
    
    font = pygame.font.SysFont('Segoe UI, San Francisco, Arial', 20, bold=True)
    y_offset = start_y
    for s in SUITS:
        img_suit = font.render(s.upper(), True, CARD_HIGHLIGHT)
        screen.blit(img_suit, (start_x, y_offset + 15))
        
        x_offset = start_x + 120
        for c in suits_dict[s]:
            key = f"{c.value}_{c.suit}"
            if key in IMAGE_CACHE:
                img = pygame.transform.smoothscale(IMAGE_CACHE[key], (45, 65))
                screen.blit(img, (x_offset, y_offset))
            x_offset += 50
        y_offset += 80
        
    btn_rect = pygame.Rect(WIDTH//2 - 100, HEIGHT//2 + 180, 200, 45)
    clock = pygame.time.Clock()
    waiting = True
    while waiting:
        mouse_pos = pygame.mouse.get_pos()
        for event in pygame.event.get():
            if event.type == pygame.QUIT: pygame.quit(); sys.exit()
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE: waiting = False
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                if btn_rect.collidepoint(event.pos): waiting = False
                    
        is_btn_hov = btn_rect.collidepoint(mouse_pos)
        draw_modern_button(screen, "CHIUDI", btn_rect, is_btn_hov)
        pygame.display.flip()
        clock.tick(FPS)

def show_xray_popup(screen, state, current_player):
    all_cards = [Card(v, s) for s in SUITS for v in VALUES]
    known_cards = set(current_player.hand + state.table + state.played_cards)
    unknown_cards = [c for c in all_cards if c not in known_cards]
    
    overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    overlay.fill((0, 0, 0, 240))
    screen.blit(overlay, (0, 0))
    
    panel_rect = pygame.Rect(WIDTH//2 - 450, HEIGHT//2 - 300, 900, 600)
    pygame.draw.rect(screen, (25, 30, 35), panel_rect, border_radius=15)
    pygame.draw.rect(screen, CARD_HIGHLIGHT, panel_rect, border_radius=15, width=2)
    
    draw_dynamic_panel(screen, "PREVISIONE X-RAY (PROBABILITÀ INFERITE)", WIDTH//2, HEIGHT//2 - 260, color=(255, 150, 255), size=26, bold=True)
    
    font = pygame.font.SysFont('Segoe UI, San Francisco, Arial', 18)
    
    P_matrix = {p_id: {} for p_id in [1, 2, 3]}
    for p_id in P_matrix:
        presence = getattr(state, 'presence_memory', {}).get(p_id, set())
        absence = getattr(state, 'absence_memory', {}).get(p_id, set())
        for c in unknown_cards:
            if c.value in absence: P_matrix[p_id][c] = 0.0
            elif c.value in presence: P_matrix[p_id][c] = 15.0
            else: P_matrix[p_id][c] = 1.0

    for _ in range(10):
        for p_id in P_matrix:
            row_sum = sum(P_matrix[p_id][c] for c in unknown_cards)
            target = len(state.players[p_id].hand)
            if row_sum > 0:
                for c in unknown_cards: P_matrix[p_id][c] *= (target / row_sum)
        for c in unknown_cards:
            col_sum = sum(P_matrix[p_id][c] for p_id in P_matrix)
            if col_sum > 0:
                for p_id in P_matrix: P_matrix[p_id][c] *= (1.0 / col_sum)
    
    start_x = WIDTH//2 - 350
    for i, p_id in enumerate([1, 2, 3]):
        p = state.players[p_id]
        x_col = start_x + (i * 280)
        
        draw_dynamic_panel(screen, f"{p.name}", x_col + 80, HEIGHT//2 - 200, color=(150, 255, 150) if p.team == 0 else (255, 150, 150), size=22, bold=True)
        
        y_offset = HEIGHT//2 - 160
        probs = []
        for c in unknown_cards:
            probs.append((c, min(100.0, P_matrix[p_id][c] * 100.0)))
            
        probs_sorted_by_val = sorted([p_val for c, p_val in probs])
        median_prob = probs_sorted_by_val[len(probs_sorted_by_val)//2] if probs_sorted_by_val else 33.3
            
        certezze = [(c, p_val) for c, p_val in probs if p_val >= 98 or p_val <= 2]
        deduzioni = [(c, p_val) for c, p_val in probs if 2 < p_val < 98 and abs(p_val - median_prob) > 3]
        base_cards = [(c, p_val) for c, p_val in probs if 2 < p_val < 98 and abs(p_val - median_prob) <= 3]
        
        display_probs = certezze + deduzioni
        display_probs.sort(key=lambda x: (-x[1], SUITS.index(x[0].suit), x[0].value))
        
        shown_count = 0
        for c, prob in display_probs:
            c_color = (100, 255, 100) if prob >= 98 else (200, 200, 200) if prob > 2 else (255, 100, 100)
            txt = font.render(f"{c.name}: {int(prob)}%", True, c_color)
            screen.blit(txt, (x_col, y_offset))
            y_offset += 25
            shown_count += 1
            if y_offset > HEIGHT//2 + 150:
                txt_more = font.render(f"... e altre {len(display_probs)-shown_count}", True, (100, 100, 100))
                screen.blit(txt_more, (x_col, y_offset))
                y_offset += 25
                break
                
        if base_cards:
            avg_base = sum(p_val for c, p_val in base_cards) / max(1, len(base_cards))
            txt_base = font.render(f"Altre {len(base_cards)} carte: ~{int(avg_base)}% (Ignoto)", True, (120, 120, 120))
            screen.blit(txt_base, (x_col, y_offset))
                
    btn_rect = pygame.Rect(WIDTH//2 - 100, HEIGHT//2 + 230, 200, 45)
    clock = pygame.time.Clock()
    waiting = True
    while waiting:
        mouse_pos = pygame.mouse.get_pos()
        for event in pygame.event.get():
            if event.type == pygame.QUIT: pygame.quit(); sys.exit()
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE: waiting = False
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                if btn_rect.collidepoint(event.pos): waiting = False
        is_btn_hov = btn_rect.collidepoint(mouse_pos)
        draw_modern_button(screen, "CHIUDI", btn_rect, is_btn_hov)
        pygame.display.flip()
        clock.tick(FPS)

def show_capture_choice_popup(screen, captures, played_card):
    overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    overlay.fill((0, 0, 0, 200))
    screen.blit(overlay, (0, 0))
    
    panel_height = max(300, 150 + len(captures) * 80 + 80)
    panel_rect = pygame.Rect(WIDTH//2 - 300, HEIGHT//2 - panel_height//2, 600, panel_height)
    pygame.draw.rect(screen, (25, 30, 35), panel_rect, border_radius=15)
    pygame.draw.rect(screen, CARD_HIGHLIGHT, panel_rect, border_radius=15, width=2)
    
    draw_dynamic_panel(screen, f"SCELTA PRESA: {played_card.name}", WIDTH//2, HEIGHT//2 - panel_height//2 + 40, color=(255, 200, 100), size=24, bold=True)
    
    font = pygame.font.SysFont('Segoe UI, San Francisco, Arial', 22)
    
    cap_rects = []
    start_y = HEIGHT//2 - panel_height//2 + 100
    for i, cap in enumerate(captures):
        cap_str = " + ".join([c.name for c in cap])
        r = pygame.Rect(WIDTH//2 - 250, start_y + i*80, 500, 60)
        cap_rects.append((r, cap, cap_str))
        
    btn_cancel = pygame.Rect(WIDTH//2 - 100, start_y + len(captures)*80 + 20, 200, 45)
        
    clock = pygame.time.Clock()
    while True:
        mouse_pos = pygame.mouse.get_pos()
        for event in pygame.event.get():
            if event.type == pygame.QUIT: pygame.quit(); sys.exit()
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE: return None
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                if btn_cancel.collidepoint(event.pos): return None
                for r, cap, _ in cap_rects:
                    if r.collidepoint(event.pos): return cap
                        
        for r, cap, c_str in cap_rects:
            hov = r.collidepoint(mouse_pos)
            color = (60, 180, 100) if hov else (40, 50, 60)
            pygame.draw.rect(screen, color, r, border_radius=10)
            pygame.draw.rect(screen, (100, 255, 150) if hov else (100, 100, 100), r, border_radius=10, width=2)
            
            img_txt = font.render(c_str, True, (255, 255, 255))
            screen.blit(img_txt, img_txt.get_rect(center=r.center))
            
        hov_cancel = btn_cancel.collidepoint(mouse_pos)
        draw_modern_button(screen, "ANNULLA", btn_cancel, hov_cancel)
        pygame.display.flip()
        clock.tick(FPS)

def execute_turn(screen, state, player, card_played, captured, mode_msg=None):
    if not hasattr(state, 'absence_memory'):
        state.absence_memory = {0: set(), 1: set(), 2: set(), 3: set()}
        state.presence_memory = {0: set(), 1: set(), 2: set(), 3: set()}
        
    if not captured:
        state.presence_memory[player.id].add(card_played.value)
        for r in range(1, len(state.table) + 1):
            for combo in combinations(state.table, r):
                # Se la presa avesse svuotato il tavolo, il giocatore potrebbe averla evitata
                # intenzionalmente per non subire scopa. Quindi non possiamo dedurre con certezza che non l'abbia.
                if len(combo) < len(state.table):
                    tsum = sum(c.value for c in combo)
                    if 0 < tsum <= 10: state.absence_memory[player.id].add(tsum)
    else:
        if card_played.value in state.presence_memory[player.id]:
            state.presence_memory[player.id].remove(card_played.value)

    hand_idx = player.hand.index(card_played)
    start_pos = player.get_hand_pos(hand_idx, len(player.hand))
    player.hand.remove(card_played)
    
    msg = mode_msg if mode_msg else f"{player.name} gioca {card_played.name}"
    mid_table_pos = (WIDTH//2 - CARD_WIDTH//2, HEIGHT//2 - CARD_HEIGHT//2 - 15)
    
    animate_movement(screen, state, [card_played], [start_pos], [mid_table_pos], duration=450, reveal=True, message=msg)
    state.table.append(card_played)
    ANIMATION_STATE[f"table_{card_played.uid}"] = mid_table_pos[1]
    
    draw_game_state(screen, state, pygame.mouse.get_pos(), message=msg)
    pygame.display.flip()
    safe_wait(1000, screen, state)
    
    state.played_cards.append(card_played)
    
    if captured:
        msg_take = f"{player.name} prende!"
        if not hasattr(state, 'unbalanced_values'):
            state.unbalanced_values = set()
        for v in [c.value for c in captured] + [card_played.value]:
            if v in state.unbalanced_values:
                state.unbalanced_values.remove(v)
            else:
                state.unbalanced_values.add(v)
        if len(state.table) - len(captured) - 1 == 0 and len(player.hand) > 0:
            msg_take = f"SCOPA DI {player.name.upper()}!"
            player.scopas += 1
            
        cards_to_move = captured + [card_played]
        start_positions = [state.get_table_pos(len(state.table)-1, len(state.table)) if c == card_played else state.get_table_pos(state.table.index(c), len(state.table)) for c in cards_to_move]
        end_positions = [player.get_pile_pos() for _ in cards_to_move]
        
        for c in cards_to_move: state.table.remove(c)
        animate_movement(screen, state, cards_to_move, start_positions, end_positions, duration=600, reveal=True, message=msg_take)
        
        player.captured.extend(cards_to_move)
        state.last_taker = player.id
        if "SCOPA" in msg_take: safe_wait(1500, screen, state)
            
    state.turn = (state.turn + 1) % 4

def main_menu(screen):
    clock = pygame.time.Clock()
    font_title = pygame.font.SysFont('Segoe UI, San Francisco, Arial', 65, bold=True)
    font_sub = pygame.font.SysFont('Segoe UI, San Francisco, Arial', 30)
    
    img_title = font_title.render("SCOPONE SCIENTIFICO", True, CARD_HIGHLIGHT)
    img_sub = font_sub.render("Seleziona la modalità di gioco:", True, TEXT_COLOR)
    
    while True:
        mouse_pos = pygame.mouse.get_pos()
        screen.blit(BG_SURFACE, (0, 0))
        
        screen.blit(img_title, img_title.get_rect(center=(WIDTH//2, 200)))
        screen.blit(img_sub, img_sub.get_rect(center=(WIDTH//2, 320)))
        
        btn_classica = pygame.Rect(WIDTH//2 - 270, 420, 220, 60)
        btn_guida = pygame.Rect(WIDTH//2 + 50, 420, 220, 60)
        
        hov_classica = btn_classica.collidepoint(mouse_pos)
        hov_guida = btn_guida.collidepoint(mouse_pos)
        
        draw_modern_button(screen, "MODALITÀ CLASSICA", btn_classica, hov_classica)
        draw_modern_button(screen, "MODALITÀ GUIDA", btn_guida, hov_guida)
        
        draw_dynamic_panel(screen, "Ritmo veloce. Solo per esperti.", WIDTH//2 - 160, 510, color=(180, 180, 180), size=18)
        draw_dynamic_panel(screen, "Ritmo lento. Tutor attivo ad ogni mossa.", WIDTH//2 + 160, 510, color=(180, 180, 180), size=18)
        
        for event in pygame.event.get():
            if event.type == pygame.QUIT: pygame.quit(); sys.exit()
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                if hov_classica: return "classica"
                if hov_guida: return "guida"
                
        pygame.display.flip()
        clock.tick(FPS)

def main():
    pygame.init()
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    pygame.display.set_caption("Scopone Scientifico - Ultra HD UI")
    init_graphics()
    load_images()

    game_mode = main_menu(screen)

    state = GameState()
    dealer = random.randint(0, 3)
    state.reset_round((dealer + 1) % 4)
    state.game_mode = game_mode
    state.xray_enabled = False
    
    selected_card, selected_capture = None, []
    clock = pygame.time.Clock()
    
    running = True
    while running:
        mouse_pos = pygame.mouse.get_pos()
        current_player = state.players[state.turn]
        
        events = pygame.event.get()
        for event in events:
            if event.type == pygame.QUIT: pygame.quit(); sys.exit()
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                show_pause_menu(screen, state)
                continue
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                btn_pause_rect = pygame.Rect(20, 10, 100, 35)
                if btn_pause_rect.collidepoint(event.pos):
                    show_pause_menu(screen, state)
                    continue
                if getattr(state, 'game_mode', 'classica') == 'guida':
                    btn_xray_rect = pygame.Rect(140, 10, 160, 35)
                    if btn_xray_rect.collidepoint(event.pos):
                        show_xray_popup(screen, state, state.players[0])
                        draw_game_state(screen, state, pygame.mouse.get_pos())
                        pygame.display.flip()
                        continue
                    btn_tracker_rect = pygame.Rect(320, 10, 160, 35)
                    if btn_tracker_rect.collidepoint(event.pos):
                        show_unknown_cards_popup(screen, state.players[0], state)
                        draw_game_state(screen, state, pygame.mouse.get_pos())
                        pygame.display.flip()
                        continue
        
        if current_player.id == 0:
            for event in events:
                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    for i, card in enumerate(current_player.hand):
                        x, base_y = current_player.get_hand_pos(i, len(current_player.hand))
                        curr_y = ANIMATION_STATE.get(f"hand_{card.uid}", base_y)
                        if pygame.Rect(x, curr_y, CARD_WIDTH, CARD_HEIGHT).collidepoint(event.pos):
                            selected_card, selected_capture = card, []
                            break
                            
                    if selected_card:
                        for i, card in enumerate(state.table):
                            x, base_y = state.get_table_pos(i, len(state.table))
                            curr_y = ANIMATION_STATE.get(f"table_{card.uid}", base_y)
                            if pygame.Rect(x, curr_y, CARD_WIDTH, CARD_HEIGHT).collidepoint(event.pos):
                                if card in selected_capture: selected_capture.remove(card)
                                else: selected_capture.append(card)
                                break
                    
                    if selected_card:
                        btn_rect = pygame.Rect(WIDTH//2 - 100, HEIGHT - 60, 200, 45)
                        if btn_rect.collidepoint(event.pos):
                            valid_captures = get_possible_captures(selected_card, state.table)
                            is_valid = False
                            
                            if not valid_captures and not selected_capture: is_valid = True
                            elif valid_captures:
                                for vc in valid_captures:
                                    if set(selected_capture) == set(vc): is_valid = True; break
                                if is_valid and len(selected_capture) > 1 and any(len(c) == 1 for c in valid_captures): is_valid = False
                                if not is_valid:
                                    if len(valid_captures) == 1:
                                        selected_capture = valid_captures[0]
                                        is_valid = True
                                    elif len(valid_captures) > 1:
                                        selected_capture = show_capture_choice_popup(screen, valid_captures, selected_card)
                                        if selected_capture is None:
                                            draw_game_state(screen, state, pygame.mouse.get_pos())
                                            pygame.display.flip()
                                            continue
                                        is_valid = True
                            
                            if is_valid:
                                custom_msg = None
                                if getattr(state, 'game_mode', 'classica') == 'guida':
                                    best_c, best_cap, best_ev, reason, _ = get_best_move(current_player, state)
                                    
                                    all_cards = [Card(v, s) for s in SUITS for v in VALUES]
                                    known_cards = set(current_player.hand + state.table + state.played_cards)
                                    unknown_cards = [c for c in all_cards if c not in known_cards]
                                    user_ev, user_reason = evaluate_move_logic(current_player, state, selected_card, selected_capture, unknown_cards)
                                    
                                    if (best_ev - user_ev) > 0.01:
                                        show_guide_popup(screen, best_c, best_cap, reason, selected_card, user_reason)
                                    else:
                                        custom_msg = "Ottima mossa! Hai massimizzato il Valore Atteso!"
                                
                                
                                # --- ACCADEMIA LOGGING ---
                                if current_player.id == 0:
                                    analysis = accademia.analyze_move(state, selected_card, selected_capture)
                                    # Memorizza lo stato del tavolo per il replay visivo (semplificato)
                                    analysis['turn_number'] = 40 - sum(len(p.hand) for p in state.players)
                                    analysis['card_played'] = selected_card
                                    state.accademia_history.append(analysis)
                                
                                execute_turn(screen, state, current_player, selected_card, selected_capture, custom_msg)
                                selected_card, selected_capture = None, []
                                
            draw_game_state(screen, state, mouse_pos, selected_card, selected_capture)
            pygame.display.flip()
            clock.tick(FPS)
            
        else:
            if not hasattr(state, 'bot_thread'):
                state.bot_thread = None
                state.bot_result = None
                state.bot_wait_start = pygame.time.get_ticks()
                
            if state.bot_thread is None:
                def think_task(st, p_id):
                    st_copy = st.clone()
                    p_copy = st_copy.players[p_id]
                    st.bot_result = get_best_move(p_copy, st_copy)
                    
                state.bot_thread = threading.Thread(target=think_task, args=(state, current_player.id))
                state.bot_thread.start()
                
            if state.bot_thread.is_alive():
                dots = "." * ((pygame.time.get_ticks() // 500) % 4)
                msg = f"{current_player.name} sta pensando{dots}"
                draw_game_state(screen, state, mouse_pos, message=msg)
                pygame.display.flip()
                clock.tick(FPS)
            else:
                elapsed = pygame.time.get_ticks() - state.bot_wait_start
                if elapsed < (2500 if getattr(state, 'game_mode', 'classica') == "guida" else 800):
                    dots = "." * ((pygame.time.get_ticks() // 500) % 4)
                    msg = f"{current_player.name} sta pensando{dots}"
                    draw_game_state(screen, state, mouse_pos, message=msg)
                    pygame.display.flip()
                    clock.tick(FPS)
                    continue
                    
                best_c_copy, best_cap_copy, best_ev, reason, _ = state.bot_result
                best_c = next((c for c in current_player.hand if c.suit == best_c_copy.suit and c.value == best_c_copy.value), None)
                best_cap = [next(c for c in state.table if c.suit == cap_c.suit and c.value == cap_c.value) for cap_c in best_cap_copy] if best_cap_copy else []
                
                state.bot_thread = None
                state.bot_result = None
                delattr(state, 'bot_thread')
                
                execute_turn(screen, state, current_player, best_c, best_cap)

        if all(len(p.hand) == 0 for p in state.players):
            if state.table and state.last_taker is not None:
                taker = state.players[state.last_taker]
                msg = f"{taker.name} ripulisce il tavolo!"
                start_positions = [state.get_table_pos(i, len(state.table)) for i in range(len(state.table))]
                end_positions = [taker.get_pile_pos() for _ in state.table]
                animate_movement(screen, state, state.table, start_positions, end_positions, duration=700, reveal=True, message=msg)
                taker.captured.extend(state.table)
                state.table = []
            
            round_stats = state.calculate_round_score()
            draw_game_state(screen, state, mouse_pos)
            
            overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
            overlay.fill((0, 0, 0, 240))
            screen.blit(overlay, (0, 0))
            
            draw_dynamic_panel(screen, "TABELLONE FINE ROUND", WIDTH//2, 80, color=(255, 200, 100), size=45, bold=True)
            
            font_item = pygame.font.SysFont('Segoe UI, San Francisco, Arial', 26)
            
            for t_id, x_c, title, col in [(0, WIDTH//2 - 250, "LA TUA SQUADRA", (150, 255, 150)), (1, WIDTH//2 + 250, "AVVERSARI", (255, 150, 150))]:
                draw_dynamic_panel(screen, title, x_c, 150, color=col, size=30, bold=True)
                y = 210
                st = round_stats[t_id]
                screen.blit(font_item.render(f"Carte ({st['carte'][0]}): {'+1' if st['carte'][1] else '0'}", True, (255, 255, 255)), (x_c - 110, y))
                screen.blit(font_item.render(f"Denari ({st['denari'][0]}): {'+1' if st['denari'][1] else '0'}", True, (255, 255, 255)), (x_c - 110, y+45))
                screen.blit(font_item.render(f"Settebello: {'+1' if st['settebello'] else '0'}", True, (255, 255, 255)), (x_c - 110, y+90))
                screen.blit(font_item.render(f"Primiera ({st['primiera'][0]}): {'+1' if st['primiera'][1] else '0'}", True, (255, 255, 255)), (x_c - 110, y+135))
                screen.blit(font_item.render(f"Scope: +{st['scopas']}", True, (255, 255, 255)), (x_c - 110, y+180))
                
                pygame.draw.line(screen, (100, 100, 100), (x_c - 150, y+240), (x_c + 150, y+240), 2)
                draw_dynamic_panel(screen, f"Punti Round: +{st['round_total']}", x_c, y+280, color=col, size=30, bold=True)
                draw_dynamic_panel(screen, f"PUNTEGGIO TOTALE: {state.scores[t_id]}", x_c, y+340, color=col, size=35, bold=True)
            
            if state.scores[0] >= 21 or state.scores[1] >= 21:
                winner = "VITTORIA!" if state.scores[0] > state.scores[1] else "SCONFITTA!"
                draw_dynamic_panel(screen, winner, WIDTH//2, HEIGHT - 60, color=(255, 215, 0), size=60, bold=True)
                pygame.display.flip()
                safe_wait(10000, screen, state)
                running = False
            else:
                draw_dynamic_panel(screen, "Il prossimo round inizierà tra poco...", WIDTH//2, HEIGHT - 50, color=(200, 200, 200), size=24)
                pygame.display.flip()
                safe_wait(8000, screen, state)
            
            # --- ACCADEMIA UI (END ROUND) ---
            screen.fill((20, 25, 30))
            draw_dynamic_panel(screen, "ACCADEMIA: ANALISI DEL ROUND", WIDTH//2, 50, color=(100, 200, 255), size=45, bold=True)
            
            font_acc_title = pygame.font.SysFont('Segoe UI, San Francisco, Arial', 22, bold=True)
            font_acc_desc = pygame.font.SysFont('Segoe UI, San Francisco, Arial', 18)
            
            y_offset = 120
            blunders = [a for a in state.accademia_history if a['classification'] in ["🔴 BLUNDER", "💀 CRITICAL BLUNDER"]]
            
            if not blunders:
                draw_dynamic_panel(screen, "Partita perfetta! Nessun errore grave rilevato.", WIDTH//2, 200, color=(150, 255, 150), size=35, bold=True)
            else:
                for idx, b in enumerate(blunders[:5]): # Mostra max 5
                    card = b['card_played']
                    best_c = b['best_move'][0]
                    c_color = (255, 100, 100) if "CRITICAL" in b['classification'] else (255, 150, 50)
                    
                    t = f"Turno {b['turn_number']} | Giocato: {card.name} | Migliore: {best_c.name} ({b['classification']} Δ{-b['ev_loss']:.1f} EV)"
                    screen.blit(font_acc_title.render(t, True, c_color), (100, y_offset))
                    
                    desc = f"Motivo: {b['primary_reason']}"
                    screen.blit(font_acc_desc.render(desc, True, (200, 200, 200)), (120, y_offset + 30))
                    
                    y_offset += 75
            
            draw_dynamic_panel(screen, "Il prossimo round inizierà tra poco...", WIDTH//2, HEIGHT - 50, color=(200, 200, 200), size=24)
            pygame.display.flip()
            safe_wait(8000, screen, state)
            state.accademia_history = []

            dealer = (dealer + 1) % 4
            state.reset_round((dealer + 1) % 4)

if __name__ == "__main__":
    main()

def distribute_unknown_cards(state, current_player, unknown_cards):
    import random
    hands = [[] for _ in range(4)]
    hands[current_player.id] = current_player.hand[:]
    needed = [0, 0, 0, 0]
    for i, p in enumerate(state.players):
        if i != current_player.id:
            needed[i] = len(p.hand)
    pool = unknown_cards[:]
    random.shuffle(pool)
    for i in range(4):
        if i != current_player.id:
            for _ in range(needed[i]):
                if pool:
                    hands[i].append(pool.pop())
    return hands
