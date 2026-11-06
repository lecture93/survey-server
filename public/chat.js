// 왼쪽 AI 챗봇: 말로 투표를 대신 넣어 주고, 결과를 물으면 데이터로 답한다.
// 서버 POST /api/ai/chat {messages:[{role,content}]} → {reply, vote|null}
// 대화는 이 탭(sessionStorage)에만 남는다.
(function () {
  var KEY = 'survey-chat-v1';
  var MAX_SEND = 12;
  var history = [];
  try { history = JSON.parse(sessionStorage.getItem(KEY) || '[]') || []; } catch (e) { history = []; }

  var css = ''
    + ':root{--chat-w:360px}'
    + '.chat{position:fixed;top:0;left:0;bottom:0;width:var(--chat-w);display:flex;flex-direction:column;background:#fff;border-right:1px solid #e5e7eb;box-shadow:4px 0 20px rgba(0,0,0,.04);z-index:50;font-family:"Pretendard","Malgun Gothic",sans-serif;color:#1f2937}'
    + '.chat-head{display:flex;align-items:center;gap:10px;padding:16px 16px 12px;border-bottom:1px solid #eef0f6}'
    + '.chat-head h2{margin:0;font-size:16px;flex:1}'
    + '.chat-head small{display:block;font-weight:400;color:#6b7280;font-size:12px;margin-top:2px}'
    + '.chat-head button{border:0;background:none;color:#6b7280;font-size:13px;cursor:pointer;padding:6px;width:auto}'
    + '.chat-log{flex:1;overflow-y:auto;padding:14px 14px 4px;display:flex;flex-direction:column;gap:10px}'
    + '.msg{max-width:88%;padding:10px 12px;border-radius:14px;font-size:14px;line-height:1.55;white-space:pre-wrap;word-break:break-word}'
    + '.msg.user{align-self:flex-end;background:#4f46e5;color:#fff;border-bottom-right-radius:4px}'
    + '.msg.bot{align-self:flex-start;background:#f3f4f8;border-bottom-left-radius:4px}'
    + '.msg.err{background:#fef2f2;color:#b91c1c}'
    + '.msg.wait{color:#6b7280}'
    + '.vote-card{margin-top:8px;padding:8px 10px;border-radius:10px;background:#fff;border:1px solid #c7d2fe;font-size:13px}'
    + '.vote-card a{color:#4f46e5;font-weight:700}'
    + '.chips{display:flex;flex-wrap:wrap;gap:6px;padding:4px 14px 10px}'
    + '.chips button{width:auto;border:1px solid #e5e7eb;background:#fff;color:#374151;border-radius:999px;padding:6px 10px;font-size:12px;font-weight:500;cursor:pointer}'
    + '.chat-form{display:flex;gap:8px;padding:12px 14px 16px;border-top:1px solid #eef0f6}'
    + '.chat-form textarea{flex:1;min-width:0;min-height:44px;max-height:120px;resize:none;padding:11px 12px;border:1px solid #e5e7eb;border-radius:12px;font:inherit;font-size:14px}'
    + '.chat-form button{width:auto;flex:none;padding:0 16px;border:0;border-radius:12px;background:#4f46e5;color:#fff;font-weight:700;font-size:14px;cursor:pointer}'
    + '.chat-form button:disabled{opacity:.6;cursor:default}'
    + '.chat-toggle{display:none}'
    + '@media (min-width:1000px){body{padding-left:var(--chat-w)}.chat-close{display:none}}'
    + '@media (max-width:999px){'
    + '.chat{width:100%;max-width:420px;transform:translateX(-102%);transition:transform .2s}'
    + 'body.chat-open .chat{transform:none}'
    + '.chat-toggle{display:block;position:fixed;left:16px;bottom:16px;z-index:51;width:auto;padding:12px 16px;border:0;border-radius:999px;background:#4f46e5;color:#fff;font-weight:700;font-size:14px;box-shadow:0 6px 20px rgba(79,70,229,.35);cursor:pointer}'
    + 'body.chat-open .chat-toggle{display:none}}';
  var style = document.createElement('style');
  style.textContent = css;
  document.head.appendChild(style);

  var aside = document.createElement('aside');
  aside.className = 'chat';
  aside.setAttribute('aria-label', 'AI 챗봇');
  aside.innerHTML = ''
    + '<div class="chat-head"><h2>🤖 투표 도우미<small>말로 투표하고, 결과를 물어보세요</small></h2>'
    + '<button type="button" id="chat-reset">새 대화</button><button type="button" id="chat-close" class="chat-close">닫기</button></div>'
    + '<div class="chat-log" id="chat-log" aria-live="polite"></div>'
    + '<div class="chips" id="chat-chips"></div>'
    + '<form class="chat-form" id="chat-form"><textarea id="chat-input" rows="1" maxlength="500" placeholder="예: 송이랑 케르반 좋았어요, 닉네임 점심왕"></textarea>'
    + '<button type="submit">보내기</button></form>';
  document.body.appendChild(aside);

  var toggle = document.createElement('button');
  toggle.type = 'button';
  toggle.className = 'chat-toggle';
  toggle.textContent = '💬 AI 도우미';
  document.body.appendChild(toggle);

  var log = document.getElementById('chat-log');
  var form = document.getElementById('chat-form');
  var input = document.getElementById('chat-input');
  var sendBtn = form.querySelector('button');
  var chips = document.getElementById('chat-chips');
  var SUGGEST = ['송이랑 케르반으로 투표해 줘', '지금 1위는 어디야?', '한줄평에서 많이 추천한 메뉴는?', '중동 음식 좋아하면 어디 가?'];

  function save() {
    try { sessionStorage.setItem(KEY, JSON.stringify(history.slice(-40))); } catch (e) { }
  }

  function bubble(role, text, extra) {
    var div = document.createElement('div');
    div.className = 'msg ' + role + (extra ? ' ' + extra : '');
    div.textContent = text;
    log.appendChild(div);
    log.scrollTop = log.scrollHeight;
    return div;
  }

  function voteCard(div, vote) {
    var card = document.createElement('div');
    card.className = 'vote-card';
    var lines = ['✅ 투표 완료 · ' + vote.picks.join(', ')];
    if (vote.nickname) lines.push('닉네임: ' + vote.nickname);
    if (vote.comment) lines.push('한줄평: ' + vote.comment);
    card.textContent = lines.join('\n');
    if (location.pathname.indexOf('/result') !== 0) {
      card.appendChild(document.createTextNode('\n'));
      var a = document.createElement('a');
      a.href = '/result'; a.textContent = '결과 보러 가기 →';
      card.appendChild(a);
    }
    div.appendChild(card);
  }

  function render() {
    log.innerHTML = '';
    if (!history.length) {
      bubble('bot', '안녕하세요! 좋았던 가게를 말해 주시면 대신 투표해 드려요. 투표 결과나 한줄평이 궁금하면 물어보세요.');
    }
    history.forEach(function (m) {
      var div = bubble(m.role === 'user' ? 'user' : 'bot', m.content);
      if (m.vote) voteCard(div, m.vote);
    });
    chips.style.display = history.length ? 'none' : '';
  }

  SUGGEST.forEach(function (t) {
    var b = document.createElement('button');
    b.type = 'button'; b.textContent = t;
    b.addEventListener('click', function () { input.value = t; input.focus(); });
    chips.appendChild(b);
  });

  async function send(text) {
    history.push({ role: 'user', content: text });
    save(); render();
    var wait = bubble('bot', '생각하는 중...', 'wait');
    sendBtn.disabled = true; input.disabled = true;
    try {
      var msgs = history.slice(-MAX_SEND).map(function (m) { return { role: m.role, content: m.content }; });
      var res = await fetch('/api/ai/chat', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ messages: msgs }) });
      var data = {};
      try { data = await res.json(); } catch (e) { }
      if (!res.ok) throw new Error(data.error || ('오류 ' + res.status));
      var item = { role: 'assistant', content: data.reply };
      if (data.vote) item.vote = data.vote;
      history.push(item);
      save(); render();
    } catch (e) {
      wait.className = 'msg bot err';
      wait.textContent = e.message || '응답을 받지 못했어요.';
      history.pop(); save();  // 실패한 질문은 다시 보낼 수 있게 대화에서 뺌
      input.value = text;
    }
    sendBtn.disabled = false; input.disabled = false; input.focus();
  }

  form.addEventListener('submit', function (ev) {
    ev.preventDefault();
    var text = input.value.trim();
    if (!text || sendBtn.disabled) return;
    input.value = '';
    send(text);
  });
  input.addEventListener('keydown', function (ev) {
    if (ev.key === 'Enter' && !ev.shiftKey && !ev.isComposing) { ev.preventDefault(); form.requestSubmit(); }
  });
  document.getElementById('chat-reset').addEventListener('click', function () {
    history = []; save(); render(); input.focus();
  });
  toggle.addEventListener('click', function () { document.body.classList.add('chat-open'); input.focus(); });
  document.getElementById('chat-close').addEventListener('click', function () { document.body.classList.remove('chat-open'); });

  render();
})();
