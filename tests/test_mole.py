# 打地鼠 測試：計分公式、暱稱、句庫（有網路／讀不到）、打地鼠過程、結算與排行榜、設定每個值
import sys, os, json, re
from playwright.sync_api import sync_playwright
import common
from common import *

R = Runner()
BANK_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'corre', 'bank'))
HAVE_BANK = os.path.exists(os.path.join(BANK_DIR, 'A1.json'))

FAKE_FB = r"""
(function(){
  window.__db = window.__db || {}; window.__ops = window.__ops || [];
  if (window.firebase && window.firebase.__fake) return;
  const DB = window.__db, ops = window.__ops, clone = x => JSON.parse(JSON.stringify(x));
  const depth = p => p.split('/').length;
  function docRef(path){ return { path, id: path.split('/').pop(),
    async get(){ return { exists: path in DB, data: () => DB[path] && clone(DB[path]) }; } }; }
  function colRef(path){ const f = []; const q = { doc: id => docRef(path + '/' + id),
    where(k, op, v){ f.push([k, v]); return q; }, orderBy(){ return q; }, limit(){ return q; },
    async get(){ const ks = Object.keys(DB).filter(k => k.startsWith(path + '/') && depth(k) === depth(path) + 1);
      const rows = ks.map(k => clone(DB[k])).filter(r => f.every(([k, v]) => r[k] === v)).sort((a,b)=>(b.score||0)-(a.score||0));
      return { docs: rows.map(r => ({ data: () => r })), size: rows.length }; } };
    return q; }
  const fsInst = { collection: colRef,
    async runTransaction(fn){ if (window.__failTx) throw new Error('tx-fail');
      return fn({ get: r => r.get(), set(r, d){ ops.push({k:'set', p:r.path, d:clone(d)}); DB[r.path] = clone(d); } }); } };
  const fire = () => fsInst; fire.FieldValue = { serverTimestamp: () => 'TS' };
  window.firebase = { __fake: true, apps: [], firestore: fire, initializeApp(){ return {}; } };
})();
"""
def route(r):
    u = r.request.url
    if u.startswith('file:'): return r.continue_()
    if 'gstatic.com/firebasejs' in u:
        return r.fulfill(status=200, content_type='application/javascript', body=FAKE_FB if 'firebase-app-compat' in u else '')
    if HAVE_BANK and 'wangchiapin.github.io/corre/bank/' in u:
        fn = u.split('/bank/')[1].split('?')[0]
        fp = os.path.join(BANK_DIR, fn)
        if os.path.exists(fp): return r.fulfill(status=200, content_type='application/json', headers={'access-control-allow-origin': '*'}, body=open(fp, encoding='utf-8').read())
    r.abort()
common.route = route

def page(p, query='', settings=None, own=None, name='Ana', bank=True, flags=None, fast=False, width=900, height=700):
    global HAVE_BANK
    init = ""
    if name is not None: init += "localStorage.setItem('moleName',%s);" % json.dumps(name)
    if own: init += "localStorage.setItem('moleSettings',%s);" % json.dumps(json.dumps(own))
    for k, v in (flags or {}).items(): init += "window.%s=%s;" % (k, json.dumps(v))
    if fast: init += "(()=>{const si=window.setInterval; window.setInterval=(f,t)=>si(f,t===1000?15:t);})();"
    saved = HAVE_BANK; HAVE_BANK = saved and bank
    try:
        b, pg, errs = open_page(p, query, settings=settings, wait=1800, extra_init=init or None, width=width, height=height)
    finally:
        HAVE_BANK = saved
    return b, pg, errs

def start(pg):
    pg.click('#start-btn'); pg.wait_for_timeout(700)
    pg.evaluate("clearInterval(spawnInterval)")      # 關掉隨機冒出，之後由測試親自控制地鼠

def raise_target(pg, n=None):
    # 讓「下一個該打的詞」冒出來，回傳是哪一格
    return pg.evaluate("""()=>{ cells.forEach(c=>{clearTimeout(c.timer);hideCell(c);c.hit=false;}); popupMole(60000,true);
      return cells.findIndex(c=>c.up&&c._isExpected&&!c.bonus); }""")
def hit_cell(pg, i):
    pg.evaluate("(i)=>cells[i].mole.dispatchEvent(new PointerEvent('pointerdown',{bubbles:true}))", i)
    pg.wait_for_timeout(30)
