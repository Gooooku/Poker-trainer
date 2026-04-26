"""
Poker Combos Trainer v6
- Ranges extraites des images fournies
- Écran de filtres : position + type de pot
- Uniquement les combos qui battent la main hero
"""
from http.server import HTTPServer, BaseHTTPRequestHandler
from socketserver import ThreadingMixIn
from treys import Card, Evaluator
from itertools import combinations
from collections import Counter
import json, random, os

eval_ = Evaluator()
RANKS = 'AKQJT98765432'
SUITS = 'shdc'
SUIT_SYM = {'s':'♠','h':'♥','d':'♦','c':'♣'}
RED_SUITS = {'h','d'}

# ═══════════════════════════════════════════════════════
# EXPANSION DE RANGE
# ═══════════════════════════════════════════════════════

def ri(r): return RANKS.index(r)

def norm_hand(r1, r2, stype=None):
    if ri(r1) > ri(r2): r1, r2 = r2, r1
    return r1+r2+(stype or '')

def poker_expand_range(tokens):
    hands = set()
    for token in tokens:
        token = token.strip()
        if not token: continue
        if '-' in token:
            t1, t2 = token.split('-')
            if len(t1)==2 and t1[0]==t1[1] and len(t2)==2 and t2[0]==t2[1]:
                lo,hi = max(ri(t1[0]),ri(t2[0])),min(ri(t1[0]),ri(t2[0]))
                for i in range(hi,lo+1): hands.add(RANKS[i]*2)
            elif len(t1)==3 and t1[2] in ('s','o'):
                stype,top = t1[2],t1[0]
                lo,hi = max(ri(t1[1]),ri(t2[1])),min(ri(t1[1]),ri(t2[1]))
                for i in range(hi,lo+1):
                    if RANKS[i]!=top: hands.add(norm_hand(top,RANKS[i],stype))
            continue
        if token.endswith('+'):
            base = token[:-1]
            if len(base)==2 and base[0]==base[1]:
                for i in range(0,ri(base[0])+1): hands.add(RANKS[i]*2)
            elif len(base)==3 and base[2] in ('s','o'):
                stype,top,kick = base[2],base[0],base[1]
                for i in range(0,ri(kick)+1):
                    if RANKS[i]!=top: hands.add(norm_hand(top,RANKS[i],stype))
            continue
        if len(token)==2 and token[0]==token[1]: hands.add(token)
        elif len(token)==3 and token[2] in ('s','o'): hands.add(norm_hand(token[0],token[1],token[2]))
    return hands

# ═══════════════════════════════════════════════════════
# RANGES 50BB
# ═══════════════════════════════════════════════════════

RANGES = {
  'LJ_open': {
    'label': 'LJ open',
    'hands': poker_expand_range(['22+','A2s+','K5s+','Q8s+','J8s+','T7s+','97s+','87s','76s','65s','A9o+','KTo+','QTo+','JTo']),
  },
  'BTN_open': {
    'label': 'BTN open',
    'hands': poker_expand_range(['22+','A2s+','K2s+','Q2s+','J2s+','T2s+','95s+','84s+','74s+','63s+','53s+','43s','A2o+','K5o+','Q7o+','J7o+','T7o+','97o+','87o','76o']),
  },
  'SB_3bet_vs_BTN': {
    'label': 'SB 3bet vs BTN',
    'hands': poker_expand_range(['TT+','AJs+','A3s','KQs','K5s-K4s','Q6s','J7s','T7s','97s','87s','76s','AQo+','A9o-A8o','KTo','QTo','JTo']),
  },
  'BB_3bet_vs_BTN': {
    'label': 'BB 3bet vs BTN',
    'hands': poker_expand_range(['TT+','AJs+','KQs','98s','87s','AQo+','A6o','A3o-A2o','K4o','Q5o']),
  },
  'BTN_3bet_vs_LJ': {
    'label': 'BTN 3bet vs LJ',
    'hands': poker_expand_range(['JJ+','AKs','A5s-A4s','K8s-K7s','Q9s-Q8s','J9s','T8s','76s','54s','AQo+','ATo','KJo']),
  },
  'SB_raise_vs_BB': {
    'label': 'SB raise vs BB',
    'hands': poker_expand_range(['KK+','TT-88','A4s+','K7s+','Q9s+','J9s+','J3s-J2s','T8s+','T3s-T2s','98s','65s','54s','AKo','AJo-A9o','KTo+','K6o-K5o','QJo','Q6o-Q5o']),
  },
}

# ═══════════════════════════════════════════════════════
# RANGES HERO (pour les scénarios 3bet)
# None = aléatoire
# ═══════════════════════════════════════════════════════

HERO_RANGES = {
  'vs_LJ_open':  None,
  'vs_BTN_open': None,
  'vs_SB_raise': None,
  'vs_SB_3bet':  poker_expand_range(['KK+','88-44','AQs-A2s','K5s+','Q8s+','J8s+','T8s+','97s+','86s+','76s','65s','54s','AJo-ATo','KJo+','QJo']),
  'vs_BB_3bet':  poker_expand_range(['KK+','99-55','AQs-A2s','K5s+','Q7s+','J8s+','T8s+','97s+','86s+','76s','AJo-A9o','KTo+','QJo']),
  'vs_BTN_3bet': poker_expand_range(['99-55','AQs-A6s','A3s-A2s','K9s+','Q9s+','J9s+','T8s+','97s+','87s','76s','65s','AQo-AJo','KQo']),
}


# Mapping pour l'interface : position hero → ranges adverses disponibles
# "Je suis en position X, l'adversaire est en position Y avec la range Z"
SCENARIOS = [
  {
    'id': 'vs_LJ_open',
    'hero_pos': 'BTN / SB / BB',
    'villain_pos': 'LJ',
    'pot_type': 'Pot ouvert',
    'range_key': 'LJ_open',
    'description': 'Face à un open LJ'
  },
  {
    'id': 'vs_BTN_open',
    'hero_pos': 'SB / BB',
    'villain_pos': 'BTN',
    'pot_type': 'Pot ouvert',
    'range_key': 'BTN_open',
    'description': 'Face à un open BTN'
  },
  {
    'id': 'vs_SB_3bet',
    'hero_pos': 'BTN',
    'villain_pos': 'SB',
    'pot_type': 'Pot 3bet',
    'range_key': 'SB_3bet_vs_BTN',
    'description': 'Face au 3bet SB (vs BTN open)'
  },
  {
    'id': 'vs_BB_3bet',
    'hero_pos': 'BTN',
    'villain_pos': 'BB',
    'pot_type': 'Pot 3bet',
    'range_key': 'BB_3bet_vs_BTN',
    'description': 'Face au 3bet BB (vs BTN open)'
  },
  {
    'id': 'vs_BTN_3bet',
    'hero_pos': 'LJ',
    'villain_pos': 'BTN',
    'pot_type': 'Pot 3bet',
    'range_key': 'BTN_3bet_vs_LJ',
    'description': 'Face au 3bet BTN (vs LJ open)'
  },
  {
    'id': 'vs_SB_raise',
    'hero_pos': 'BB',
    'villain_pos': 'SB',
    'pot_type': 'Pot ouvert',
    'range_key': 'SB_raise_vs_BB',
    'description': 'Face au raise SB (vs BB)'
  },
]

CLASS_NAMES = {
  1:'Quinte Flush', 2:'Carré', 3:'Full House',
  4:'Couleur', 5:'Quinte', 6:'Brelan',
  7:'Deux Paires', 8:'Paire', 9:'Hauteur',
}
DISPLAY_ORDER = [1,2,3,4,5,6,7,8,9]

def build_deck():
    return [Card.new(r+s) for r in RANKS for s in SUITS]

def cs(c): return Card.int_to_str(c)

def card_display(s):
    r,s2 = s[0],s[1]
    return {'rank':r,'suit':SUIT_SYM[s2],'red':s2 in RED_SUITS,'raw':s}

def poker_expand_range(range_set):
    hands = []
    seen = set()
    for h in range_set:
        h = h.strip()
        if not h: continue
        if len(h)==2 and h[0]==h[1]:  # pocket pair
            r = h[0]
            if r not in RANKS: continue
            for s1,s2 in combinations(SUITS,2):
                key = (r,r,s1,s2)
                if key not in seen:
                    seen.add(key); hands.append(key)
        elif len(h)==3 and h[2]=='s':
            r1,r2 = h[0],h[1]
            if r1 not in RANKS or r2 not in RANKS: continue
            for s in SUITS:
                key = (r1,r2,s,s)
                if key not in seen:
                    seen.add(key); hands.append(key)
        elif len(h)==3 and h[2]=='o':
            r1,r2 = h[0],h[1]
            if r1 not in RANKS or r2 not in RANKS: continue
            for s1 in SUITS:
                for s2 in SUITS:
                    if s1!=s2:
                        key=(r1,r2,s1,s2)
                        if key not in seen:
                            seen.add(key); hands.append(key)
    return hands

def hands_after_blockers(range_hands, blockers_set):
    return [(r1,r2,s1,s2) for (r1,r2,s1,s2) in range_hands
            if r1+s1 not in blockers_set and r2+s2 not in blockers_set]

# ── PRÉCALCUL DES RANGES ET GRILLES (fait une seule fois au démarrage) ──
_EXPANDED_RANGES = {}
_GRIDS = {}

def _precompute():
    for key, info in RANGES.items():
        _EXPANDED_RANGES[key] = poker_expand_range(info['hands'])
        grid = {}
        for r1 in RANKS:
            for r2 in RANKS:
                i,j = RANKS.index(r1),RANKS.index(r2)
                if i==j: k=r1+r2
                elif i<j: k=r1+r2+'s'
                else: k=r2+r1+'o'
                grid[r1+'_'+r2] = k in info['hands']
        _GRIDS[key] = grid

_precompute()

# ── CACHE DE QUESTIONS (générées à l'avance) ──
import threading
_QUESTION_CACHE = []
_CACHE_SIZE = 30
_CACHE_LOCK = threading.Lock()

