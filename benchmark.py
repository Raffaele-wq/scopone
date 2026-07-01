import random
import multiprocessing
import math
import pickle
import sys
import os

import scopone_scientifico
import ai_v1

def run_simulation(seed):
    # Esegue la partita senza swap (V1=T0, V2=T1) e con swap (V2=T0, V1=T1)
    res_normal = simulate_hand(seed, swap=False)
    res_swapped = simulate_hand(seed, swap=True)
    return res_normal, res_swapped

def simulate_hand(seed, swap=False):
    random.seed(seed)
    state = scopone_scientifico.GameState()
    state.reset_round(0)
        
    state.turn = 0
    state.table = []
    state.played_cards = []
    state.last_taker = 0
    
    t0_scope = 0
    t1_scope = 0
    
    moves_history = []
    
    eval_v1 = ai_v1.evaluate_move_logic_v1
    eval_v2 = scopone_scientifico.evaluate_move_logic
    
    for _ in range(40):
        current_player = state.players[state.turn]
        is_t0 = (current_player.team == 0)
        
        if not swap:
            current_eval = eval_v1 if is_t0 else eval_v2
        else:
            current_eval = eval_v2 if is_t0 else eval_v1
            
        scopone_scientifico.evaluate_move_logic = current_eval
        
        best_c, best_cap, best_ev, reason, all_evals = scopone_scientifico.get_best_move(current_player, state)
        
        current_player.hand.remove(best_c)
        state.played_cards.append(best_c)
        
        moves_history.append({
            'turn': state.turn,
            'player': current_player.id,
            'card': best_c,
            'capture': best_cap,
            'reason': reason,
            'ev': best_ev,
            'ai_version': 'v2' if current_eval == eval_v2 else 'v1'
        })
        
        if best_cap:
            for c in best_cap:
                state.table.remove(c)
            current_player.captured.extend(best_cap + [best_c])
            state.last_taker = current_player.id
            if len(state.table) == 0 and sum(len(p.hand) for p in state.players) > 0:
                if is_t0: t0_scope += 1
                else: t1_scope += 1
        else:
            state.table.append(best_c)
            
        state.turn = (state.turn + 1) % 4
        
    if state.table:
        taker = state.players[state.last_taker]
        taker.captured.extend(state.table)
        state.table = []
        
    t0_caps = state.players[0].captured + state.players[2].captured
    t1_caps = state.players[1].captured + state.players[3].captured
    
    t0_pts = t0_scope
    t1_pts = t1_scope
    
    metrics = {'scope_t0': t0_scope, 'scope_t1': t1_scope, 'carte_t0': 0, 'carte_t1': 0, 
               'denari_t0': 0, 'denari_t1': 0, 'settebello_t0': 0, 'settebello_t1': 0,
               'primiera_t0': 0, 'primiera_t1': 0}
               
    if len(t0_caps) > 20: 
        t0_pts += 1
        metrics['carte_t0'] = 1
    elif len(t1_caps) > 20: 
        t1_pts += 1
        metrics['carte_t1'] = 1
        
    d0 = sum(1 for c in t0_caps if c.suit == 'Denari')
    d1 = sum(1 for c in t1_caps if c.suit == 'Denari')
    if d0 > 5: 
        t0_pts += 1
        metrics['denari_t0'] = 1
    elif d1 > 5: 
        t1_pts += 1
        metrics['denari_t1'] = 1
        
    if any(c.value == 7 and c.suit == 'Denari' for c in t0_caps):
        t0_pts += 1
        metrics['settebello_t0'] = 1
    else:
        t1_pts += 1
        metrics['settebello_t1'] = 1
        
    p0 = ai_v2.calc_primiera_score(t0_caps)
    p1 = ai_v2.calc_primiera_score(t1_caps)
    if p0 > p1:
        t0_pts += 1
        metrics['primiera_t0'] = 1
    elif p1 > p0:
        t1_pts += 1
        metrics['primiera_t1'] = 1
        
    if not swap:
        v1_pts, v2_pts = t0_pts, t1_pts
        v1_mets = {k.replace('_t0', ''): v for k, v in metrics.items() if '_t0' in k}
        v2_mets = {k.replace('_t1', ''): v for k, v in metrics.items() if '_t1' in k}
    else:
        v2_pts, v1_pts = t0_pts, t1_pts
        v2_mets = {k.replace('_t0', ''): v for k, v in metrics.items() if '_t0' in k}
        v1_mets = {k.replace('_t1', ''): v for k, v in metrics.items() if '_t1' in k}
        
    return {
        'seed': seed,
        'swap': swap,
        'v1_pts': v1_pts,
        'v2_pts': v2_pts,
        'v1_mets': v1_mets,
        'v2_mets': v2_mets,
        'history': moves_history
    }

