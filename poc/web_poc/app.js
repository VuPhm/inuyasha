const state = {
  serverUrl: '',
  player: null,
  heroes: [],
  chapters: [],
  nodes: [],
  gameData: null,
  atlases: {},
  images: {},
  audioOn: true,
  bgm: null,
  battle: null,
};

const $ = (id) => document.getElementById(id);

function logRpc(line) {
  const el = $('rpc-log');
  if (!el) return;
  el.textContent += `${line}\n`;
  el.scrollTop = el.scrollHeight;
}

function showScreen(name) {
  for (const s of document.querySelectorAll('.screen')) s.classList.remove('active');
  $(`screen-${name}`).classList.add('active');
}

function playBgm(file) {
  if (!state.audioOn) return;
  if (state.bgm) {
    state.bgm.pause();
    state.bgm = null;
  }
  const a = new Audio(`/assets/res/music/${file}`);
  a.loop = true;
  a.volume = 0.35;
  a.play().catch(() => {});
  state.bgm = a;
}

function playSfx(file) {
  if (!state.audioOn || !file || file === '0') return;
  const f = file.endsWith('.mp3') ? file : `${file}.mp3`;
  const a = new Audio(`/assets/res/music/${f}`);
  a.volume = 0.65;
  a.play().catch(() => {});
}

async function rpc(moduleName, methodName, data = []) {
  const res = await fetch('/client.aspx', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'X-Plain-Json': '1' },
    body: JSON.stringify({
      PartnerId: '1001',
      ServerId: 1,
      Session: state.player?.Session || '',
      PlayerId: state.player?.PlayerId || '',
      GameVersionId: '505',
      ModuleName: moduleName,
      MethodName: methodName,
      Data: data,
    }),
  });
  const json = await res.json();
  if (json.Avatar) state.player = json.Avatar;
  updateHud();
  return json;
}

function updateHud() {
  if (!state.player) return;
  $('hud-player').textContent = `${state.player.PlayerName} (Lv.${state.player.Lv} | VIP ${state.player.VIPLv})`;
  $('hud-stats').textContent = `Gold: ${state.player.Gold} | Jade: ${state.player.Diamond} | VIT: ${state.player.VIT}/${state.player.VITMaxNum}`;
}

async function loadImage(url) {
  if (state.images[url]) return state.images[url];
  return new Promise((resolve, reject) => {
    const img = new Image();
    img.onload = () => { state.images[url] = img; resolve(img); };
    img.onerror = reject;
    img.src = url;
  });
}

async function loadAtlasSprite(largePic) {
  if (!state.atlases[largePic]) {
    const res = await fetch(`/api/atlas/${largePic}`);
    const atlas = await res.json();
    const img = await loadImage(`/assets/res/animation/${atlas.page}`);
    // Pick best idle/stand region from the Spine atlas
    const keys = Object.keys(atlas.regions);
    const preferred = keys.find((k) => /daiji|stand|idle/i.test(k))
      || keys.find((k) => /tou|body|shen/i.test(k))
      || keys[0];
    state.atlases[largePic] = { atlas, img, idleKey: preferred, keys };
  }
  return state.atlases[largePic];
}

function drawAtlasRegion(ctx, sprite, regionKey, cx, cy, scale = 0.7, flipX = false) {
  const r = sprite.atlas.regions[regionKey];
  if (!r || !r.xy || !r.size) {
    ctx.drawImage(sprite.img, cx - 45, cy - 90, 90, 90);
    return;
  }
  const [sx, sy] = r.xy;
  const [rw, rh] = r.size;
  const sw = r.rotate ? rh : rw;
  const sh = r.rotate ? rw : rh;
  ctx.save();
  ctx.translate(cx, cy);
  if (flipX) ctx.scale(-1, 1);
  if (r.rotate) {
    ctx.rotate(-Math.PI / 2);
    ctx.drawImage(sprite.img, sx, sy, sw, sh, -sh * scale * 0.5, -sw * scale * 0.5, sw * scale, sh * scale);
  } else {
    ctx.drawImage(sprite.img, sx, sy, sw, sh, -sw * scale * 0.5, -sh * scale, sw * scale, sh * scale);
  }
  ctx.restore();
}

