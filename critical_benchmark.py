import random
import multiprocessing
import copy
import sys
import json
import os
import pickle
import time

import scopone_scientifico
import ai_v1
import ai_v2

# Define critical state check
def get_critical_state_type(state, current_player):
    if len(current_player.hand) <= 3:
        return "Finale 2-3 carte"
        
    table_sum = sum(c.value for c in state.table)
    if 0 < table_sum <= 10:
        return "Rischio scopa"
        
    if any(c.suit == 'Denari' for c in state.table):
        return "Denari contesi"
        
    primiera_vals = {7:21, 6:18, 1:16, 5:15, 4:14, 3:13, 2:12}
    table_has_primiera = any(c.value in primiera_vals for c in state.table)
    hand_has_primiera = any(c.value in primiera_vals for c in current_player.hand)
    if table_has_primiera and hand_has_primiera:
        return "Scelta primiera"
        
    if len(state.table) >= 4:
        return "Tavolo pieno"
        
    return None

def evaluate_move_with_pimc(state, player, card, cap, num_rollouts=50):
    all_cards = [scopone_scientifico.Card(v, s) for s in scopone_scientifico.SUITS for v in scopone_scientifico.VALUES]
    known_cards = set(player.hand + state.table + state.played_cards)
    unknown_cards = [c for c in all_cards if c not in known_cards]
    
    total_pts = 0
    for _ in range(num_rollouts):
        hands = ai_v2.distribute_unknown_cards(state, player, unknown_cards)
        sim_state = copy.deepcopy(state)
        
        sim_p = sim_state.players[player.id]
        for i, h in enumerate(hands):
            sim_state.players[i].hand = [scopone_scientifico.Card(c.value, c.suit) for c in h]
            sim_state.players[i].captured = [scopone_scientifico.Card(c.value, c.suit) for c in state.players[i].captured]
        
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
            if not sim_state.table and sum(len(x.hand) for x in sim_state.players) > 0:
                pass 
        else:
            sim_state.table.append(sim_card)
            
        sim_state.turn = (sim_state.turn + 1) % 4
        
        t0, t1 = ai_v2.simulate_playout(sim_state, sim_state.turn, unknown_cards, [p.hand for p in sim_state.players])
        if player.team == 0:
            total_pts += t0 - t1
        else:
            total_pts += t1 - t0
            
    return total_pts / num_rollouts

def run_critical_scenario(seed):
    random.seed(seed)
    state = scopone_scientifico.GameState()
    state.reset_round(0)
    
    state.turn = 0
    state.table = []
    state.played_cards = []
    state.last_taker = 0
    
    target_turn = random.randint(10, 32)
    
    for current_turn in range(40):
        current_player = state.players[state.turn]
        
        if current_turn == target_turn:
            crit_type = get_critical_state_type(state, current_player)
            if crit_type:
                # We found a critical state!
                # V1 move
                scopone_scientifico.evaluate_move_logic = ai_v1.evaluate_move_logic_v1
                v1_card, v1_cap, _, _, _ = scopone_scientifico.get_best_move(current_player, state)
                
                # V2 move
                v2_card, v2_cap, _, _, _ = ai_v2.get_best_move_v2(current_player, state)
                
                v1_sig = (v1_card.name, tuple(sorted(c.name for c in v1_cap)))
                v2_sig = (v2_card.name, tuple(sorted(c.name for c in v2_cap)))
                
                if v1_sig != v2_sig:
                    # Divergence! Measure true EV
                    ev_v1 = evaluate_move_with_pimc(state, current_player, v1_card, v1_cap, 50)
                    ev_v2 = evaluate_move_with_pimc(state, current_player, v2_card, v2_cap, 50)
                    delta_ev = ev_v2 - ev_v1
                    
                    return {
                        'seed': seed,
                        'type': crit_type,
                        'v1_move': v1_sig,
                        'v2_move': v2_sig,
                        'ev_v1': ev_v1,
                        'ev_v2': ev_v2,
                        'delta_ev': delta_ev
                    }
                return None
                
        # Random play
        card = random.choice(current_player.hand)
        caps = scopone_scientifico.get_possible_captures(card, state.table)
        cap = random.choice(caps) if caps else []
        
        current_player.hand.remove(card)
        state.played_cards.append(card)
        
        if cap:
            for c in cap:
                state.table.remove(c)
            current_player.captured.extend(cap + [card])
            state.last_taker = current_player.id
        else:
            state.table.append(card)
            
        state.turn = (state.turn + 1) % 4
        
    return None

if __name__ == '__main__':
    N_STATES = 200
    print(f"Generating and evaluating up to {N_STATES} critical states...")
    t0 = time.time()
    
    divergences = []
    
    # We will just search seeds sequentially until we get enough divergences or checked enough seeds
    # Let's check 500 seeds to find divergences.
    with multiprocessing.Pool() as pool:
        results = pool.map(run_critical_scenario, range(500))
        
    for res in results:
        if res:
            divergences.append(res)
            
    print(f"\\n--- CRITICAL STATE BENCHMARK RESULTS ---")
    print(f"Seeds analyzed: 500")
    print(f"Decision Divergences found: {len(divergences)}")
    
    if divergences:
        avg_delta = sum(d['delta_ev'] for d in divergences) / len(divergences)
        print(f"E[ΔEV] (Expected Value Differential): {avg_delta:+.3f} points per critical decision")
        
        print("\nDivergence Types:")
        types = {}
        for d in divergences:
            types[d['type']] = types.get(d['type'], 0) + 1
        for t, count in types.items():
            print(f"  - {t}: {count}")
            
    print(f"\nExecution time: {time.time()-t0:.1f}s")
