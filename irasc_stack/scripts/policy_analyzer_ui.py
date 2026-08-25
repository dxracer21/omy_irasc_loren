#!/usr/bin/env python3
"""Small local UI for inspecting LeRobot datasets and checkpoints."""

from __future__ import annotations

import argparse
import base64
import hashlib
import io
import json
import os
import shutil
import threading
import time
from pathlib import Path
from urllib.parse import parse_qs, urlparse
from http.server import BaseHTTPRequestHandler, HTTPServer

HTTPServer.allow_reuse_address = True

import pandas as pd
from PIL import Image
import torch

try:
    from lerobot.configs.policies import PreTrainedConfig
    from lerobot.datasets.lerobot_dataset import LeRobotDataset, LeRobotDatasetMetadata
    from lerobot.policies import make_policy, make_pre_post_processors
except Exception:  # pragma: no cover
    LeRobotDataset = None
    LeRobotDatasetMetadata = None
    PreTrainedConfig = None
    make_policy = None
    make_pre_post_processors = None


HTML = r"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>LeRobot Policy Analyzer</title>
  <style>
    :root { color-scheme: light; --line:#d9dee7; --ink:#172033; --muted:#667085; --bg:#f6f7f9; --panel:#fff; --blue:#2563eb; }
    * { box-sizing: border-box; }
    body { margin:0; font-family: Arial, sans-serif; color:var(--ink); background:var(--bg); }
    header { height:54px; display:flex; align-items:center; gap:16px; padding:0 18px; border-bottom:1px solid var(--line); background:#fff; }
    h1 { margin:0; font-size:18px; letter-spacing:0; }
    main { display:grid; grid-template-columns: 330px 1fr; min-height:calc(100vh - 54px); }
    aside { border-right:1px solid var(--line); background:#fff; padding:14px; overflow:auto; }
    section { padding:14px; overflow:auto; }
    label { display:block; font-size:12px; color:var(--muted); margin:12px 0 5px; }
    select, input, button { width:100%; height:34px; border:1px solid var(--line); border-radius:6px; background:#fff; padding:0 9px; font-size:13px; }
    button { background:var(--blue); color:#fff; border-color:var(--blue); cursor:pointer; font-weight:600; }
    button.secondary { background:#fff; color:var(--ink); border-color:var(--line); }
    .row { display:grid; grid-template-columns:1fr 1fr; gap:10px; }
    .panel { background:var(--panel); border:1px solid var(--line); border-radius:8px; padding:12px; margin-bottom:12px; }
    .panel h2 { font-size:14px; margin:0 0 10px; }
    .cams { display:grid; grid-template-columns:1fr 1fr; gap:12px; }
    .cam img { width:100%; height:auto; display:block; background:#111827; border-radius:6px; }
    .cam .title { font-size:13px; font-weight:700; margin-bottom:7px; }
    pre { margin:0; white-space:pre-wrap; word-break:break-word; font-size:12px; line-height:1.45; }
    table { width:100%; border-collapse:collapse; font-size:12px; }
    td, th { border-bottom:1px solid var(--line); text-align:left; padding:6px; }
    .muted { color:var(--muted); font-size:12px; }
    .slider { width:100%; }
    .status { font-size:12px; color:var(--muted); margin-left:auto; }
    .transport { display:grid; grid-template-columns:1fr 1fr 1fr; gap:8px; margin-top:10px; }
    .transport button { height:32px; }
    .cam img.loading { opacity:0.45; }
    .cam .error { color:#b91c1c; font-size:12px; min-height:18px; margin-top:5px; }
    .bars { display:grid; gap:8px; }
    .barsection { border-top:1px solid var(--line); padding-top:10px; margin-top:10px; }
    .barsection:first-child { border-top:0; padding-top:0; margin-top:0; }
    .barrow { display:grid; grid-template-columns:88px 1fr 82px; align-items:center; gap:10px; font-size:12px; }
    .bartrack { height:12px; background:#eef2f7; border-radius:999px; overflow:hidden; }
    .barfill { height:100%; background:#2563eb; }
    .barfill.wrist { background:#16a34a; }
    .warn { color:#b45309; }
    .timeline { margin-top:12px; }
    .timeline h3 { font-size:13px; margin:12px 0 6px; padding-top:12px; border-top:1px solid var(--line); }
    .timeline svg { width:100%; height:92px; display:block; background:#fafafa; border:1px solid var(--line); border-radius:6px; }
    .legend { display:flex; gap:12px; font-size:12px; color:var(--muted); margin-top:5px; }
    .legend span::before { content:""; display:inline-block; width:10px; height:10px; border-radius:50%; margin-right:5px; background:#2563eb; }
    .legend span.wrist::before { background:#16a34a; }
  </style>
</head>
<body>
  <header>
    <h1>LeRobot Policy Analyzer</h1>
    <div class="status" id="status">ready</div>
  </header>
  <main>
    <aside>
      <label>Dataset Root</label>
      <input id="datasetRoot" value="/workspace/lerobot">
      <button id="loadDatasets">Load Datasets</button>
      <label>Dataset</label>
      <select id="dataset"></select>

      <label>Model Root</label>
      <input id="modelRoot" value="/workspace/model/lerobot">
      <button id="loadModels" class="secondary">Load Models</button>
      <label>Model Run</label>
      <select id="modelRun"></select>
      <label>Checkpoint</label>
      <select id="checkpoint"></select>

      <div class="row">
        <div>
          <label>Episode</label>
          <select id="episode"></select>
        </div>
        <div>
          <label>Frame</label>
          <input id="frame" type="number" min="0" value="0">
        </div>
      </div>
      <label>Frame Scrub</label>
      <input id="frameSlider" class="slider" type="range" min="0" max="0" value="0">
      <button id="loadFrame">Load Frame</button>
      <div class="transport">
        <button id="prevFrame" class="secondary">Prev</button>
        <button id="playPause">Play</button>
        <button id="nextFrame" class="secondary">Next</button>
      </div>
      <div class="row">
        <div>
          <label>Playback FPS</label>
          <input id="playFps" type="number" min="1" max="30" value="10">
        </div>
        <div>
          <label>Stride</label>
          <input id="playStride" type="number" min="1" max="30" value="1">
        </div>
      </div>
      <label>Image Mode</label>
      <select id="imageMode">
        <option value="png">Direct PNG API</option>
        <option value="embedded">Embedded Base64 legacy</option>
      </select>
      <button id="analyzeInfluence" class="secondary">Analyze Episode</button>
      <p class="muted">선택 episode 전체의 top/wrist influence를 계산해 저장한다. 저장된 값은 Play 중 프레임에 맞춰 함께 갱신된다.</p>
    </aside>
    <section>
      <div class="panel">
        <h2>Cameras</h2>
        <div class="cams">
          <div class="cam"><div class="title">Front-top original</div><img id="front"><div id="frontError" class="error"></div></div>
          <div class="cam"><div class="title">Wrist original</div><img id="wrist"><div id="wristError" class="error"></div></div>
        </div>
      </div>
      <div class="panel">
        <h2>Task / Subtask Instruction</h2>
        <pre id="task"></pre>
      </div>
      <div class="panel">
        <h2>Camera Influence</h2>
        <div id="influence" class="muted">checkpoint를 선택하고 Analyze Episode를 누르면 episode 전체 영향도가 저장된다.</div>
      </div>
      <div class="panel">
        <h2>State / Action Raw</h2>
        <table id="stateAction"></table>
      </div>
    </section>
  </main>
  <script>
    const $ = (id) => document.getElementById(id);
    const status = (msg) => $('status').textContent = msg;
    const STORAGE_KEY = 'lerobotPolicyAnalyzerState.v1';
    function savedState() {
      try { return JSON.parse(localStorage.getItem(STORAGE_KEY) || '{}'); }
      catch (_) { return {}; }
    }
    function saveState(extra = {}) {
      const previous = savedState();
      const keep = (id) => ($(id)?.value ? $(id).value : previous[id]);
      const state = {
        ...previous,
        datasetRoot: $('datasetRoot').value,
        dataset: keep('dataset'),
        modelRoot: $('modelRoot').value,
        modelRun: keep('modelRun'),
        checkpoint: keep('checkpoint'),
        episode: keep('episode'),
        frame: $('frame').value || previous.frame,
        playFps: $('playFps').value,
        playStride: $('playStride').value,
        imageMode: $('imageMode').value,
        ...extra,
      };
      localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
    }
    function restoreInputs() {
      const state = savedState();
      ['datasetRoot', 'modelRoot', 'playFps', 'playStride', 'imageMode'].forEach((id) => {
        if (state[id] !== undefined && $(id)) $(id).value = state[id];
      });
    }
    let playTimer = null;
    let loadingFrame = false;
    let influenceRows = new Map();
    let influenceMeta = null;
    async function api(path, params = {}) {
      status('loading');
      const qs = new URLSearchParams(params).toString();
      const res = await fetch('/api/' + path + (qs ? '?' + qs : ''));
      const data = await res.json();
      status(data.ok === false ? 'error' : 'ready');
      if (data.ok === false) throw new Error(data.error || 'request failed');
      return data;
    }
    function setOptions(el, rows, labelFn, valueFn, preferredValue = '') {
      const previous = preferredValue || el.value;
      el.innerHTML = '';
      rows.forEach((row) => {
        const opt = document.createElement('option');
        opt.value = valueFn(row);
        opt.textContent = labelFn(row);
        el.appendChild(opt);
      });
      if (previous && Array.from(el.options).some((opt) => opt.value === previous)) {
        el.value = previous;
      }
    }
    async function loadDatasets() {
      const data = await api('datasets', { root: $('datasetRoot').value });
      const previous = $('dataset').value || savedState().dataset;
      setOptions($('dataset'), data.datasets, d => `${d.name} (${d.episodes} ep, ${d.frames} frames)`, d => d.path, previous);
      saveState();
      if ($('dataset').value) await loadDataset();
    }
    async function loadModels() {
      const data = await api('model_runs', { root: $('modelRoot').value });
      const previous = $('modelRun').value || savedState().modelRun;
      setOptions($('modelRun'), data.runs, r => `${r.name} (${r.checkpoints} ckpt)`, r => r.path, previous);
      saveState();
      if ($('modelRun').value) await loadCheckpoints();
    }
    async function loadCheckpoints() {
      const data = await api('checkpoints', { run: $('modelRun').value });
      const previous = $('checkpoint').value || savedState().checkpoint;
      setOptions($('checkpoint'), data.checkpoints, c => `${c.checkpoint_name} (${c.policy_type || 'unknown'}, ${c.dataset || 'no dataset'})`, c => c.path, previous);
      saveState();
      updateMeta();
    }
    async function loadDataset() {
      const data = await api('dataset_meta', { dataset: $('dataset').value });
      const preferredEpisode = $('episode').value || savedState().episode;
      setOptions($('episode'), data.episodes, e => `episode ${e.episode_index} (${e.length} frames)`, e => e.episode_index, preferredEpisode);
      if (data.episodes.length) {
        const selected = data.episodes.find(e => String(e.episode_index) === $('episode').value) || data.episodes[0];
        setFrameBounds(selected);
        const state = savedState();
        if (state.frame !== undefined) {
          const frame = Math.max(Number($('frame').min), Math.min(Number($('frame').max), Number(state.frame)));
          $('frame').value = frame;
          $('frameSlider').value = frame;
        }
        saveState();
        await loadFrame();
      }
    }
    function setFrameBounds(ep) {
      $('frame').min = ep.from;
      $('frame').max = ep.to - 1;
      $('frame').value = ep.from;
      $('frameSlider').min = ep.from;
      $('frameSlider').max = ep.to - 1;
      $('frameSlider').value = ep.from;
      saveState();
    }
    async function updateEpisodeBounds() {
      const data = await api('dataset_meta', { dataset: $('dataset').value });
      const ep = data.episodes.find(e => String(e.episode_index) === $('episode').value);
      if (ep) setFrameBounds(ep);
      saveState();
      await loadFrame();
    }
    function setCameraSrc(id, errorId, src) {
      const img = $(id);
      const err = $(errorId);
      err.textContent = '';
      img.classList.add('loading');
      img.onload = () => { img.classList.remove('loading'); err.textContent = ''; };
      img.onerror = () => { img.classList.remove('loading'); err.textContent = 'image load failed'; };
      img.src = src;
    }
    async function loadFrame() {
      if (loadingFrame) return;
      loadingFrame = true;
      try {
        const embedded = $('imageMode').value === 'embedded';
        const data = await api('frame', { dataset: $('dataset').value, index: $('frame').value, include_images: embedded ? '1' : '0' });
        if (embedded && data.images) {
          setCameraSrc('front', 'frontError', data.images.front);
          setCameraSrc('wrist', 'wristError', data.images.wrist);
        } else {
          const cacheBust = Date.now();
          setCameraSrc('front', 'frontError', `/api/image?dataset=${encodeURIComponent($('dataset').value)}&index=${encodeURIComponent($('frame').value)}&camera=front&t=${cacheBust}`);
          setCameraSrc('wrist', 'wristError', `/api/image?dataset=${encodeURIComponent($('dataset').value)}&index=${encodeURIComponent($('frame').value)}&camera=wrist&t=${cacheBust}`);
        }
        $('task').textContent = data.task || '';
        const rows = data.state.map((s, i) => `<tr><td>${i}</td><td>${Number(s).toFixed(6)}</td><td>${Number(data.action[i]).toFixed(6)}</td></tr>`).join('');
        $('stateAction').innerHTML = `<tr><th>joint</th><th>state</th><th>recorded action</th></tr>${rows}`;
        saveState();
        updateInfluenceForCurrentFrame();
      } catch (e) {
        status('error');
        $('frontError').textContent = e.message;
        $('wristError').textContent = e.message;
      } finally {
        loadingFrame = false;
      }
    }
    function stopPlayback() {
      if (playTimer) clearInterval(playTimer);
      playTimer = null;
      $('playPause').textContent = 'Play';
    }
    function stepFrame(delta) {
      const current = Number($('frame').value || 0);
      const min = Number($('frame').min || 0);
      const max = Number($('frame').max || 0);
      const next = Math.max(min, Math.min(max, current + delta));
      $('frame').value = next;
      $('frameSlider').value = next;
      if (next >= max) stopPlayback();
      saveState();
      loadFrame();
    }
    function togglePlayback() {
      if (playTimer) { stopPlayback(); return; }
      $('playPause').textContent = 'Pause';
      const tick = () => stepFrame(Number($('playStride').value || 1));
      playTimer = setInterval(tick, 1000 / Math.max(1, Number($('playFps').value || 10)));
    }
    function updateMeta() {
      influenceRows = new Map();
      influenceMeta = null;
      $('influence').textContent = $('checkpoint').value ? 'checkpoint 선택됨. Analyze Episode로 episode 전체 계산 가능.' : 'checkpoint를 선택해줘.';
      saveState();
      loadInfluenceSeries().catch(() => {});
    }
    function pct(v) {
      return `${(Number(v) * 100).toFixed(1)}%`;
    }
    function ratio(front, wrist) {
      const total = Number(front || 0) + Number(wrist || 0);
      return total <= 1e-9 ? [0, 0] : [Number(front || 0) / total, Number(wrist || 0) / total];
    }
    function lineSvg(rows, frontKey, wristKey, yMax = 1.0) {
      if (!rows.length) return '';
      const w = 640, h = 86, pad = 10;
      const minX = Number(rows[0].global_index);
      const maxX = Number(rows[rows.length - 1].global_index);
      const x = (row) => pad + ((Number(row.global_index) - minX) / Math.max(1, maxX - minX)) * (w - pad * 2);
      const y = (v) => h - pad - (Math.max(0, Math.min(yMax, Number(v || 0))) / yMax) * (h - pad * 2);
      const path = (key) => rows.map((row, i) => `${i ? 'L' : 'M'}${x(row).toFixed(1)},${y(row[key]).toFixed(1)}`).join(' ');
      const currentX = x({global_index: Number($('frame').value)}).toFixed(1);
      return `<svg viewBox="0 0 ${w} ${h}" preserveAspectRatio="none">
        <line x1="${pad}" y1="${y(0.5).toFixed(1)}" x2="${w-pad}" y2="${y(0.5).toFixed(1)}" stroke="#d9dee7" stroke-dasharray="4 4"/>
        <path d="${path(frontKey)}" fill="none" stroke="#2563eb" stroke-width="2"/>
        <path d="${path(wristKey)}" fill="none" stroke="#16a34a" stroke-width="2"/>
        <line x1="${currentX}" y1="4" x2="${currentX}" y2="${h-4}" stroke="#111827" stroke-width="1"/>
      </svg>`;
    }
    function timeline(title, frontKey, wristKey, yMax = 1.0) {
      const rows = Array.from(influenceRows.values()).sort((a, b) => Number(a.global_index) - Number(b.global_index));
      return `<div class="timeline"><h3>${title}</h3>${lineSvg(rows, frontKey, wristKey, yMax)}<div class="legend"><span>Front</span><span class="wrist">Wrist</span></div></div>`;
    }
    function renderInfluenceRow(row) {
      const currentFrontRatio = Number(row.current_front_ratio ?? row.front_ratio ?? 0);
      const currentWristRatio = Number(row.current_wrist_ratio ?? row.wrist_ratio ?? 0);
      const chunkFrontRatio = Number(row.chunk_front_ratio ?? currentFrontRatio);
      const chunkWristRatio = Number(row.chunk_wrist_ratio ?? currentWristRatio);
      const armFrontRatio = Number(row.arm_chunk_front_ratio ?? 0);
      const armWristRatio = Number(row.arm_chunk_wrist_ratio ?? 0);
      const gripFrontRatio = Number(row.gripper_chunk_front_ratio ?? 0);
      const gripWristRatio = Number(row.gripper_chunk_wrist_ratio ?? 0);
      const bar = (label, frontValue, wristValue) => {
        const frontPct = Math.max(0, Math.min(100, Number(frontValue) * 100));
        const wristPct = Math.max(0, Math.min(100, Number(wristValue) * 100));
        return `<div class="barsection">
                  <div class="barrow"><b>${label}</b><div class="bartrack"><div class="barfill" style="width:${frontPct}%"></div></div><span>F ${pct(frontValue)}</span></div>
                  <div class="barrow"><b></b><div class="bartrack"><div class="barfill wrist" style="width:${wristPct}%"></div></div><span>W ${pct(wristValue)}</span></div>
                </div>`;
      };
      const signal = row.low_signal ? '<div class="warn">effect가 작아서 비율 해석은 조심해야 한다.</div>' : '';
      const names = influenceMeta?.joint_names || [];
      const jointRows = names.map((name, i) => `
        <tr>
          <td>${name}</td>
          <td>${Number(row['joint' + i + '_current_front_effect'] ?? row['joint' + i + '_front_effect']).toFixed(5)}</td>
          <td>${Number(row['joint' + i + '_current_wrist_effect'] ?? row['joint' + i + '_wrist_effect']).toFixed(5)}</td>
          <td>${Number(row['joint' + i + '_chunk_front_effect'] ?? 0).toFixed(5)}</td>
          <td>${Number(row['joint' + i + '_chunk_wrist_effect'] ?? 0).toFixed(5)}</td>
        </tr>`).join('');
      $('influence').innerHTML = `
        <div class="bars">
          ${bar('Current', currentFrontRatio, currentWristRatio)}
          ${bar('Future chunk', chunkFrontRatio, chunkWristRatio)}
          ${bar('Arm chunk', armFrontRatio, armWristRatio)}
          ${bar('Grip chunk', gripFrontRatio, gripWristRatio)}
        </div>
        <p class="muted">frame ${row.frame_index} / global ${row.global_index} / chunk ${row.chunk_horizon || influenceMeta?.chunk_horizon || '?'} steps</p>
        <p class="muted">current L2: front ${Number(row.current_front_l2 ?? row.front_l2).toFixed(6)}, wrist ${Number(row.current_wrist_l2 ?? row.wrist_l2).toFixed(6)} / chunk mean effect: front ${Number(row.chunk_front_mean ?? 0).toFixed(6)}, wrist ${Number(row.chunk_wrist_mean ?? 0).toFixed(6)}</p>
        ${signal}
        <table>
          <tr><th>joint</th><th>current F</th><th>current W</th><th>chunk F</th><th>chunk W</th></tr>
          ${jointRows}
        </table>
        ${timeline('Current Action Camera Influence', 'current_front_ratio', 'current_wrist_ratio')}
        ${timeline('Future Chunk Camera Influence', 'chunk_front_ratio', 'chunk_wrist_ratio')}
        ${timeline('Arm Chunk Camera Influence', 'arm_chunk_front_ratio', 'arm_chunk_wrist_ratio')}
        ${timeline('Gripper Chunk Camera Influence', 'gripper_chunk_front_ratio', 'gripper_chunk_wrist_ratio')}
        ${timeline('Raw Chunk Effect Magnitude', 'chunk_front_mean', 'chunk_wrist_mean', Math.max(0.001, ...(Array.from(influenceRows.values()).flatMap(r => [Number(r.chunk_front_mean || 0), Number(r.chunk_wrist_mean || 0)]))))}
        <p class="muted">cache: ${influenceMeta?.cache_file || ''}</p>`;
    }
    function updateInfluenceForCurrentFrame() {
      if (!influenceRows.size) {
        $('influence').textContent = '저장된 episode influence가 없다. Analyze Episode를 먼저 눌러줘.';
        return;
      }
      const row = influenceRows.get(Number($('frame').value));
      if (row) renderInfluenceRow(row);
      else $('influence').textContent = '이 프레임에 해당하는 influence cache가 없다.';
    }
    async function loadInfluenceSeries() {
      if (!$('dataset').value || !$('checkpoint').value || !$('episode').value) return;
      const data = await api('influence_series', { dataset: $('dataset').value, checkpoint: $('checkpoint').value, episode: $('episode').value });
      influenceRows = new Map();
      influenceMeta = null;
      if (!data.cached) {
        $('influence').textContent = '저장된 episode influence가 없다. Analyze Episode를 먼저 눌러줘.';
        return;
      }
      influenceMeta = data.meta;
      data.rows.forEach((row) => influenceRows.set(Number(row.global_index), row));
      updateInfluenceForCurrentFrame();
    }
    async function analyzeInfluence() {
      stopPlayback();
      if (!$('checkpoint').value) {
        $('influence').textContent = '먼저 checkpoint를 선택해줘.';
        return;
      }
      try {
        const started = await api('analyze_episode_start', { dataset: $('dataset').value, checkpoint: $('checkpoint').value, episode: $('episode').value });
        if (started.cached) {
          await loadInfluenceSeries();
          return;
        }
        $('influence').textContent = started.already_running ? '이미 계산 중인 episode influence에 연결됨...' : 'episode influence 계산 시작...';
        const poll = async () => {
          const job = await api('analyze_job', { id: started.job_id });
          $('influence').textContent = `계산 중 ${job.done}/${job.total} frames (${job.status})`;
          if (job.status === 'done') {
            await loadInfluenceSeries();
          } else if (job.status === 'error') {
            $('influence').textContent = job.error || 'analysis failed';
          } else {
            setTimeout(poll, 1200);
          }
        };
        setTimeout(poll, 800);
      } catch (e) {
        $('influence').textContent = e.message;
      }
    }
    $('loadDatasets').onclick = () => { saveState(); loadDatasets(); };
    $('loadModels').onclick = () => { saveState(); loadModels(); };
    $('dataset').onchange = () => { saveState(); loadDataset(); };
    $('modelRun').onchange = () => { saveState(); loadCheckpoints(); };
    $('checkpoint').onchange = () => { saveState(); updateMeta(); };
    $('episode').onchange = async () => { saveState(); await updateEpisodeBounds(); await loadInfluenceSeries().catch(() => {}); };
    $('loadFrame').onclick = () => { saveState(); loadFrame(); };
    $('analyzeInfluence').onclick = analyzeInfluence;
    $('prevFrame').onclick = () => stepFrame(-Number($('playStride').value || 1));
    $('nextFrame').onclick = () => stepFrame(Number($('playStride').value || 1));
    $('playPause').onclick = togglePlayback;
    $('frameSlider').oninput = () => { $('frame').value = $('frameSlider').value; saveState(); updateInfluenceForCurrentFrame(); };
    $('frameSlider').onchange = () => { saveState(); loadFrame(); };
    $('frame').onchange = () => { $('frameSlider').value = $('frame').value; saveState(); loadFrame(); };
    $('imageMode').onchange = () => { saveState(); loadFrame(); };
    $('playFps').onchange = saveState;
    $('playStride').onchange = saveState;
    restoreInputs();
    loadDatasets().then(loadModels).catch((e) => { status('error'); alert(e.message); });
  </script>
</body>
</html>
"""


class Analyzer:
    def __init__(self) -> None:
        self.datasets: dict[str, LeRobotDataset] = {}
        self.dataset_lock = threading.RLock()
        self.policy_cache: dict[tuple[str, str], tuple[object, object]] = {}
        self.policy_lock = threading.RLock()
        self.jobs: dict[str, dict] = {}
        self.jobs_lock = threading.RLock()

    def list_datasets(self, root: Path) -> list[dict]:
        rows = []
        for info_path in sorted(root.glob("*/meta/info.json")):
            ds_root = info_path.parent.parent
            try:
                info = json.loads(info_path.read_text())
            except Exception:
                info = {}
            rows.append({
                "name": ds_root.name,
                "path": str(ds_root),
                "episodes": info.get("total_episodes", 0),
                "frames": info.get("total_frames", 0),
                "fps": info.get("fps"),
                "robot_type": info.get("robot_type"),
            })
        return rows

    def list_model_runs(self, root: Path) -> list[dict]:
        rows = []
        for run in sorted(root.iterdir() if root.exists() else []):
            if not run.is_dir():
                continue
            checkpoints = list(run.glob("checkpoints/*/pretrained_model"))
            if checkpoints:
                rows.append({"name": run.name, "path": str(run), "checkpoints": len(checkpoints)})
        return rows

    def list_checkpoints(self, run_root: Path) -> list[dict]:
        rows = []
        for pretrained in sorted(run_root.glob("checkpoints/*/pretrained_model")):
            run = run_root
            ckpt = pretrained.parent
            config = self._read_json(pretrained / "config.json")
            train_config = self._read_json(pretrained / "train_config.json")
            rows.append({
                "run_name": run.name,
                "checkpoint_name": ckpt.name,
                "path": str(pretrained),
                "policy_type": config.get("type", ""),
                "dataset": train_config.get("dataset", {}).get("repo_id", ""),
            })
        return rows

    def dataset_meta(self, dataset_root: Path) -> dict:
        info = self._read_json(dataset_root / "meta/info.json")
        episodes = self._episode_ranges(dataset_root)
        info["path"] = str(dataset_root)
        info["feature_keys"] = list(info.get("features", {}).keys())
        return {"info": info, "episodes": episodes}

    def frame(self, dataset_root: Path, index: int, include_images: bool = False) -> dict:
        with self.dataset_lock:
            ds = self._load_dataset(dataset_root)
            index = max(0, min(index, len(ds) - 1))
            item = ds[index]
            front_key, wrist_key = self._camera_keys(item)
            state = self._tensor_list(item["observation.state"])
            action = self._tensor_list(item["action"])
            task = item.get("task", "")
            diagnostics = {
                "index": index,
                "episode_index": int(item["episode_index"]),
                "frame_index": int(item["frame_index"]),
                "timestamp": float(item["timestamp"]),
                "front_key": front_key,
                "wrist_key": wrist_key,
                "front_shape": list(item[front_key].shape),
                "wrist_shape": list(item[wrist_key].shape),
                "state_shape": list(item["observation.state"].shape),
                "action_shape": list(item["action"].shape),
                "state_dtype": str(item["observation.state"].dtype),
                "action_dtype": str(item["action"].dtype),
            }
            images = None
            if include_images:
                images = {
                    "front": self._image_data_url(item[front_key], max_width=720),
                    "wrist": self._image_data_url(item[wrist_key], max_width=520),
                }
        payload = {
            "task": task,
            "state": state,
            "action": action,
            "diagnostics": diagnostics,
        }
        if images is not None:
            payload["images"] = images
        return payload

    def image_png(self, dataset_root: Path, index: int, camera: str) -> bytes:
        with self.dataset_lock:
            ds = self._load_dataset(dataset_root)
            index = max(0, min(index, len(ds) - 1))
            item = ds[index]
            front_key, wrist_key = self._camera_keys(item)
            key = wrist_key if camera == "wrist" else front_key
            max_width = 520 if camera == "wrist" else 720
            return self._image_png(item[key], max_width=max_width)

    def influence_series(self, dataset_root: Path, checkpoint_root: Path, episode_index: int) -> dict:
        cache_file = self._influence_cache_file(dataset_root, checkpoint_root, episode_index)
        config_file = cache_file.parent / "config.json"
        if not cache_file.exists() or not self._cache_is_current(config_file):
            return {"cached": False, "cache_file": str(cache_file)}
        df = pd.read_parquet(cache_file)
        meta = self._read_json(config_file)
        meta["cache_file"] = str(cache_file)
        return {"cached": True, "meta": meta, "rows": df.to_dict(orient="records")}

    def start_episode_analysis(self, dataset_root: Path, checkpoint_root: Path, episode_index: int, mask_value: float = 0.5) -> dict:
        cache_file = self._influence_cache_file(dataset_root, checkpoint_root, episode_index)
        if cache_file.exists() and self._cache_is_current(cache_file.parent / "config.json"):
            return {"cached": True, "cache_file": str(cache_file)}

        existing_job = self._running_job_for_cache(cache_file)
        if existing_job is not None:
            return {
                "cached": False,
                "job_id": existing_job["id"],
                "cache_file": str(cache_file),
                "total": existing_job["total"],
                "already_running": True,
            }

        job_id = hashlib.sha1(f"{dataset_root}|{checkpoint_root}|{episode_index}|{time.time()}".encode("utf-8")).hexdigest()[:16]
        ranges = self._episode_ranges(dataset_root)
        episode = next((row for row in ranges if int(row["episode_index"]) == int(episode_index)), None)
        if episode is None:
            raise RuntimeError(f"episode not found: {episode_index}")
        total = int(episode["to"]) - int(episode["from"])
        job = {
            "id": job_id,
            "status": "running",
            "done": 0,
            "total": total,
            "error": "",
            "cache_file": str(cache_file),
        }
        with self.jobs_lock:
            self.jobs[job_id] = job
        thread = threading.Thread(
            target=self._episode_analysis_worker,
            args=(job_id, dataset_root, checkpoint_root, episode, mask_value),
            daemon=True,
        )
        thread.start()
        return {"cached": False, "job_id": job_id, "cache_file": str(cache_file), "total": total}

    def job_status(self, job_id: str) -> dict:
        with self.jobs_lock:
            if job_id not in self.jobs:
                raise RuntimeError(f"job not found: {job_id}")
            return dict(self.jobs[job_id])

    def _running_job_for_cache(self, cache_file: Path) -> dict | None:
        target = str(cache_file)
        with self.jobs_lock:
            for job in self.jobs.values():
                if job.get("cache_file") == target and job.get("status") == "running":
                    return dict(job)
        return None

    def _episode_analysis_worker(self, job_id: str, dataset_root: Path, checkpoint_root: Path, episode: dict, mask_value: float) -> None:
        rows = []
        cache_file = self._influence_cache_file(dataset_root, checkpoint_root, int(episode["episode_index"]))
        try:
            for index in range(int(episode["from"]), int(episode["to"])):
                result = self.influence(dataset_root, checkpoint_root, index, mask_value)
                rows.append(self._flatten_influence(result))
                with self.jobs_lock:
                    self.jobs[job_id]["done"] = len(rows)
            cache_file.parent.mkdir(parents=True, exist_ok=True)
            df = pd.DataFrame(rows)
            tmp_file = cache_file.parent / (cache_file.name + ".tmp")
            df.to_parquet(tmp_file, index=False)
            tmp_file.replace(cache_file)
            config = self._influence_config(dataset_root, checkpoint_root, int(episode["episode_index"]), mask_value)
            (cache_file.parent / "config.json").write_text(json.dumps(config, indent=2) + "\n")
            with self.jobs_lock:
                self.jobs[job_id]["status"] = "done"
                self.jobs[job_id]["done"] = len(rows)
        except Exception as exc:
            with self.jobs_lock:
                self.jobs[job_id]["status"] = "error"
                self.jobs[job_id]["error"] = str(exc)

    def _flatten_influence(self, result: dict) -> dict:
        row = {
            "global_index": result["index"],
            "episode_index": result["episode_index"],
            "frame_index": result["frame_index"],
            "timestamp": result["timestamp"],
            "task": result["task"],
            "chunk_horizon": result["chunk_horizon"],
            "current_front_l2": result["current"]["effects"]["front_l2"],
            "current_wrist_l2": result["current"]["effects"]["wrist_l2"],
            "current_front_ratio": result["current"]["ratios"]["front"],
            "current_wrist_ratio": result["current"]["ratios"]["wrist"],
            "chunk_front_mean": result["chunk"]["effects"]["front_mean"],
            "chunk_wrist_mean": result["chunk"]["effects"]["wrist_mean"],
            "chunk_front_l2": result["chunk"]["effects"]["front_l2"],
            "chunk_wrist_l2": result["chunk"]["effects"]["wrist_l2"],
            "chunk_front_ratio": result["chunk"]["ratios"]["front"],
            "chunk_wrist_ratio": result["chunk"]["ratios"]["wrist"],
            "arm_chunk_front_mean": result["arm_chunk"]["effects"]["front_mean"],
            "arm_chunk_wrist_mean": result["arm_chunk"]["effects"]["wrist_mean"],
            "arm_chunk_front_ratio": result["arm_chunk"]["ratios"]["front"],
            "arm_chunk_wrist_ratio": result["arm_chunk"]["ratios"]["wrist"],
            "gripper_chunk_front_mean": result["gripper_chunk"]["effects"]["front_mean"],
            "gripper_chunk_wrist_mean": result["gripper_chunk"]["effects"]["wrist_mean"],
            "gripper_chunk_front_ratio": result["gripper_chunk"]["ratios"]["front"],
            "gripper_chunk_wrist_ratio": result["gripper_chunk"]["ratios"]["wrist"],
            "low_signal": result["low_signal"],
        }
        for i, joint in enumerate(result["joints"]):
            row[f"joint{i}_predicted"] = joint["predicted"]
            row[f"joint{i}_recorded"] = joint["recorded"]
            row[f"joint{i}_current_front_effect"] = joint["current_front_effect"]
            row[f"joint{i}_current_wrist_effect"] = joint["current_wrist_effect"]
            row[f"joint{i}_chunk_front_effect"] = joint["chunk_front_effect"]
            row[f"joint{i}_chunk_wrist_effect"] = joint["chunk_wrist_effect"]
        return row

    def _influence_config(self, dataset_root: Path, checkpoint_root: Path, episode_index: int, mask_value: float) -> dict:
        with self.dataset_lock:
            ds = self._load_dataset(dataset_root)
            item = ds[0]
        front_key, wrist_key = self._camera_keys(item)
        joint_names = self._joint_names(dataset_root, len(item["action"].detach().cpu().flatten()))
        return {
            "analysis_type": "camera_ablation_influence",
            "analysis_version": "v2_chunk",
            "dataset": str(dataset_root),
            "checkpoint": str(checkpoint_root),
            "episode_index": episode_index,
            "front_key": front_key,
            "wrist_key": wrist_key,
            "mask_value": mask_value,
            "chunk_horizon": 50,
            "joint_names": joint_names,
            "groups": {"arm": joint_names[:-1], "gripper": joint_names[-1:]},
        }

    @staticmethod
    def _cache_is_current(config_file: Path) -> bool:
        try:
            data = json.loads(config_file.read_text())
        except Exception:
            return False
        return data.get("analysis_version") == "v2_chunk"

    @staticmethod
    def _influence_cache_file(dataset_root: Path, checkpoint_root: Path, episode_index: int) -> Path:
        run_root = checkpoint_root.parents[2]
        checkpoint_name = checkpoint_root.parent.name
        return run_root / "analysis" / "influence" / dataset_root.name / checkpoint_name / f"episode_{episode_index:06d}.parquet"

    def influence(self, dataset_root: Path, checkpoint_root: Path, index: int, mask_value: float = 0.5) -> dict:
        if any(x is None for x in (LeRobotDataset, LeRobotDatasetMetadata, PreTrainedConfig, make_policy, make_pre_post_processors)):
            raise RuntimeError("lerobot policy imports are not available in this Python environment")

        with self.dataset_lock:
            ds = self._load_dataset(dataset_root)
            index = max(0, min(index, len(ds) - 1))
            item = ds[index]

        front_key, wrist_key = self._camera_keys(item)
        policy, preprocessor = self._load_policy(dataset_root, checkpoint_root)

        baseline = self._predict_action_chunk(policy, preprocessor, item)
        front_masked_item = self._clone_item(item)
        front_masked_item[front_key] = torch.full_like(front_masked_item[front_key], mask_value)
        front_masked = self._predict_action_chunk(policy, preprocessor, front_masked_item)

        wrist_masked_item = self._clone_item(item)
        wrist_masked_item[wrist_key] = torch.full_like(wrist_masked_item[wrist_key], mask_value)
        wrist_masked = self._predict_action_chunk(policy, preprocessor, wrist_masked_item)

        recorded = item["action"].detach().cpu().flatten().float()
        front_delta = (baseline - front_masked).abs()
        wrist_delta = (baseline - wrist_masked).abs()
        current_front = front_delta[0]
        current_wrist = wrist_delta[0]
        joint_names = self._joint_names(dataset_root, baseline.shape[-1])
        arm_slice = slice(0, max(1, baseline.shape[-1] - 1))
        grip_slice = slice(max(0, baseline.shape[-1] - 1), baseline.shape[-1])

        current = self._effect_summary(current_front, current_wrist)
        chunk = self._effect_summary(front_delta, wrist_delta)
        arm_chunk = self._effect_summary(front_delta[:, arm_slice], wrist_delta[:, arm_slice])
        gripper_chunk = self._effect_summary(front_delta[:, grip_slice], wrist_delta[:, grip_slice])
        total_signal = chunk["effects"]["front_mean"] + chunk["effects"]["wrist_mean"]

        return {
            "index": index,
            "episode_index": int(item["episode_index"]),
            "frame_index": int(item["frame_index"]),
            "timestamp": float(item["timestamp"]),
            "task": item.get("task", ""),
            "checkpoint": str(checkpoint_root),
            "front_key": front_key,
            "wrist_key": wrist_key,
            "mask_value": mask_value,
            "chunk_horizon": int(baseline.shape[0]),
            "current": current,
            "chunk": chunk,
            "arm_chunk": arm_chunk,
            "gripper_chunk": gripper_chunk,
            "low_signal": total_signal < 1e-6,
            "joints": [
                {
                    "name": joint_names[i],
                    "predicted": float(baseline[0, i]),
                    "recorded": float(recorded[i]),
                    "current_front_effect": float(current_front[i]),
                    "current_wrist_effect": float(current_wrist[i]),
                    "chunk_front_effect": float(front_delta[:, i].mean()),
                    "chunk_wrist_effect": float(wrist_delta[:, i].mean()),
                }
                for i in range(baseline.shape[-1])
            ],
        }

    @staticmethod
    def _effect_summary(front_delta, wrist_delta) -> dict:
        front_l2 = float(torch.linalg.vector_norm(front_delta))
        wrist_l2 = float(torch.linalg.vector_norm(wrist_delta))
        front_mean = float(front_delta.mean())
        wrist_mean = float(wrist_delta.mean())
        total = front_mean + wrist_mean
        return {
            "effects": {
                "front_l2": front_l2,
                "wrist_l2": wrist_l2,
                "front_mean": front_mean,
                "wrist_mean": wrist_mean,
            },
            "ratios": {
                "front": 0.0 if total < 1e-9 else front_mean / total,
                "wrist": 0.0 if total < 1e-9 else wrist_mean / total,
            },
        }

    def _load_policy(self, dataset_root: Path, checkpoint_root: Path):
        key = (str(dataset_root), str(checkpoint_root))
        with self.policy_lock:
            if key in self.policy_cache:
                return self.policy_cache[key]

            repo_id = f"local/{dataset_root.name}"
            metadata = LeRobotDatasetMetadata(repo_id, root=dataset_root)
            analyzer_ckpt = self._prepare_checkpoint(checkpoint_root)
            cfg = PreTrainedConfig.from_pretrained(analyzer_ckpt, local_files_only=True)
            cfg.pretrained_path = str(analyzer_ckpt)
            cfg.device = "cuda" if torch.cuda.is_available() else "cpu"
            policy = make_policy(cfg, ds_meta=metadata)
            policy.eval()
            preprocessor, _ = make_pre_post_processors(cfg, pretrained_path=str(analyzer_ckpt))
            self.policy_cache.clear()
            self.policy_cache[key] = (policy, preprocessor)
            return policy, preprocessor

    @staticmethod
    def _prepare_checkpoint(checkpoint_root: Path) -> Path:
        digest = hashlib.sha1(str(checkpoint_root).encode("utf-8")).hexdigest()[:16]
        target = Path("/tmp/policy_analyzer_ckpts") / digest
        marker = target / ".ready"
        if marker.exists():
            return target

        tmp = target.with_name(target.name + ".tmp")
        if tmp.exists():
            shutil.rmtree(tmp)
        tmp.mkdir(parents=True, exist_ok=True)

        for child in checkpoint_root.iterdir():
            dest = tmp / child.name
            if child.name in {"config.json", "policy_preprocessor.json"}:
                data = json.loads(child.read_text())
                if child.name == "config.json":
                    data.pop("pretrained_revision", None)
                else:
                    data = Analyzer._fix_processor_paths(data)
                dest.write_text(json.dumps(data, indent=2) + "\n")
            else:
                os.symlink(child, dest, target_is_directory=child.is_dir())

        (tmp / ".ready").write_text(str(checkpoint_root) + "\n")
        if target.exists():
            shutil.rmtree(target)
        tmp.rename(target)
        return target

    @staticmethod
    def _fix_processor_paths(value):
        if isinstance(value, dict):
            fixed = {}
            for key, child in value.items():
                if key == "tokenizer_name" and isinstance(child, str) and child.startswith("/"):
                    fixed[key] = "tokenizer"
                else:
                    fixed[key] = Analyzer._fix_processor_paths(child)
            return fixed
        if isinstance(value, list):
            return [Analyzer._fix_processor_paths(child) for child in value]
        return value

    @staticmethod
    def _clone_item(item: dict) -> dict:
        cloned = {}
        for key, value in item.items():
            cloned[key] = value.clone() if torch.is_tensor(value) else value
        return cloned

    @staticmethod
    def _predict_action_chunk(policy, preprocessor, item: dict):
        if hasattr(policy, "reset"):
            policy.reset()
        processed = preprocessor(item)
        with torch.inference_mode():
            if hasattr(policy, "predict_action_chunk"):
                pred = policy.predict_action_chunk(processed)
            else:
                pred = policy.select_action(processed).unsqueeze(1)
        pred = pred.detach().cpu().float()
        if pred.ndim == 3:
            pred = pred[0]
        return pred.reshape(pred.shape[0], -1)

    def _joint_names(self, dataset_root: Path, count: int) -> list[str]:
        info = self._read_json(dataset_root / "meta/info.json")
        names = info.get("features", {}).get("action", {}).get("names") or []
        if len(names) < count:
            names = list(names) + [f"joint{i}" for i in range(len(names), count)]
        return names[:count]

    def _load_dataset(self, dataset_root: Path):
        if LeRobotDataset is None:
            raise RuntimeError("lerobot is not importable in this Python environment")
        key = str(dataset_root)
        if key not in self.datasets:
            repo_id = f"local/{dataset_root.name}"
            self.datasets[key] = LeRobotDataset(repo_id, root=dataset_root)
        return self.datasets[key]

    @staticmethod
    def _read_json(path: Path) -> dict:
        try:
            return json.loads(path.read_text())
        except Exception:
            return {}

    @staticmethod
    def _episode_ranges(dataset_root: Path) -> list[dict]:
        data_files = sorted(dataset_root.glob("data/chunk-*/file-*.parquet"))
        if not data_files:
            return []
        df = pd.concat(pd.read_parquet(p, columns=["episode_index", "index"]) for p in data_files)
        grouped = df.groupby("episode_index")["index"].agg(["min", "max", "count"]).reset_index()
        return [
            {
                "episode_index": int(row["episode_index"]),
                "from": int(row["min"]),
                "to": int(row["max"]) + 1,
                "length": int(row["count"]),
            }
            for _, row in grouped.iterrows()
        ]

    @staticmethod
    def _camera_keys(item: dict) -> tuple[str, str]:
        keys = [k for k in item.keys() if k.startswith("observation.images")]
        front = next((k for k in keys if "front" in k), keys[0])
        wrist = next((k for k in keys if "wrist" in k), keys[-1])
        return front, wrist

    @staticmethod
    def _tensor_list(tensor) -> list[float]:
        return [float(x) for x in tensor.detach().cpu().flatten().tolist()]

    @staticmethod
    def _image_data_url(tensor, max_width: int | None = None) -> str:
        return "data:image/png;base64," + base64.b64encode(
            Analyzer._image_png(tensor, max_width=max_width)
        ).decode("ascii")

    @staticmethod
    def _image_png(tensor, max_width: int | None = None) -> bytes:
        arr = tensor.detach().cpu().clamp(0, 1).mul(255).byte().permute(1, 2, 0).numpy()
        img = Image.fromarray(arr)
        if max_width and img.width > max_width:
            new_height = int(img.height * (max_width / img.width))
            img = img.resize((max_width, new_height))
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return buf.getvalue()


def make_handler(analyzer: Analyzer):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802
            parsed = urlparse(self.path)
            try:
                if parsed.path == "/":
                    self._send_html(HTML)
                    return
                if not parsed.path.startswith("/api/"):
                    self.send_error(404)
                    return
                qs = parse_qs(parsed.query)
                name = parsed.path.removeprefix("/api/")
                if name == "image":
                    body = analyzer.image_png(
                        Path(qs["dataset"][0]),
                        int(qs["index"][0]),
                        qs.get("camera", ["front"])[0],
                    )
                    self._send_binary(body, "image/png")
                    return
                if name == "datasets":
                    payload = {"datasets": analyzer.list_datasets(Path(qs.get("root", ["/workspace/lerobot"])[0]))}
                elif name == "model_runs":
                    payload = {"runs": analyzer.list_model_runs(Path(qs.get("root", ["/workspace/model/lerobot"])[0]))}
                elif name == "checkpoints":
                    payload = {"checkpoints": analyzer.list_checkpoints(Path(qs["run"][0]))}
                elif name == "dataset_meta":
                    payload = analyzer.dataset_meta(Path(qs["dataset"][0]))
                elif name == "frame":
                    payload = analyzer.frame(
                        Path(qs["dataset"][0]),
                        int(qs["index"][0]),
                        qs.get("include_images", ["0"])[0] == "1",
                    )
                elif name == "influence":
                    payload = analyzer.influence(
                        Path(qs["dataset"][0]),
                        Path(qs["checkpoint"][0]),
                        int(qs["index"][0]),
                        float(qs.get("mask_value", ["0.5"])[0]),
                    )
                elif name == "analyze_episode_start":
                    payload = analyzer.start_episode_analysis(
                        Path(qs["dataset"][0]),
                        Path(qs["checkpoint"][0]),
                        int(qs["episode"][0]),
                        float(qs.get("mask_value", ["0.5"])[0]),
                    )
                elif name == "analyze_job":
                    payload = analyzer.job_status(qs["id"][0])
                elif name == "influence_series":
                    payload = analyzer.influence_series(
                        Path(qs["dataset"][0]),
                        Path(qs["checkpoint"][0]),
                        int(qs["episode"][0]),
                    )
                else:
                    self.send_error(404)
                    return
                payload["ok"] = True
                self._send_json(payload)
            except Exception as exc:
                self._send_json({"ok": False, "error": str(exc)}, status=500)

        def log_message(self, fmt, *args):
            print(fmt % args)

        def _send_html(self, body: str) -> None:
            encoded = body.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)

        def _send_binary(self, body: bytes, content_type: str, status: int = 200) -> None:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _send_json(self, payload: dict, status: int = 200) -> None:
            encoded = json.dumps(payload).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)

    return Handler


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=7860)
    args = parser.parse_args()
    server = HTTPServer((args.host, args.port), make_handler(Analyzer()))
    print(f"LeRobot Policy Analyzer UI: http://{args.host}:{args.port}")
    server.serve_forever()


if __name__ == "__main__":
    main()
