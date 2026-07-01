import scopone_scientifico

def classify_blunder(delta_ev):
    # Unified scale for EV (L1/L2/L3) where 1.0 roughly equals 1 match point.
    if delta_ev < 0.2:
        return "🟢 OPTIMAL"
    elif delta_ev < 0.6:
        return "🟡 SUBOPTIMAL"
    elif delta_ev < 1.2:
        return "🔴 BLUNDER"
    else:
        return "💀 CRITICAL BLUNDER"

DIDACTIC_ENCYCLOPEDIA = {
    "[CAFFO]": "Nello Scopone, il 'Caffo' (o carta spaiata) è una carta di cui rimangono esemplari dispari non catturati. Se sei il giocatore 'di mano', il tuo obiettivo principale è sbilanciare il tavolo creando caffi. Lasciando carte spaiate, impedisci al mazziere di chiudere in pari, costringendolo a regalare carte a fine mano.",
    "[PERDITA CAFFO]": "Essendo tu o il compagno 'di mano', non dovresti mai riaccoppiare carte sul tavolo. Se catturi una carta lasciando il tavolo pulito o senza carte scompagnate, regali un enorme vantaggio al mazziere, che gioca per 'accoppiare' tutto.",
    "[PAREGGIO MIRATO]": "Il ruolo del Mazziere (e del compagno) è 'pareggiare'. Devi catturare le carte in modo che alla fine rimangano solo coppie di carte. Questo garantisce matematicamente alla tua squadra l'importantissima presa finale.",
    "[SPARIGLIO]": "Errore tattico posizionale: essendo nella squadra del Mazziere, non dovresti 'sparigliare' (creare carte dispari). Il tuo obiettivo è pareggiare il tavolo. Aprendo un nuovo Caffo, regali l'iniziativa alla squadra di Mano.",
    "[SANGUE BLU]": "Regola d'oro: il Settebello (7 di Denari) è il pezzo più prezioso. Non si gioca MAI un 7 se il Settebello non è ancora caduto. Regalarlo significa cedere pesantissimi punti per la Primiera, le Carte e i Denari.",
    "[SUICIDIO]": "Scartare il Settebello quando l'avversario può prenderlo è un errore catastrofico. Il Settebello vale un punto intero da solo ed è vitale per Primiera e Denari. È come sacrificare la Regina agli scacchi.",
    "[PERICOLO DENARI]": "I Denari sono il seme più conteso. Anche una scartina di Denari vale tantissimo a fine partita. Scartare Denari in modo incauto regala un punto certo all'avversario.",
    "[SPRECO DI ASSO]": "L'Asso è un'arma tattica: prende sempre in modo diretto (un altro asso). Essendo una presa sicura e indipendente dalle somme, va conservata per rubare una scopa o chiudere in sicurezza.",
    "[SPRECO DI SCUDI]": "Le figure (Fante, Cavallo, Re) sono 'scudi'. Essendo alte, è difficile che subiscano somme. Si usano per sbloccare situazioni pericolose o 'blindare' il tavolo.",
    "[PARIGLIA]": "La Pariglia: giocare una carta di cui possiedi il gemello (es. due 3) è matematicamente sicuro se sei l'unico ad averle. Potrai raccoglierla in totale sicurezza nel turno successivo.",
    "[RISCHIO PRIMIERA]": "I 7 e i 6 sono il fulcro della Primiera, che da sola vale un punto. Lasciarli incustoditi sul tavolo senza garanzie è un grave errore strategico.",
    "[PULIZIA]": "La presa multipla: prendere più carte contemporaneamente in una singola mossa aumenta la tua quota per il punto delle 'Carte' e dei 'Denari'. Una mossa chirurgica.",
    "[PRESA]": "Una cattura diretta mette in sicurezza le carte ed evita l'accumulo di prede pericolose sul tavolo che l'avversario potrebbe spazzare via.",
    "[DENARI]": "Ottima intuizione. A fine round chi ha più di 20 carte di Denari guadagna un punto. Raccoglierli è il fondamento della vittoria.",
    "[SETTEBELLO]": "Hai messo in cassaforte il Settebello! Assicura 1 punto immediato e un contributo essenziale per Primiera e Denari.",
    "[SEME MANCANTE CRITICO]": "Per la Primiera è obbligatorio possedere almeno una carta per ogni seme. Catturare l'unica carta di un seme ti salva dalla sconfitta matematica nel conteggio.",
    "[SEME MANCANTE]": "Avere carte in tutti i semi è essenziale per il calcolo della Primiera. Mossa preventiva magistrale.",
    "[NEGAZIONE]": "La difesa è vitale: sottraendo questa carta mirata, hai appena inflitto un duro colpo alla Primiera o ai Denari degli avversari.",
    "[SCOPA]": "Mossa Perfetta! Nello Scopone la scopa vale un intero punto bonus e spezza moralmente gli avversari.",
    "[PALO A TERRA]": "Tecnica avanzata: 'Piantare un Palo'. Mettendo a terra una carta sapendo tramite deduzione che gli avversari non l'hanno, blocchi il gioco a tuo totale favore.",
    "[RISCHIO SCOPA IN APERTURA]": "Non aprire MAI un tavolo vuoto con carte medio-basse (1-4). Matematicamente, le probabilità che due avversari abbiano proprio quella carta per farti scopa sono letali.",
    "[APERTURA]": "Se devi aprire un tavolo vuoto, usare una carta di cui possiedi copie o che è già uscita riduce ai minimi termini il rischio di subire una Scopa.",
    "[SCARTO SICURO]": "La Memoria Deduttiva in azione! Ricordando cosa gli avversari hanno lasciato a terra in precedenza, hai giocato una carta con la certezza al 100% di non subire danni.",
    "[RISCHIO SCOPA DIRETTO]": "Hai esposto il fianco a una scopa avversaria calcolabile. Devi sempre contare le carte uscite per calcolare le probabilità residue prima di poggiare una carta a terra.",
    "[ASSIST]": "Il Gioco di Squadra: hai preparato il tavolo basandoti sulle probabilità matematiche affinché il tuo compagno possa trarre vantaggio al suo turno.",
    "[RISCHIO PRESA MULTIPLA]": "Lasciare una somma (es. 4+3) espone il tavolo a molteplici attacchi avversari: possono prendere la somma (7) o i singoli (4 o 3). Superficie di rischio triplicata.",
    "[TAVOLO BLINDATO]": "Tecnica di difesa suprema. Hai combinato le carte a terra in valori talmente alti o rari che è statisticamente impossibile per l'avversario fare danni."
}