def print_stats(v1_wins, v2_wins, draws, v1_tot_pts, v2_tot_pts, N, start_time):
    print(f"\n--- RISULTATI SU {N} PARTITE (V1 vs V2, a specchio) ---")
    
    p_v2_win = v2_wins / N
    p_v1_win = v1_wins / N
    p_draw = draws / N
    
    print(f"Vittorie V2 (PIMC) : {v2_wins} ({p_v2_win*100:.2f}%)")
    print(f"Vittorie V1 (Euris): {v1_wins} ({p_v1_win*100:.2f}%)")
    print(f"Pareggi            : {draws} ({p_draw*100:.2f}%)")
    
    diff = p_v2_win - p_v1_win
    # Intervallo di confidenza al 95% per la differenza (approssimazione normale)
    se = math.sqrt((p_v2_win*(1-p_v2_win)/N) + (p_v1_win*(1-p_v1_win)/N))
    ci = 1.96 * se
    print(f"Δ Win Rate         : {diff*100:+.2f}% (± {ci*100:.2f}%)")
    if abs(diff) > ci:
        print(f"Significatività    : SI (La differenza è statisticamente rilevante al 95%)")
    else:
        print(f"Significatività    : NO (Puro rumore statistico)")
        
    print(f"Punti Medi V2      : {v2_tot_pts/N:.2f}")
    print(f"Punti Medi V1      : {v1_tot_pts/N:.2f}")

if __name__ == '__main__':
    N_MATCHES = 100 # Default a 100, cambialo a 10000 per un run completo
    if len(sys.argv) > 1:
        N_MATCHES = int(sys.argv[1])
        
    print(f"Avvio Benchmark A/B per {N_MATCHES} seeds ({N_MATCHES*2} partite totali)...")
    import time
    t0 = time.time()
    
    v1_wins = 0
    v2_wins = 0
    draws = 0
    v1_tot_pts = 0
    v2_tot_pts = 0
    
    os.makedirs("replays", exist_ok=True)
    
    with multiprocessing.Pool() as pool:
        results = pool.map(run_simulation, range(N_MATCHES))
        
    divergences = 0
    for res_normal, res_swapped in results:
        # Aggregazione punti (la partita a specchio è pensata per pareggiare la sfortuna delle carte)
        tot_v1 = res_normal['v1_pts'] + res_swapped['v1_pts']
        tot_v2 = res_normal['v2_pts'] + res_swapped['v2_pts']
        
        v1_tot_pts += tot_v1
        v2_tot_pts += tot_v2
        
        if tot_v2 > tot_v1: v2_wins += 1
        elif tot_v1 > tot_v2: v1_wins += 1
        else: draws += 1
        
        # Salvataggio divergenze per Replay
        hist_n = res_normal['history']
        hist_s = res_swapped['history']
        
        # Confrontiamo le mosse fatte dal giocatore 0 nel normal (V1) e nel swapped (V2)
        # Ovviamente le partite divergono appena viene fatta una scelta diversa.
        for idx in range(len(hist_n)):
            if hist_n[idx]['card'].name != hist_s[idx]['card'].name or hist_n[idx]['capture'] != hist_s[idx]['capture']:
                divergences += 1
                with open(f"replays/divergence_seed_{res_normal['seed']}_turn_{idx}.pkl", "wb") as f:
                    pickle.dump({
                        'seed': res_normal['seed'],
                        'turn': idx,
                        'v1_move': hist_n[idx],
                        'v2_move': hist_s[idx],
                        'v1_history': hist_n[:idx],
                    }, f)
                break
                
    print_stats(v1_wins, v2_wins, draws, v1_tot_pts, v2_tot_pts, N_MATCHES, t0)
    print(f"\nDivergenze salvate in 'replays/': {divergences}")
    print(f"Tempo esecuzione: {time.time()-t0:.1f}s")
