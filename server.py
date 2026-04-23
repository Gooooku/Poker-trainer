"""
Poker Combos Trainer v6
- Ranges extraites des images fournies
- Écran de filtres : position + type de pot
- Uniquement les combos qui battent la main hero
"""
from http.server import HTTPServer, BaseHTTPRequestHandler
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

def expand_range(tokens):
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
    'hands': expand_range(['22+','A2s+','K5s+','Q8s+','J8s+','T7s+','97s+','87s','76s','65s','A9o+','KTo+','QTo+','JTo']),
  },
  'BTN_open': {
    'label': 'BTN open',
    'hands': expand_range(['22+','A2s+','K2s+','Q2s+','J2s+','T2s+','95s+','84s+','74s+','63s+','53s+','43s','A2o+','K5o+','Q7o+','J7o+','T7o+','97o+','87o','76o']),
  },
  'SB_3bet_vs_BTN': {
    'label': 'SB 3bet vs BTN',
    'hands': expand_range(['TT+','AJs+','A3s','KQs','K5s-K4s','Q6s','J7s','T7s','97s','87s','76s','AQo+','A9o-A8o','KTo','QTo','JTo']),
  },
  'BB_3bet_vs_BTN': {
    'label': 'BB 3bet vs BTN',
    'hands': expand_range(['TT+','AJs+','KQs','98s','87s','AQo+','A6o','A3o-A2o','K4o','Q5o']),
  },
  'BTN_3bet_vs_LJ': {
    'label': 'BTN 3bet vs LJ',
    'hands': expand_range(['JJ+','AKs','A5s-A4s','K8s-K7s','Q9s-Q8s','J9s','T8s','76s','54s','AQo+','ATo','KJo']),
  },
  'SB_raise_vs_BB': {
    'label': 'SB raise vs BB',
    'hands': expand_range(['KK+','TT-88','A4s+','K7s+','Q9s+','J9s+','J3s-J2s','T8s+','T3s-T2s','98s','65s','54s','AKo','AJo-A9o','KTo+','K6o-K5o','QJo','Q6o-Q5o']),
  },
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

def expand_range(range_set):
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

def deal_question(scenario_id=None):
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

    for _ in range(400):
        deck = deck_base[:]
        random.shuffle(deck)
        hero = deck[:2]
        board = deck[2:2+board_size]
        hkey = hero_hand_key(hero)
        if is_interesting(hero, board): break

    blockers_raw = set([cs(c) for c in hero+board])
    hero_score = eval_.evaluate(board, hero)
    hero_cl = eval_.get_rank_class(hero_score)
    hero_hand_name = CLASS_NAMES.get(hero_cl,'?')

    valid_hands = hands_after_blockers(expand_range(range_set), blockers_raw)

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

    grid = {}
    for r1 in RANKS:
        for r2 in RANKS:
            i,j = RANKS.index(r1),RANKS.index(r2)
            if i==j: key=r1+r2
            elif i<j: key=r1+r2+'s'
            else: key=r2+r1+'o'
            grid[r1+'_'+r2] = key in range_set

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


HTML = r"""<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Poker Combos Trainer</title>
<link href="https://fonts.googleapis.com/css2?family=DM+Mono:wght@400;500&family=Syne:wght@700;800&display=swap" rel="stylesheet">
<style>
:root{--bg:#0d0f14;--surface:#161920;--surface2:#1e2330;--border:#2a3045;--accent:#4f8ef7;--accent2:#7c5cfc;--green:#2dd4a0;--red:#f75f5f;--amber:#f7c94f;--text:#e8ecf5;--text2:#7a8399;--text3:#4a5268;}
*{box-sizing:border-box;margin:0;padding:0;}
body{background:var(--bg);color:var(--text);font-family:'DM Mono',monospace;min-height:100vh;display:flex;flex-direction:column;align-items:center;padding:28px 12px 80px;}
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
<div style="text-align:center">
  <h1>Poker Combos Trainer</h1>
  <p class="sub">Ranges 50BB · Combien de combos te battent ?</p>
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


class Handler(BaseHTTPRequestHandler):
    def log_message(self, format, *args): pass
    def do_GET(self):
        from urllib.parse import urlparse, parse_qs
        parsed = urlparse(self.path)
        if parsed.path=='/':
            self.send_response(200)
            self.send_header('Content-Type','text/html; charset=utf-8')
            self.end_headers()
            self.wfile.write(HTML.encode())
        elif parsed.path=='/question':
            qs = parse_qs(parsed.query)
            scenario_id = qs.get('scenario',[''])[0] or None
            data = deal_question(scenario_id)
            body = json.dumps(data).encode()
            self.send_response(200)
            self.send_header('Content-Type','application/json')
            self.send_header('Access-Control-Allow-Origin','*')
            self.end_headers()
            self.wfile.write(body)
        else:
            self.send_response(404)
            self.end_headers()

if __name__=='__main__':
    PORT = int(os.environ.get('PORT', 8765))
    server = HTTPServer(('0.0.0.0', PORT), Handler)
    print(f"Poker Combos Trainer v6 — http://localhost:{PORT}")
    print("Ne ferme pas cette fenetre !")
    try: server.serve_forever()
    except KeyboardInterrupt: print("Arrete.")