def finish_sentence(pg):
    n = pg.evaluate("currentSentenceObj.words.length - targetIndex")
    for _ in range(n):
        i = raise_target(pg); assert i >= 0
        hit_cell(pg, i)
def wrong_hit(pg):
    # 冒出一個「不是現在要打的詞」
    i = pg.evaluate("""()=>{ cells.forEach(c=>{clearTimeout(c.timer);hideCell(c);c.hit=false;}); const c=cells[0];
      c.mole.dataset.face='1'; c.bonus=false; c.word='不對的詞'; c.pinyin='bù duì'; c._isExpected=false; c.wordText.textContent=c.word; setPhon(c); c.up=true; c.el.classList.add('up'); return 0; }""")
    hit_cell(pg, i)

with sync_playwright() as p:
    # ───── 1) 計分公式與暱稱 ─────
    b, pg, errs = page(p)
    for args, want in (((0, 5, 5), 0), ((1, 5, 5), 125), ((3, 10, 0), 350), ((2, 0, 0), 200), ((1, 3, 1), 138), ((0, 0, 9), 0), ((5, 0, 5), 500)):
        got = pg.evaluate("(a)=>computeScore(a[0],a[1],a[2]).score", list(args))
        R.check(got == want, f'計分 完成{args[0]}句 打對{args[1]} 打錯{args[2]} → {want}（得 {got}）')
    R.check(pg.evaluate("computeScore(2,3,1).pct") == 75, '準確度 3/(3+1)＝75%')
    R.check(pg.evaluate("cleanName('   ')") == 'Jugador', '空白暱稱 → Jugador')
    R.check(pg.evaluate("cleanName('a   b')") == 'a b', '暱稱連續空白合併')
    R.check(len(pg.evaluate("cleanName('x'.repeat(40))")) == 12, '暱稱最多 12 字')
    R.check(pg.evaluate("cleanName('一二三四五六七八九十十一十二十三')") == '一二三四五六七八九十十一', '中文暱稱最多 12 字')
    R.check(pg.evaluate("nameKeyOf('ANA ')") == pg.evaluate("nameKeyOf('ana')"), '暱稱不分大小寫／前後空白視為同一人')
    R.check(not errs, '沒有網頁錯誤 %s' % errs)
    b.close()

    # ───── 2) 第一次按開始 → 問暱稱 ─────
    b, pg, errs = page(p, name=None)
    pg.click('#start-btn'); pg.wait_for_timeout(300)
    R.check(pg.is_visible('#name-modal') and not pg.evaluate("isPlaying"), '沒有暱稱：先跳出暱稱視窗，還沒開始')
    pg.fill('#name-input', '  Mia  '); pg.press('#name-input', 'Enter'); pg.wait_for_timeout(900)
    R.check(pg.evaluate("isPlaying") and pg.evaluate("playerName") == 'Mia', '輸入暱稱按 Enter：開始遊戲，暱稱存為 Mia')
    R.check(pg.evaluate("localStorage.getItem('moleName')") == 'Mia', '暱稱記在本機')
    b.close()

    # ───── 3) 句庫：讀不到 → 內建 3 句 ─────
    b, pg, errs = page(p, bank=False)
    start(pg)
    R.check(pg.evaluate("levelFallback") is True and pg.evaluate("settings.level") == 'mix', '句庫讀不到：改用備援，等級變 mix')
    sents = set()
    for _ in range(12):
        pg.evaluate("loadNextSentence()"); sents.add(pg.evaluate("currentSentenceObj.text"))
    R.check(sents <= {'今天天氣真好', '小貓在草地上玩', '我喜歡吃西瓜'} and len(sents) == 3, '備援只有 3 句內建句子：%s' % sents)
    R.check(pg.evaluate("document.querySelectorAll('#settings .seg[data-key=level]').length") == 0, '備援模式不顯示「句庫等級」選項')
    b.close()

    # ───── 4) 句庫：A1／A2／B1 ─────
    if HAVE_BANK:
        for L in ('A1', 'A2', 'B1'):
            # A1／A2 用遊戲自己的設定；B1 只能用網址 ?level=B1 指定（存檔裡的 B1 會被改回 A1）
            b, pg, errs = page(p, '?level=B1') if L == 'B1' else page(p, own={'diff': 'easy', 'level': L})
            start(pg)
            ok = pg.evaluate("""(L)=>{ const rows=[...levelSrc[L].bank.values()]; let bad=0;
              for(let i=0;i<40;i++){ loadNextSentence(); const t=currentSentenceObj.text; if(!rows.some(r=>r.trad.join('')===t)) bad++; }
              return {n:rows.length,bad,fb:levelFallback}; }""", L)
            R.check(ok['bad'] == 0 and not ok['fb'] and ok['n'] >= 50, f'{L}：句子都來自 {L} 句庫（{ok["n"]} 句）')
            R.check(not errs, f'{L}：沒有網頁錯誤 {errs}')
            b.close()
        b, pg, errs = page(p, own={'diff': 'easy', 'level': 'B1'})
        R.check(pg.evaluate("settings.level") == 'A1', '存檔裡寫 B1：被改回 A1（B1 只能用網址指定）')
        b.close()
    else:
        print('  －  找不到 corre/bank，略過 A1／A2／B1 句庫測試')

    # ───── 5) 打地鼠過程 ─────
    b, pg, errs = page(p, bank=HAVE_BANK)
    start(pg)
    R.check(pg.evaluate("isPlaying") and pg.is_visible('#restart-btn') and not pg.is_visible('#start-btn'), '開始後：顯示「重新開始」、隱藏「開始」')
    R.check(pg.inner_text('#timer') in ('02:00', '01:59'), '計時從 02:00 開始')
    n = pg.evaluate("currentSentenceObj.words.length")
    R.check(pg.evaluate("document.querySelectorAll('#target-sentence .target-char').length") == n, '題目句子每個詞一格')
    R.check(pg.evaluate("targetIndex") == 0, '從第一個詞開始')
    # 打錯 1 次
    wrong_hit(pg)
    R.check(pg.evaluate("errorHits") == 1 and pg.evaluate("targetIndex") == 0, '打到不對的詞：錯誤 +1，進度不動')
    wrong_hit(pg); wrong_hit(pg); pg.wait_for_timeout(400)
    R.check(pg.evaluate("errorHits") == 3 and pg.evaluate("hintOn") is True, '連錯 3 次：出現發光提示')
    # 打對第一個
    pg.wait_for_timeout(400)
    i = raise_target(pg); hit_cell(pg, i)
    R.check(pg.evaluate("targetIndex") == 1 and pg.evaluate("correctHits") == 1 and pg.evaluate("hintOn") is False, '打對：進度 +1、提示消失')
    # 驚喜地鼠
    pg.wait_for_timeout(450)
    before = pg.evaluate("[correctHits, errorHits, targetIndex]")
    pg.evaluate("cells.forEach(c=>{clearTimeout(c.timer);hideCell(c);c.hit=false;}); const c=cells[1]; c.bonus=true; c.word=''; c._isExpected=false; c.up=true; c.el.classList.add('up');")
    hit_cell(pg, 1)
    R.check(pg.evaluate("[correctHits, errorHits, targetIndex]") == before, '驚喜地鼠：不計分、不算錯')
    # 沒冒出來的洞不能打
    pg.wait_for_timeout(450)
    pg.evaluate("cells.forEach(c=>{clearTimeout(c.timer);hideCell(c);c.hit=false;})")
    hit_cell(pg, 2)
    R.check(pg.evaluate("[correctHits, errorHits]") == before[:2], '沒冒出來的洞：打了沒反應')
    # 打完整句
    pg.wait_for_timeout(450)
    finish_sentence(pg); pg.wait_for_timeout(200)
    R.check(pg.evaluate("correctSentenceCount") == 1, '打完整句：完成句數 +1')
    R.check(pg.evaluate("doneList.length") == 1, '完成的句子進複習清單')
    pg.wait_for_timeout(900)
    R.check(pg.evaluate("targetIndex") == 0 and pg.evaluate("currentSentenceObj") is not None, '0.6 秒後自動換下一句')
    R.check(len(pg.evaluate("window.__spoken")) >= 3, '有念出句子和詞（語音）')
    # 結算
    pg.evaluate("endGame()"); pg.wait_for_timeout(900)
    R.check(pg.is_visible('#result-modal'), '結算視窗出現')
    exp = pg.evaluate("computeScore(correctSentenceCount, correctHits, errorHits)")
    R.check(pg.inner_text('#final-score') == str(exp['score']), f'結算分數＝公式：{pg.inner_text("#final-score")}')
    R.check(pg.inner_text('#final-correct') == '1' and pg.inner_text('#final-errors') == '3', '完成句數 1、打錯 3')
    R.check(re.match(r'\d+%$', pg.inner_text('#final-acc')) is not None, '準確度顯示百分比：' + pg.inner_text('#final-acc'))
    R.check(pg.is_visible('#start-btn') and not pg.evaluate("isPlaying"), '結算後可再開始')
    R.check(not errs, '沒有網頁錯誤 %s' % errs)
    rank_html = pg.inner_html('#final-rank')
    R.check('#1' in rank_html, '名次：#1（%s）' % re.sub('<[^>]+>', '', rank_html)[:60])
    b.close()

    # ───── 6) 排行榜：公開榜（A1）寫 Firebase；備援／B1 寫本機 ─────
    if HAVE_BANK:
        b, pg, errs = page(p, own={'diff': 'normal', 'level': 'A1'})
        start(pg)
        finish_sentence(pg)
        pg.evaluate("endGame()"); pg.wait_for_timeout(900)
        sc1 = pg.evaluate("computeScore(correctSentenceCount, correctHits, errorHits).score")
        doc = pg.evaluate("window.__db['moleScores/normal__A1__ana']")
        R.check(doc is not None and doc['score'] == sc1 and doc['difficulty'] == 'normal' and doc['level'] == 'A1', '公開榜文件 moleScores/normal__A1__ana：%s' % doc)
        R.check(doc and doc['name'] == 'Ana' and doc['script'] == 'zh-TW', '成績帶暱稱與字形')
        R.check('newBest' not in pg.inner_html('#final-rank') and '<span class="badge">' in pg.inner_html('#final-rank'), '第一次：顯示「新紀錄」')
        pg.click('#modal-ok')
        # 再玩一局，分數更低 → 不覆蓋
        pg.click('#start-btn'); pg.wait_for_timeout(700); pg.evaluate("clearInterval(spawnInterval)")
        pg.evaluate("endGame()"); pg.wait_for_timeout(700)
        doc2 = pg.evaluate("window.__db['moleScores/normal__A1__ana']")
        R.check(doc2['score'] == sc1, '第二局 0 句：不覆蓋較高的舊分數')
        pg.click('#modal-ok')
        # 同暱稱換大小寫 → 視為同一人
        pg.evaluate("savePlayerName('ANA')")
        pg.click('#start-btn'); pg.wait_for_timeout(700); pg.evaluate("clearInterval(spawnInterval)")
        finish_sentence(pg); pg.wait_for_timeout(900); finish_sentence(pg)
        pg.evaluate("endGame()"); pg.wait_for_timeout(900)
        keys = [k for k in pg.evaluate("Object.keys(window.__db)") if k.startswith('moleScores/')]
        R.check(keys == ['moleScores/normal__A1__ana'], '同名不分大小寫：仍是同一筆 %s' % keys)
        R.check(pg.evaluate("window.__db['moleScores/normal__A1__ana'].score") > sc1, '更高分 → 覆蓋為新高分')
        pg.click('#modal-ok')
        # 開排行榜視窗
        (pg.click('#settings-toggle') if pg.is_visible('#settings-toggle') else None); pg.wait_for_timeout(300); pg.click('#open-board'); pg.wait_for_timeout(600)
        R.check(pg.is_visible('#board-modal') and 'ANA' in pg.inner_text('#board-body') or 'Ana' in pg.inner_text('#board-body'), '排行榜視窗顯示自己：' + pg.inner_text('#board-body')[:30].replace('\n', ' '))
        R.check(pg.locator('#board-levels button').count() == 2, '公開榜有 A1／A2 兩個分頁')
        R.check(pg.locator('#board-tabs button').count() == 3, '難度分頁：簡單／普通／困難')
        pg.click('#board-close')
        R.check(not errs, '沒有網頁錯誤 %s' % errs)
        b.close()

        # 寫入失敗：不當掉，顯示儲存失敗
        b, pg, errs = page(p, own={'diff': 'easy', 'level': 'A1'}, flags={'__failTx': True})
        start(pg); finish_sentence(pg)
        pg.evaluate("endGame()"); pg.wait_for_timeout(900)
        t = pg.inner_text('#final-rank')
        R.check(('儲存' in t or 'guardar' in t or 'save' in t) and pg.is_visible('#result-modal'), '雲端寫入失敗：結算視窗仍正常，顯示儲存失敗：' + t.replace('\n', ' ')[:50])
        R.check(not [e for e in errs if 'tx-fail' in e], '寫入失敗不會變成網頁錯誤（有被接住）')
        b.close()

        # B1 → 不進公開榜（只存本機）
        b, pg, errs = page(p, '?level=B1')
        start(pg); finish_sentence(pg)
        pg.evaluate("endGame()"); pg.wait_for_timeout(900)
        R.check(not [k for k in pg.evaluate("Object.keys(window.__db)") if k.startswith('moleScores/')], '?level=B1：不寫公開榜')
        loc = json.loads(pg.evaluate("localStorage.getItem('moleScoresLocal')") or '{}')
        R.check(any('B1' in k for k in loc), '?level=B1：成績存本機 %s' % list(loc))
        b.close()

    # 備援句庫 → 本機榜
    b, pg, errs = page(p, bank=False)
    start(pg); finish_sentence(pg)
    pg.evaluate("endGame()"); pg.wait_for_timeout(900)
    R.check(not [k for k in pg.evaluate("Object.keys(window.__db)") if k.startswith('moleScores/')], '句庫讀不到（備援）：不寫公開榜')
    loc = json.loads(pg.evaluate("localStorage.getItem('moleScoresLocal')") or '{}')
    R.check('easy' in loc and loc['easy'][0]['name'] == 'Ana', '備援：成績存本機 easy：%s' % list(loc))
    b.close()

    # 一句都沒完成 → 不上榜
    b, pg, errs = page(p, bank=HAVE_BANK)
    start(pg); wrong_hit(pg)
    pg.evaluate("endGame()"); pg.wait_for_timeout(700)
    R.check(not [k for k in pg.evaluate("Object.keys(window.__db)") if k.startswith('moleScores/')] and pg.evaluate("localStorage.getItem('moleScoresLocal')") is None, '一句都沒完成：不寫任何榜')
    R.check(('至少完成一句' in pg.inner_text('#final-rank')) or ('Completa' in pg.inner_text('#final-rank')) or ('Complete' in pg.inner_text('#final-rank')), '提示「至少完成一句才會進排行榜」：' + pg.inner_text('#final-rank')[:40])
    b.close()

    # ───── 7) 時間到自動結束／重新開始 ─────
    b, pg, errs = page(p, bank=HAVE_BANK, fast=True)
    pg.click('#start-btn')
    pg.wait_for_function("document.getElementById('result-modal').style.display==='flex'", timeout=15000)
    R.check(True, '120 秒到：自動出現結算視窗')
    R.check(not pg.evaluate("isPlaying") and pg.inner_text('#timer') == '02:00', '結算後計時重設為 02:00')
    b.close()
    b, pg, errs = page(p, bank=HAVE_BANK)
    start(pg); finish_sentence(pg)
    pg.click('#restart-btn'); pg.wait_for_timeout(500)
    R.check(not pg.is_visible('#result-modal') and not pg.evaluate("isPlaying"), '按「重新開始」：不顯示結算、回到待機')
    R.check(pg.evaluate("localStorage.getItem('moleScoresLocal')") is None and not [k for k in pg.evaluate("Object.keys(window.__db||{})") if k.startswith('moleScores/')], '中途重新開始：不寫成績')
    R.check(pg.evaluate("document.getElementById('settings-sheet').classList.contains('open')"), '重新開始後自動打開設定面板')
    b.close()

    # ───── 8) 設定每個值 ─────
    PY = re.compile('[āáǎàēéěèīíǐìōóǒòūúǔùǖǘǚǜ]'); ZY = re.compile('[ㄅ-ㄩ]')
    base = {'v': 1, 'script': 'trad', 'lang': 'es', 'phon': 'pinyin', 'rate': 'normal'}
    for key, vals in (('script', ['trad', 'simp']), ('lang', ['es', 'en', 'zh']), ('phon', ['pinyin', 'zhuyin', 'both', 'off']), ('rate', ['slow', 'normal', 'fast'])):
        for v in vals:
            st = dict(base, **{key: v})
            label = f'{key}={v}'
            b, pg, errs = page(p, settings=st, bank=False)
            start(pg)
            pg.evaluate("loadNextSentence(); const i=popupMole(60000,true);")
            info = pg.evaluate("""()=>{ const c=cells.find(c=>c.up&&!c.bonus);
              return { words:currentSentenceObj.words.join(''), phonCell:c?c.phonText.textContent:'', lbl:document.getElementById('target-lbl').textContent,
                       ph:[...document.querySelectorAll('#target-sentence .target-char')].map(e=>e.textContent).join(' '),
                       ui:settings.ui, scr:settings.script, rate:settings.rate, spoken:window.__spoken.map(s=>s.rate) }; }""")
            if key == 'script':
                simp_words = {'今天天气真好', '小猫在草地上玩', '我喜欢吃西瓜'}; trad_words = {'今天天氣真好', '小貓在草地上玩', '我喜歡吃西瓜'}
                R.check(info['words'] in (simp_words if v == 'simp' else trad_words), f'{label}：題目字形正確「{info["words"]}」')
            if key == 'lang':
                if v == 'zh': R.check(info['lbl'].strip() == '照順序打出詞語：' and 'Pulsa' not in info['lbl'], f'{label}：純中文標題「{info["lbl"]}」')
                elif v == 'es': R.check('照順序打出詞語' in info['lbl'] and re.search('[a-zA-Z]{4,}', info['lbl']), f'{label}：中文＋西文「{info["lbl"][:40]}」')
                else: R.check('Hit the words' in info['lbl'], f'{label}：中文＋英文「{info["lbl"][:40]}」')
            if key == 'phon':
                txt = info['phonCell'] + ' ' + info['ph']
                got = (bool(PY.search(txt)), bool(ZY.search(txt)))
                want = {'pinyin': (True, False), 'zhuyin': (False, True), 'both': (True, True), 'off': (False, False)}[v]
                if v == 'off': got = (bool(PY.search(info['phonCell'])), bool(ZY.search(info['phonCell'])))
                R.check(got == want or (v == 'off' and got == (False, False)), f'{label}：地鼠卡 拼音{"有" if got[0] else "無"} 注音{"有" if got[1] else "無"}')
                R.check(pg.evaluate("document.getElementById('game-area').classList.contains('ph-on')") == (v != 'off'), f'{label}：phon 開關 class 正確')
            if key == 'rate':
                want_r = {'slow': 0.45, 'normal': 0.65, 'fast': 0.85}[v]
                R.check(info['spoken'] and abs(info['spoken'][-1] - want_r) < 1e-6, f'{label}：念出速度 {info["spoken"][-1] if info["spoken"] else None}（應為 {want_r}）')
            R.check(not errs, f'{label}：沒有網頁錯誤 {errs}')
            b.close()
    # 面板點選 → 存檔 → 重新整理仍在；難度表
    b, pg, errs = page(p, bank=False)
    for k, v, exp in (('script', 'zh-CN', ('script', 'simp')), ('ui', 'en', ('lang', 'en')), ('phon', 'zhuyin', ('phon', 'zhuyin')), ('rate', 'fast', ('rate', 'fast'))):
        pg.evaluate("(a)=>setSetting(a[0],a[1])", [k, v])
        saved = json.loads(pg.evaluate("localStorage.getItem('hanziGames.settings')"))
        R.check(saved.get(exp[0]) == exp[1], f'設定 {k}={v}：共用設定存 {exp[0]}={saved.get(exp[0])}')
    pg.evaluate("setSetting('diff','hard')"); pg.evaluate("setSetting('level','A2')")
    own = json.loads(pg.evaluate("localStorage.getItem('moleSettings')"))
    R.check(own.get('diff') == 'hard' and own.get('level') == 'A2', '難度、等級存在遊戲自己的設定：%s' % own)
    pg.reload(); pg.wait_for_timeout(1500)
    R.check(pg.evaluate("[settings.ui, settings.script, settings.phon, settings.rate, settings.diff]") == ['en', 'zh-CN', 'zhuyin', 'fast', 'hard'], '重新整理後設定還在：%s' % pg.evaluate("[settings.ui, settings.script, settings.phon, settings.rate, settings.diff]"))
    cfgs = pg.evaluate("diffSettings")
    R.check(cfgs['easy']['count'] == 1 and cfgs['normal']['count'] == 2 and cfgs['hard']['count'] == 3, '難度：簡單 1 隻、普通 2 隻、困難 3 隻同時冒出')
    R.check(cfgs['easy']['duration'] > cfgs['normal']['duration'] > cfgs['hard']['duration'], '難度越高，地鼠停留越短')
    R.check(cfgs['easy']['interval'] > cfgs['normal']['interval'] > cfgs['hard']['interval'], '難度越高，冒出間隔越短')
    b.close()
    # 遊戲中不能改難度
    b, pg, errs = page(p, bank=False)
    start(pg)
    pg.evaluate("setSetting('diff','hard')")
    R.check(pg.evaluate("settings.diff") != 'hard', '遊戲進行中不能改難度')
    b.close()

print('FAILS', R.fails); sys.exit(1 if R.fails else 0)