def _fill_cache():
    while True:
        with _CACHE_LOCK:
            size = len(_QUESTION_CACHE)
        if size < _CACHE_SIZE:
            q = _generate_question()
            with _CACHE_LOCK:
                _QUESTION_CACHE.append(q)
        else:
            import time; time.sleep(0.5)

def _start_cache_filler():
    t = threading.Thread(target=_fill_cache, daemon=True)
    t.start()

def is_interesting(hero, board):
    h0r,h1r = cs(hero[0])[0],cs(hero[1])[0]
    board_ranks = [cs(c)[0] for c in board]
    board_suits = [cs(c)[1] for c in board]
    h0s,h1s = cs(hero[0])[1],cs(hero[1])[1]
    cl = eval_.get_rank_class(eval_.evaluate(board, hero))
    flush_draw = (h0s==h1s and board_suits.count(h0s)>=2) or board_suits.count(h0s)>=3 or board_suits.count(h1s)>=3
    all_ri = sorted(set([RANKS.index(r) for r in board_ranks+[h0r,h1r]]))
    straight_draw = any(
        len([x for x in all_ri if all_ri[i]<=x<=all_ri[i]+4])>=4
        for i in range(len(all_ri)-2)
    )
    has_pair = h0r in board_ranks or h1r in board_ranks
    return cl<=6 or has_pair or (h0r==h1r) or flush_draw or straight_draw

def hero_hand_key(hero):
    h0s,h1s = cs(hero[0]),cs(hero[1])
    h0r,h0suit = h0s[0],h0s[1]
    h1r,h1suit = h1s[0],h1s[1]
    ri0,ri1 = RANKS.index(h0r),RANKS.index(h1r)
    if ri0<ri1: top,bot,ts,bs = h0r,h1r,h0suit,h1suit
    elif ri0>ri1: top,bot,ts,bs = h1r,h0r,h1suit,h0suit
    else: return h0r+h1r
    return top+bot+('s' if ts==bs else 'o')

def _generate_question(scenario_id=None):
    deck_base = build_deck()
    board_size = random.choices([3,4,5], weights=[3,3,4])[0]
    street = {3:'Flop',4:'Turn',5:'River'}[board_size]

    if scenario_id:
        scenario = next((s for s in SCENARIOS if s['id']==scenario_id), None)
    if not scenario_id or not scenario:
        scenario = random.choice(SCENARIOS)

    range_key = scenario['range_key']
    range_info = RANGES[range_key]
    range_set = range_info['hands']

    # Range hero : definie ou aleatoire
    hero_range = HERO_RANGES.get(scenario['id'], None)

    for _ in range(100):
        deck = deck_base[:]
        random.shuffle(deck)
        hero = deck[:2]
        board = deck[2:2+board_size]
        hkey = hero_hand_key(hero)
        # Si range hero definie, verifier que la main est dedans
        if hero_range is not None and hkey not in hero_range:
            continue
        if is_interesting(hero, board):
            break

    blockers_raw = set([cs(c) for c in hero+board])
    hero_score = eval_.evaluate(board, hero)
    hero_cl = eval_.get_rank_class(hero_score)
    hero_hand_name = CLASS_NAMES.get(hero_cl,'?')

    valid_hands = hands_after_blockers(_EXPANDED_RANGES[range_key], blockers_raw)

    beating_by_class = Counter()
    total_beating = 0
    for (r1,r2,s1,s2) in valid_hands:
        score = eval_.evaluate(board, [Card.new(r1+s1), Card.new(r2+s2)])
        if score < hero_score:
            cl = eval_.get_rank_class(score)
            beating_by_class[cl] += 1
            total_beating += 1

    fields = []
    for cl in DISPLAY_ORDER:
        if cl > hero_cl: continue
        fields.append({'class_id':cl,'label':CLASS_NAMES[cl],'answer':beating_by_class.get(cl,0)})
    if not fields:
        fields.append({'class_id':hero_cl,'label':CLASS_NAMES.get(hero_cl,'?'),'answer':0})

    grid = _GRIDS[range_key]

    return {
        'hero':[card_display(cs(c)) for c in hero],
        'board':[card_display(cs(c)) for c in board],
        'street':street,
        'hero_hand':hero_hand_name,
        'hero_hand_key':hero_hand_key(hero),
        'scenario': scenario,
        'range_label': range_info['label'],
        'total_range_combos':len(valid_hands),
        'total_beating':total_beating,
        'fields':fields,
        'grid':grid,
    }


def deal_question(scenario_id=None):
    """Sert une question depuis le cache si possible, sinon génère à la volée."""
    if not scenario_id:
        with _CACHE_LOCK:
            if _QUESTION_CACHE:
                return _QUESTION_CACHE.pop(0)
    return _generate_question(scenario_id)