async function initManageCenter() {
  try {
    const res = await fetch('/API/ServerList_Client.ashx', {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded', 'X-Plain-Json': '1' },
      body: 'gameID=0&PartnerID=1001&GameVersionID=505',
    });
    const data = await res.json();
    const svr = data.Data.Server[0];
    state.serverUrl = svr.ServerUrl;
    $('server-box').textContent = `Server Online: ${svr.ServerName} (${svr.ServerUrl})`;
    logRpc(`POST /API/ServerList_Client.ashx -> Code=${data.Code} (${svr.ServerName})`);

    const gdRes = await fetch('/api/gamedata');
    state.gameData = await gdRes.json();
    logRpc(`Loaded GameData: ${state.gameData.counts.heroes} heroes, ${state.gameData.counts.chapters} chapters, ${state.gameData.counts.nodes} nodes`);
  } catch (err) {
    $('server-box').textContent = `ManageCenter Error: ${err.message}`;
  }
}

async function enterGame() {
  playBgm('music_login.mp3');
  const loginRes = await rpc('Player', 'Login', ['web', '12', 1001, 'local', '', '100001']);
  logRpc(`POST /client.aspx Player.Login -> PlayerId=${loginRes.Value.PlayerId}`);

  const initRes = await rpc('Player', 'GetInitData', []);
  state.heroes = initRes.Value.HeroInfo;
  logRpc(`POST /client.aspx Player.GetInitData -> ${state.heroes.length} active heroes`);

  await refreshChapterMap();
  showScreen('home');
}

async function refreshChapterMap() {
  const bInfo = await rpc('Battle', 'GetBattleInfo', [1, 1]);
  state.chapters = bInfo.Value.ChapterList;
  const nRes = await rpc('Battle', 'GetNodeList', [11]);
  state.nodes = nRes.Value;

  const squadEl = $('squad-list');
  squadEl.innerHTML = '';
  for (const h of state.heroes) {
    const cfg = state.gameData.heroes[String(h.HeroModelId)];
    const card = document.createElement('div');
    card.className = 'hero-card';
    const cv = document.createElement('canvas');
    cv.width = 64; cv.height = 64;
    const meta = document.createElement('div');
    meta.className = 'hero-meta';
    meta.innerHTML = `<strong>${cfg.name}</strong>Lv.${h.Lv} • HP ${h.HP} • AP ${h.AP}`;
    card.appendChild(cv);
    card.appendChild(meta);
    squadEl.appendChild(card);

    loadAtlasSprite(cfg.largePic).then((sp) => {
      const c = cv.getContext('2d');
      drawAtlasRegion(c, sp, sp.idleKey, 32, 58, 0.24, false);
    }).catch(() => {});
  }

  const nodeEl = $('node-list');
  nodeEl.innerHTML = '';
  for (const n of state.nodes) {
    const nCfg = state.gameData.nodes[String(n.NodeModelId)] || { name: String(n.NodeModelId), dropGold: 50 };
    const unlocked = n.Flag === 1 || n.StarCount > 0;
    const row = document.createElement('div');
    row.className = `node-row ${unlocked ? '' : 'locked'}`;
    const stars = '★'.repeat(n.StarCount) + '☆'.repeat(3 - n.StarCount);
    row.innerHTML = `
      <div>
        <strong>Stage ${nCfg.name}</strong> (Node ${n.NodeModelId})<br/>
        <small>${stars} • Drop Gold: ${nCfg.dropGold}</small>
      </div>
    `;
    const btn = document.createElement('button');
    btn.className = 'btn-primary';
    btn.textContent = unlocked ? 'Battle!' : 'Locked';
    btn.disabled = !unlocked;
    btn.onclick = () => startBattle(n.NodeModelId, nCfg.name);
    row.appendChild(btn);
    nodeEl.appendChild(row);
  }
}

async function startBattle(nodeId, nodeName) {
  const res = await rpc('Battle', 'GetFightInfo', [11, nodeId, 1]);
  const herosRaw = res.Value.FightInfo.FightObjs[0].Heros;

  const allies = [];
  const enemies = [];
  for (let i = 0; i < 6; i++) {
    if (herosRaw[i] && herosRaw[i].HeroModelId) allies.push({ ...herosRaw[i], pos: i, flash: 0, lunge: 0 });
  }
  for (let i = 6; i < 12; i++) {
    if (herosRaw[i] && herosRaw[i].HeroModelId) enemies.push({ ...herosRaw[i], pos: i - 6, flash: 0, lunge: 0 });
  }

  for (const u of [...allies, ...enemies]) {
    u.sprite = await loadAtlasSprite(u.LargePic).catch(() => null);
  }
  const bgLayers = await Promise.all([
    loadImage('/assets/res/map/changjing_pingyuan_jinjing_tiankong.png'),
    loadImage('/assets/res/map/changjing_pingyuan_jinjing_yuanshan.png'),
    loadImage('/assets/res/map/changjing_pingyuan_jinjing.png'),
  ]);

  state.battle = {
    nodeId,
    nodeName,
    round: 1,
    allies,
    enemies,
    activeIdx: 0,
    auto: false,
    busy: false,
    finished: false,
    bgLayers,
  };

  $('battle-title').textContent = `Stage ${nodeName} (Chapter 1)`;
  $('battle-round').textContent = `Round 1`;
  $('btn-auto').textContent = '⚡ Auto: Off';
  $('turn-banner').textContent = `${allies[0].Name}'s turn! Choose Attack or Rage Skill.`;
  showScreen('battle');
  playBgm('music_battle_first.mp3');
  updateBattleButtons();
  requestAnimationFrame(renderBattleFrame);
}

