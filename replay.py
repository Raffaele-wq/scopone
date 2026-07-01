import sys
import pickle
import os

def print_replay(filepath):
    if not os.path.exists(filepath):
        print(f"File non trovato: {filepath}")
        return
        
    with open(filepath, "rb") as f:
        data = pickle.load(f)
        
    seed = data['seed']
    turn = data['turn']
    v1_move = data['v1_move']
    v2_move = data['v2_move']
    
    print("="*60)
    print(f" REPLAY ANALISI DIVERGENZA - SEED {seed} - TURNO {turn}")
    print("="*60)
    print(f"\nGiocatore al turno: {v1_move['player']}")
    
    print("\n[SCELTA AI V1 - EURISTICA MANUALE]")
    print(f"Carta giocata: {v1_move['card'].name}")
    catture1 = [c.name for c in v1_move['capture']] if v1_move['capture'] else ['Nessuna']
    print(f"Cattura: {', '.join(catture1)}")
    print(f"EV Stimato: {v1_move['ev']:.2f}")
    print("Motivazioni:")
    for line in v1_move['reason'].split('\n'):
        print(f"  {line}")
        
    print("\n[SCELTA AI V2 - PIMC PRIMIERA GLOBALE]")
    print(f"Carta giocata: {v2_move['card'].name}")
    catture2 = [c.name for c in v2_move['capture']] if v2_move['capture'] else ['Nessuna']
    print(f"Cattura: {', '.join(catture2)}")
    print(f"EV Stimato: {v2_move['ev']:.2f}")
    print("Motivazioni:")
    for line in v2_move['reason'].split('\n'):
        print(f"  {line}")

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Uso: python replay.py replays/divergence_seed_X_turn_Y.pkl")
    else:
        print_replay(sys.argv[1])
