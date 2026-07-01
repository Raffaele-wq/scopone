import random
import multiprocessing
import copy
from typing import List, Dict

import scopone_scientifico as sc

# Pesi Base (Fungono da avversario "Standard")
BASE_WEIGHTS = {
    "BASE_CAPTURE_BONUS": 2.0,
    "PAIR_DISCARD_BONUS": 1.5,
    "SCOPA_BONUS": 30.0,
    "SETTEBELLO_BONUS": 15.0,
    "THREAT_MULTIPLIER": 0.8,
    "SYNERGY_MULTIPLIER": 0.8,
    "PRIMIERA_TIE_MULTIPLIER": 2.0,
    "PRIMIERA_BASE_MULTIPLIER": 0.6
}

# --- PARAMETRI PROFESSIONALI ---
NUM_GENERATIONS = 50
POPULATION_SIZE = 20
GAMES_PER_MATCH = 500 # Aumentato drasticamente per abbattere la varianza
INITIAL_MUTATION_RATE = 0.3
INITIAL_MUTATION_IMPACT = 0.4
ELITISM_COUNT = max(1, int(POPULATION_SIZE * 0.05)) # Conserva il top 5% senza mutazioni

def generate_random_weights():
    w = {}
    for k, v in BASE_WEIGHTS.items():
        variation = random.uniform(0.5, 1.5)
        w[k] = v * variation
    return w

def crossover_and_mutate(w1, w2, mutation_rate, mutation_impact):
    w = {}
    for k in w1.keys():
        w[k] = w1[k] if random.random() < 0.5 else w2[k]
        if random.random() < mutation_rate:
            w[k] *= random.uniform(1.0 - mutation_impact, 1.0 + mutation_impact)
    return w

def play_match(weights_t0, weights_t1):
    state = sc.GameState()
    state.players = [sc.Player("Bot0", 0, 0), sc.Player("Bot1", 1, 1), 
                     sc.Player("Bot2", 2, 0), sc.Player("Bot3", 3, 1)]
    for i in [0, 2]: state.players[i].weights = weights_t0
    for i in [1, 3]: state.players[i].weights = weights_t1

    deck = [sc.Card(v, s) for s in sc.SUITS for v in sc.VALUES]
    random.shuffle(deck)
    for i in range(4):
        state.players[i].hand = deck[i*10 : (i+1)*10]
        
    state.turn = 0
    while sum(len(p.hand) for p in state.players) > 0:
        p = state.players[state.turn]
        sc.WEIGHTS.update(p.weights)
        sc.NUM_DETS_TRAINING = 5 
        
        best_c, best_cap, _, _, _ = sc.get_best_move(p, state)
        if not best_cap:
            state.table.append(best_c)
        else:
            p.captured.append(best_c)
            p.captured.extend(best_cap)
            for cap_card in best_cap:
                state.table = [tc for tc in state.table if not (tc.value == cap_card.value and tc.suit == cap_card.suit)]
            if not state.table and sum(len(h.hand) for h in state.players) > 1:
                p.scopas += 1
                
        p.hand = [hc for hc in p.hand if not (hc.value == best_c.value and hc.suit == best_c.suit)]
        state.played_cards.append(best_c)
        
        if not hasattr(state, 'absence_memory'):
            state.absence_memory = {0: set(), 1: set(), 2: set(), 3: set()}
            state.presence_memory = {0: set(), 1: set(), 2: set(), 3: set()}
            
        if not best_cap:
            state.presence_memory[p.id].add(best_c.value)
            import itertools
            for r in range(1, len(state.table) + 1):
                for combo in itertools.combinations(state.table, r):
                    tsum = sum(c.value for c in combo)
                    if 0 < tsum <= 10: state.absence_memory[p.id].add(tsum)
        else:
            if best_c.value in state.presence_memory[p.id]: state.presence_memory[p.id].remove(best_c.value)
            
        state.turn = (state.turn + 1) % 4
        
    t0_caps = state.players[0].captured + state.players[2].captured
    t1_caps = state.players[1].captured + state.players[3].captured
    
    score0, score1 = 0, 0
    if len(t0_caps) > 20: score0 += 1
    elif len(t1_caps) > 20: score1 += 1
    d0 = sum(1 for c in t0_caps if c.suit == 'Denari')
    d1 = sum(1 for c in t1_caps if c.suit == 'Denari')
    if d0 > 5: score0 += 1
    elif d1 > 5: score1 += 1
    if any(c.value == 7 and c.suit == 'Denari' for c in t0_caps): score0 += 1
    if any(c.value == 7 and c.suit == 'Denari' for c in t1_caps): score1 += 1
    score0 += state.players[0].scopas + state.players[2].scopas
    score1 += state.players[1].scopas + state.players[3].scopas
    
    return score0, score1