function updateBattleButtons() {
  const b = state.battle;
  if (!b || b.finished) return;
  const actor = b.allies[b.activeIdx];
  const canAct = !b.busy && actor && actor.HP > 0;
  $('btn-attack').disabled = !canAct;
  $('btn-skill').disabled = !canAct || actor.RP < 100;
}

function renderBattleFrame() {
  const b = state.battle;
  if (!b) return;
  const canvas = $('battle-canvas');
  const ctx = canvas.getContext('2d');
  ctx.clearRect(0, 0, canvas.width, canvas.height);

  // Real layered Seek Jade pingyuan background
  const [sky, mtn, ground] = b.bgLayers;
  ctx.drawImage(sky, 0, 0, canvas.width, 360);
  ctx.drawImage(mtn, 0, 120, canvas.width, 250);
  ctx.drawImage(ground, 0, 240, canvas.width, 400);

  const allyPositions = [
    [220, 420], [270, 520], [130, 460], [160, 560],
  ];
  const enemyPositions = [
    [870, 430], [930, 525], [1000, 455],
  ];

  const drawUnit = (u, [bx, by], isEnemy, isActive) => {
    if (u.HP <= 0) return;
    const x = bx + (isEnemy ? -u.lunge : u.lunge);
    const y = by;
    u.lunge *= 0.85;
    if (u.flash > 0) u.flash -= 1;

    ctx.save();
    // Ground shadow
    ctx.fillStyle = isActive ? 'rgba(255, 220, 90, 0.55)' : 'rgba(0,0,0,0.42)';
    ctx.beginPath();
    ctx.ellipse(x, y, 42, 12, 0, 0, Math.PI * 2);
    ctx.fill();

    if (u.flash > 0) ctx.globalAlpha = 0.55;
    if (u.sprite) {
      drawAtlasRegion(ctx, u.sprite, u.sprite.idleKey, x, y, u.IsBoss ? 0.65 : 0.55, isEnemy);
    }
    ctx.restore();

    // Name + HP + RP bars
    ctx.fillStyle = 'rgba(0,0,0,0.7)';
    ctx.fillRect(x - 46, y - 142, 92, 18);
    ctx.fillStyle = u.HP > 0 ? (isEnemy ? '#e04f4f' : '#43b868') : '#555';
    ctx.fillRect(x - 44, y - 134, 88 * Math.max(0, u.HP / u.TotalHp), 6);
    ctx.fillStyle = '#f2b830';
    ctx.fillRect(x - 44, y - 127, 88 * Math.min(1, u.RP / 100), 3);

    ctx.fillStyle = '#fff5d6';
    ctx.font = 'bold 12px sans-serif';
    ctx.textAlign = 'center';
    ctx.fillText(u.Name, x, y - 146);
  };

  b.allies.forEach((u, i) => drawUnit(u, allyPositions[i % allyPositions.length], false, !b.busy && i === b.activeIdx));
  b.enemies.forEach((u, i) => drawUnit(u, enemyPositions[i % enemyPositions.length], true, false));

  if (!b.finished) requestAnimationFrame(renderBattleFrame);
}

