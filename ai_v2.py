import random
import copy
from scopone_scientifico import GameState, Card, get_possible_captures, get_probability_matrix, PRIMIERA_VALUES, SUITS, calc_primiera_score, distribute_unknown_cards

def pimc_fast_policy(player, state):
    best_card = None
    best_cap = None
    max_ev = -9999
    
    for card in player.hand:
        caps = get_possible_captures(card, state.table)
        if not caps:
            ev = 0.0
            if card.suit == 'Denari': ev -= 1.0
            if card.value == 7: ev -= 1.5
            if card.value == 6: ev -= 1.0
            if ev > max_ev:
                max_ev = ev
                best_card = card
                best_cap = []
        else:
            for cap in caps:
                ev = 5.0 # Base capture priority
                ev += sum(1.5 for c in cap if c.suit == 'Denari')
                ev += sum(1.0 for c in cap if c.value == 7)
                if card.suit == 'Denari': ev += 1.5
                if card.value == 7: ev += 1.0
                if len(cap) == len(state.table):
                    ev += 10.0 # Scopa priority
                if ev > max_ev:
                    max_ev = ev
                    best_card = card
                    best_cap = cap
    return best_card, best_cap

def simulate_playout(state, current_player_idx, unknown_cards, player_hands):
    # state is a deepcopy, we can mutate it
    # player_hands is a list of lists of cards
    for i, h in enumerate(player_hands):
        state.players[i].hand = h[:]
    
    t0_scope = 0
    t1_scope = 0
    
    # We need to resume from state.turn, but it's passed as current_player_idx
    state.turn = current_player_idx
    
    total_cards_left = sum(len(p.hand) for p in state.players)
    
    for _ in range(total_cards_left):
        p = state.players[state.turn]
        
        card, cap = pimc_fast_policy(p, state)
        
        p.hand.remove(card)
        if cap:
            for c in cap:
                state.table.remove(c)
            p.captured.extend(cap + [card])
            state.last_taker = p.id
            if not state.table and len(p.hand) > 0:
                if p.team == 0: t0_scope += 1
                else: t1_scope += 1
        else:
            state.table.append(card)
            
        state.turn = (state.turn + 1) % 4
        
    if state.table:
        state.players[state.last_taker].captured.extend(state.table)
        
    t0_caps = state.players[0].captured + state.players[2].captured
    t1_caps = state.players[1].captured + state.players[3].captured
    
    t0_pts = t0_scope
    t1_pts = t1_scope
    
    if len(t0_caps) > 20: t0_pts += 1
    elif len(t1_caps) > 20: t1_pts += 1
    
    d0 = sum(1 for c in t0_caps if c.suit == 'Denari')
    d1 = sum(1 for c in t1_caps if c.suit == 'Denari')
    if d0 > 5: t0_pts += 1
    elif d1 > 5: t1_pts += 1
    
    if any(c.value == 7 and c.suit == 'Denari' for c in t0_caps): t0_pts += 1
    else: t1_pts += 1
        
    p0 = calc_primiera_score(t0_caps)
    p1 = calc_primiera_score(t1_caps)
    if p0 > p1: t0_pts += 1
    elif p1 > p0: t1_pts += 1
    
    return t0_pts, t1_pts

def get_best_move_v2(player, state):
    best_card, best_cap, max_ev = None, None, -float('inf')
    
    all_cards = [Card(v, s) for s in ['Coppe','Denari','Bastoni','Spade'] for v in range(1,11)]
    known_cards = set(player.hand + state.table + state.played_cards)
    unknown_cards = [c for c in all_cards if c not in known_cards]
    
    valid_moves = []
    for card in player.hand:
        caps = get_possible_captures(card, state.table)
        if not caps:
            valid_moves.append((card, []))
        else:
            for cap in caps:
                valid_moves.append((card, cap))
                
    NUM_ROLLOUTS = 50 # Reduced from 300 to balance performance and accuracy
    
    move_evs = {}
    
    for card, cap in valid_moves:
        total_pts = 0
        
        for _ in range(NUM_ROLLOUTS):
            t0_scope_move = 0
            t1_scope_move = 0
            
            hands = distribute_unknown_cards(state, player, unknown_cards)
            sim_state = copy.deepcopy(state)
            
            # Apply move
            sim_p = sim_state.players[player.id]
            # Hands are lists of cards. We need to assign them correctly to sim_state
            for i, h in enumerate(hands):
                sim_state.players[i].hand = [Card(c.value, c.suit) for c in h]
                sim_state.players[i].captured = [Card(c.value, c.suit) for c in state.players[i].captured]
            
            # Find the equivalent card in sim_p.hand
            sim_card = next(c for c in sim_p.hand if c.value == card.value and c.suit == card.suit)
            sim_p.hand.remove(sim_card)
            
            if cap:
                sim_cap = []
                for c in cap:
                    sim_c = next(tc for tc in sim_state.table if tc.value == c.value and tc.suit == c.suit)
                    sim_cap.append(sim_c)
                    sim_state.table.remove(sim_c)
                sim_p.captured.extend(sim_cap + [sim_card])
                sim_state.last_taker = sim_p.id
                if not sim_state.table and len(sim_p.hand) > 0:
                    if sim_p.team == 0:
                        t0_scope_move = 1
                    else:
                        t1_scope_move = 1
                else:
                    t0_scope_move = 0
                    t1_scope_move = 0
            else:
                sim_state.table.append(sim_card)
                
            sim_state.turn = (sim_state.turn + 1) % 4
            
            t0, t1 = simulate_playout(sim_state, sim_state.turn, unknown_cards, [p.hand for p in sim_state.players])
            
            if player.team == 0:
                total_pts += (t0 + t0_scope_move) - (t1 + t1_scope_move)
            else:
                total_pts += (t1 + t1_scope_move) - (t0 + t0_scope_move)
                
        ev = (total_pts / NUM_ROLLOUTS) * 3.0 # Normalize to heuristic scale (which divides by 10)
        move_evs[(card, tuple(cap))] = ev
        if ev > max_ev:
            max_ev = ev
            best_card = card
            best_cap = cap
            
    reason = f"Expected Match Points diff: {max_ev:.2f}"
    all_evals = {k: v for k, v in move_evs.items()}
    return best_card, list(best_cap) if best_cap else [], max_ev, reason, all_evals


def calc_primiera_score(cards):
    best = {s: 0 for s in SUITS}
    for c in cards:
        val = PRIMIERA_VALUES.get(c.value, 0)
        if val > best[c.suit]:
            best[c.suit] = val
    # In some variants you need a card of each suit to get Primiera, in others just sum the best
    return sum(best.values())

def distribute_unknown_cards(state, current_player, unknown_cards):
    hands = [[] for _ in range(4)]
    hands[current_player.id] = current_player.hand[:]
    
    needed = [0, 0, 0, 0]
    for i, p in enumerate(state.players):
        if i != current_player.id:
            needed[i] = len(p.hand)
            
    pool = unknown_cards[:]
    random.shuffle(pool)
    P_mat = get_probability_matrix(state, current_player, pool)
    
    for card in pool:
        weights = []
        candidates = []
        for p_id in range(4):
            if p_id != current_player.id and needed[p_id] > 0:
                candidates.append(p_id)
                weights.append(P_mat[p_id].get(card, 1.0))
        
        if not candidates:
            break
            
        chosen = random.choices(candidates, weights=weights, k=1)[0]
        hands[chosen].append(card)
        needed[chosen] -= 1
        
    return hands
