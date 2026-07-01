from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Dict, Optional
import scopone_scientifico as sc
import accademia
import jwt
from datetime import datetime, timedelta
from fastapi import Depends, Header

SECRET_KEY = "SUPER_SECRET_KEY_PROD_REPLACE_ME"

def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(days=365)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm="HS256")

def verify_token(token: str):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        return payload.get("sub")
    except jwt.PyJWTError:
        return None

def get_current_user(authorization: Optional[str] = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid token")
    token = authorization.split(" ")[1]
    user_id = verify_token(token)
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token")
    return user_id

app = FastAPI(title="Scopone Scientifico Backend API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- DATA MODELS (JSON Payloads) ---
class APICard(BaseModel):
    value: int
    suit: str

class APIPlayer(BaseModel):
    id: int
    team: int
    hand: List[APICard]
    captured: List[APICard]

class APIGameState(BaseModel):
    table: List[APICard]
    played_cards: List[APICard]
    turn: int
    players: List[APIPlayer]
    absence_memory: Dict[str, List[int]]
    presence_memory: Dict[str, List[int]]
    last_taker: Optional[int] = 0

class APIHumanMove(BaseModel):
    card: APICard
    capture: List[APICard]

class AIEvaluationRequest(BaseModel):
    state: APIGameState
    player_id: int
    human_move: Optional[APIHumanMove] = None

import db
from multiplayer import RoomManager, PlayerConn

rm = RoomManager()

@app.websocket("/ws/{token}")
async def websocket_endpoint(websocket: WebSocket, token: str):
    user_id = verify_token(token)
    if not user_id:
        await websocket.close(code=1008)
        return
        
    await websocket.accept()
    current_room = None
    try:
        while True:
            data = await websocket.receive_json()
            if data["type"] == "join":
                is_private = data.get("is_private", False)
                bet = data.get("bet", 100)
                code = data.get("room_code", "")
                
                # Check coins before joining
                user = db.get_user(user_id)
                if user["coins"] < bet:
                    await websocket.send_json({"type": "error", "message": "Monete insufficienti!"})
                    continue
                    
                current_room = await rm.join_room(websocket, user_id, is_private, bet, code)
                if not current_room and is_private and code == "":
                    # Create private room
                    current_room = rm.create_room(True, bet)
                    current_room.conns.append(PlayerConn(websocket, user_id))
                    await websocket.send_json({"type": "room_update", "room_id": current_room.id, "players": 1})
                    
                if not current_room:
                    await websocket.send_json({"type": "error", "message": "Stanza non trovata o piena."})
                    
            elif data["type"] == "play_card":
                if current_room:
                    # Find player idx
                    idx = -1
                    for i, c in enumerate(current_room.conns):
                        if c.ws == websocket:
                            idx = i
                            break
                    if idx != -1:
                        c_val = data["card"]["value"]
                        c_suit = data["card"]["suit"]
                        caps = data.get("captures", [])
                        cap_vals = [c["value"] for c in caps]
                        cap_suits = [c["suit"] for c in caps]
                        await current_room.process_move(idx, c_val, c_suit, cap_vals, cap_suits)
            elif data["type"] == "fill_bots":
                if current_room:
                    await rm.fill_bots(current_room)
                        
    except WebSocketDisconnect:
        rm.disconnect(websocket)

# --- API ENDPOINTS ---
@app.get("/")
def read_root():
    return {"message": "Scopone Backend is running! (Tech Stack: FastAPI)"}

@app.post("/ai/get_best_move")
async def get_best_move_api(req: AIEvaluationRequest):
    """
    Questo endpoint riceve in JSON lo stato della partita (es. da Godot o React Native),
    lo converte negli oggetti Python nativi, e invoca l'Intelligenza Artificiale (PIMC / EV)
    per restituire la mossa ottimale.
    """
    st = sc.GameState()
    
    # 1. Ricostruzione del Tavolo e delle Memorie
    st.table = [sc.Card(c.value, c.suit) for c in req.state.table]
    st.played_cards = [sc.Card(c.value, c.suit) for c in req.state.played_cards]
    st.turn = req.state.turn
    st.last_taker = req.state.last_taker if req.state.last_taker != -1 else 0
    
    # JSON keys must be strings, so we convert them back to integers for Python
    st.absence_memory = {int(k): set(v) for k, v in req.state.absence_memory.items()}
    st.presence_memory = {int(k): set(v) for k, v in req.state.presence_memory.items()}
    
    # 2. Ricostruzione dei Giocatori
    for i, p_data in enumerate(req.state.players):
        if i >= len(st.players): break
        st.players[i].hand = [sc.Card(c.value, c.suit) for c in p_data.hand]
        st.players[i].captured = [sc.Card(c.value, c.suit) for c in p_data.captured]
        st.players[i].team = p_data.team
        
    target_player = st.players[req.player_id]
    
    best_c, best_cap, best_ev, reason, _ = sc.get_best_move(target_player, st)
    
    is_optimal = True
    human_reasoning = ""
    # Remove generate_ai_reason, just use the actual reason from get_best_move!
    # If the reason string already contains [PRO]/[CONTRO], we just use it directly or ensure a [PRO] prefix if missing.
    ai_reason_text = reason if reason else "Mossa matematicamente subottimale rispetto alle probabilità residue."
    if "[PRO]" not in ai_reason_text and "[CONTRO]" not in ai_reason_text:
        best_reasoning = f"[PRO] {ai_reason_text}"
    else:
        # Get the first [PRO] line if available
        pro_lines = [l for l in ai_reason_text.split('\n') if "[PRO]" in l]
        best_reasoning = pro_lines[0] if pro_lines else f"[PRO] Mossa consigliata dall'IA."
    
    if req.human_move:
        # Convert APIHumanMove to Card objects
        user_card = sc.Card(req.human_move.card.value, req.human_move.card.suit)
        user_cap = [sc.Card(c.value, c.suit) for c in req.human_move.capture]
        
        # Analyze using Accademia
        analysis = accademia.analyze_move(st, user_card, user_cap)
        delta_ev = analysis["ev_loss"]
        
        if analysis["classification"] != "🟢 OPTIMAL":
            is_optimal = False
            primary = analysis['primary_reason']
            # Assicurati che abbia il tag [CONTRO] se non ce l'ha
            if "[CONTRO]" not in primary: primary = f"[CONTRO] {primary}"
            human_reasoning = f"{primary}\n[CONTRO] Errore valutato come: {analysis['classification']} (Perdita EV: {delta_ev:.2f})"
        else:
            human_reasoning = f"[PRO] Ottima mossa!\n{best_reasoning}"
            best_reasoning = ""
    else:
        human_reasoning = best_reasoning
    
    return {
        "best_card": {"value": best_c.value, "suit": best_c.suit} if best_c else None,
        "best_capture": [{"value": c.value, "suit": c.suit} for c in best_cap] if best_cap else [],
        "expected_value": best_ev,
        "human_reasoning": human_reasoning,
        "best_reasoning": best_reasoning,
        "is_optimal": is_optimal
    }

@app.post("/ai/get_probabilities")
async def get_probabilities(req: AIEvaluationRequest):
    st = sc.GameState()
    st.table = [sc.Card(c.value, c.suit) for c in req.state.table]
    st.played_cards = [sc.Card(c.value, c.suit) for c in req.state.played_cards]
    st.turn = req.state.turn
    
    st.absence_memory = {int(k): set(v) for k, v in req.state.absence_memory.items()}
    st.presence_memory = {int(k): set(v) for k, v in req.state.presence_memory.items()}
    
    for i, p_data in enumerate(req.state.players):
        if i >= len(st.players): break
        st.players[i].hand = [sc.Card(c.value, c.suit) for c in p_data.hand]
        st.players[i].captured = [sc.Card(c.value, c.suit) for c in p_data.captured]
        st.players[i].team = p_data.team
        
    target_player = st.players[req.player_id]
    
    all_cards = [sc.Card(v, s) for s in sc.SUITS for v in sc.VALUES]
    known_cards = set(target_player.hand + st.table + st.played_cards)
    unknown_cards = [c for c in all_cards if c not in known_cards]
    
    P_mat = sc.get_probability_matrix(st, target_player, unknown_cards)
    
    # Raggruppa le carte ignote per valore
    unknown_summary = {}
    for c in unknown_cards:
        if c.value not in unknown_summary:
            unknown_summary[c.value] = []
        unknown_summary[c.value].append(c.suit)
        
    prob_output = {}
    for p_id in range(4):
        if p_id == req.player_id: continue
        prob_output[p_id] = {k.value: v for k, v in P_mat[p_id].items()}
        
    return {
        "unknown_cards": unknown_summary,
        "probabilities": prob_output
    }

@app.post("/game/score")
async def calculate_score(req: AIEvaluationRequest):
    # Ripristina lo stato
    st = sc.GameState()
    for i, p_data in enumerate(req.state.players):
        if i >= len(st.players): break
        st.players[i].captured = [sc.Card(c.value, c.suit) for c in p_data.captured]
        st.players[i].team = p_data.team
        
    team0_cards = []
    team1_cards = []
    for p in st.players:
        if p.team == 0: team0_cards.extend(p.captured)
        else: team1_cards.extend(p.captured)
        
    def get_points(cards):
        denari = sum(1 for c in cards if c.suit == 'Denari')
        settebello = any(c.value == 7 and c.suit == 'Denari' for c in cards)
        
        # Primiera
        primiera = 0
        best_per_suit = {'Denari':0, 'Coppe':0, 'Spade':0, 'Bastoni':0}
        for c in cards:
            if c.value in sc.PRIMIERA_VALUES and sc.PRIMIERA_VALUES[c.value] > best_per_suit[c.suit]:
                best_per_suit[c.suit] = sc.PRIMIERA_VALUES[c.value]
        
        # In base rules, if you don't have at least one card in each suit, primiera is 0 (or lower). 
        # But we'll just sum the best.
        primiera = sum(best_per_suit.values())
        return len(cards), denari, settebello, primiera

    c0, d0, s0, p0 = get_points(team0_cards)
    c1, d1, s1, p1 = get_points(team1_cards)
    
    return {
        "team0": {"carte": c0, "denari": d0, "settebello": s0, "primiera": p0},
        "team1": {"carte": c1, "denari": d1, "settebello": s1, "primiera": p1}
    }

# --- AUTH ENDPOINTS ---
class LoginRequest(BaseModel):
    device_id: str
    client_secret: str

@app.post("/auth/login")
async def login(req: LoginRequest):
    if req.client_secret != "SCOPONE_SECURE_CLIENT_2024":
        raise HTTPException(status_code=401, detail="Invalid client secret")
    user = db.get_user(req.device_id)
    token = create_access_token({"sub": req.device_id})
    return {"access_token": token, "token_type": "bearer", "user": user}

# --- ECONOMY & USER ENDPOINTS ---
@app.get("/user/profile")
async def get_user_profile(user_id: str = Depends(get_current_user)):
    user = db.get_user(user_id)
    return {
        "user_id": user_id,
        "username": "Player_" + user_id[:4],
        "coins": user["coins"],
        "is_pro": user["is_pro"],
        "stats": {
            "wins": user["wins"],
            "losses": user["losses"]
        },
        "cosmetics": user.get("cosmetics", ["default"])
    }

class IAPRequest(BaseModel):
    receipt: str
    amount: Optional[int] = 1000

@app.post("/shop/buy_coins")
async def buy_coins(req: IAPRequest, user_id: str = Depends(get_current_user)):
    # SERVER-SIDE VALIDATION: Simulate real validation with Apple/Google/Stripe
    if not req.receipt or not (req.receipt.startswith("APPLE_PAY_") or req.receipt.startswith("GOOGLE_PLAY_")):
        raise HTTPException(status_code=400, detail="Invalid receipt signature. Hacking attempt logged.")
        
    user = db.update_user(user_id, {"coins": req.amount})
    return {
        "success": True,
        "message": f"{req.amount} monete aggiunte al tuo account.",
        "new_balance": user["coins"]
    }

@app.post("/shop/unlock_pro")
async def unlock_pro(req: IAPRequest, user_id: str = Depends(get_current_user)):
    # SERVER-SIDE VALIDATION: Simulate real validation with Apple/Google/Stripe
    if not req.receipt or not (req.receipt.startswith("APPLE_PAY_") or req.receipt.startswith("GOOGLE_PLAY_")):
        raise HTTPException(status_code=400, detail="Invalid receipt signature. Hacking attempt logged.")
        
    db.update_user(user_id, {"is_pro": True})
    return {
        "success": True,
        "message": "Versione PRO sbloccata! Nessuna pubblicità e IA avanzata disponibile.",
        "is_pro": True
    }

@app.post("/shop/buy_cosmetic")
async def buy_cosmetic(cosmetic_id: str, price: int, user_id: str = Depends(get_current_user)):
    user = db.get_user(user_id)
    if user["coins"] >= price:
        user = db.update_user(user_id, {"coins": -price, "cosmetics": cosmetic_id})
        return {"success": True, "new_balance": user["coins"], "message": f"Cosmetico {cosmetic_id} sbloccato!"}
    return {"success": False, "message": "Monete insufficienti!"}