async function performPlayerMove(useSkill) {
  const b = state.battle;
  if (!b || b.busy || b.finished) return;
  const actor = b.allies[b.activeIdx];
  const target = b.enemies.find((e) => e.HP > 0);
  if (!actor || !target) return;

  b.busy = true;
  updateBattleButtons();

  actor.lunge = 130;
  const mult = useSkill ? 2.1 : 1.0;
  if (useSkill) {
    actor.RP = Math.max(0, actor.RP - 100);
    playSfx(actor.SkillSound);
  } else {
    actor.RP = Math.min(100, actor.RP + 25);
  }

  const dmg = Math.max(60, Math.round((actor.AP * 1.4 - target.DEF * 0.45) * mult));
  target.HP = Math.max(0, target.HP - dmg);
  target.flash = 10;
  $('turn-banner').textContent = `${actor.Name} uses ${useSkill ? 'Rage Skill' : 'Attack'} on ${target.Name} for ${dmg} dmg!`;

  await new Promise((r) => setTimeout(r, 550));

  if (b.enemies.every((e) => e.HP <= 0)) {
    await finishBattle(true);
    return;
  }

  // Advance to next alive ally or enemy phase
  let nextIdx = b.activeIdx + 1;
  while (nextIdx < b.allies.length && b.allies[nextIdx].HP <= 0) nextIdx++;
  if (nextIdx >= b.allies.length) {
    await runEnemyPhase();
  } else {
    b.activeIdx = nextIdx;
    b.busy = false;
    $('turn-banner').textContent = `${b.allies[b.activeIdx].Name}'s turn!`;
    updateBattleButtons();
    if (b.auto) performPlayerMove(b.allies[b.activeIdx].RP >= 100);
  }
}

async function runEnemyPhase() {
  const b = state.battle;
  for (const enemy of b.enemies) {
    if (enemy.HP <= 0) continue;
    const victim = b.allies.find((a) => a.HP > 0);
    if (!victim) break;
    enemy.lunge = 120;
    const dmg = Math.max(35, Math.round(enemy.AP * 1.15 - victim.DEF * 0.5));
    victim.HP = Math.max(0, victim.HP - dmg);
    victim.flash = 10;
    $('turn-banner').textContent = `${enemy.Name} strikes ${victim.Name} for ${dmg} dmg!`;
    await new Promise((r) => setTimeout(r, 480));
    if (b.allies.every((a) => a.HP <= 0)) {
      await finishBattle(false);
      return;
    }
  }
  b.round += 1;
  $('battle-round').textContent = `Round ${b.round}`;
  b.activeIdx = b.allies.findIndex((a) => a.HP > 0);
  b.busy = false;
  $('turn-banner').textContent = `${b.allies[b.activeIdx].Name}'s turn!`;
  updateBattleButtons();
  if (b.auto) performPlayerMove(b.allies[b.activeIdx].RP >= 100);
}

async function finishBattle(won) {
  const b = state.battle;
  b.finished = true;
  if (won) playBgm('music_battle_win.mp3');
  const settle = await rpc('Battle', 'Fight', [11, b.nodeId, 3, won, '', false]);
  $('modal-title').textContent = won ? 'Victory! (★★★)' : 'Defeated';
  const rewards = (settle.Value.BaseGetGameResourceList || []).map((r) => `+${r.Count}`).join(' / ');
  $('modal-body').textContent = won
    ? `Stage ${b.nodeName} cleared! Server saved progress. Rewards: ${rewards} (Gold / HeroEXP)`
    : `Your squad fell in Stage ${b.nodeName}. Try again!`;
  $('victory-modal').classList.remove('hidden');
}

$('btn-connect').onclick = enterGame;
$('btn-attack').onclick = () => performPlayerMove(false);
$('btn-skill').onclick = () => performPlayerMove(true);
$('btn-auto').onclick = () => {
  if (!state.battle) return;
  state.battle.auto = !state.battle.auto;
  $('btn-auto').textContent = `⚡ Auto: ${state.battle.auto ? 'On' : 'Off'}`;
  if (state.battle.auto && !state.battle.busy) {
    const actor = state.battle.allies[state.battle.activeIdx];
    performPlayerMove(actor.RP >= 100);
  }
};
$('btn-retreat').onclick = async () => {
  state.battle = null;
  playBgm('music_login.mp3');
  await refreshChapterMap();
  showScreen('home');
};
$('btn-modal-ok').onclick = async () => {
  $('victory-modal').classList.add('hidden');
  state.battle = null;
  playBgm('music_login.mp3');
  await refreshChapterMap();
  showScreen('home');
};
$('btn-audio').onclick = () => {
  state.audioOn = !state.audioOn;
  $('btn-audio').textContent = state.audioOn ? '🔊 Audio: On' : '🔇 Audio: Off';
  if (!state.audioOn && state.bgm) state.bgm.pause();
  else if (state.audioOn && state.bgm) state.bgm.play().catch(() => {});
};

initManageCenter();