HTML = r"""<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, viewport-fit=cover">
<title>Poker Combos Trainer</title>
<meta name="theme-color" content="#0d0f14">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
<meta name="apple-mobile-web-app-title" content="Poker Combos">
<link rel="manifest" href="/manifest.json">
<link rel="apple-touch-icon" href="/icon-192.png">
<link href="https://fonts.googleapis.com/css2?family=DM+Mono:wght@400;500&family=Syne:wght@700;800&display=swap" rel="stylesheet">
<style>
:root{--bg:#0d0f14;--surface:#161920;--surface2:#1e2330;--border:#2a3045;--accent:#4f8ef7;--accent2:#7c5cfc;--green:#2dd4a0;--red:#f75f5f;--amber:#f7c94f;--text:#e8ecf5;--text2:#7a8399;--text3:#4a5268;}
*{box-sizing:border-box;margin:0;padding:0;}
body{background:var(--bg);color:var(--text);font-family:'DM Mono',monospace;min-height:100vh;display:flex;flex-direction:column;align-items:center;padding:max(28px,env(safe-area-inset-top)) 12px max(80px,env(safe-area-inset-bottom));}
h1{font-family:'Syne',sans-serif;font-size:28px;font-weight:800;letter-spacing:-1px;background:linear-gradient(135deg,var(--accent),var(--accent2));-webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text;}
.sub{color:var(--text2);font-size:11px;margin-top:4px;}
.main{width:100%;max-width:920px;margin-top:24px;display:flex;flex-direction:column;gap:12px;}

/* STATS */
.stats{display:grid;grid-template-columns:repeat(4,1fr);gap:8px;}
.stat{background:var(--surface2);border:1px solid var(--border);border-radius:10px;padding:10px;text-align:center;}
.stat-v{font-family:'Syne',sans-serif;font-size:20px;font-weight:800;}
.stat-l{font-size:10px;color:var(--text3);margin-top:2px;text-transform:uppercase;letter-spacing:.07em;}
.s-ok .stat-v{color:var(--green);}.s-str .stat-v{color:var(--amber);}.s-sc .stat-v{color:var(--accent);}

/* FILTER SCREEN */
#filter-screen{width:100%;max-width:920px;margin-top:24px;}
.filter-card{background:var(--surface);border:1px solid var(--border);border-radius:16px;padding:24px 26px;margin-bottom:12px;}
.filter-title{font-family:'Syne',sans-serif;font-size:18px;font-weight:800;margin-bottom:16px;color:var(--text);}
.filter-group{margin-bottom:20px;}
.filter-group-label{font-size:10px;text-transform:uppercase;letter-spacing:.12em;color:var(--text3);margin-bottom:10px;}
.filter-chips{display:flex;flex-wrap:wrap;gap:8px;}
.chip{padding:8px 16px;border-radius:24px;border:1px solid var(--border);background:var(--surface2);color:var(--text2);font-size:13px;font-family:'DM Mono',monospace;cursor:pointer;transition:all .15s;}
.chip:hover{border-color:var(--accent);color:var(--text);}
.chip.active{background:var(--accent);border-color:var(--accent);color:#fff;font-weight:500;}
.chip.pot-3bet.active{background:var(--accent2);border-color:var(--accent2);}
.start-btn{width:100%;height:52px;border-radius:12px;border:none;background:linear-gradient(135deg,var(--accent),var(--accent2));color:#fff;font-family:'Syne',sans-serif;font-size:16px;font-weight:800;cursor:pointer;transition:opacity .15s;margin-top:8px;}
.start-btn:hover{opacity:.9;}
.start-btn:disabled{opacity:.4;cursor:default;}
.scenario-cards{display:grid;grid-template-columns:repeat(auto-fill,minmax(240px,1fr));gap:10px;}
.scenario-card{padding:14px 16px;border-radius:12px;border:1px solid var(--border);background:var(--surface2);cursor:pointer;transition:all .15s;}
.scenario-card:hover{border-color:var(--accent);background:#1a2235;}
.scenario-card.selected{border-color:var(--accent);background:#1a2235;box-shadow:0 0 0 2px var(--accent);}
.sc-pot{font-size:10px;text-transform:uppercase;letter-spacing:.1em;color:var(--text3);margin-bottom:4px;}
.sc-desc{font-size:13px;color:var(--text);font-weight:500;}
.sc-sub{font-size:11px;color:var(--text2);margin-top:3px;}

/* GAME SCREEN */
#game-screen{display:none;width:100%;max-width:920px;margin-top:24px;}
.card{background:var(--surface);border:1px solid var(--border);border-radius:14px;padding:18px 20px;}
.lbl{font-size:10px;font-weight:500;letter-spacing:.14em;text-transform:uppercase;color:var(--text3);margin-bottom:8px;}
.top-row{display:flex;justify-content:space-between;align-items:center;margin-bottom:4px;flex-wrap:wrap;gap:6px;}
.progress{height:3px;background:var(--border);border-radius:2px;overflow:hidden;margin-bottom:12px;}
.prog-fill{height:100%;background:linear-gradient(90deg,var(--accent),var(--accent2));border-radius:2px;transition:width .4s;width:0%;}
.two-col{display:grid;grid-template-columns:1fr 1fr;gap:16px;align-items:start;}
@media(max-width:640px){.two-col{grid-template-columns:1fr;}}

/* CARTES */
.playing-card{display:inline-flex;flex-direction:column;align-items:flex-start;justify-content:space-between;width:50px;height:70px;background:#fff;border-radius:7px;border:1px solid #bbb;padding:4px 5px;box-shadow:2px 3px 8px rgba(0,0,0,.5);font-family:'DM Mono',monospace;}
.playing-card .top{font-size:14px;font-weight:700;line-height:1;}
.playing-card .mid{font-size:20px;text-align:center;width:100%;line-height:1;}
.playing-card .bot{font-size:14px;font-weight:700;line-height:1;transform:rotate(180deg);align-self:flex-end;}
.playing-card.black .top,.playing-card.black .bot,.playing-card.black .mid{color:#111;}
.playing-card.red-c .top,.playing-card.red-c .bot,.playing-card.red-c .mid{color:#cc1111;}
.playing-card.hero-c{border:2.5px solid var(--accent);box-shadow:2px 3px 6px rgba(0,0,0,.5),0 0 12px rgba(79,142,247,.4);}
.cards-row{display:flex;gap:6px;flex-wrap:wrap;}
.cards-label{font-size:10px;color:var(--text3);margin-bottom:5px;letter-spacing:.1em;text-transform:uppercase;}
.cards-block{display:flex;gap:16px;flex-wrap:wrap;align-items:flex-start;margin-bottom:10px;}

.badge{display:inline-block;font-size:11px;padding:3px 10px;border-radius:20px;margin-right:5px;margin-bottom:4px;}
.b-street{background:#1a2a4a;color:var(--accent);border:1px solid #2a3f6a;}
.b-sit{background:#1a2a1a;color:var(--green);border:1px solid #1a4a2a;}
.b-sit-3bet{background:#2a1a3a;color:#b07cf7;border:1px solid #3f2a6a;}
.b-hero{background:#2a1e0a;color:var(--amber);border:1px solid #4a3210;}
.b-info{background:#1e1e1e;color:var(--text2);border:1px solid var(--border);font-size:10px;}

.main-question{background:linear-gradient(135deg,#0f1a2e,#1a0f2e);border:1px solid #2a3f6a;border-radius:12px;padding:14px 16px;margin-bottom:14px;}
.mq-text{font-family:'Syne',sans-serif;font-size:16px;font-weight:800;color:var(--text);line-height:1.4;}
.mq-sub{font-size:11px;color:var(--text2);margin-top:4px;}

/* GRILLE */
.range-toggle button{height:28px;padding:0 12px;border-radius:8px;font-size:11px;font-family:'Syne',sans-serif;font-weight:700;border:1px solid var(--border);background:var(--surface2);color:var(--text);cursor:pointer;margin-bottom:6px;}
.range-toggle button:hover{background:var(--border);}
.grid-wrap{overflow-x:auto;}
table.rgrid{border-collapse:collapse;width:100%;}
table.rgrid td{width:7.69%;aspect-ratio:1;border:0.5px solid #1a1e2a;font-size:8px;font-weight:500;text-align:center;vertical-align:middle;color:var(--text3);background:var(--surface2);padding:0;line-height:1;}
table.rgrid td.in-range{background:#1a3a2a;color:#5dca9e;}
table.rgrid td.pp{background:#1e1e2a;}
table.rgrid td.pp.in-range{background:#1a2a3a;color:var(--accent);}
table.rgrid td.hero-hand{outline:2px solid var(--amber);outline-offset:-2px;}

/* FIELDS */
.fields-title{font-size:12px;color:var(--text2);margin-bottom:8px;line-height:1.5;}
.fields-grid{display:grid;grid-template-columns:1fr 1fr;gap:7px;}
.field-row{display:flex;align-items:center;gap:7px;background:var(--surface2);border:1px solid var(--border);border-radius:9px;padding:8px 10px;}
.field-label{flex:1;font-size:12px;color:var(--text2);}
.field-input{width:64px;height:36px;background:#fff;border:1.5px solid #999;border-radius:7px;color:#111;font-family:'Syne',sans-serif;font-size:16px;font-weight:800;text-align:center;outline:none;transition:border-color .15s;}
.field-input:focus{border-color:var(--accent);}
.field-input.correct{background:#e6fff5;border-color:#2dd4a0!important;}
.field-input.wrong{background:#fff2f2;border-color:#f75f5f!important;}
.field-res{width:20px;text-align:center;font-size:12px;}
.field-res.ok{color:var(--green);}.field-res.ko{color:var(--red);}
.field-ans{font-size:11px;color:var(--red);min-width:20px;text-align:right;display:none;font-weight:700;}
.field-ans.show{display:block;}

.actions{display:flex;gap:8px;margin-top:12px;flex-wrap:wrap;}
.btn{height:44px;padding:0 18px;border-radius:10px;font-family:'Syne',sans-serif;font-size:13px;font-weight:700;border:none;cursor:pointer;transition:transform .1s;}
.btn:active{transform:scale(.97);}
.btn-p{background:linear-gradient(135deg,var(--accent),var(--accent2));color:#fff;}
.btn-n{background:var(--surface2);color:var(--text);border:1px solid var(--border);height:34px;padding:0 12px;font-size:12px;}
.btn-amber{background:#1e1c0d;color:var(--amber);border:1px solid #3a3210;height:44px;padding:0 16px;}
.btn-filter{background:var(--surface2);color:var(--text2);border:1px solid var(--border);height:34px;padding:0 12px;font-size:12px;}

.summary{margin-top:10px;padding:12px 14px;border-radius:10px;display:none;}
.summary.show{display:block;}
.summary.all-ok{background:#0a2018;border:1px solid #1a4a30;}
.summary.partial{background:#1a1400;border:1px solid #3a2a00;}
.sum-title{font-family:'Syne',sans-serif;font-size:15px;font-weight:800;margin-bottom:4px;}
.sum-title.ok{color:var(--green);}.sum-title.ko{color:var(--amber);}
.sum-detail{font-size:11px;color:var(--text2);line-height:2;}

.hint-box{margin-top:8px;padding:10px 14px;background:#1e1c0d;border:1px solid #3a3210;border-radius:8px;font-size:12px;color:var(--amber);display:none;}
.hint-box.show{display:block;}
.loading{color:var(--text2);font-size:14px;padding:40px 0;text-align:center;}
.help{font-size:11px;color:var(--text3);line-height:2;}
.help b{color:var(--text2);}
@keyframes shake{0%,100%{transform:translateX(0)}20%{transform:translateX(-6px)}40%{transform:translateX(6px)}60%{transform:translateX(-4px)}80%{transform:translateX(4px)}}
.shake{animation:shake .3s ease;}
</style>
</head>
<body>
<div style="display:flex;align-items:center;justify-content:space-between;width:100%;max-width:920px;margin-bottom:4px;">
  <div>
    <h1>Poker Combos Trainer</h1>
    <p class="sub">Ranges 50BB · Combien de combos te battent ?</p>
  </div>
  <a href="/" style="height:36px;padding:0 14px;border-radius:9px;background:#1e2330;border:1px solid #2a3045;color:#7a8399;font-family:'Syne',sans-serif;font-size:13px;font-weight:700;text-decoration:none;display:flex;align-items:center;gap:6px;flex-shrink:0;">&#8592; Accueil</a>
</div>

<!-- ══ ÉCRAN FILTRES ══ -->
<div id="filter-screen">
  <div class="filter-card">
    <div class="filter-title">Choisis un scénario <span style="font-size:13px;font-weight:400;color:var(--text2);margin-left:8px;">— Ranges 50BB</span></div>
    <div class="scenario-cards" id="scenario-cards"></div>
    <button class="start-btn" id="start-btn" disabled onclick="startGame()">Lancer →</button>
  </div>
</div>

<!-- ══ ÉCRAN JEU ══ -->
<div id="game-screen">
  <div class="stats">
    <div class="stat s-ok"><div class="stat-v" id="s-ok">0</div><div class="stat-l">Corrects</div></div>
    <div class="stat"><div class="stat-v" id="s-tot">0</div><div class="stat-l">Tentatives</div></div>
    <div class="stat s-str"><div class="stat-v" id="s-str">0</div><div class="stat-l">Streak</div></div>
    <div class="stat s-sc"><div class="stat-v" id="s-pct">—</div><div class="stat-l">Score</div></div>
  </div>
  <div style="margin-top:10px">
    <div class="card">
      <div class="top-row">
        <div class="lbl">Question</div>
        <div style="display:flex;gap:6px;">
          <button class="btn btn-filter" onclick="goToFilters()">← Filtres</button>
          <button class="btn btn-n" onclick="newQ()">Nouvelle ↺</button>
        </div>
      </div>
      <div class="progress"><div class="prog-fill" id="prog"></div></div>
      <div id="q-area"><div class="loading">Chargement...</div></div>
    </div>
    <div class="card" style="margin-top:12px">
      <div class="lbl">Rappel</div>
      <div class="help">
        <b>Objectif</b> : compter uniquement les combos de la range qui font une main plus forte que la tienne.<br>
        <b>Bloqueurs</b> : ta main + board retirent des copies de chaque rang.<br>
        <b>Même classe</b> : un brelan peut battre un autre brelan si le rang est plus élevé.
      </div>
    </div>
  </div>
</div>

<script>
const RANKS13=['A','K','Q','J','T','9','8','7','6','5','4','3','2'];
const SCENARIOS_CLIENT = """ + json.dumps(SCENARIOS) + r""";

let state={},stats={ok:0,tot:0,streak:0,fok:0,ftot:0};
let answered=false,gridVisible=false;
let selectedScenario=null;

// ── FILTRES ──────────────────────────────────────────
function initFilters(){
  const container=document.getElementById('scenario-cards');
  container.innerHTML=SCENARIOS_CLIENT.map(s=>`
    <div class="scenario-card" onclick="selectScenario('${s.id}',this)" data-id="${s.id}">
      <div class="sc-pot">${s.pot_type}</div>
      <div class="sc-desc">${s.description}</div>
      <div class="sc-sub">Hero : ${s.hero_pos} · Villain : ${s.villain_pos}</div>
    </div>`).join('');
}

function selectScenario(id, el){
  document.querySelectorAll('.scenario-card').forEach(c=>c.classList.remove('selected'));
  el.classList.add('selected');
  selectedScenario=id;
  document.getElementById('start-btn').disabled=false;
}

function startGame(){
  if(!selectedScenario) return;
  document.getElementById('filter-screen').style.display='none';
  document.getElementById('game-screen').style.display='block';
  newQ();
}

function goToFilters(){
  document.getElementById('game-screen').style.display='none';
  document.getElementById('filter-screen').style.display='block';
}

// ── JEU ──────────────────────────────────────────────
function cardHTML(c,cls=''){
  const col=c.red?'red-c':'black';
  return `<div class="playing-card ${col} ${cls}"><span class="top">${c.rank}${c.suit}</span><span class="mid">${c.suit}</span><span class="bot">${c.rank}${c.suit}</span></div>`;
}

function buildGrid(grid,heroKey){
  let html='<table class="rgrid">';
  for(let i=0;i<13;i++){
    html+='<tr>';
    for(let j=0;j<13;j++){
      const r1=RANKS13[i],r2=RANKS13[j];
      const pp=i===j,suited=i<j;
      let label=pp?r1+r2:(suited?r1+r2+'s':r2+r1+'o');
      const inRange=grid[r1+'_'+r2],isHero=label===heroKey;
      let cls=pp?'pp':'';
      if(inRange)cls+=' in-range';
      if(isHero)cls+=' hero-hand';
      html+=`<td class="${cls.trim()}">${label}</td>`;
    }
    html+='</tr>';
  }
  return html+'</table>';
}

async function newQ(){
  answered=false; gridVisible=false;
  document.getElementById('q-area').innerHTML='<div class="loading">Calcul en cours...</div>';
  try{
    const url='/question'+(selectedScenario?'?scenario='+selectedScenario:'');
    const r=await fetch(url);
    state=await r.json();
    renderQ();
  }catch(e){
    document.getElementById('q-area').innerHTML='<div class="loading" style="color:#f75f5f">Erreur serveur.</div>';
  }
}

function renderQ(){
  const heroHTML=state.hero.map(c=>cardHTML(c,'hero-c')).join('');
  const boardHTML=state.board.map(c=>cardHTML(c,'')).join('');
  const fieldsHTML=state.fields.map((f,i)=>`
    <div class="field-row">
      <span class="field-label">${f.label}</span>
      <input class="field-input" id="fi-${i}" type="number" min="0" max="9999" placeholder="?"
             onkeydown="if(event.key==='Enter')focusNext(${i})"/>
      <span class="field-res" id="fres-${i}"></span>
      <span class="field-ans" id="fans-${i}"></span>
    </div>`).join('');

  const is3bet = state.scenario.pot_type.includes('3bet');
  const sitClass = is3bet ? 'b-sit-3bet' : 'b-sit';

  document.getElementById('q-area').innerHTML=`
    <div style="display:flex;align-items:center;flex-wrap:wrap;gap:5px;margin-bottom:12px;">
      <span class="badge b-street">${state.street}</span>
      <span class="badge ${sitClass}">${state.scenario.description}</span>
      <span class="badge b-info">${state.total_range_combos} combos dans la range</span><span class="badge b-info">50BB</span>
    </div>
    <div class="main-question">
      <div class="mq-text">Combien de combos de la range <b>${state.range_label}</b> battent ta main ?</div>
      <div class="mq-sub">Décompose par type de main — uniquement les mains plus fortes que toi</div>
    </div>
    <div class="two-col">
      <div>
        <div class="cards-block">
          <div>
            <div class="cards-label">Ta main (hero)</div>
            <div class="cards-row">${heroHTML}</div>
            <div style="margin-top:6px"><span class="badge b-hero">Ta main : ${state.hero_hand}</span></div>
          </div>
          <div>
            <div class="cards-label">Board — ${state.street}</div>
            <div class="cards-row">${boardHTML}</div>
          </div>
        </div>
        <div style="margin-top:8px">
          <div class="range-toggle"><button onclick="toggleGrid()">Voir la range ▾</button></div>
          <div id="grid-area" style="display:none">
            <div class="grid-wrap">${buildGrid(state.grid,state.hero_hand_key)}</div>
            <div style="display:flex;gap:10px;margin-top:5px;font-size:10px;color:var(--text3);flex-wrap:wrap;">
              <span><span style="display:inline-block;width:8px;height:8px;background:#1a3a2a;border-radius:2px;vertical-align:middle;margin-right:3px;"></span>Dans la range</span>
              <span><span style="display:inline-block;width:8px;height:8px;outline:2px solid var(--amber);border-radius:2px;vertical-align:middle;margin-right:3px;"></span>Ta main</span>
            </div>
          </div>
        </div>
      </div>
      <div>
        <div class="fields-title">Décompose les <b style="color:var(--text)">${state.total_beating}</b> combos qui te battent :</div>
        <div class="fields-grid">${fieldsHTML}</div>
        <div class="actions">
          <button class="btn btn-p" onclick="checkAll()">Valider</button>
          <button class="btn btn-amber" onclick="showHint()">Indice</button>
        </div>
        <div class="hint-box" id="hint-box"></div>
        <div class="summary" id="summary">
          <div class="sum-title" id="sum-title"></div>
          <div class="sum-detail" id="sum-detail"></div>
        </div>
      </div>
    </div>`;
  setTimeout(()=>{const f=document.getElementById('fi-0');if(f)f.focus();},100);
}

function toggleGrid(){
  const area=document.getElementById('grid-area');
  if(!area)return;
  gridVisible=!gridVisible;
  area.style.display=gridVisible?'block':'none';
}

function focusNext(i){
  const next=document.getElementById('fi-'+(i+1));
  if(next)next.focus();else checkAll();
}

function checkAll(){
  if(answered){newQ();return;}
  answered=true;
  let okCount=0,details=[];
  state.fields.forEach((f,i)=>{
    const inp=document.getElementById('fi-'+i),res=document.getElementById('fres-'+i),ans=document.getElementById('fans-'+i);
    const val=parseInt(inp.value),correct=f.answer;
    stats.ftot++;
    if(!isNaN(val)&&val===correct){
      inp.className='field-input correct';res.className='field-res ok';res.textContent='✓';stats.fok++;okCount++;
    }else{
      inp.className='field-input wrong';res.className='field-res ko';res.textContent='✗';
      ans.className='field-ans show';ans.textContent=correct;
      details.push(`${f.label} → ${correct}`);
      inp.classList.add('shake');setTimeout(()=>inp.classList.remove('shake'),350);
    }
  });
  stats.tot++;
  if(okCount===state.fields.length){stats.ok++;stats.streak++;}else stats.streak=0;
  const sumEl=document.getElementById('summary'),titleEl=document.getElementById('sum-title'),detailEl=document.getElementById('sum-detail');
  if(okCount===state.fields.length){
    sumEl.className='summary show all-ok';titleEl.className='sum-title ok';
    titleEl.textContent=`Parfait ! ${state.total_beating} combos te battent sur ${state.total_range_combos} dans la range.`;
    detailEl.textContent='';
  }else{
    sumEl.className='summary show partial';titleEl.className='sum-title ko';
    titleEl.textContent=`${okCount}/${state.fields.length} correct${okCount>1?'s':''}. Corrections :`;
    detailEl.innerHTML=details.map(d=>`<span style="color:var(--text)">${d}</span>`).join(' · ');
  }
  const area=document.getElementById('grid-area');
  if(area){area.style.display='block';gridVisible=true;}
  updateStats();
}

function showHint(){
  const h=document.getElementById('hint-box');
  if(h.classList.contains('show')){h.className='hint-box';return;}
  const top=state.fields.reduce((a,b)=>b.answer>a.answer?b:a,state.fields[0]);
  h.innerHTML=`Total qui te battent : <b style="color:var(--text)">${state.total_beating}</b> · Catégorie dominante : <b style="color:var(--text)">${top.label} (${top.answer})</b>`;
  h.className='hint-box show';
}

function updateStats(){
  document.getElementById('s-ok').textContent=stats.ok;
  document.getElementById('s-tot').textContent=stats.tot;
  document.getElementById('s-str').textContent=stats.streak;
  document.getElementById('s-pct').textContent=stats.tot?Math.round(stats.ok/stats.tot*100)+'%':'—';
  document.getElementById('prog').style.width=stats.ftot?Math.round(stats.fok/stats.ftot*100)+'%':'0%';
}

initFilters();
</script>
</body>
</html>"""