def evaluate_genome(args):
    weights, opponent_pool = args
    total_score0 = 0
    total_score1 = 0
    wins = 0
    losses = 0
    
    for opponent in opponent_pool:
        # Gioca N partite contro ogni avversario nel pool
        for _ in range(GAMES_PER_MATCH // len(opponent_pool)):
            s0, s1 = play_match(weights, opponent)
            total_score0 += s0
            total_score1 += s1
            if s0 > s1: wins += 1
            elif s1 > s0: losses += 1
            
    print(".", end="", flush=True)
    
    win_rate = wins / max(1, (wins + losses))
    avg_points = total_score0 / GAMES_PER_MATCH
    point_diff = (total_score0 - total_score1) / GAMES_PER_MATCH
    
    # Nuova Fitness Dinamica (Punto 7)
    fitness = (3.0 * win_rate) + (1.0 * avg_points) + (0.5 * point_diff)
    
    return (weights, fitness, win_rate)

if __name__ == "__main__":
    print("Avvio Ottimizzatore Genetico Professionale per Scopone Scientifico...")
    population = [BASE_WEIGHTS] + [generate_random_weights() for _ in range(POPULATION_SIZE - 1)]
    
    best_ever_weights = BASE_WEIGHTS
    best_ever_fitness = -999.0
    
    # Pool di Avversari (Punto 8)
    opponent_pool = [BASE_WEIGHTS]
    
    for generation in range(NUM_GENERATIONS):
        # Mutazione Adattiva (Punto 10)
        progress = generation / float(NUM_GENERATIONS)
        current_mut_rate = INITIAL_MUTATION_RATE * (1.0 - progress)
        current_mut_impact = INITIAL_MUTATION_IMPACT * (1.0 - progress)
        
        print(f"\n--- Generazione {generation + 1}/{NUM_GENERATIONS} [MutRate: {current_mut_rate:.2f}] ---")
        
        args_list = [(p, opponent_pool) for p in population]
        with multiprocessing.Pool() as pool:
            results = pool.map(evaluate_genome, args_list)
            
        results.sort(key=lambda x: x[1], reverse=True)
        best_weights, best_fitness, best_win_rate = results[0]
        
        print(f"\nMiglior Punteggio Gen: {best_fitness:.3f} (Win Rate: {best_win_rate*100:.1f}%)")
        
        # Salvataggio Assoluto Globale (Punto 3)
        if best_fitness > best_ever_fitness:
            best_ever_fitness = best_fitness
            best_ever_weights = copy.deepcopy(best_weights)
            print(">>> NUOVO RECORD GLOBALE SALVATO! <<<")
            
        # Aggiornamento Pool Avversari (Evitare Overfitting)
        if generation % 5 == 0 and generation > 0:
            opponent_pool.append(copy.deepcopy(best_ever_weights))
            if len(opponent_pool) > 3:
                opponent_pool.pop(1) # Tieni sempre la BASE (idx 0), ruota gli altri
        
        # Elitismo Assoluto (Punto 9)
        new_population = [r[0] for r in results[:ELITISM_COUNT]]
        
        # Crossover
        while len(new_population) < POPULATION_SIZE:
            p1 = random.choice(results[:int(POPULATION_SIZE*0.4)])[0]
            p2 = random.choice(results[:int(POPULATION_SIZE*0.4)])[0]
            new_population.append(crossover_and_mutate(p1, p2, current_mut_rate, current_mut_impact))
            
        population = new_population
        
    print("\n[!] ADDESTRAMENTO COMPLETATO.")
    print(f"Miglior Punteggio Assoluto: {best_ever_fitness:.3f}")
    print("I pesi definitivi da usare in produzione sono:")
    print(best_ever_weights)
