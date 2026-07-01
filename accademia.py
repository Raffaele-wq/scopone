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
    "[CAFFO]": "TEORIA DEL CAFFO: Nello Scopone, un 'Caffo' è una carta spaiata (esemplari dispari rimasti in gioco). Il Giocatore 'di Mano' (il primo a giocare o il suo compagno) ha l'imperativo tattico di sbilanciare il tavolo creando caffi (sparigliando). Impedendo al mazziere di chiudere le prese in modo accoppiato, lo si costringe a subire scope o a cedere le carte finali sul tavolo.",
    "[PERDITA CAFFO]": "ERRORE DI POSIZIONE: Essendo nella squadra 'di Mano', il tuo vantaggio risiede nel mantenere il tavolo sbilanciato. Riaccoppiando le carte o pulendo il tavolo, hai regalato un enorme vantaggio matematico al mazziere, che gioca esclusivamente per 'accoppiare' e dominare i resti.",
    "[PAREGGIO MIRATO]": "IL RUOLO DEL MAZZIERE: La tua squadra (Mazziere e compagno) deve sempre 'pareggiare'. L'obiettivo è catturare le carte in modo che rimangano solo coppie. Un tavolo perfettamente pareggiato garantisce matematicamente la conquista dell'ultima presa, un vantaggio spesso decisivo per le sorti della partita.",
    "[SPARIGLIO]": "ERRORE DI SPARIGLIO: Come membro della squadra del Mazziere, non devi mai 'sparigliare' (creare nuovi caffi). Il tuo compito è annullare lo sbilanciamento. Mettendo a terra una carta spaiata, hai appena ceduto l'iniziativa strategica alla squadra avversaria.",
    "[SANGUE BLU]": "SANGUE BLU (REGOLA DEI SETTE): Il Settebello (7 di Denari) è la singola carta più importante del gioco. È severamente vietato giocare un 7 se il Settebello non è ancora caduto. Cedere un 7 regala un vantaggio asimmetrico per la Primiera, il punto delle Carte e i Denari.",
    "[SUICIDIO]": "SUICIDIO TATTICO: Hai scartato il Settebello esponendolo a un'altissima probabilità di cattura avversaria. Il Settebello vale un punto diretto ed è l'ago della bilancia per Primiera e Denari. Una mossa del genere equivale a sacrificare la Regina negli scacchi senza alcuna contropartita.",
    "[PERICOLO DENARI]": "DIFESA DEI DENARI: I Denari sono il seme che decide le partite equilibrate. Ogni singola scartina di Denari conta. Scartare Denari in modo incauto o senza la certezza matematica di poterli riprendere regala punti inestimabili agli avversari.",
    "[SPRECO DI ASSO]": "CONSERVAZIONE DEGLI ASSI: L'Asso cattura esclusivamente in modo diretto (un altro Asso) ed è immune alle somme. È un'arma tattica assoluta, fondamentale per eseguire scope in sicurezza o per chiudere i varchi a fine mano. Va conservato con cura, non sprecato.",
    "[SPRECO DI SCUDI]": "USO DEGLI SCUDI: Le figure (Fante, Cavallo, Re) sono i tuoi 'scudi'. Il loro alto valore numerico le rende statisticamente molto difficili da catturare per somma. Devono essere utilizzate strategicamente per sbloccare il gioco o per 'blindare' il tavolo quando si è sotto pressione.",
    "[PARIGLIA]": "TEORIA DELL'APERTURA (LA PARIGLIA): Giocare una carta di cui possiedi il gemello (es. due 3) è una delle aperture più sicure nello Scopone. Poiché sei l'unico a possedere la chiave per raccoglierla, hai la certezza matematica di poterla riprendere nel turno successivo.",
    "[RISCHIO PRIMIERA]": "GESTIONE DELLA PRIMIERA: I 7 e i 6 sono il motore del punto di Primiera. Lasciarli incustoditi sul tavolo senza una copertura probabilistica è un grave azzardo. La Primiera da sola decide un quarto dei punti in palio.",
    "[PULIZIA]": "LA PRESA MULTIPLA: Una mossa chirurgica. Catturare più carte contemporaneamente in una singola mossa massimizza l'accumulo per il punto delle 'Carte' e dei 'Denari', riducendo contestualmente le opzioni di presa per l'avversario.",
    "[PRESA]": "CATTURA DIRETTA: La base del gioco di accumulo. Portare a casa carte sicure è sempre una mossa solida, poiché priva l'avversario di potenziali bersagli per scope e arricchisce il tuo mazzo per il conteggio finale.",
    "[DENARI]": "ACCUMULO DENARI: Hai incamerato un'ulteriore carta di Denari. Raggiungere quota 6 Denari assicura matematicamente 1 punto a fine partita. Questa è la strategia di base più solida per la vittoria.",
    "[SETTEBELLO]": "CONQUISTA DEL SETTEBELLO: Mossa eccellente! Hai acquisito il pezzo più potente del gioco. Questa cattura assicura 1 punto immediato e sposta drasticamente gli equilibri per i punti di Primiera e Denari.",
    "[SEME MANCANTE CRITICO]": "SALVATAGGIO PRIMIERA: Per calcolare la Primiera è obbligatorio possedere almeno una carta per ogni seme. Catturando l'unico o ultimo esemplare di questo seme, ti sei salvato dalla sconfitta matematica in quella categoria.",
    "[SEME MANCANTE]": "DIVERSIFICAZIONE SEMI: Mossa preventiva da manuale. Mantenere carte in tutti i semi ti permette di concorrere sempre e comunque al calcolo del punto di Primiera.",
    "[NEGAZIONE]": "DIFESA ATTIVA (NEGAZIONE): Nello Scopone, negare punti all'avversario vale quanto guadagnarne. Sottraendo questa carta mirata, hai inflitto un colpo devastante alla loro Primiera o ai loro Denari.",
    "[SCOPA]": "SCOPA MATEMATICA: Un'esecuzione perfetta. La scopa non solo vale un intero punto bonus netto, ma esercita una pressione psicologica immensa, ribaltando l'inerzia della mano a tuo favore.",
    "[PALO A TERRA]": "TECNICA AVANZATA (PIANTARE UN PALO): Mettendo a terra una carta che, per via deduttiva, sai con certezza che gli avversari non possiedono (e non possono sommare), blocchi l'iniziativa tattica. Hai costruito una fortezza inespugnabile.",
    "[RISCHIO SCOPA IN APERTURA]": "ERRORE DI APERTURA: È un dogma dello Scopone Scientifico non aprire mai un tavolo vuoto con carte di valore basso (1, 2, 3, 4). Matematicamente, le combinazioni in mano ai due avversari rendono la probabilità di subire una Scopa inaccettabilmente alta.",
    "[APERTURA]": "APERTURA PROBABILISTICA: Se si è costretti ad aprire un tavolo vuoto, farlo con una carta già uscita in precedenza o di cui si possiedono copie riduce drasticamente l'albero delle probabilità che un avversario possa effettuare una Scopa.",
    "[SCARTO SICURO]": "MEMORIA DEDUTTIVA: Il marchio del vero professionista. Ricordando gli scarti passati e le rinunce avversarie, hai calcolato l'assenza di determinate carte nelle loro mani, giocando uno scarto matematicamente blindato al 100%.",
    "[RISCHIO SCOPA DIRETTO]": "GESTIONE DEL RISCHIO FALLITA: Hai esposto il fianco a una scopa calcolabile. Un buon giocatore conta sempre le carte uscite per determinare le probabilità residue prima di depositare incautamente una carta a terra.",
    "[ASSIST]": "IL GIOCO DI SQUADRA (ASSIST): Lo Scopone si vince in due. Hai preparato il terreno calcolando le probabilità affinché il tuo compagno (che gioca subito dopo l'avversario) possa finalizzare la mossa a vantaggio della squadra.",
    "[RISCHIO PRESA MULTIPLA]": "SUPERFICIE DI RISCHIO: Lasciare sul tavolo una somma (es. 4+3=7) espone a molteplici vettori d'attacco: l'avversario può usare un 7 per prendere tutto, o singoli 4 e 3. Hai triplicato le loro chance di successo.",
    "[TAVOLO BLINDATO]": "BLINDATURA DEL TAVOLO: Hai architettato una difesa perfetta. Combinando le carte a terra in configurazioni di alto valore o asimmetriche, hai reso statisticamente o matematicamente impossibile per gli avversari causare danni.",
    "[COSTRUZIONE]": "COSTRUZIONE MATEMATICA: Non tutte le mosse servono a prendere. Hai giocato questa carta per preparare un incastro probabilistico futuro, aumentando matematicamente le chance di successo per te o per il tuo compagno nel giro successivo."
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
                        lesson = f"[CONTRO] Errore Tattico ({tag})\n[LEZIONE]\n{explanation}"
                        return lesson
                return line.strip() # Fallback

    if ai_reason:
        for line in ai_reason.split('\n'):
            if "[PRO]" in line:
                for tag, explanation in DIDACTIC_ENCYCLOPEDIA.items():
                    if tag in line:
                        lesson = f"[CONTRO] Occasione Persa ({tag})\nHai ignorato l'alternativa matematicamente superiore.\n\n[LEZIONE]\n{explanation}"
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