MANIFEST = json.dumps({
    "name": "Poker Combos Trainer",
    "short_name": "Poker Combos",
    "description": "Entraîne-toi à compter les combos poker — Ranges 50BB",
    "start_url": "/",
    "display": "standalone",
    "background_color": "#0d0f14",
    "theme_color": "#0d0f14",
    "orientation": "portrait",
    "icons": [
        {"src": "/icon-192.png", "sizes": "192x192", "type": "image/svg+xml", "purpose": "any maskable"},
        {"src": "/icon-512.png", "sizes": "512x512", "type": "image/svg+xml", "purpose": "any maskable"}
    ]
})

SW = '''
const CACHE = 'poker-v1';
const ASSETS = ['/'];
self.addEventListener('install', e => {
    e.waitUntil(caches.open(CACHE).then(c => c.addAll(ASSETS)));
});
self.addEventListener('fetch', e => {
    if (e.request.url.includes('/question')) return;
    e.respondWith(
        caches.match(e.request).then(r => r || fetch(e.request).then(res => {
            return caches.open(CACHE).then(c => { c.put(e.request, res.clone()); return res; });
        }))
    );
});
'''

import base64

# Icône SVG : fond dégradé bleu foncé + symbole poker
def make_icon_svg(size):
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}" viewBox="0 0 100 100">
  <defs>
    <linearGradient id="g" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" style="stop-color:#1a2a4a"/>
      <stop offset="100%" style="stop-color:#0d0f14"/>
    </linearGradient>
  </defs>
  <rect width="100" height="100" rx="22" fill="url(#g)"/>
  <rect x="20" y="15" width="60" height="70" rx="8" fill="#1e2a3a" stroke="#4f8ef7" stroke-width="2.5"/>
  <text x="50" y="52" font-family="Georgia,serif" font-size="28" font-weight="bold" fill="#4f8ef7" text-anchor="middle" dominant-baseline="middle">P</text>
  <text x="26" y="28" font-family="Georgia,serif" font-size="13" fill="#4f8ef7">♠</text>
  <text x="68" y="80" font-family="Georgia,serif" font-size="13" fill="#4f8ef7" text-anchor="middle">♠</text>