def extract_primary_reason(user_reason, ai_reason):
    lesson = ""
    # Cerca il primo tag significativo nel feedback dell'IA (la mossa ideale)
    if user_reason:
        for line in user_reason.split('\n'):
            if "[CONTRO]" in line:
                # E' un errore diretto dell'utente
                for tag, explanation in DIDACTIC_ENCYCLOPEDIA.items():
                    if tag in line:
                        lesson = f"[CONTRO] Errore Tattico ({tag})\n{explanation}\n\n[INFO_TECNICA] {line.replace('[CONTRO]', '').strip()}"
                        return lesson
                return line.strip() # Fallback

    if ai_reason:
        for line in ai_reason.split('\n'):
            if "[PRO]" in line:
                for tag, explanation in DIDACTIC_ENCYCLOPEDIA.items():
                    if tag in line:
                        lesson = f"[CONTRO] Occasione Persa ({tag})\nHai ignorato l'alternativa matematicamente superiore.\n\n[LEZIONE]\n{explanation}\n\n[INFO_TECNICA] L'IA avrebbe scelto questa via: {line.replace('[PRO]', '').strip()}"
                        return lesson
                return f"[CONTRO] Occasione Persa\nHai ignorato un'alternativa migliore: {line.replace('[PRO]', '').strip()}"
                
    return "[CONTRO] Analisi Tattica\nMossa matematicamente subottimale rispetto al bilancio delle probabilità e dei caffi residui."

def analyze_move(state, user_card, user_cap):
    current_player = state.players[state.turn]
    ai_card, ai_cap, ev_ai, reason_ai, all_evals = scopone_scientifico.get_best_move(current_player, state)
    
    user_key = (user_card, tuple(user_cap))
    ev_user = ev_ai
    user_reason = reason_ai
    
    if user_key != (ai_card, tuple(ai_cap)):
        if all_evals and user_key in all_evals:
            val = all_evals[user_key]
            ev_user = val[0] if isinstance(val, tuple) else val
            user_reason = val[1] if isinstance(val, tuple) and len(val)>1 else ""
        else:
            all_cards = [scopone_scientifico.Card(v, s) for s in scopone_scientifico.SUITS for v in scopone_scientifico.VALUES]
            known_cards = set(current_player.hand + state.table + state.played_cards)
            unknown_cards = [c for c in all_cards if c not in known_cards]
            ev_user, user_reason = scopone_scientifico.evaluate_move_logic(current_player, state, user_card, user_cap, unknown_cards)

    delta = ev_ai - ev_user
    if delta < 0: delta = 0.0

    return {
        "classification": classify_blunder(delta),
        "primary_reason": extract_primary_reason(user_reason, reason_ai),
        "best_move": (ai_card, ai_cap),
        "ev_loss": delta
    }