</svg>'''
    return svg.encode()

ICON_192_SVG = make_icon_svg(192)
ICON_512_SVG = make_icon_svg(512)


# ======= RANGE TRAINER =======

"""Range Trainer v5 - 50BB + 20BB, menu déroulant, aléatoire"""
from http.server import HTTPServer, BaseHTTPRequestHandler
import json, os, random

RANKS = 'AKQJT98765432'

def range_ri(r): return RANKS.index(r)
def range_norm_hand(r1, r2, stype=None):
    if range_ri(r1) > range_ri(r2): r1, r2 = r2, r1
    return r1+r2+(stype or '')

def range_expand(tokens):
    hands = set()
    for token in tokens:
        token = token.strip()
        if not token: continue
        if '-' in token:
            t1, t2 = token.split('-')
            if len(t1)==2 and t1[0]==t1[1] and len(t2)==2 and t2[0]==t2[1]:
                lo,hi = max(range_ri(t1[0]),range_ri(t2[0])),min(range_ri(t1[0]),range_ri(t2[0]))
                for i in range(hi,lo+1): hands.add(RANKS[i]*2)
            elif len(t1)==3 and t1[2] in ('s','o'):
                stype,top = t1[2],t1[0]
                lo,hi = max(range_ri(t1[1]),range_ri(t2[1])),min(range_ri(t1[1]),range_ri(t2[1]))
                for i in range(hi,lo+1):
                    if RANKS[i]!=top: hands.add(range_norm_hand(top,RANKS[i],stype))
            continue
        if token.endswith('+'):
            base = token[:-1]
            if len(base)==2 and base[0]==base[1]:
                for i in range(0,range_ri(base[0])+1): hands.add(RANKS[i]*2)
            elif len(base)==3 and base[2] in ('s','o'):
                stype,top,kick = base[2],base[0],base[1]
                for i in range(0,range_ri(kick)+1):
                    if RANKS[i]!=top: hands.add(range_norm_hand(top,RANKS[i],stype))
            continue
        if len(token)==2 and token[0]==token[1]: hands.add(token)
        elif len(token)==3 and token[2] in ('s','o'): hands.add(range_norm_hand(token[0],token[1],token[2]))
    return hands

def range_make_layers(*layers_raw):
    seen = set()
    layers = []
    for (color, label, notation) in layers_raw:
        hands = range_expand([t.strip() for t in notation.split(',')])
        hands -= seen
        seen |= hands
        layers.append({'color':color,'label':label,'notation':notation,'hands':list(hands)})
    return layers

RANGE_SCENARIOS = [
  {'id':'lj_open_50','position':'LJ','stack':50,'action':'Open raise 2.5bb','label':'LJ open','group':'50BB',
   'layers':range_make_layers(
     ('orange','Raise','22+, A2s+, K5s+, Q8s+, J8s+, T7s+, 97s+, 87s, 76s, 65s, A9o+, KTo+, QTo+, JTo'),
   )},
  {'id':'btn_open_50','position':'BTN','stack':50,'action':'Open raise 2.5bb','label':'BTN open','group':'50BB',
   'layers':range_make_layers(
     ('orange','Raise','22+, A2s+, K2s+, Q2s+, J2s+, T2s+, 95s+, 84s+, 74s+, 63s+, 53s+, 43s, A2o+, K5o+, Q7o+, J7o+, T7o+, 97o+, 87o, 76o'),
   )},
  {'id':'btn_vs_lj_open_50','position':'BTN','stack':50,'action':'Face open LJ — 3bet, Call ou Fold ?','label':'BTN vs open LJ','group':'50BB',
   'layers':range_make_layers(
     ('violet','3bet','JJ+, AKs, A5s-A4s, K8s-K7s, Q9s, J9s, T8s, 76s, 54s, AQo+, ATo, KJo'),
     ('green','Call','TT-22, AQs-A6s, A3s-A2s, K9s+, QTs+, JTs, T9s, 97s+, 87s, 65s, AJo, KQo'),
   )},
  {'id':'sb_vs_lj_open_50','position':'SB','stack':50,'action':'Face open LJ — 3bet, Call ou Fold ?','label':'SB vs open LJ','group':'50BB',
   'layers':range_make_layers(
     ('violet','3bet','JJ+, AKs, A6s-A5s, K9s-K8s, Q9s, J9s, T8s, 87s, AKo, ATo, KJo'),
     ('green','Call','TT-22, AQs-A7s, A4s-A2s, KTs+, QTs+, Q8s, JTs, J8s, 97s+, AQo-AJo, KQo'),
   )},
  {'id':'bb_vs_lj_open_50','position':'BB','stack':50,'action':'Face open LJ — 3bet, Call ou Fold ?','label':'BB vs open LJ','group':'50BB',
   'layers':range_make_layers(
     ('violet','3bet','TT+, AQs+, K7s-K6s, Q8s, J8s, T9s, 65s, AQo+, A5o'),
     ('green','Call','99-22, AQs-A2s, K8s+, K5s-K2s, Q9s+, Q7s-Q2s, J9s+, J7s-J2s, T8s-T2s, 92s+, 82s+, 72s+, 64s-62s, 52s+, 42s+, 32s, AJo-A6o, A4o-A2o, K6o+, Q8o+, J8o+, T8o+, 98o, 87o, 76o, 65o'),
   )},
  {'id':'sb_vs_btn_open_50','position':'SB','stack':50,'action':'Face open BTN — 3bet, Call ou Fold ?','label':'SB vs open BTN','group':'50BB',
   'layers':range_make_layers(
     ('violet','3bet','TT+, AJs+, A3s, KQs, K5s-K4s, Q6s, J7s, T7s, 97s, 87s, 76s, AQo+, A9o-A8o, KTo, QTo, JTo'),
     ('green','Call','99-22, ATs-A4s, A2s, KJs-K6s, Q7s+, J8s+, T8s+, 98s, AJo-ATo, KJo+, QJo'),
   )},
  {'id':'bb_vs_btn_open_50','position':'BB','stack':50,'action':'Face open BTN — 3bet, Call ou Fold ?','label':'BB vs open BTN','group':'50BB',
   'layers':range_make_layers(
     ('violet','3bet','99+, AJs+, KQs, 98s, 87s, AJo+, A6o, A3o-A2o, KQo, K4o, Q5o'),
     ('green','Call','88-22, ATs-A2s, KJs-K2s, Q2s+, J2s+, T2s+, 97s-92s, 86s-82s, 72s+, 62s+, 52s+, 42s+, 32s, ATo-A7o, A5o-A4o, KJo-K5o, K3o-K2o, Q6o+, Q4o-Q3o, J5o+, T6o+, 96o+, 86o+, 75o+, 64o+, 53o+'),
   )},
  {'id':'btn_vs_sb3bet_50','position':'BTN','stack':50,'action':'Face au 3bet SB — Allin, Call ou Fold ?','label':'BTN vs 3bet SB','group':'50BB',
   'layers':range_make_layers(
     ('red','Allin','QQ-88, 33-22, AQs+, A5s-A2s, KJs-KTs, AQo+'),
     ('green','Call','KK+, 88-44, AQs-A2s, K5s+, Q8s+, J8s+, T8s+, 97s+, 86s+, 76s, 65s, 54s, AJo-ATo, KJo+, QJo'),
   )},
  {'id':'btn_vs_bb3bet_50','position':'BTN','stack':50,'action':'Face au 3bet BB — Allin, Call ou Fold ?','label':'BTN vs 3bet BB','group':'50BB',
   'layers':range_make_layers(
     ('red','Allin','QQ-99, 44-33, AKs, AQo+'),
     ('green','Call','KK+, 99-55, AQs-A2s, K5s+, Q7s+, J8s+, T8s+, 97s+, 86s+, 76s, AJo-A9o, KTo+, QJo'),
   )},
  {'id':'lj_vs_btn3bet_50','position':'LJ','stack':50,'action':'Face au 3bet BTN — 4bet, Allin, Call ou Fold ?','label':'LJ vs 3bet BTN','group':'50BB',
   'layers':range_make_layers(
     ('brown','4bet sizer','QQ+, AKs, ATo'),
     ('red','Allin','JJ-TT, A5s-A4s, AKo'),
     ('green','Call','99-55, AQs-A6s, A3s-A2s, K9s+, Q9s+, J9s+, T8s+, 97s+, 87s, 76s, 65s, AQo-AJo, KQo'),
   )},
  {'id':'bb_vs_sb_raise_50','position':'BB','stack':50,'action':'Face au raise SB — 3bet, Call ou Fold ?','label':'BB vs raise SB','group':'50BB',
   'layers':range_make_layers(
     ('violet','3bet','99+, AJs+, 87s, 76s, AQo+, A4o-A2o, K6o-K5o, Q7o, J7o'),
     ('green','Call','88-22, ATs-A2s, K2s+, Q2s+, J2s+, T2s+, 92s+, 86s-84s, 75s-73s, 62s+, 52s+, 42s+, 32s, AJo-A5o, K7o+, Q8o+, J8o+, T7o+, 97o+, 87o'),
   )},
  {'id':'bb_vs_limp_sb_50','position':'BB','stack':50,'action':'Face au limp SB — Raise ou Check ?','label':'BB vs limp SB','group':'50BB',
   'layers':range_make_layers(
     ('orange','Raise','55+, A2s+, K6s+, Q8s+, J8s+, T8s+, 98s, 86s+, 82s, 75s+, 72s, 64s+, 62s, 53s+, 43s, A7o+, KTo+, QJo, Q5o-Q2o, J5o-J2o, T5o-T2o, 95o-92o'),
   )},
  {'id':'sb_vs_bb_50','position':'SB','stack':50,'action':'Depuis SB face BB — Raise ou Limp ?','label':'SB vs BB','group':'50BB',
   'layers':range_make_layers(
     ('orange','Raise','KK+, TT-88, A4s+, K7s+, Q9s+, J9s+, J3s-J2s, T8s+, T3s-T2s, 98s, 65s, 54s, AJo-A9o, KTo+, K6o-K5o, QJo, Q6o-Q5o'),
     ('green','Limp','QQ-JJ, 77-22, A3s-A2s, K6s-K2s, Q8s-Q2s, J8s-J4s, T7s-T4s, 97s-92s, 82s+, 73s+, 64s-63s, 53s-52s, 42s+, 32s, AQo+, A8o-A2o, K9o-K7o, K4o-K2o, QTo-Q7o, Q4o-Q3o, J5o+, T6o+, 96o+, 86o+, 76o, 65o, 54o'),
   )},
  {'id':'lj_open_20','position':'LJ','stack':20,'action':'Open raise','label':'LJ open','group':'20BB',
   'layers':range_make_layers(
     ('orange','Raise','44+, A2s+, K6s+, Q8s+, J8s+, T8s+, 97s+, 87s, 76s, A9o+, KTo+, QTo+, JTo'),
   )},
  {'id':'btn_open_20','position':'BTN','stack':20,'action':'Open ou Allin ?','label':'BTN open/allin','group':'20BB',
   'layers':range_make_layers(
     ('orange','Open','66+, A6s+, K2s+, Q4s+, J5s+, T6s+, 96s+, 86s+, 75s+, 65s, A2o+, K7o+, Q8o+, J8o+, T8o+, 98o'),
     ('red','Allin','55-22, A5s-A2s'),
   )},
  {'id':'btn_call_vs_sb_allin_20','position':'BTN','stack':20,'action':'Face allin SB — Call ou Fold ?','label':'BTN vs allin SB','group':'20BB',
   'layers':range_make_layers(
     ('green','Call','22+, A2s+, KTs+, QTs+, A6o+, KJo+'),
   )},
  {'id':'btn_call_vs_bb_allin_20','position':'BTN','stack':20,'action':'Face allin BB — Call ou Fold ?','label':'BTN vs allin BB','group':'20BB',
   'layers':range_make_layers(
     ('green','Call','33+, A5s+, KTs+, QTs+, JTs, A8o+, KJo+'),
   )},
  {'id':'lj_call_vs_btn_allin_20','position':'LJ','stack':20,'action':'Face allin BTN — Call ou Fold ?','label':'LJ vs allin BTN','group':'20BB',
   'layers':range_make_layers(
     ('green','Call','55+, A9s+, KJs+, ATo+'),
   )},
  {'id':'bb_vs_sb_raise_20','position':'BB','stack':20,'action':'Face au raise SB — 3bet, Allin, Call ou Fold ?','label':'BB vs raise SB','group':'20BB',
   'layers':range_make_layers(
     ('violet','3bet','JJ-TT, AQs+, Q6o, J7o'),
     ('red','Allin','99-22, AJs-A9s, A3s-A2s, A2o+, K3o-K2o'),
     ('green','Call','QQ+, 99-88, A8s-A4s, K2s+, Q2s+, J2s+, T2s+, 92s+, 84s+, 73s+, 62s+, 52s+, 42s+, 32s, K4o+, Q7o+, J8o+, T7o+, 97o, 87o'),
   )},
  {'id':'bb_vs_limp_sb_20','position':'BB','stack':20,'action':'Face au limp SB — Raise, Allin ou Check ?','label':'BB vs limp SB','group':'20BB',
   'layers':range_make_layers(
     ('orange','Raise','77+, A8s+, KTs+, QJs, JTs, ATo+, KQo, Q2o, J3o-J2o, T5o-T2o, 95o-92o, 85o-82o'),
     ('red','Allin','66-22, A9o-A2o'),
   )},
  {'id':'sb_vs_bb_20','position':'SB','stack':20,'action':'Depuis SB — Raise, Limp ou Allin ?','label':'SB vs BB','group':'20BB',
   'layers':range_make_layers(
     ('orange','Raise','77+, A8s+, KTs+, QJs, J4s-J2s, T4s-T2s, 94s-92s, AQo+, KJo+, K8o-K7o, Q8o-Q7o, J8o, T8o'),
     ('green','Limp','66, A7s-A2s, K9s-K2s, QTs-Q2s, J5s+, T5s+, 95s+, 82s+, 72s+, 62s+, 52s+, 42s+, 32s, KTo-K9o, K6o-K2o, Q9o+, Q6o-Q2o, J9o+, J7o-J4o, T9o, T7o-T6o, 96o+, 86o+, 76o, 65o'),
     ('red','Allin','55-22, AJo-A2o'),
   )},
]

def get_scenario(sid=None):
    if sid:
        s = next((x for x in RANGE_SCENARIOS if x['id']==sid), None)
        if not s: s = random.choice(RANGE_SCENARIOS)
    else:
        s = random.choice(RANGE_SCENARIOS)
    return {'id':s['id'],'position':s['position'],'stack':s['stack'],
            'action':s['action'],'label':s['label'],'group':s['group'],
            'layers':[{'color':l['color'],'label':l['label'],'notation':l['notation'],'hands':l['hands']} for l in s['layers']]}

def get_scenarios_list():
    return [{'id':s['id'],'label':s['label'],'group':s['group'],'stack':s['stack'],'position':s['position']} for s in RANGE_SCENARIOS]


HTML_RANGE = """<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Range Trainer</title>
<link href="https://fonts.googleapis.com/css2?family=DM+Mono:wght@400;500&family=Syne:wght@700;800&display=swap" rel="stylesheet">
<style>
:root{--bg:#0d0f14;--surface:#161920;--surface2:#1e2330;--border:#2a3045;--accent:#4f8ef7;--accent2:#7c5cfc;--green:#2dd4a0;--red:#f75f5f;--amber:#f7c94f;--text:#e8ecf5;--text2:#7a8399;--text3:#4a5268;--col-orange:#E8951A;--col-violet:#7c5cfc;--col-red:#c0392b;--col-green:#1e8c4e;--col-brown:#7B4A1E;}
*{box-sizing:border-box;margin:0;padding:0;}
body{background:var(--bg);color:var(--text);font-family:'DM Mono',monospace;min-height:100vh;display:flex;flex-direction:column;align-items:center;padding:12px 10px 40px;}
.header{display:flex;align-items:center;justify-content:space-between;width:100%;max-width:960px;margin-bottom:10px;flex-wrap:wrap;gap:8px;}
.header h1{font-family:'Syne',sans-serif;font-size:20px;font-weight:800;letter-spacing:-0.5px;background:linear-gradient(135deg,var(--accent),var(--accent2));-webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text;}
.header-controls{display:flex;gap:8px;align-items:center;flex-wrap:wrap;}
select.scenario-select{height:36px;padding:0 10px;border-radius:9px;border:1px solid var(--border);background:var(--surface2);color:var(--text);font-family:'DM Mono',monospace;font-size:12px;cursor:pointer;outline:none;min-width:200px;}
select.scenario-select option{background:var(--surface2);color:var(--text);}
select.scenario-select optgroup{color:var(--text2);font-style:normal;}
.main{width:100%;max-width:960px;display:flex;flex-direction:column;gap:10px;}
.stats{display:grid;grid-template-columns:repeat(4,1fr);gap:7px;}
.stat{background:var(--surface2);border:1px solid var(--border);border-radius:8px;padding:7px 10px;text-align:center;}
.stat-v{font-family:'Syne',sans-serif;font-size:18px;font-weight:800;}
.stat-l{font-size:9px;color:var(--text3);margin-top:1px;text-transform:uppercase;letter-spacing:.07em;}
.s-ok .stat-v{color:var(--green);}.s-miss .stat-v{color:var(--red);}.s-sc .stat-v{color:var(--accent);}
.card{background:var(--surface);border:1px solid var(--border);border-radius:12px;padding:14px 16px;}
.situation{background:linear-gradient(135deg,#0f1a2e,#1a0f2e);border:1px solid #2a3f6a;border-radius:10px;padding:10px 16px;display:flex;align-items:center;gap:12px;flex-wrap:wrap;margin-bottom:8px;}
.pos-badge{font-family:'Syne',sans-serif;font-size:28px;font-weight:800;color:var(--col-orange);min-width:50px;text-align:center;}
.sit-info{}
.sit-title{font-family:'Syne',sans-serif;font-size:15px;font-weight:800;color:var(--text);}
.sit-sub{font-size:11px;color:var(--text2);margin-top:2px;}
.stack-badge{margin-left:auto;background:#1a2a0a;border:1px solid #2a4a10;border-radius:8px;padding:6px 14px;text-align:center;}
.stack-v{font-family:'Syne',sans-serif;font-size:20px;font-weight:800;color:var(--amber);}
.stack-l{font-size:9px;color:var(--text3);text-transform:uppercase;letter-spacing:.08em;}
.progress{height:3px;background:var(--border);border-radius:2px;overflow:hidden;margin-bottom:8px;}
.prog-fill{height:100%;background:linear-gradient(90deg,var(--col-orange),#f7a84f);border-radius:2px;transition:width .3s;width:0%;}
.mode-selector{display:flex;gap:8px;margin-bottom:10px;flex-wrap:wrap;}
.mode-btn{padding:7px 18px;border-radius:8px;font-size:13px;font-family:'Syne',sans-serif;font-weight:700;border:3px solid transparent;cursor:pointer;transition:all .15s;opacity:.55;}
.mode-btn.active{opacity:1;border-color:rgba(255,255,255,.5);transform:scale(1.04);}
.mode-orange{background:var(--col-orange);color:#fff;}
.mode-violet{background:var(--col-violet);color:#fff;}
.mode-red{background:var(--col-red);color:#fff;}
.mode-green{background:var(--col-green);color:#fff;}
.mode-brown{background:var(--col-brown);color:#fff;}
.grid-container{overflow-x:auto;}
table.rgrid{border-collapse:collapse;width:100%;min-width:600px;}
table.rgrid td{width:7.69%;height:46px;border:1.5px solid #0d0f14;font-size:13px;font-weight:700;text-align:center;vertical-align:middle;cursor:pointer;user-select:none;color:#5a6080;background:#1c1f2b;padding:0;line-height:1;transition:filter .08s;}
table.rgrid td.pp{background:#202330;color:#5a6080;}
table.rgrid td:hover{filter:brightness(1.3);}
table.rgrid td.sel-orange,table.rgrid td.cor-orange{background:var(--col-orange)!important;color:#fff!important;border-color:#b06a08!important;}
table.rgrid td.sel-violet,table.rgrid td.cor-violet{background:var(--col-violet)!important;color:#fff!important;border-color:#5a3adc!important;}
table.rgrid td.sel-red,table.rgrid td.cor-red{background:var(--col-red)!important;color:#fff!important;border-color:#8a2010!important;}
table.rgrid td.sel-green,table.rgrid td.cor-green{background:var(--col-green)!important;color:#fff!important;border-color:#156035!important;}
table.rgrid td.sel-brown,table.rgrid td.cor-brown{background:var(--col-brown)!important;color:#fff!important;border-color:#5a3010!important;}
table.rgrid td.missed{background:#7a1515!important;color:#ffbbbb!important;border-color:#5a0f0f!important;}
table.rgrid td.extra{background:#4a3a00!important;color:#f7c94f!important;border-color:#3a2c00!important;}
.legend{display:flex;gap:12px;flex-wrap:wrap;font-size:11px;color:var(--text2);margin-top:8px;align-items:center;}
.leg-dot{width:12px;height:12px;border-radius:2px;display:inline-block;vertical-align:middle;margin-right:4px;}
.actions{display:flex;gap:8px;margin-top:10px;flex-wrap:wrap;align-items:center;}
.btn{height:40px;padding:0 18px;border-radius:9px;font-family:'Syne',sans-serif;font-size:13px;font-weight:700;border:none;cursor:pointer;transition:transform .1s;}
.btn:active{transform:scale(.97);}
.btn-p{background:var(--col-orange);color:#fff;}
.btn-s{background:var(--surface2);color:var(--text2);border:1px solid var(--border);}
.btn-amber{background:#1e1c0d;color:var(--amber);border:1px solid #3a3210;}
.btn-red2{background:#2a0d0d;color:var(--red);border:1px solid #4a1a1a;}
.btn-new{background:linear-gradient(135deg,var(--accent),var(--accent2));color:#fff;}
.btn:disabled{opacity:.4;cursor:default;}
.result-bar{display:none;margin-top:10px;padding:12px 16px;border-radius:10px;font-size:13px;line-height:1.7;}
.result-bar.show{display:block;}
.result-bar.all-ok{background:#0a2018;border:1px solid #1a4a30;color:var(--green);}
.result-bar.partial{background:#1a1000;border:1px solid #3a2800;color:var(--amber);}
.r-title{font-family:'Syne',sans-serif;font-size:16px;font-weight:800;margin-bottom:4px;}
.r-detail{font-size:12px;color:var(--text2);line-height:1.9;}
.counter{font-size:12px;color:var(--text2);margin-left:auto;}
.counter b{color:var(--text);}
</style>
</head>
<body>
<div class="header">
  <div style="display:flex;align-items:center;gap:12px;">
    <a href="/" style="height:36px;padding:0 14px;border-radius:9px;background:#1e2330;border:1px solid #2a3045;color:#7a8399;font-family:'Syne',sans-serif;font-size:13px;font-weight:700;text-decoration:none;display:flex;align-items:center;">&#8592; Accueil</a>
    <h1>Range Trainer</h1>
  </div>
  <div class="header-controls">
    <select class="scenario-select" id="scenario-select" onchange="onSelectChange(this)">
      <option value="">-- Aleatoire --</option>
    </select>
    <button class="btn btn-new" onclick="loadSelected()" style="height:36px;font-size:12px;">Go &#8594;</button>
  </div>
</div>
<div class="main">
  <div class="stats">
    <div class="stat s-ok"><div class="stat-v" id="st-ok">0</div><div class="stat-l">Correctes</div></div>
    <div class="stat s-miss"><div class="stat-v" id="st-miss">0</div><div class="stat-l">Oubliees</div></div>
    <div class="stat"><div class="stat-v" id="st-extra">0</div><div class="stat-l">En trop</div></div>
    <div class="stat s-sc"><div class="stat-v" id="st-score">-</div><div class="stat-l">Score</div></div>
  </div>
  <div class="card">
    <div class="situation">
      <div class="pos-badge" id="pos-badge">-</div>
      <div class="sit-info">
        <div class="sit-title" id="sit-title">Chargement...</div>
        <div class="sit-sub" id="sit-sub"></div>
      </div>
      <div class="stack-badge">
        <div class="stack-v" id="stack-v">-</div>
        <div class="stack-l">BB</div>
      </div>
    </div>
    <div class="mode-selector" id="mode-selector" style="display:none"></div>
    <div class="progress"><div class="prog-fill" id="prog"></div></div>
    <div class="grid-container"><table class="rgrid" id="range-grid"></table></div>
    <div class="legend" id="legend"></div>
    <div class="actions">
      <button class="btn btn-p" id="validate-btn" onclick="validate()">Valider</button>
      <button class="btn btn-amber" onclick="showSolution()">Solution</button>
      <button class="btn btn-red2" onclick="clearGrid()">Effacer</button>
      <button class="btn btn-s" onclick="newAttempt()">&#8635; Recommencer</button>
      <div class="counter">Selectionnees : <b id="sel-count">0</b> / <b id="total-count">0</b></div>
    </div>
    <div class="result-bar" id="result-bar"><div class="r-title" id="r-title"></div><div class="r-detail" id="r-detail"></div></div>
  </div>
</div>
<script>
const RANKS13=['A','K','Q','J','T','9','8','7','6','5','4','3','2'];
const CM={orange:'#E8951A',violet:'#7c5cfc',red:'#c0392b',green:'#1e8c4e',brown:'#7B4A1E'};
let scenario=null,userSelected={},validated=false,isDragging=false,dragMode=true,activeColor='orange';
let scenariosList=[];

async function init(){
  buildGrid();
  await loadScenariosList();
  await fetchScenario(null);
}

async function loadScenariosList(){
  try{
    const r=await fetch('/scenarios');
    scenariosList=await r.json();
    buildSelect();
  }catch(e){}
}

function buildSelect(){
  const sel=document.getElementById('scenario-select');
  // Grouper par BB
  const groups={};
  scenariosList.forEach(s=>{
    if(!groups[s.group]) groups[s.group]=[];
    groups[s.group].push(s);
  });
  let html='<option value="">-- Aleatoire --</option>';
  Object.keys(groups).sort().forEach(g=>{
    html+=`<optgroup label="${g}">`;
    groups[g].forEach(s=>{
      html+=`<option value="${s.id}">${s.position} — ${s.label}</option>`;
    });
    html+='</optgroup>';
  });
  sel.innerHTML=html;
}

function onSelectChange(el){ /* rien, on attend Go */ }

async function loadSelected(){
  const sid=document.getElementById('scenario-select').value||null;
  await fetchScenario(sid);
}

async function fetchScenario(sid){
  validated=false; userSelected={};
  document.getElementById('result-bar').className='result-bar';
  document.getElementById('validate-btn').disabled=false;
  try{
    const url=sid?'/scenario?id='+sid:'/scenario';
    const r=await fetch(url);
    scenario=await r.json();
    renderScenario(scenario);
  }catch(e){document.getElementById('sit-title').textContent='Erreur serveur';}
}

function renderScenario(s){
  document.getElementById('pos-badge').textContent=s.position;
  document.getElementById('sit-title').textContent=s.label+' — '+s.group;
  document.getElementById('sit-sub').textContent=s.action;
  document.getElementById('stack-v').textContent=s.stack;
  const total=s.layers.reduce((n,l)=>n+l.hands.length,0);
  document.getElementById('total-count').textContent=total;
  document.getElementById('sel-count').textContent=0;
  document.getElementById('prog').style.width='0%';
  activeColor=s.layers[0].color;
  // Sync le select
  const sel=document.getElementById('scenario-select');
  for(let i=0;i<sel.options.length;i++){if(sel.options[i].value===s.id){sel.selectedIndex=i;break;}}
  // Mode buttons
  const ms=document.getElementById('mode-selector');
  if(s.layers.length>1){
    ms.style.display='flex';
    ms.innerHTML=s.layers.map((l,i)=>`<button class="mode-btn mode-${l.color}${i===0?' active':''}" onclick="setColor('${l.color}',this)">${l.label}</button>`).join('');
  } else { ms.style.display='none'; }
  buildLegend(s);
  refreshGrid();
}

function setColor(c,el){activeColor=c;document.querySelectorAll('.mode-btn').forEach(b=>b.classList.remove('active'));el.classList.add('active');}

function buildLegend(s){
  let h=s.layers.map(l=>`<span><span class="leg-dot" style="background:${CM[l.color]};"></span>${l.label}</span>`).join('');
  h+=`<span><span class="leg-dot" style="background:#7a1515;"></span>Oublie</span>`;
  h+=`<span><span class="leg-dot" style="background:#4a3a00;"></span>En trop</span>`;
  document.getElementById('legend').innerHTML=h;
}

function buildGrid(){
  const tbl=document.getElementById('range-grid');tbl.innerHTML='';
  for(let i=0;i<13;i++){
    const row=document.createElement('tr');
    for(let j=0;j<13;j++){
      const td=document.createElement('td');
      const r1=RANKS13[i],r2=RANKS13[j],pp=i===j,suited=i<j;
      const label=pp?r1+r2:(suited?r1+r2+'s':r2+r1+'o');
      td.textContent=label;td.dataset.key=label;
      if(pp)td.classList.add('pp');
      td.addEventListener('mousedown',e=>{e.preventDefault();if(validated)return;isDragging=true;dragMode=userSelected[label]!==activeColor;toggleCell(label,td);});
      td.addEventListener('mouseenter',()=>{if(!isDragging||validated)return;toggleCell(label,td,dragMode);});
      row.appendChild(td);
    }
    tbl.appendChild(row);
  }
  document.addEventListener('mouseup',()=>{isDragging=false;});
}

function toggleCell(key,td,forceMode=null){
  const isActive=userSelected[key]===activeColor;
  const select=forceMode!==null?forceMode:!isActive;
  if(select)userSelected[key]=activeColor;
  else if(userSelected[key]===activeColor)delete userSelected[key];
  if(!validated){td.className=key.length===2&&key[0]===key[1]?'pp':'';if(userSelected[key])td.classList.add('sel-'+userSelected[key]);}
  updateCounter();
}

function refreshGrid(){
  document.querySelectorAll('#range-grid td[data-key]').forEach(td=>{
    const k=td.dataset.key,pp=k.length===2&&k[0]===k[1];
    td.className=pp?'pp':'';
    if(!validated&&userSelected[k])td.classList.add('sel-'+userSelected[k]);
  });
}

function updateCounter(){
  const n=Object.keys(userSelected).length;
  document.getElementById('sel-count').textContent=n;
  if(!scenario)return;
  const total=scenario.layers.reduce((a,l)=>a+l.hands.length,0);
  document.getElementById('prog').style.width=Math.min(total>0?Math.round(n/total*100):0,100)+'%';
}

function validate(){
  if(validated||!scenario)return;
  validated=true;
  const correct={};
  scenario.layers.forEach(l=>l.hands.forEach(h=>correct[h]=l.color));
  let ok=0,miss=0,extra=0;
  document.querySelectorAll('#range-grid td[data-key]').forEach(td=>{
    const k=td.dataset.key,pp=k.length===2&&k[0]===k[1];
    td.className=pp?'pp':'';
    const cc=correct[k],uc=userSelected[k];
    if(cc&&uc===cc){td.classList.add('cor-'+cc);ok++;}
    else if(cc&&uc!==cc){td.classList.add('missed');miss++;}
    else if(!cc&&uc){td.classList.add('extra');extra++;}
  });
  const total=Object.keys(correct).length,score=Math.max(0,Math.round((ok-extra*0.5)/total*100));
  document.getElementById('st-ok').textContent=ok;
  document.getElementById('st-miss').textContent=miss;
  document.getElementById('st-extra').textContent=extra;
  document.getElementById('st-score').textContent=score+'%';
  document.getElementById('prog').style.width=Math.round(ok/total*100)+'%';
  document.getElementById('validate-btn').disabled=true;
  const rb=document.getElementById('result-bar');
  if(miss===0&&extra===0){
    rb.className='result-bar show all-ok';
    document.getElementById('r-title').textContent='Parfait ! Range exacte.';
    document.getElementById('r-detail').textContent=ok+' mains correctes sur '+total+'.';
  }else{
    rb.className='result-bar show partial';
    document.getElementById('r-title').textContent='Score : '+score+'% - '+ok+'/'+total+' correctes';
    document.getElementById('r-detail').innerHTML=(miss>0?'<span style="color:var(--red)">'+miss+' oubliee'+(miss>1?'s':'')+'</span>':'')+((miss>0&&extra>0)?' &middot; ':'')+(extra>0?'<span style="color:var(--amber)">'+extra+' en trop</span>':'');
  }
}

function showSolution(){
  if(!scenario)return;
  validated=true;
  const correct={};
  scenario.layers.forEach(l=>l.hands.forEach(h=>correct[h]=l.color));
  document.querySelectorAll('#range-grid td[data-key]').forEach(td=>{
    const k=td.dataset.key,pp=k.length===2&&k[0]===k[1];
    td.className=pp?'pp':'';
    if(correct[k])td.classList.add('cor-'+correct[k]);
  });
  document.getElementById('result-bar').className='result-bar show partial';
  document.getElementById('r-title').textContent='Solution affichee';
  document.getElementById('r-detail').innerHTML=scenario.layers.map(l=>'<b style="color:'+CM[l.color]+'">'+l.label+'</b> : <span style="color:var(--text2)">'+l.notation+'</span>').join('<br>');
  document.getElementById('validate-btn').disabled=true;
}

function clearGrid(){userSelected={};validated=false;document.getElementById('validate-btn').disabled=false;document.getElementById('result-bar').className='result-bar';refreshGrid();updateCounter();}
function newAttempt(){clearGrid();}

init();
</script>
</body>
</html>"""



HOME_HTML = """<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Poker Trainer</title>
<link href="https://fonts.googleapis.com/css2?family=Syne:wght@700;800&family=DM+Mono&display=swap" rel="stylesheet">
<style>
:root{--bg:#0d0f14;--surface:#161920;--border:#2a3045;--accent:#4f8ef7;--accent2:#7c5cfc;--text:#e8ecf5;--text2:#7a8399;}
*{box-sizing:border-box;margin:0;padding:0;}
body{background:var(--bg);color:var(--text);font-family:"DM Mono",monospace;min-height:100vh;display:flex;flex-direction:column;align-items:center;justify-content:center;padding:40px 20px;}
h1{font-family:"Syne",sans-serif;font-size:32px;font-weight:800;background:linear-gradient(135deg,var(--accent),var(--accent2));-webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text;text-align:center;margin-bottom:8px;}
.sub{color:var(--text2);font-size:13px;text-align:center;margin-bottom:48px;}
.apps{display:grid;grid-template-columns:1fr 1fr;gap:20px;width:100%;max-width:600px;}
@media(max-width:500px){.apps{grid-template-columns:1fr;}}
.app-card{background:var(--surface);border:1px solid var(--border);border-radius:16px;padding:28px 24px;text-decoration:none;color:var(--text);transition:border-color .2s,transform .15s;display:block;}
.app-card:hover{border-color:var(--accent);transform:translateY(-2px);}
.app-icon{font-size:36px;margin-bottom:14px;}
.app-title{font-family:"Syne",sans-serif;font-size:18px;font-weight:800;margin-bottom:6px;}
.app-desc{font-size:12px;color:var(--text2);line-height:1.7;}
.app-badge{display:inline-block;margin-top:12px;font-size:11px;padding:3px 10px;border-radius:20px;background:#1a2a4a;color:var(--accent);border:1px solid #2a3f6a;}
</style>
</head>
<body>
<h1>Poker Trainer</h1>
<p class="sub">Ranges 50BB et 20BB</p>
<div class="apps">
  <a class="app-card" href="/combos">
    <div class="app-icon">&#9824;</div>
    <div class="app-title">Combos Trainer</div>
    <div class="app-desc">Compte les combos qui te battent a partir de la range adverse. Bloqueurs, flop/turn/river.</div>
    <div class="app-badge">9 scenarios</div>
  </a>
  <a class="app-card" href="/range">
    <div class="app-icon">&#9830;</div>
    <div class="app-title">Range Trainer</div>
    <div class="app-desc">Reconstruit la range de memoire en cliquant sur la grille. 21 scenarios 50BB et 20BB.</div>
    <div class="app-badge">21 scenarios</div>
  </a>
</div>
</body>
</html>"""


class ThreadingHTTPServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True

class Handler(BaseHTTPRequestHandler):
    def log_message(self, format, *args): pass
    def do_GET(self):
        from urllib.parse import urlparse, parse_qs
        parsed = urlparse(self.path)
        path = parsed.path
        qs = parse_qs(parsed.query)

        if path == '/':
            self._html(HOME_HTML)
        elif path == '/combos':
            self._html(HTML)
        elif path == '/question':
            sid = qs.get('scenario',[''])[0] or None
            self._json(deal_question(sid))
        elif path == '/manifest.json':
            self.send_response(200)
            self.send_header('Content-Type','application/manifest+json')
            self.end_headers()
            self.wfile.write(MANIFEST.encode())
        elif path == '/sw.js':
            self.send_response(200)
            self.send_header('Content-Type','application/javascript')
            self.end_headers()
            self.wfile.write(SW.encode())
        elif path in ('/icon-192.png','/icon-512.png'):
            self.send_response(200)
            self.send_header('Content-Type','image/svg+xml')
            self.end_headers()
            self.wfile.write(ICON_192_SVG if '192' in path else ICON_512_SVG)
        elif path == '/range':
            self._html(HTML_RANGE)
        elif path == '/scenario':
            sid = qs.get('id',[''])[0] or None
            self._json(get_scenario(sid))
        elif path == '/scenarios':
            self._json(get_scenarios_list())
        else:
            self.send_response(404)
            self.end_headers()

    def _html(self, html):
        self.send_response(200)
        self.send_header('Content-Type','text/html; charset=utf-8')
        self.end_headers()
        self.wfile.write(html.encode())

    def _json(self, data):
        body = json.dumps(data).encode()
        self.send_response(200)
        self.send_header('Content-Type','application/json')
        self.send_header('Access-Control-Allow-Origin','*')
        self.end_headers()
        self.wfile.write(body)

if __name__ == '__main__':
    PORT = int(os.environ.get('PORT', 8765))
    print("Précalcul du cache de questions...")
    _start_cache_filler()
    server = ThreadingHTTPServer(('0.0.0.0', PORT), Handler)
    print(f"Poker Trainer — http://localhost:{PORT}")
    print("  /        -> Accueil")
    print("  /combos  -> Combos Trainer")
    print("  /range   -> Range Trainer")
    print("Ne ferme pas cette fenetre !")
    try: server.serve_forever()
    except KeyboardInterrupt: print("Arrete.")
